#include "overlay_core.h"
#include <MinHook.h>
#include <cstdio>

// ---------------------------------------------------------------------------
// Vtable indices (from spec Section 14)
//   IDXGISwapChain::Present          index  8
//   IDXGISwapChain::ResizeBuffers    index 13
//   ID3D12CommandQueue::ExecuteCommandLists  index 10
// ---------------------------------------------------------------------------
static constexpr int VTBL_PRESENT            =  8;
static constexpr int VTBL_RESIZE_BUFFERS     = 13;
static constexpr int VTBL_ECL               = 10;

// ---------------------------------------------------------------------------
// Typedefs matching the real vtable signatures
// ---------------------------------------------------------------------------
using PFN_Present = HRESULT(STDMETHODCALLTYPE*)(
    IDXGISwapChain*, UINT, UINT);
using PFN_ResizeBuffers = HRESULT(STDMETHODCALLTYPE*)(
    IDXGISwapChain*, UINT, UINT, UINT, DXGI_FORMAT, UINT);
using PFN_ECL = void(STDMETHODCALLTYPE*)(
    ID3D12CommandQueue*, UINT, ID3D12CommandList* const*);

static PFN_Present         originalPresent        = nullptr;
static PFN_ResizeBuffers   originalResizeBuffers  = nullptr;
static PFN_ECL             originalECL            = nullptr;

// Captured command queue — set by hookECL so frame.cpp can submit ImGui work.
ID3D12CommandQueue* g_capturedQueue = nullptr;

static bool hooksEnabled = false;

// ---------------------------------------------------------------------------
// Hook implementations
// ---------------------------------------------------------------------------
static HRESULT STDMETHODCALLTYPE hookPresent(
    IDXGISwapChain* swapChain, UINT syncInterval, UINT flags)
{
    if (!hooksEnabled)
        return originalPresent(swapChain, syncInterval, flags);

    // Log first invocation so DebugView confirms the hook is live.
    static bool firstCall = true;
    if (firstCall) {
        firstCall = false;
        OutputDebugStringW(L"[overlay] hookPresent — first frame\n");
    }

    ComPtr<IDXGISwapChain3> sc3;
    if (SUCCEEDED(swapChain->QueryInterface(IID_PPV_ARGS(&sc3)))) {
        frame::renderOverlay(sc3.Get());
    }

    return originalPresent(swapChain, syncInterval, flags);
}

static HRESULT STDMETHODCALLTYPE hookResizeBuffers(
    IDXGISwapChain* swapChain,
    UINT bufferCount, UINT width, UINT height,
    DXGI_FORMAT newFormat, UINT swapChainFlags)
{
    OutputDebugStringW(L"[overlay] hookResizeBuffers\n");
    imgui_init::invalidate();
    frame::cleanupRenderTargets();

    HRESULT hr = originalResizeBuffers(
        swapChain, bufferCount, width, height, newFormat, swapChainFlags);

    ComPtr<IDXGISwapChain3> sc3;
    if (SUCCEEDED(swapChain->QueryInterface(IID_PPV_ARGS(&sc3)))) {
        frame::createRenderTargets(sc3.Get());
        imgui_init::recreate();
    }
    return hr;
}

static void STDMETHODCALLTYPE hookECL(
    ID3D12CommandQueue* queue, UINT count, ID3D12CommandList* const* lists)
{
    // Only capture DIRECT queues — our command list is DIRECT type and cannot
    // be submitted to a compute or copy queue (causes immediate device removal).
    D3D12_COMMAND_QUEUE_DESC qDesc = queue->GetDesc();

    static bool loggedFirst = false;
    if (!loggedFirst) {
        loggedFirst = true;
        wchar_t buf[128];
        swprintf_s(buf, L"[overlay] hookECL first call: queue type=%u  ptr=%p\n",
                   static_cast<unsigned>(qDesc.Type), (void*)queue);
        OutputDebugStringW(buf);
    }

    if (qDesc.Type == D3D12_COMMAND_LIST_TYPE_DIRECT && g_capturedQueue == nullptr) {
        g_capturedQueue = queue;
    }

    return originalECL(queue, count, lists);
}

