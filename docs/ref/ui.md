# UI Reference

**Last updated:** 2026-03-16
**Files:** `static/index.html`, `static/debug.html`

---

## In-Game Browser — Confirmed Environment

Probed 2026-03-13. EVE Frontier uses **Chromium 122** (Chrome/537.36 UA, AppleWebKit). This is modern desktop Chrome level.

| Feature | Status |
|---------|--------|
| SSE (`EventSource`) | Supported |
| WebSocket | Supported |
| Fetch / XHR | Supported |
| ResizeObserver | Supported |
| Container Queries | Supported |
| `visibilitychange` event | Supported |

**Viewport:** Always resizable (probe showed 555×1246 at 3440×1440 resolution). The current `index.html` uses `clamp()` + Tailwind flex + `container-type: inline-size` to handle any panel size.

**Origin:** The browser loads `http://vps-ip:8745/static/index.html` and hits `/chat` on the same origin — zero CORS, zero preflight.

**SSE persistence:** Confirmed alive across panel resize and alt-tab (`visibilitychange` green). The 5-second auto-reconnect in `index.html` handles brief network blips.

**SSE keep-alive:** Server should send a `: keep-alive\n\n` comment every 15–20 seconds to prevent embedded-view timeout. **Not yet implemented.** Add to the `event_stream()` generator in `main.py` if connection stability issues appear.

---

## `static/index.html` — In-Game Browser Chat UI

Updated 2026-03-13. Full replacement of the previous minimal version.

**Stack:**
- Tailwind CSS via CDN (no build step)
- `container-type: inline-size` + `clamp(13px, 2.2cqw, 16px)` for font scaling at any panel size
- `ResizeObserver` on `document.body` (Tailwind flex + container queries handle layout automatically)
- SSE via `EventSource` with 5-second auto-reconnect on error
- Dark terminal aesthetic (black background, lime-400 text, Courier New)

**SSE flow:**
1. `startSSE()` opens `EventSource('/chat?token=...')`
2. `onmessage`: parses `data.text`, appends to message list
3. `onerror`: closes, schedules reconnect after 5s, updates status to `RECONNECTING...`
4. `sendMessage()`: POSTs `{message, history: []}` to `/chat` via fetch (history not tracked in this UI — the overlay's companion panel tracks its own history)

**Token:** `SERVER_TOKEN` constant in the script block, set to the `.env` value at deploy time.

**No polling fallback.** SSE is confirmed native in Chromium 122. Polling was considered and explicitly dropped.

---

## `static/debug.html` — Developer Debug Console

Added 2026-03-16. Standalone dev tool served at `http://vps-ip:8745/static/debug.html`. Not linked from `index.html`; browser-only, not shown in-game.

**Layout:** Three-column (equal thirds):

| Column | Contents |
|--------|----------|
| Left | Live log stream — SSE from `GET /logs/stream`, auto-scroll, line counter |
| Middle | Ship profile editor → Nav computer route planner → Route result display → Agent chat |
| Right | Pipeline state — `GET /pipeline-state` polled every 5 s, full column height |

**Nav computer in debug.html:**
- Origin / Destination fields: `oninput` uppercases, `text-transform: uppercase` CSS
- Ship type dropdown (all 13 ships), fuel type dropdown, fuel quantity, adaptive level
- **Route mode dropdown:** "Fewest jumps" (`cost_mode=jumps`), "Least fuel" (`cost_mode=fuel`), "Gate only" (`cost_mode=gate`)
- POSTs `POST /route` with full ship profile + `cost_mode`; renders result as vertical hop chain

**Route result display:**
Each hop rendered as a labeled connector between system boxes:
```
[ SYSTEM-A ] ──GATE── [ SYSTEM-B ]
                         78.2° | 3 planets
[ SYSTEM-B ] ──142.5 LY── [ SYSTEM-C ]
                              22.1° | 5 planets
```
Temp color-coding: green < 70°, yellow 70–79°, orange 80–89°, red ≥ 90°.

**Agent chat:**
- POSTs `{message, history}` to `POST /chat` with `SERVER_TOKEN` bearer auth
- Response body is **streamed directly** via `ReadableStream` reader (not via separate SSE endpoint)
- `chatBusy` flag disables send button during streaming; clears on stream close

**Token:** `SERVER_TOKEN` constant in script block — set to `.env` value at deploy time (same as `index.html`).
