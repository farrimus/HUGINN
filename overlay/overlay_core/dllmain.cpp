#define WIN32_LEAN_AND_MEAN
#include <windows.h>
#include "overlay_core.h"
#include "../overlay_ui/render.h"

// ---------------------------------------------------------------------------
// renderer::initialize — called from worker thread after DLL_PROCESS_ATTACH
// ---------------------------------------------------------------------------
namespace renderer {
void initialize() {
    OutputDebugStringW(L"[overlay] renderer::initialize — starting hook setup\n");
    ui::init();
    hook::initialize();
}
} // namespace renderer

// ---------------------------------------------------------------------------
// Worker thread entry — runs on a thread-pool thread so DllMain returns fast.
// ---------------------------------------------------------------------------
static DWORD WINAPI deferredInit(LPVOID /*param*/) {
    OutputDebugStringW(L"[overlay] deferredInit — thread started\n");
    renderer::initialize();
    OutputDebugStringW(L"[overlay] deferredInit — complete\n");
    return 0;
}

// ---------------------------------------------------------------------------
// DllMain
// ---------------------------------------------------------------------------
BOOL WINAPI DllMain(HINSTANCE hModule, DWORD reason, LPVOID /*reserved*/) {
    if (reason == DLL_PROCESS_ATTACH) {
        DisableThreadLibraryCalls(hModule);
        OutputDebugStringW(L"[overlay] DllMain DLL_PROCESS_ATTACH\n");
        // Deferred init avoids loader-lock issues with COM / D3D12.
        QueueUserWorkItem(deferredInit, nullptr, WT_EXECUTELONGFUNCTION);
    }
    return TRUE;
}
