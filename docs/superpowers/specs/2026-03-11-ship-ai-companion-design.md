# Ship AI Companion — Design Spec

**Project:** EVE Frontier Hackathon 2026 — "A Toolkit for Civilization"
**Track:** B — External Application
**Date:** 2026-03-11
**Status:** Draft — Pending User Review

---

## Overview

An AI-powered in-lore companion chat agent for EVE Frontier. The agent presents as the player's ship AI — dry, functional, with emergent personality quirks. It is aware of the live game state, reacts to client log events, calculates routes, and answers questions grounded in EVE Frontier lore.

Two entry points, one UI:
- **Overlay** — player opens the web app in a browser alongside the game
- **In-game browser** — player interacts with a Smart Assembly that has the app URL configured; EVE Frontier opens it in an internal browser window (max 787×1198px at 1440p, fluid/responsive layout)

**Hosting:** Hetzner VPS (`ubuntu-4gb-hel1-5`), `/opt/eve-frontier/`. Runs alongside OpenClaw on a separate port.

---

## Architecture

```
[EVE Frontier game client]
        |
        | in-game browser opens URL  /  player opens overlay in browser
        v
[HTML/JS chat window]  <-- streaming responses (SSE) --  [FastAPI server on VPS]
        |                                                        |
        | POST /chat {message, context}                         |
        v                                                        |
[FastAPI server]                                                 |
    |           |              |               |                 |
    v           v              v               v                 |
[Claude API] [World API]  [Log parser]  [Route engine]          |
                                          (Phase 2)
```

