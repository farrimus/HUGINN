# Overlay — DX12 ImGui Overlay

**Last updated:** 2026-03-16
**Source:** `overlay/` (built on Windows, deployed as `overlay.dll` + `injector.exe`)
**Key config:** `overlay_ui/config.h` — edit `SERVER_HOST`, `SERVER_PORT`, `SERVER_TOKEN` before building.

---

## `overlay_core/dllmain.cpp`
DLL entry point. On `DLL_PROCESS_ATTACH`, queues a worker thread via `QueueUserWorkItem` to avoid loader-lock. Worker calls `hook::initialize()`.

---

## `overlay_core/hook.cpp`
MinHook setup. Creates dummy D3D12 device/queue/swap chain to read vtable addresses, then installs three hooks:

| Hook | Vtable slot | Purpose |
|---|---|---|
| `hookPresent` | IDXGISwapChain slot 8 | Calls `frame::renderOverlay` before original Present |
| `hookResizeBuffers` | IDXGISwapChain slot 13 | Invalidates + recreates render targets around resize |
| `hookECL` | ID3D12CommandQueue slot 10 | Captures the game's primary DIRECT command queue |

**Critical detail:** `hookECL` captures `g_capturedQueue` only on the **first** DIRECT ECL call (`g_capturedQueue == nullptr` guard). This is required because Dear ImGui 1.91.5 creates its own temporary `ID3D12CommandQueue` during font upload (`ImGui_ImplDX12_NewFrame` first call). Without the guard, hookECL overwrites `g_capturedQueue` with the temp queue pointer, which ImGui then destroys, leaving a dangling pointer that causes `DXGI_ERROR_ACCESS_DENIED` at the next ECL call.

---

## `overlay_core/imgui_init.cpp`
Initializes ImGui on the first Present call. Gets device from the captured queue (`g_capturedQueue->GetDevice`), creates SRV + RTV descriptor heaps, creates render targets for each back buffer, calls `ImGui_ImplWin32_Init` + `ImGui_ImplDX12_Init`. Strips SRGB from RTV format (flip swap chains reject SRGB RTVs). Subclasses the game window for input via `SetWindowLongPtrW`.

---

## `overlay_core/frame.cpp`
Per-frame render logic called from `hookPresent`:
1. Fence wait on the current frame context
2. Reset command allocator + command list
3. Barrier: PRESENT → RENDER_TARGET
4. `OMSetRenderTargets`, `SetDescriptorHeaps`
5. `ImGui_ImplDX12_NewFrame` / `ImGui_ImplWin32_NewFrame` / `ImGui::NewFrame`
6. `ui::renderImGui()` — the UI content call
7. `ImGui::Render` + `ImGui_ImplDX12_RenderDrawData`
8. Barrier: RENDER_TARGET → PRESENT
9. Close + `ExecuteCommandLists` on `g_capturedQueue`
10. `Signal` fence

---

## `overlay_core/input.cpp`
WndProc subclass (`overlayWndProc`). F8 toggle fires first (`ui::visible = !ui::visible`); F7 toggle fires next (`ship_profile_panel::g_visible = !g_visible`). Then passes messages to `ImGui_ImplWin32_WndProcHandler`. Blocks mouse/keyboard messages from reaching the game when ImGui wants capture.

---

## `overlay_ui/config.h`
Compile-time constants: `SERVER_HOST`, `SERVER_HOST_W`, `SERVER_PORT`, `SERVER_TOKEN`, `CHAT_PATH`. Edit before building on Windows.

---

## `overlay_ui/http_client.h` / `http_client.cpp`
WinHTTP client. Four public functions:
- `http::postChat()` — SSE streaming POST; `onChunk`/`onDone` callbacks; used by companion panel.
- `http::getJson()` — synchronous GET; returns full response body; used by route and ship profile panels.
- `http::postEmpty()` — fire-and-forget POST (no body); used for `/route/clear`.
- `http::postJson()` — synchronous POST with JSON body; returns full response body; used for `/route/activate` and `/ship-profile`.

All run synchronously — always call from a background thread. Shared `_openHandles`/`_closeHandles` helpers.

---

## `overlay_ui/companion_panel.h` / `companion_panel.cpp`
Chat panel state and ImGui draw loop. Module-static state: message vector, input buffer, mutex, scroll flag, status line. `send()` pushes user + streaming assistant messages, spawns a detached `std::thread` that calls `http::postChat()` and appends chunks to the last message under mutex. `draw()` renders fixed-position panel (right side, 400×600px, dark terminal aesthetic, green text) every frame.

---

## `overlay_ui/route_panel.h` / `route_panel.cpp`
NAV COMPUTER panel (bottom-left, 440×260px). Background poller calls `GET /current-route` every 5s. Shows two rows when an alternative route is available:
- Primary route: bright green text, no USE button (already active).
- Alternative route: dimmed text, `[USE]` button → fires detached thread calling `POST /route/activate {"variant":"alternative"}`.
- CLEAR ROUTE button calls `POST /route/clear`. Both `s_activating` and `s_clearing` are `std::atomic<bool>`.
- Summary line format: `SYS-A → SYS-B   6 jumps · 142 LY · 87u`.

---

## `overlay_ui/ship_profile_panel.h` / `ship_profile_panel.cpp`
SHIP PROFILE panel (top-left, 440×280px). Toggled by F7 (`g_visible` bool). Five inputs:
1. Ship type dropdown — 13 ships (Carom → Chumaq); resets fuel category on change.
2. Fuel type dropdown — filtered to ship category (basic: D1/D2; advanced: SOF-40/EU-40/SOF-80/EU-90).
3. Fuel units — InputInt clamped to `[0, max_fuel]`.
4. Adaptive level — InputInt clamped to `[0, 10]`.
5. Extra cargo (kg) — InputInt.

Computes and displays live jump range (LY) and fuel budget (LY) using mirrored server formulas. Background poller fetches `current_system_temp` from `GET /current-route` every 5s (`std::atomic<float> s_cur_temp`). SAVE button POSTs to `/ship-profile`; shows SAVED/ERROR feedback for 2 seconds.

---

## `overlay_ui/render.cpp`
UI entry point called every frame from `frame.cpp`. Checks `ui::visible`; if true, calls `companion_panel::draw()`, `route_panel::draw()`, `ship_profile_panel::draw()`. `init()`/`shutdown()` lifecycle manages both panel poller threads.
