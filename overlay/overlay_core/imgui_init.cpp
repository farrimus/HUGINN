#include "overlay_core.h"
#include <imgui.h>
#include <imgui_impl_dx12.h>
#include <imgui_impl_win32.h>
#include <cstdio>

// WndProc hook — declared here, defined in input.cpp
extern WNDPROC g_originalWndProc;
extern LRESULT CALLBACK overlayWndProc(HWND, UINT, WPARAM, LPARAM);

// Captured command queue — defined in hook.cpp
extern ID3D12CommandQueue* g_capturedQueue;

namespace imgui_init {

static bool             s_initialized  = false;
static ComPtr<ID3D12DescriptorHeap> s_srvHeap;
static ComPtr<ID3D12DescriptorHeap> s_rtvHeap;
static HWND             s_hwnd         = nullptr;
static UINT             s_bufferCount  = 0;
static ComPtr<ID3D12Device> s_device;
static ComPtr<ID3D12InfoQueue> s_infoQueue;

// Called from frame.cpp on first Present
void initialize(IDXGISwapChain3* swapChain) {
    if (s_initialized) return;

    OutputDebugStringW(L"[overlay] imgui_init::initialize\n");

    // Get device from swap chain
    ComPtr<ID3D12Device> scDevice;
    if (FAILED(swapChain->GetDevice(IID_PPV_ARGS(&scDevice)))) {
        OutputDebugStringW(L"[overlay] imgui_init: swapChain GetDevice failed\n");
        return;
    }

    // Get device from the captured command queue — must match for command list submission.
    // If the game has multiple D3D12 devices, using the wrong one causes ACCESS_DENIED.
    ComPtr<ID3D12Device> queueDevice;
    if (g_capturedQueue) {
        g_capturedQueue->GetDevice(IID_PPV_ARGS(&queueDevice));
    }

    // Log both so we can see if they differ
    wchar_t devLog[256];
    swprintf_s(devLog,
        L"[overlay] swapChain device=%p  queue device=%p  same=%d\n",
        (void*)scDevice.Get(),
        (void*)queueDevice.Get(),
        scDevice.Get() == queueDevice.Get());
    OutputDebugStringW(devLog);

    // Use the queue's device — it is the one we submit command lists to
    s_device = queueDevice ? queueDevice : scDevice;

    // Acquire InfoQueue for validation messages (only works if debug layer is active)
    if (SUCCEEDED(s_device->QueryInterface(IID_PPV_ARGS(&s_infoQueue)))) {
        OutputDebugStringW(L"[overlay] ID3D12InfoQueue acquired — validation messages enabled\n");
    } else {
        OutputDebugStringW(L"[overlay] ID3D12InfoQueue not available (debug layer not active)\n");
    }

    // Get swap chain description for HWND, buffer count, and actual format
    DXGI_SWAP_CHAIN_DESC desc{};
    swapChain->GetDesc(&desc);
    s_hwnd        = desc.OutputWindow;
    s_bufferCount = desc.BufferCount;

    // Log detected format so we can verify it in DebugView
    wchar_t fmtLog[128];
    swprintf_s(fmtLog, L"[overlay] swap chain format: %u  buffers: %u\n",
               static_cast<unsigned>(desc.BufferDesc.Format), s_bufferCount);
    OutputDebugStringW(fmtLog);

    // Use the actual back-buffer format — never assume R8G8B8A8.
    // SRGB formats cannot be used directly as RTV for flip swap chains;
    // strip SRGB to get the linear equivalent for ImGui's pipeline.
    DXGI_FORMAT rtvFormat = desc.BufferDesc.Format;
    // Map common SRGB variants to their linear equivalents
    if (rtvFormat == DXGI_FORMAT_R8G8B8A8_UNORM_SRGB)
        rtvFormat = DXGI_FORMAT_R8G8B8A8_UNORM;
    else if (rtvFormat == DXGI_FORMAT_B8G8R8A8_UNORM_SRGB)
        rtvFormat = DXGI_FORMAT_B8G8R8A8_UNORM;

    // SRV descriptor heap (1 slot — for ImGui font texture)
    D3D12_DESCRIPTOR_HEAP_DESC srvDesc{};
    srvDesc.Type           = D3D12_DESCRIPTOR_HEAP_TYPE_CBV_SRV_UAV;
    srvDesc.NumDescriptors = 1;
    srvDesc.Flags          = D3D12_DESCRIPTOR_HEAP_FLAG_SHADER_VISIBLE;
    if (FAILED(s_device->CreateDescriptorHeap(&srvDesc, IID_PPV_ARGS(&s_srvHeap)))) {
        OutputDebugStringW(L"[overlay] imgui_init: CreateDescriptorHeap SRV failed\n");
        return;
    }

    // RTV descriptor heap (one slot per back buffer)
    D3D12_DESCRIPTOR_HEAP_DESC rtvDesc{};
    rtvDesc.Type           = D3D12_DESCRIPTOR_HEAP_TYPE_RTV;
    rtvDesc.NumDescriptors = s_bufferCount;
    rtvDesc.Flags          = D3D12_DESCRIPTOR_HEAP_FLAG_NONE;
    if (FAILED(s_device->CreateDescriptorHeap(&rtvDesc, IID_PPV_ARGS(&s_rtvHeap)))) {
        OutputDebugStringW(L"[overlay] imgui_init: CreateDescriptorHeap RTV failed\n");
        return;
    }

    // Create render targets now that heaps exist
    frame::createRenderTargets(swapChain);

    // ImGui context
    ImGui::CreateContext();
    ImGuiIO& io = ImGui::GetIO();
    io.ConfigFlags |= ImGuiConfigFlags_NoMouseCursorChange;

    ImGui_ImplWin32_Init(s_hwnd);
    ImGui_ImplDX12_Init(
        s_device.Get(),
        static_cast<int>(s_bufferCount),
        rtvFormat,
        s_srvHeap.Get(),
        s_srvHeap->GetCPUDescriptorHandleForHeapStart(),
        s_srvHeap->GetGPUDescriptorHandleForHeapStart());

    // Subclass the game window to intercept input
    g_originalWndProc = reinterpret_cast<WNDPROC>(
        SetWindowLongPtrW(s_hwnd, GWLP_WNDPROC,
                          reinterpret_cast<LONG_PTR>(overlayWndProc)));

    s_initialized = true;
    OutputDebugStringW(L"[overlay] imgui_init::initialize complete\n");
}

// Release ImGui device objects (called before ResizeBuffers)
void invalidate() {
    if (!s_initialized) return;
    OutputDebugStringW(L"[overlay] imgui_init::invalidate\n");
    ImGui_ImplDX12_InvalidateDeviceObjects();
}

// Recreate ImGui device objects (called after ResizeBuffers)
void recreate() {
    if (!s_initialized) return;
    OutputDebugStringW(L"[overlay] imgui_init::recreate\n");
    ImGui_ImplDX12_CreateDeviceObjects();
}

// Accessors used by frame.cpp
ID3D12DescriptorHeap* getSrvHeap()    { return s_srvHeap.Get(); }
ID3D12DescriptorHeap* getRtvHeap()    { return s_rtvHeap.Get(); }
ID3D12Device*         getDevice()     { return s_device.Get(); }
UINT                  getBufferCount(){ return s_bufferCount; }
ID3D12InfoQueue*      getInfoQueue()  { return s_infoQueue.Get(); }

} // namespace imgui_init