// ---------------------------------------------------------------------------
// hook::initialize — creates dummy D3D12 objects, reads vtables, installs hooks
// ---------------------------------------------------------------------------
namespace hook {
void initialize() {
    OutputDebugStringW(L"[overlay] hook::initialize\n");

    // --- Dummy device ---
    ComPtr<ID3D12Device> dummyDevice;
    HRESULT hr = D3D12CreateDevice(
        nullptr, D3D_FEATURE_LEVEL_11_0, IID_PPV_ARGS(&dummyDevice));
    if (FAILED(hr)) {
        OutputDebugStringW(L"[overlay] D3D12CreateDevice failed — cannot install hooks\n");
        return;
    }

    // --- Dummy command queue ---
    D3D12_COMMAND_QUEUE_DESC qDesc{};
    qDesc.Type  = D3D12_COMMAND_LIST_TYPE_DIRECT;
    qDesc.Flags = D3D12_COMMAND_QUEUE_FLAG_NONE;
    ComPtr<ID3D12CommandQueue> dummyQueue;
    if (FAILED(dummyDevice->CreateCommandQueue(&qDesc, IID_PPV_ARGS(&dummyQueue)))) {
        OutputDebugStringW(L"[overlay] CreateCommandQueue failed\n");
        return;
    }

    // --- Dummy DXGI factory ---
    ComPtr<IDXGIFactory4> dummyFactory;
    if (FAILED(CreateDXGIFactory1(IID_PPV_ARGS(&dummyFactory)))) {
        OutputDebugStringW(L"[overlay] CreateDXGIFactory1 failed\n");
        return;
    }

    // --- Dummy swap chain (needs a window) ---
    // Create a hidden message-only window just long enough to get the vtable.
    HWND hwndDummy = CreateWindowExW(
        0, L"STATIC", L"DummyOverlay", WS_OVERLAPPEDWINDOW,
        0, 0, 8, 8, nullptr, nullptr, GetModuleHandleW(nullptr), nullptr);
    if (!hwndDummy) {
        OutputDebugStringW(L"[overlay] CreateWindowEx for dummy HWND failed\n");
        return;
    }

    DXGI_SWAP_CHAIN_DESC scDesc{};
    scDesc.BufferCount        = 2;
    scDesc.BufferDesc.Width   = 8;
    scDesc.BufferDesc.Height  = 8;
    scDesc.BufferDesc.Format  = DXGI_FORMAT_R8G8B8A8_UNORM;
    scDesc.BufferUsage        = DXGI_USAGE_RENDER_TARGET_OUTPUT;
    scDesc.SwapEffect         = DXGI_SWAP_EFFECT_FLIP_DISCARD;
    scDesc.OutputWindow       = hwndDummy;
    scDesc.SampleDesc.Count   = 1;
    scDesc.Windowed           = TRUE;

    ComPtr<IDXGISwapChain> dummySwapChain;
    hr = dummyFactory->CreateSwapChain(dummyQueue.Get(), &scDesc, &dummySwapChain);
    if (FAILED(hr)) {
        OutputDebugStringW(L"[overlay] CreateSwapChain (dummy) failed\n");
        DestroyWindow(hwndDummy);
        return;
    }

    // --- Read vtable addresses ---
    void** scVtbl    = *reinterpret_cast<void***>(dummySwapChain.Get());
    void** queueVtbl = *reinterpret_cast<void***>(dummyQueue.Get());

    // --- Install hooks ---
    MH_Initialize();

    if (MH_CreateHook(scVtbl[VTBL_PRESENT],
                      reinterpret_cast<void*>(&hookPresent),
                      reinterpret_cast<void**>(&originalPresent)) != MH_OK) {
        OutputDebugStringW(L"[overlay] MH_CreateHook Present failed\n");
    }
    if (MH_CreateHook(scVtbl[VTBL_RESIZE_BUFFERS],
                      reinterpret_cast<void*>(&hookResizeBuffers),
                      reinterpret_cast<void**>(&originalResizeBuffers)) != MH_OK) {
        OutputDebugStringW(L"[overlay] MH_CreateHook ResizeBuffers failed\n");
    }
    if (MH_CreateHook(queueVtbl[VTBL_ECL],
                      reinterpret_cast<void*>(&hookECL),
                      reinterpret_cast<void**>(&originalECL)) != MH_OK) {
        OutputDebugStringW(L"[overlay] MH_CreateHook ECL failed\n");
    }

    if (MH_EnableHook(MH_ALL_HOOKS) != MH_OK) {
        OutputDebugStringW(L"[overlay] MH_EnableHook failed\n");
    } else {
        hooksEnabled = true;
        OutputDebugStringW(L"[overlay] hooks enabled\n");
    }

    // --- Destroy dummy objects (hooks point into the real game vtables now) ---
    dummySwapChain.Reset();
    dummyQueue.Reset();
    dummyDevice.Reset();
    dummyFactory.Reset();
    DestroyWindow(hwndDummy);
}
} // namespace hook
