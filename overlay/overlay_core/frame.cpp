#include "overlay_core.h"
#include <imgui.h>
#include <imgui_impl_dx12.h>
#include <imgui_impl_win32.h>
#include "../overlay_ui/render.h"
#include <vector>
#include <d3d12.h>

// Captured command queue — set by hookECL in hook.cpp
extern ID3D12CommandQueue* g_capturedQueue;

// Accessors exposed by imgui_init.cpp
namespace imgui_init {
    ID3D12DescriptorHeap* getSrvHeap();
    ID3D12DescriptorHeap* getRtvHeap();
    ID3D12Device*         getDevice();
    UINT                  getBufferCount();
    ID3D12InfoQueue*      getInfoQueue();
}

namespace frame {

struct FrameContext {
    ComPtr<ID3D12CommandAllocator> allocator;
    D3D12_CPU_DESCRIPTOR_HANDLE    rtv{};
    UINT64                         fenceValue = 0;
};

static bool                              s_initialized = false;
static std::vector<FrameContext>         s_frames;
static std::vector<ComPtr<ID3D12Resource>> s_backBuffers;
static ComPtr<ID3D12GraphicsCommandList> s_commandList;
static ComPtr<ID3D12Fence>               s_fence;
static HANDLE                            s_fenceEvent  = nullptr;
static UINT64                            s_fenceCounter = 0;

// ---------------------------------------------------------------------------
// createRenderTargets — called from imgui_init::initialize and hookResizeBuffers
// ---------------------------------------------------------------------------
void createRenderTargets(IDXGISwapChain3* swapChain) {
    ID3D12Device* device         = imgui_init::getDevice();
    ID3D12DescriptorHeap* rtvHeap = imgui_init::getRtvHeap();
    UINT bufferCount              = imgui_init::getBufferCount();
    if (!device || !rtvHeap || bufferCount == 0) return;

    UINT rtvDescSize = device->GetDescriptorHandleIncrementSize(
        D3D12_DESCRIPTOR_HEAP_TYPE_RTV);

    s_frames.resize(bufferCount);
    s_backBuffers.resize(bufferCount);

    // Create command allocators (one per frame)
    for (UINT i = 0; i < bufferCount; ++i) {
        device->CreateCommandAllocator(
            D3D12_COMMAND_LIST_TYPE_DIRECT,
            IID_PPV_ARGS(&s_frames[i].allocator));

        swapChain->GetBuffer(i, IID_PPV_ARGS(&s_backBuffers[i]));

        D3D12_CPU_DESCRIPTOR_HANDLE rtvHandle =
            rtvHeap->GetCPUDescriptorHandleForHeapStart();
        rtvHandle.ptr += static_cast<SIZE_T>(i) * rtvDescSize;

        // Get the resource's actual format and strip SRGB — flip swap chains
        // do not allow SRGB RTVs, which causes device removal.
        D3D12_RESOURCE_DESC resourceDesc = s_backBuffers[i]->GetDesc();
        DXGI_FORMAT rtvFmt = resourceDesc.Format;
        if (rtvFmt == DXGI_FORMAT_R8G8B8A8_UNORM_SRGB)
            rtvFmt = DXGI_FORMAT_R8G8B8A8_UNORM;
        else if (rtvFmt == DXGI_FORMAT_B8G8R8A8_UNORM_SRGB)
            rtvFmt = DXGI_FORMAT_B8G8R8A8_UNORM;

        D3D12_RENDER_TARGET_VIEW_DESC rtvDesc{};
        rtvDesc.Format        = rtvFmt;
        rtvDesc.ViewDimension = D3D12_RTV_DIMENSION_TEXTURE2D;

        device->CreateRenderTargetView(s_backBuffers[i].Get(), &rtvDesc, rtvHandle);
        s_frames[i].rtv = rtvHandle;
    }

    // Create command list (once)
    if (!s_commandList) {
        device->CreateCommandList(
            0, D3D12_COMMAND_LIST_TYPE_DIRECT,
            s_frames[0].allocator.Get(), nullptr,
            IID_PPV_ARGS(&s_commandList));
        s_commandList->Close(); // starts in recording state; close immediately
    }

    // Create fence (once)
    if (!s_fence) {
        device->CreateFence(0, D3D12_FENCE_FLAG_NONE, IID_PPV_ARGS(&s_fence));
        s_fenceEvent = CreateEventW(nullptr, FALSE, FALSE, nullptr);
    }
}

// ---------------------------------------------------------------------------
// cleanupRenderTargets — called before ResizeBuffers
// ---------------------------------------------------------------------------
void cleanupRenderTargets() {
    s_backBuffers.clear();
    for (auto& f : s_frames)
        f.allocator.Reset();
    s_frames.clear();
}

// ---------------------------------------------------------------------------
// renderOverlay — called every frame from hookPresent
// ---------------------------------------------------------------------------
void renderOverlay(IDXGISwapChain3* swapChain) {
    // Lazy init on first Present — safe to call D3D12 here (not in DllMain).
    if (!s_initialized) {
        imgui_init::initialize(swapChain);
        s_initialized = true;
        OutputDebugStringW(L"[overlay] frame: init done, entering first render\n");
    }

    // Log queue state on first render attempt
    static bool firstRender = true;
    if (firstRender) {
        firstRender = false;
        wchar_t buf[128];
        swprintf_s(buf, L"[overlay] frame: queue=%p  frames=%zu\n",
                   (void*)g_capturedQueue, s_frames.size());
        OutputDebugStringW(buf);
    }

    if (!g_capturedQueue) {
        OutputDebugStringW(L"[overlay] frame: queue null, skipping render\n");
        return;
    }
    if (s_frames.empty()) {
        OutputDebugStringW(L"[overlay] frame: frames empty, skipping render\n");
        return;
    }

    UINT bufferIndex = swapChain->GetCurrentBackBufferIndex();
    FrameContext& fc = s_frames[bufferIndex];

    // Fence wait
    if (fc.fenceValue > 0 && s_fence->GetCompletedValue() < fc.fenceValue) {
        s_fence->SetEventOnCompletion(fc.fenceValue, s_fenceEvent);
        WaitForSingleObject(s_fenceEvent, 5000);
    }

    ID3D12Device* dev = imgui_init::getDevice();
    wchar_t buf[512];
    auto logReason = [&](const wchar_t* tag) {
        HRESULT r = dev->GetDeviceRemovedReason();
        if (r != S_OK) {
            swprintf_s(buf, L"[overlay] DEVICE REMOVED at %ls: 0x%08X\n", tag, (unsigned)r);
            OutputDebugStringW(buf);
        }
    };
    auto drainInfoQueue = [&]() {
        ID3D12InfoQueue* iq = imgui_init::getInfoQueue();
        if (!iq) return;
        UINT64 n = iq->GetNumStoredMessages();
        for (UINT64 i = 0; i < n; ++i) {
            SIZE_T len = 0;
            iq->GetMessageW(i, nullptr, &len);
            std::vector<BYTE> raw(len);
            auto* msg = reinterpret_cast<D3D12_MESSAGE*>(raw.data());
            iq->GetMessageW(i, msg, &len);
            wchar_t wbuf[512];
            swprintf_s(wbuf, L"[D3D12] %hs\n", msg->pDescription);
            OutputDebugStringW(wbuf);
        }
        iq->ClearStoredMessages();
    };

    HRESULT hr = fc.allocator->Reset();
    hr = s_commandList->Reset(fc.allocator.Get(), nullptr);
    logReason(L"after cmdlist Reset");

    // Barrier PRESENT → RENDER_TARGET
    D3D12_RESOURCE_BARRIER barrier{};
    barrier.Type                   = D3D12_RESOURCE_BARRIER_TYPE_TRANSITION;
    barrier.Flags                  = D3D12_RESOURCE_BARRIER_FLAG_NONE;
    barrier.Transition.pResource   = s_backBuffers[bufferIndex].Get();
    barrier.Transition.Subresource = D3D12_RESOURCE_BARRIER_ALL_SUBRESOURCES;
    barrier.Transition.StateBefore = D3D12_RESOURCE_STATE_PRESENT;
    barrier.Transition.StateAfter  = D3D12_RESOURCE_STATE_RENDER_TARGET;
    s_commandList->ResourceBarrier(1, &barrier);

    s_commandList->OMSetRenderTargets(1, &fc.rtv, FALSE, nullptr);
    logReason(L"after OMSetRenderTargets");

    // Bind shader-visible SRV heap (required for ImGui font texture)
    ID3D12DescriptorHeap* heaps[] = { imgui_init::getSrvHeap() };
    s_commandList->SetDescriptorHeaps(1, heaps);

    // ImGui frame
    ImGui_ImplDX12_NewFrame();
    ImGui_ImplWin32_NewFrame();
    ImGui::NewFrame();

    ui::renderImGui();

    ImGui::Render();
    ImGui_ImplDX12_RenderDrawData(ImGui::GetDrawData(), s_commandList.Get());
    logReason(L"after RenderDrawData");

    // Barrier RENDER_TARGET → PRESENT
    barrier.Transition.StateBefore = D3D12_RESOURCE_STATE_RENDER_TARGET;
    barrier.Transition.StateAfter  = D3D12_RESOURCE_STATE_PRESENT;
    s_commandList->ResourceBarrier(1, &barrier);

    hr = s_commandList->Close();
    if (FAILED(hr)) {
        swprintf_s(buf, L"[overlay] cmdlist Close FAILED: 0x%08X\n", (unsigned)hr);
        OutputDebugStringW(buf);
    }
    logReason(L"after Close");

    ID3D12CommandList* lists[] = { s_commandList.Get() };
    g_capturedQueue->ExecuteCommandLists(1, lists);
    logReason(L"after ECL");
    drainInfoQueue();

    fc.fenceValue = ++s_fenceCounter;
    g_capturedQueue->Signal(s_fence.Get(), fc.fenceValue);
}

} // namespace frame
