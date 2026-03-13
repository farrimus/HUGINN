#pragma once
// Forward declarations shared across overlay_core translation units.

#define WIN32_LEAN_AND_MEAN
#include <windows.h>
#include <d3d12.h>
#include <dxgi1_4.h>
#include <wrl/client.h>

using Microsoft::WRL::ComPtr;

namespace hook        { void initialize(); }
namespace imgui_init  { void initialize(IDXGISwapChain3* swapChain);
                        void invalidate();
                        void recreate(); }
namespace frame       { void renderOverlay(IDXGISwapChain3* swapChain);
                        void createRenderTargets(IDXGISwapChain3* swapChain);
                        void cleanupRenderTargets(); }
namespace renderer    { void initialize(); }
