# UI Reference

**Last updated:** 2026-03-17
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

**SSE keep-alive:** Server sends a `: keep-alive\n\n` comment at the start of each stream to prevent embedded-view timeout. **Implemented** — all `event_stream()` generators in `main.py` emit the keep-alive comment immediately (heartbeat sent every connection open).

---

## `static/index.html` — In-Game Browser Chat UI

Updated 2026-03-13. Full replacement of the previous minimal version.

**Stack:**
- Tailwind CSS via CDN (no build step)
- `container-type: inline-size` + `clamp(13px, 2.2cqw, 16px)` for font scaling at any panel size
- `ResizeObserver` on `document.body` (Tailwind flex + container queries handle layout automatically)
- SSE via `EventSource` with 5-second auto-reconnect on error
- Dark terminal aesthetic (black background, lime-400 text, Courier New)

### Token Handling for SSE

**Problem:** The `EventSource` API has a fundamental limitation — it does **not support custom HTTP headers**. This means you cannot pass an `Authorization: Bearer` token directly via headers when opening an SSE stream.

**Solution:** Pass the token as a **query parameter** in the URL. The backend validates the token from the query string instead of from headers.

**JavaScript approach (EventSource):**
```javascript
const token = "5740edb0fb25a051db4a932c3622bd69ce47d487bc501f2bde4cb7e19907c454";
const eventSource = new EventSource(`/chat?token=${encodeURIComponent(token)}`);

eventSource.onmessage = (event) => {
  const data = JSON.parse(event.data);
  appendMessage(data.text);
};

eventSource.onerror = () => {
  eventSource.close();
  setTimeout(() => startSSE(), 5000); // reconnect
};
```

**Current implementation (index.html):** Uses `fetch()` with `ReadableStream` instead of `EventSource`, because fetch allows custom headers (`X-Server-Token`). This avoids the query-parameter workaround but requires manual stream parsing.

---

**SSE flow (fetch-based, current):**
1. `startSSE()` opens `fetch('/chat', { headers: { 'X-Server-Token': SERVER_TOKEN } })`
2. Manually reads response stream via `res.body.getReader()`
3. Parses SSE-formatted lines (`data: {json}`)
4. `onerror`: closes stream, schedules reconnect after 5s, updates status to `RECONNECTING...`
5. `sendMessage()`: POSTs `{message, history: []}` to `/chat` via fetch with same headers (history not tracked in this UI — the overlay's companion panel tracks its own history)

**Token handling:**
- Stored in `SERVER_TOKEN` constant (set from `.env` at deploy time)
- Passed as `X-Server-Token` header on both POST and stream fetch calls
- Backend validates via `require_token()` dependency in `src/auth.py`
- On invalid token: receives HTTP 403 response, status shows "AUTH ERROR: HTTP 403"
- Token lifecycle: set once on page load, persists for all subsequent requests until browser closes

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
- **Route mode dropdown:** "Fewest jumps" (`cost_mode=jumps`), "Least fuel" (`cost_mode=fuel`), "Gate only" (`gate_only=true`)
- Checkbox: "Gate-only route (no heat cost)" → POSTs `POST /route` with full ship profile + `gate_only=true`; renders result as vertical hop chain

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
- POSTs `{message, history}` to `POST /chat` with `X-Server-Token` header auth (not Bearer — raw token value)
- Response body is **streamed directly** via `ReadableStream` reader (not via separate SSE endpoint)
- `chatBusy` flag disables send button during streaming; clears on stream close

**Token source and usage:**
The `TOKEN` constant is hardcoded in the `<script>` block — set to `.env` value at deploy time. All API calls include it in the `X-Server-Token` header:

```javascript
const TOKEN = "5740edb0fb25a051db4a932c3622bd69ce47d487bc501f2bde4cb7e19907c454";

// Log stream (SSE via fetch):
fetch('/logs/stream', { headers: { 'X-Server-Token': TOKEN } })

// Agent chat (POST):
fetch('/chat', {
  method: 'POST',
  headers: {
    'Content-Type': 'application/json',
    'X-Server-Token': TOKEN
  },
  body: JSON.stringify({ message, history })
})

// Ship profile (GET/POST):
fetch('/ship-profile', {
  method: 'GET', // or 'POST'
  headers: { 'X-Server-Token': TOKEN }
})
```

**Token acquisition (for manual testing via curl):**
1. **If no token required:** Not set in `.env`, all endpoints open (local dev mode)
2. **With token (production):** Token value is in `/etc/systemd/system/openclaw-gateway.service` or stored in deployment config

**Example curl requests with token:**
```bash
# Get token from deployment (example):
TOKEN="5740edb0fb25a051db4a932c3622bd69ce47d487bc501f2bde4cb7e19907c454"

# Send a chat message:
curl -X POST http://localhost:8745/chat \
  -H "X-Server-Token: $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"message": "hello", "history": []}'

# Stream logs (returns SSE):
curl -H "X-Server-Token: $TOKEN" http://localhost:8745/logs/stream
```

**Token lifecycle:** Loaded at debug.html page load, persists for all requests in that session. No refresh or re-authentication required. On invalid/missing token: server responds with HTTP 403 Forbidden.
