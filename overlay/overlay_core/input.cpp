#include "overlay_core.h"
#include <imgui.h>
#include <imgui_impl_win32.h>
#include "../overlay_ui/render.h"
#include "../overlay_ui/ship_profile_panel.h"

// Declared extern in imgui_init.cpp; defined here.
WNDPROC g_originalWndProc = nullptr;

// Forward declaration from imgui_impl_win32 — returns nonzero if ImGui consumed the message.
extern IMGUI_IMPL_API LRESULT ImGui_ImplWin32_WndProcHandler(HWND, UINT, WPARAM, LPARAM);

static bool isMouseMessage(UINT msg) {
    return (msg >= WM_MOUSEFIRST && msg <= WM_MOUSELAST)
        || msg == WM_MOUSEWHEEL
        || msg == WM_MOUSEHWHEEL;
}

static bool isKeyboardMessage(UINT msg) {
    switch (msg) {
        case WM_KEYDOWN:
        case WM_KEYUP:
        case WM_SYSKEYDOWN:
        case WM_SYSKEYUP:
        case WM_CHAR:
        case WM_SYSCHAR:
            return true;
        default:
            return false;
    }
}

LRESULT CALLBACK overlayWndProc(HWND hwnd, UINT msg, WPARAM wParam, LPARAM lParam) {
    // F8 toggles overlay visibility before ImGui sees the message
    if (msg == WM_KEYDOWN && wParam == VK_F8) {
        ui::visible = !ui::visible;
        return 0;
    }
    if (msg == WM_KEYDOWN && wParam == VK_F7) {
        ship_profile_panel::g_visible = !ship_profile_panel::g_visible;
        return 0;
    }

    // Let ImGui process the message first
    if (ImGui_ImplWin32_WndProcHandler(hwnd, msg, wParam, lParam))
        return 1;

    ImGuiIO& io = ImGui::GetIO();

    // Block mouse messages if ImGui wants mouse
    if (io.WantCaptureMouse && isMouseMessage(msg))
        return 0;

    // Block keyboard messages if ImGui wants keyboard
    if (io.WantCaptureKeyboard && isKeyboardMessage(msg))
        return 0;

    // Pass everything else to the original game WndProc
    return CallWindowProcW(g_originalWndProc, hwnd, msg, wParam, lParam);
}
