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

Persistent system prompt defines the character: name (TBD by Markús), personality (dry, functional, slight quirks), in-universe knowledge boundaries, tone.

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

Watches the EVE Frontier client log file. Parses new lines as they arrive. Extracts structured events: jumps, combat, docking, interactions.

**Rolling buffer:** Last 50 events stored in memory. Last 10 injected into context per message.

**Transport — candidate approach: Syncthing**
Syncthing is already running between Markús's machine and this server. The EVE Frontier log folder will be added to the Syncthing sync. The log parser watches the synced local copy. This requires no new infrastructure.

Fallback if Syncthing is unsuitable: a small Python script on the gaming PC that tails the log file and POSTs new lines to a `/log/ingest` endpoint on the server.

**Log file location on Windows:** Typically `%USERPROFILE%\AppData\Local\CCP\EVE Frontier\logs\` — to be confirmed. The path will be configurable via `.env` (`LOG_FILE_PATH`). On startup, the log parser validates the path exists and logs a clear error if not — it does not fail silently.

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
| Ship AI name and personality details | Markús to decide |
| Exact log file path on Windows | Confirm during setup |
| World API auth requirements | Check docs during implementation |
| Route engine map data source | Phase 2 investigation |
| Port number for the FastAPI server | Assigned: 8745 |
| Syncthing log folder sync confirmation | Markús to configure |

---

## Hackathon Prize Category Targets

| Category | Rationale |
|---|---|
| Live Frontier Integration (primary) | Runs against live game data during judging |
| Creative (secondary) | In-lore ship AI character with personality is novel |
| Utility (stretch) | Situational awareness = practical player tool |
