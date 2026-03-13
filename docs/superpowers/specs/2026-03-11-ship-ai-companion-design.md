# Ship AI Companion — Design Spec

**Project:** EVE Frontier Hackathon 2026 — "A Toolkit for Civilization"
**Track:** B — External Application
**Date:** 2026-03-11
**Status:** Approved / Implemented (2026-03-11)

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
These are passed by whoever configures the Smart Assembly URL. Not currently used by the backend — system context comes from the log agent instead. Reserved for Phase 2 (pre-loading context on session start without log agent).

**SSE compatibility risk:** EVE Frontier's in-game browser is an embedded web view. SSE requires persistent HTTP connections which some embedded browsers break. This must be tested once the log agent is deployed and the in-game URL is accessible. Polling fallback (`/chat/poll`) is not implemented — if SSE fails in-game, this becomes a Phase 2 item.

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

**History management:** Sliding window — oldest exchanges dropped first when cap is reached. No summarisation. The cap is 40 messages (20 exchange pairs) applied both client-side (JS) and server-side (`build_messages()`).

**World API fetch timing:** World API data is fetched serially before context assembly (simple `await` call). Parallel fetching is a possible future optimisation but not implemented.

**Summarisation:** World API responses are formatted by a deterministic Python formatter (not a Claude pre-pass) before injection. This keeps latency and cost low.

**Cost controls:** Claude API calls are per user message only. No background polling. History cap limits token growth. No additional rate limiting needed for personal use.

**Context block cap:** The context block is hard-capped at 2000 characters by the deterministic formatter (`context_builder.py`). Dynamic token-budget trimming is not implemented.

### 2. World API Client

Thin wrapper around EVE Frontier's public World API (`https://world-api-stillness.live.tech.evefrontier.com`).

- Fetches: current system data (gates, coordinates, constellation, security status)
- No auth required — public API
- No killmails endpoint exists in the API. No Smart Assembly data endpoint exists.
- Cache: per-endpoint, per-parameter, 30 seconds TTL
- System lookup requires an ID — a name→ID index is built from the `/v2/solarsystems` paginated list (24,500+ systems) and persisted to `data/system_index.json`. Loaded from disk on startup; rebuilt via `POST /admin/rebuild-index` when needed.
- Startup: index build runs as a background `asyncio.create_task()` so the server starts immediately. Retries 5 times with 3s delay to handle DNS readiness at boot.
- World API refresh is triggered event-driven: when the log agent sends a `system_change` event, the server fires a background fetch for the new system so data is warm by the time the player asks a question.

### 3. Log Parser

Two components: a **client-side log agent** (runs on the gaming PC) and a **server-side buffer** (receives and stores events).

**Why not Syncthing:** EVE Frontier generates large volumes of log data, most of it irrelevant. Syncing raw files is wasteful. The client agent pre-filters and pre-parses on the PC, sending only structured events the AI actually needs.

**Client-side log agent (`log-agent/log_agent.py` — runs on gaming PC):**
- Watches `Gamelogs\` and `Chatlogs\` (path configurable via `LOG_BASE_PATH` in `.env`)
- Parses lines into structured events: combat (in/out/miss), mining, docking, undock, autopilot, system_change, chat. Unrecognised lines preserved as `gamelog_raw` for visibility
- **New-file behaviour (mtime fix):** on first encounter of a file, if `mtime > agent_start` the file is new — read from position 0. If `mtime ≤ agent_start` — old file, seek to end. Handles Windows watchdog race where `on_modified` fires before `on_created`
- **Session tracker:** combat and mining events are absorbed into sessions locally. Summaries are sent to the server when sessions close (on jump, dock, 60s/120s inactivity timeout, or shutdown). Pass-through events (system_change, docking, chat, etc.) are sent immediately
- **Bootstrap:** on startup, scans the tail of the most recent `Local_*` chatlog for the last known system. A daemon thread retries every 30s if agent starts before the game client
- POSTs structured events to `/log/ingest` as they occur (or on session close)
- Lightweight, runs in background while playing

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
- `Local` channel file — system entry announcements appear here when the player jumps to a new system. This acts as a **trigger**: on detecting a system change, the server immediately fires a World API fetch for the new system. The API is the source of truth for location data; the chat log is the event that tells the server when to refresh it. This avoids constant polling while keeping context accurate.
- Tribe/corp channel files — optional context for tribe chat summarisation. Injected on demand ("what's happening in tribe chat?") not automatically.

**Path configurable** via `LOG_BASE_PATH` in log-agent `.env`. Agent validates both subfolders exist at startup and logs a clear error if not found.

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
| SSE broken | Chat stops — no fallback implemented | N/A — Phase 2 item |

---

## Security

Personal use. The app runs on port 8745.

**If accessed only from Markús's local machine (overlay mode):** port stays firewalled, no auth needed.

**If accessed from the in-game browser (which connects from the game client's machine to the VPS):** port must be open. In that case, auth via a shared secret in a request header:

```
X-Server-Token: <secret>
```

Token checked server-side on every request. Stored in a `.env` file, not hardcoded. The Smart Assembly URL does NOT include the token — the frontend JS sends it as a header on API calls.

Note: URL query params (`?token=...`) are avoided because they appear in server logs, browser history, and Referer headers.

---

## Open Items / Phase 2

| Item | Status |
|---|---|
| Log regex verification | In progress — parsers fully unit-tested (56 tests); real-game validation underway |
| SERVER_TOKEN | Pending — `.env` still has placeholder value; set before exposing port 8745 publicly |
| Log agent deployment to Windows | In progress — agent ready; Markús deploying to gaming PC |
| Route engine (Phase 2) | Deferred — players get "navigation charts loading" response until implemented |
| SSE in-game browser compatibility | Untested — needs verification once in-game URL is accessible |

---

## Hackathon Prize Category Targets

| Category | Rationale |
|---|---|
| Live Frontier Integration (primary) | Runs against live game data during judging |
| Creative (secondary) | In-lore ship AI character with personality is novel |
| Utility (stretch) | Situational awareness = practical player tool |