**Stack:**
- Backend: Python, FastAPI
- Frontend: Plain HTML/CSS/JS (no framework, no build step)
- AI: Claude API (Anthropic) with streaming via Server-Sent Events
- Game data: EVE Frontier World API (docs: https://docs.evefrontier.com)
- Hosting: this VPS, port **8745** (separate from OpenClaw gateway on 18789)

**MVP modules:** Claude API, World API client, Log parser
**Phase 2:** Route engine

---

## Frontend

Single `index.html` served by FastAPI.

**Visual style:** Dark background, monospace font — ship terminal aesthetic. AI messages dim green left-aligned, player messages distinct colour right-aligned.

**Responsive layout:** Fluid, fills whatever size the in-game browser provides. Reference size: 787px wide (1440p). No hardcoded pixel widths.

**Mode detection:** A URL query param determines mode:
- `?mode=ingame` — in-game browser mode: no minimize button, fills window
- No param (default) — overlay mode: minimize button collapses to corner tab

**Context params when opened from a Smart Assembly:**
```
?mode=ingame&system=<system_name>&object_id=<assembly_id>
```
These are passed by whoever configures the Smart Assembly URL. The backend uses them to pre-load system context on session start.

**SSE compatibility risk:** EVE Frontier's in-game browser is an embedded web view of unknown origin. SSE requires persistent HTTP connections which some embedded browsers break. This must be tested early in implementation. Fallback: polling (`/chat/poll`) if SSE fails.

**Responses:** Stream token by token via SSE. If SSE is unavailable, fall back to polling every 500ms.

---

## Backend Modules

### 1. Claude API — Ship AI Voice

Persistent system prompt defines the character: personality (dry, functional, slight quirks), in-universe knowledge boundaries, tone.

**Identity:** No name. The AI presents as the ship's onboard computer — anonymous, functional. Refers to itself in third person as "this unit" or "ship systems." It does not adopt a persona if the player tries to give it a name — it acknowledges the input and continues as a computer. This is enforced in the system prompt.

Context assembled per request:
```
[system prompt: ship AI character]
[context block: current system summary, recent log events]
[conversation history: sliding window of last 20 exchanges]
[user message]
```

**History management:** Sliding window — oldest exchanges dropped first when cap is reached. No summarisation. The 20-exchange cap applies to what is sent to Claude per request, not to the stored session history (which is kept in full for the session).

**World API fetch timing:** World API data is fetched on session start and refreshed on demand (when the player asks something location-related). Fetches run in parallel with context assembly to minimise latency, not serially.

**Summarisation:** World API responses are formatted by a deterministic Python formatter (not a Claude pre-pass) before injection. This keeps latency and cost low.

**Cost controls:** Claude API calls are per user message only. No background polling. History cap limits token growth. No additional rate limiting needed for personal use.

**Token budget risk:** If the World API context block or a user message is unusually large, 20 exchanges may still approach Claude's context window limit. Mitigation: the context block is capped to 500 tokens by the deterministic formatter. If total prompt tokens exceed 80% of the model's context window, the oldest exchanges are trimmed further until it fits.

### 2. World API Client

Thin wrapper around EVE Frontier's public World API.

- Fetches: current system data, nearby systems, recent killmails, Smart Assembly data
- Cache: per-endpoint, per-parameter, 30 seconds TTL (e.g. system "Jita" cached independently from system "Uedama")
- Fetched on session start (using `?system=` param if present) and refreshed on demand
- World API auth requirements: TBD (check docs during implementation). Risk: if auth requires OAuth or a non-trivial token flow, the World API client will need an auth layer. Fallback for MVP: if auth is required and non-trivial, the MVP will operate without live World API data and the AI will note sensors are offline.

### 3. Log Parser

Two components: a **client-side log agent** (runs on the gaming PC) and a **server-side buffer** (receives and stores events).

**Why not Syncthing:** EVE Frontier generates large volumes of log data, most of it irrelevant. Syncing raw files is wasteful. The client agent pre-filters and pre-parses on the PC, sending only structured events the AI actually needs.

**Client-side log agent (`log-agent.py` — runs on gaming PC):**
- Watches the EVE Frontier log file (path configurable, default: `%USERPROFILE%\AppData\Local\CCP\EVE Frontier\logs\`)
- Filters for relevant event types only: jumps, combat, docking, interactions, deaths, warp
- Parses matching lines into structured JSON
- POSTs events to the server's `/log/ingest` endpoint as they occur
- Lightweight, single Python script, runs in background while playing

**Server-side buffer:**
- `/log/ingest` endpoint receives structured JSON events
- Maintains a rolling in-memory buffer of the last 50 events
- Last 10 events injected into Claude context per message

**Log file location:** `C:\Users\Markus\Documents\Frontier\logs\` — confirmed.

Four subfolders:

| Folder | Contents | Used by agent |
|---|---|---|
| `Gamelogs\` | Combat, mining, damage, game events | Yes — MVP |
| `Chatlogs\` | All in-game chat channels | Yes — MVP |
| `Marketlogs\` | Market exports (empty unless manually exported) | Phase 2 |
| `Fleetlogs\` | Fleet activity (currently empty) | No |

**Gamelogs:** Agent watches for relevant event types — combat hits, mining yields, deaths, docking, undocking. Irrelevant lines discarded on the PC before sending.

**Chatlogs:** Agent watches two channel types:
- `Local` channel file — system entry announcements appear here when the player jumps to a new system. This is the primary source of current location, supplementing or replacing World API polling for location.
- Tribe/corp channel files — optional context for tribe chat summarisation. Injected on demand ("what's happening in tribe chat?") not automatically.

**Path configurable** via `LOG_FILE_PATH` in log-agent `.env`. Agent validates both subfolders exist at startup and logs a clear error if not found.

### 4. Route Engine — Phase 2 (out of scope for MVP)

Takes origin + destination system name → ordered jump list + threat annotations from killmail data.

Requires a star map graph. Map data source (World API vs static dataset) is not yet confirmed. This module is deferred until Phase 1 (chat + log + World API) is working. Players can ask the AI to calculate routes; it will respond that navigation charts are loading until Phase 2 is complete.

---

## Graceful Degradation

Each module fails independently. All error responses are delivered in the ship AI's voice.

| Module fails | UI behaviour | AI response |
|---|---|---|
| World API down | No indicator, silent | "Sensor array offline. Proceeding without live data." |
| Log file not found / not synced | No indicator, silent | Operates without log context |
| Route engine unavailable (Phase 2) | No indicator | "Navigation charts not yet loaded." |
| Claude API error | Inline error message in chat | N/A |
| SSE broken | Auto-fallback to polling | No change in UX |

---

## Security

Personal use. The app runs on port 8745.

**If accessed only from Markús's local machine (overlay mode):** port stays firewalled, no auth needed.

**If accessed from the in-game browser (which connects from the game client's machine to the VPS):** port must be open. In that case, auth via a shared secret in a request header:

```
X-Ship-Token: <secret>
```

Token checked server-side on every request. Stored in a `.env` file, not hardcoded. The Smart Assembly URL does NOT include the token — the frontend JS sends it as a header on API calls.

Note: URL query params (`?token=...`) are avoided because they appear in server logs, browser history, and Referer headers.

---

## Deferred / Open Items

| Item | Status |
|---|---|
| Ship AI personality details (system prompt) | Draft during implementation |
| Exact log file path on Windows | Confirm during setup |
| World API auth requirements | Check docs during implementation |
| Route engine map data source | Phase 2 investigation |
| Port number for the FastAPI server | Assigned: 8745 |
| Exact log file path on Windows | Confirmed: `C:\Users\Markus\Documents\Frontier\logs\` |

---

## Hackathon Prize Category Targets

| Category | Rationale |
|---|---|
| Live Frontier Integration (primary) | Runs against live game data during judging |
| Creative (secondary) | In-lore ship AI character with personality is novel |
| Utility (stretch) | Situational awareness = practical player tool |
