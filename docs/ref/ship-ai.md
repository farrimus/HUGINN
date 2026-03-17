# Ship AI — Modules Reference

**Last updated:** 2026-03-16 (on-chain asset data — Phase 3: PLAYER STRUCTURE lines)
**What this covers:** Server modules for Ship AI, log agent, route_planned event, end-to-end event flow, test coverage

For the full pipeline narrative (the "why"), see `docs/log-pipeline.md`.
For routing architecture details, see `docs/ref/routing.md`.

---

## `main.py` — FastAPI Entry Point

Binds all modules together. Runs on port 8745.

**Ship AI endpoints:**

| Route | Method | Auth | Purpose |
|-------|--------|------|---------|
| `/health` | GET | No | Returns `{status, systems_indexed}` |
| `/log/ingest` | POST | Bearer JWT | Receives events from log agent (including `route_planned`) |
| `/chat` | POST | Legacy X-Server-Token | Streaming chat; auto-plots route on navigation intent; returns SSE |
| `/debug` | GET | Legacy X-Server-Token | Full pipeline state dump |
| `/logs/stream` | GET | Legacy X-Server-Token | SSE stream of server logs; for debugging |
| `/admin/rebuild-index` | POST | Legacy X-Server-Token | Force rebuild system index from world API |
| `/admin/rebuild-location-index` | POST | Legacy X-Server-Token | Rebuild location index from world API |
| `/data/gate-graph` | GET | Legacy X-Server-Token | Serve legacy `gate_graph.json` (ETag + 304 support) |
| `/data/systems` | GET | Legacy X-Server-Token | Serve `data/systems.json` (ETag + 304 support, FileResponse) |
| `/route` | POST | Legacy X-Server-Token | Compute route (BFS or A* hybrid); store in `current_route` |
| `/route/clear` | POST | Legacy X-Server-Token | Clear active route; sets `current_route = null` |
| `/current-route` | GET | Legacy X-Server-Token | Return `{route, alternative, current_system_temp}` |
| `/route/activate` | POST | Legacy X-Server-Token | Swap `current_route ↔ pending_alternative` |
| `/ship-profile` | GET | Legacy X-Server-Token | Return current ship profile + computed jump range + fuel budget |
| `/ship-profile` | POST | Legacy X-Server-Token | Update stored ship profile (partial updates supported) |
| `/search/radius` | POST | Legacy X-Server-Token | Search for structures within radius of current system |
| `/structures/record` | POST | Legacy X-Server-Token | Record player-owned structures in a system |
| `/structures/locations` | GET | Legacy X-Server-Token | Get cached list of player-owned structures |
| `/structure-debug/chat` | POST | Legacy X-Server-Token | Structure AI debug chat endpoint |
| `/structure-debug/{structure_id}` | GET | Legacy X-Server-Token | Get debug state for a structure |
| `/structure-debug/{structure_id}` | POST | Legacy X-Server-Token | Post debug data to a structure |
| `/auth/challenge` | POST | No | Initiate SUI login challenge (blockchain auth) |
| `/auth/verify` | POST | No | Verify SUI login signature and issue JWT |
| `/auth/deal/offer` | POST | No | Blockchain deal offer endpoint |
| `/auth/deal/claim` | POST | No | Blockchain deal claim endpoint |
| `/structure/{structure_id}` | GET | Structure JWT | Get structure profile (authenticated via JWT) |
| `/structure/{structure_id}` | POST | Structure JWT | Update structure profile |
| `/structure/{structure_id}` | PATCH | Structure JWT | Patch structure profile |
| `/structure-chat` | POST | Structure JWT | Structure AI chat endpoint |
| `/static/*` | GET | No | Serves `index.html`, `debug.html` |

### Authentication Methods

**Bearer JWT (New Method for Log Ingest):**
- Endpoints: `/log/ingest` only
- Requires: `Authorization: Bearer <jwt>` header
- Token acquisition: `POST /auth/token` (pass `{"agent_id": "..."}`)
- Token lifetime: 24 hours
- Implementation: `validate_token()` dependency in FastAPI routes
- Use case: Log agent authentication for secure event ingestion

**Legacy X-Server-Token (Deprecated, Still Widely Used):**
- Endpoints: All other protected endpoints (`/chat`, `/route`, `/ship-profile`, `/admin/rebuild-index`, structure debug endpoints, etc.)
- Requires: `X-Server-Token` header
- Token value: Set via `SERVER_TOKEN` environment variable
- Status: Maintained for backward compatibility; if `SERVER_TOKEN` is not set, endpoints are open access (local-only mode)
- Implementation: `require_token()` dependency in FastAPI routes

**Structure JWT (SUI Blockchain Auth):**
- Endpoints: `/structure/{structure_id}`, `/structure-chat`
- Requires: `Authorization: Bearer <jwt>` header (from `/auth/verify` after blockchain challenge)
- Token acquisition: `POST /auth/challenge` → verify signature with `POST /auth/verify`
- Implementation: `require_structure_jwt()` dependency

**No Authentication Required:**
- Endpoints: `/health`, `/auth/challenge`, `/auth/verify`, `/auth/deal/offer`, `/auth/deal/claim`, `/static/*`

**Note:** Log agent client must use Bearer auth for `/log/ingest`. See `log-agent/auth_flow.py` for implementation.

**Ingest routing logic:**
- `in_progress: True` → `log_buffer.set_live([event])` (heartbeat snapshot)
- Regular event → `log_buffer.add(event)` + `clear_live(session_type)` if session closed
- `system_change` event → background task fires `world_api.get_system(name)` to warm cache
- `route_planned` event → `log_buffer.add(event)` (which also sets `log_buffer.current_route`)

**Chat flow:**
1. Fetch `world_api.get_system(current_system)`
2. `get_player_structures_in_system(current_system)` → list of nearby player-owned structure summaries
3. `build_context_block(system_data, recent_events, current_system, live_sessions, current_route, structure_alerts=log_buffer.pop_structure_alerts(), nearby_structures=_nearby)`
4. `claude.stream(message, history, context_block)` → yield SSE chunks

**`/data/gate-graph` endpoint:**
- Returns `gate_graph.json` as JSON with `ETag` header set to `"built_at"` value
- Supports `If-None-Match` → 304 Not Modified when client already has the latest
- `Cache-Control: public, max-age=3600`
- Returns HTTP 503 if the file hasn't been built yet

### TokenManager and Auth Router Initialization

In main.py lifespan, the following happens:

1. TokenManager is created: `token_manager = TokenManager(key_dir=".keys")`
   - Generates or loads RSA key pair
   - Private key encrypted at rest

2. Auth endpoints are initialized: `init_auth(token_manager)`
   - Binds TokenManager to /auth/token endpoint

3. Auth router is registered: `app.include_router(auth_router)`
   - Makes /auth/token endpoint available

This enables the token acquisition flow:
- Client: POST /auth/token with agent_id → receives JWT
- Client: Store JWT securely (DPAPI on Windows, 0o600 on Unix)
- Client: Include Authorization: Bearer <jwt> in all requests to /log/ingest

See src/token_manager.py and src/endpoints/auth.py for implementation details.

**Lifespan:**
1. Launches `world_api.load_or_build_index()` as a background task (non-blocking)
2. Bootstraps memory store for `STRUCTURE_ID` env var
3. Reads `SSU_OBJECT_ID` env var; loads profile to get `system_id`
4. Calls `start_background_tasks(structure_id, ssu_object_id, system_id)` from `ssu_poller`

---

## `src/log_buffer.py` — Ring Buffer + Live Store

In-memory state. Bridges real-time heartbeat snapshots, finalized summaries, and planned routes.

**Class `LogBuffer`:**

| Field | Type | Updated by |
|-------|------|------------|
| `events` | `deque(maxlen=50)` | `add()` — all events |
| `current_system` | `Optional[str]` | `add()` when `type == "system_change"` |
| `current_route` | `Optional[dict]` | `add()` when `type == "route_planned"` |
| `pending_alternative` | `Optional[dict]` | Set by `route_engine.route()` when warm intermediates found |
| `_live` | `list` | `set_live()` — in-progress heartbeat snapshots |
| `pending_structure_alerts` | `list` | `add_structure_alert()` — urgent alerts from Structure AI |

| Method | Signature | Behavior |
|--------|-----------|----------|
| `add` | `(event: dict)` | Appends to ring buffer. Sets `current_system` on system_change, `current_route` on route_planned. |
| `get_recent` | `(n: int) → list` | Last n events from ring buffer. |
| `set_live` | `(snapshots: list)` | Replaces live list. Stamps each entry with `_ts = time.time()`. |
| `get_live` | `() → list` | Returns entries younger than 120s (LIVE_TTL_S). Evicts stale. |
| `clear_live` | `(session_type: str)` | Removes live entries of that type when real summary arrives. |
| `add_structure_alert` | `(event: dict)` | Appends urgent structure alert. Never evicted by TTL. |
| `pop_structure_alerts` | `() → list` | Returns and clears all pending structure alerts. Called by `/chat` handler. |

**`current_route`** persists until replaced by a new `route_planned` event. Never evicted by TTL.

**Alert bridge:** When the Structure AI detects an urgent alert (shield < 20% or fuel < 10%), it calls `log_buffer.add_structure_alert()`. The next Ship AI `/chat` call pops these and passes them to `build_context_block()` as `STRUCTURE ALERT [name]: message` lines prepended before LOCATION.

**Global singleton:** `log_buffer = LogBuffer(max_size=50)`

---

## `src/context_builder.py` — Context Formatter

Formats pipeline state into a compact text block passed to Claude. Hard cap: **2000 characters**.

**Function:**
```python
def build_context_block(
    system_data: Optional[dict],
    log_events: list,
    current_system: Optional[str],
    live_sessions: Optional[list] = None,
    current_route: Optional[dict] = None,
    structure_alerts: Optional[list] = None,
    ship_profile=None,
    nearby_structures: Optional[list] = None,
) -> str
```

`nearby_structures` — list of dicts from `ssu_poller.get_player_structures_in_system()`, each: `{type_name, status, fuel_pct, services_online, system_name}`.

**Output example (with route + player structure):**
```
LOCATION: UTR-SN4 | security: 0.3 | 2 recent kill(s) in system
PLAYER STRUCTURE: SSU (ONLINE) | fuel:64% | 2 svc
SHIP: Lai | EU-90 x 2400u | range 18 LY | budget 36 LY
ROUTE PLANNED: UTR-SN4 → I.59R.8J2 → Morioka (2 jumps, est 14 min)
MINING (ongoing): Carbonaceous Ore ×847, Hermetite ×312 over 34 min | cargo full ×2
JUMPED TO: UTR-SN4
LOCAL CHAT: zaroot, ikeee active
```

**Output order:**
1. `STRUCTURE ALERT [name]: message` — when `structure_alerts` is non-empty (prepended first)
2. `LOCATION` — always next
3. `PLAYER STRUCTURE: type (STATUS) | fuel:N% | N svc` — capped at 3 structures; omitted if empty
4. `SHIP:` — when `ship_profile` is provided
5. `MINING` / `COMBAT` — most recent session summaries
6. Transition events (jumps, dock, undock, autopilot) — last 5
7. `LOCAL CHAT` — active pilot count
8. `ROUTE PLANNED` — when `current_route` is set

**ROUTE PLANNED format:**
- Path shown as `→`-separated system names
- Jump count and optional estimate from `route_planned.est_time_min`
- `WARNINGS:` appended if `route_planned.warnings` is non-empty
- Persists across all chat turns until replaced by a new route_planned event

**Rules:**
- Live snapshots override buffered summaries (most recent picture wins)
- `(ongoing)` appended when data came from a live heartbeat snapshot
- Transitions capped at last 5 for brevity
- Chat: deduplicates senders, shows count if multiple

---

## `src/claude_client.py` — Claude Streaming Client

**Model:** `claude-sonnet-4-6`

**System prompt identity:** Dry, functional ship computer. No name. Refers to itself as "this unit" or "ship systems." No pleasantries, no filler.

**Two-tier knowledge model (core of the system prompt):**

| Tier | Source | How the companion handles it |
|------|--------|------------------------------|
| **Sensor data** | Client logs, World API, gate graph | Only assert what appears in `[SHIP SENSORS]`. If absent, say so plainly. Never invent. |
| **Lore** | EVE Frontier history, factions, the Collapse, item lore | Fragmentary by CCP's design. Speculate in-character from known fragments. Frame uncertainty authentically: "Records from before the Collapse are incomplete." Never claim to resolve what the universe left deliberately open. |

**Route instructions in system prompt:**
> When a ROUTE appears in [SHIP SENSORS], report it as: "Plotting course: N jumps. [list of systems]." Dry, functional. If no ROUTE is in sensors but the pilot asks for navigation, state that navigation data is not available for that query.

**Key methods:**

| Method | Purpose |
|--------|---------|
| `build_messages(user_message, history, context_block)` | Formats request. Windowed to last 40 history entries. Prepends `[SHIP SENSORS]\n{context}\n\n[PILOT]\n{message}`. |
| `stream(user_message, history, context_block)` | Yields text chunks via `messages.stream()`. |

**Global singleton:** `claude = ClaudeClient()`

---

## `src/world_api.py` — EVE Universe Cache + Gate Graph Builder

**API base (2026-03-15):** Defaults to `utopia` (`https://world-api-utopia.live.tech.evefrontier.com`). Override via `WORLD_API_BASE_URL` env var (highest priority), or set `WORLD_API_ENV=stillness` to switch to the Stillness endpoint.

Priority order: `base_url` constructor param > `WORLD_API_BASE_URL` env var > `WORLD_API_ENV` (default `utopia`).

**Key methods:**

| Method | Purpose |
|--------|---------|
| `load_or_build_index()` | Load from disk; rebuild from API if missing. |
| `rebuild_index(retries=5)` | Paginated fetch of `/v2/solarsystems` (limit=1000). Saves `system_index.json` AND `gate_graph.json` in one pass. |
| `resolve_system_id(name)` | Case-insensitive name → ID lookup. |
| `get_system(system_name)` | Fetch `/v2/solarsystems/{id}` with 30s cache TTL. Returns `None` on failure. |
| `get_killmails(system_id: int) → list` | Fetch recent killmails for a system. Returns `[]` on error. Handles both list and `{"data": [...]}` response shapes. Used by `/structure-chat` to populate `kills_nearby`. |

**System index (`data/system_index.json`):**
```json
{
  "built_at": "2026-03-11T16:31:15Z",
  "count": 24501,
  "index": { "utr-sn4": 1001, "jita": 1002 }
}
```

**Gate graph (`data/gate_graph.json`):**
```json
{
  "built_at": "2026-03-13T10:00:00Z",
  "adj": {
    "utr-sn4": ["i.59r.8j2", "some-neighbor"]
  },
  "meta": {
    "utr-sn4": { "id": 30001001, "security": 0.3, "location": {"x": 1.5e14, "y": -2.1e13, "z": 8.7e13} }
  }
}
```
All keys are **lowercase system names**. `adj` edges are bidirectional.

**Known uncertainty:** Unconfirmed whether the bulk `/v2/solarsystems` endpoint includes `gateLinks`. If `adj` is empty after a rebuild, individual system fetches will be needed. Check with:
```bash
curl -H "X-Server-Token: $TOKEN" http://localhost:8745/data/gate-graph | jq '(.adj | length)'
```

---

## `src/auth.py` — Token Validation

FastAPI `Depends` on `require_token()`. Checks `X-Server-Token` header against env `SERVER_TOKEN`. Returns HTTP 403 on mismatch. If `SERVER_TOKEN` not set → open access (local dev).

---

## Log Agent: File-by-File

### `log-agent/log_agent.py` — File Watcher + Threads

**Startup sequence:**
1. `validate_paths()` — checks Gamelogs/ and Chatlogs/ exist
2. `bootstrap_system(tracker)` — scans tail of most recent `Local_*` chatlog for last known system
3. Start `PeriodicBootstrap` thread — retries bootstrap every 30s until system is known
4. Start `HeartbeatEmitter` thread — snapshots + flushes stale sessions every 30s
5. Start `Observer` (watchdog) watching both log directories
6. Blocking loop; on `KeyboardInterrupt`: flush all sessions, stop threads

**`LogFileHandler(FileSystemEventHandler)`:**
- Tracks per-file position, encoding, and partial line buffer
- `on_modified`: reads new bytes, decodes (UTF-8 for gamelogs, UTF-16 LE/BE for chatlogs), buffers partial lines, calls parser
- `on_created`: resets position to 0

**Encoding fixes implemented:**
- Partial line buffer: holds unterminated trailing fragment across reads
- UTF-16 alignment: odd-byte remainders held between reads
- Truncation detection: if file size < position, reset to 0
- Mtime-based new-file detection: resolves Windows race where `on_created` fires late

**`PeriodicBootstrap`:** Daemon thread. Runs `bootstrap_system()` every 30s until `tracker.current_system` is set.

**`HeartbeatEmitter`:** Daemon thread. Every 30s:
1. `tracker.flush_stale()` — closes timeout-expired sessions → sends summaries
2. `tracker.snapshot()` — returns in-progress snapshots without closing
3. POSTs both to `/log/ingest` with `in_progress: True`

---

### `log-agent/parsers.py` — Line-Level Parsing

Two functions: `parse_gamelog_line(raw)` and `parse_chatlog_line(raw)`. Both return `Optional[dict]` or `None` if the line is noise/discarded.

**Gamelog events produced:**

| Type | Tag | Example trigger |
|------|-----|-----------------|
| `undock` | untagged | `Undocking from X to Y solar system` |
| `combat_out` | (combat) | `136 to Bihepopths - Tier 3 Coilgun (S) - Grazes` |
| `combat_in` | (combat) | `22 from Faulty Scout Drone - Penetrates` |
| `combat_miss` | (combat) | `Your weapon misses TARGET completely` |
| `sightline_blocked` | (combat) | `Sightline of TARGET to you is obscured` |
| `mining` | (mining) | `You mined 24 units of Feldspar Crystals` |
| `autopilot` | (notify) | `Autopilot engaged / disabled` |
| `docking` | (notify) | `Requested to dock` / `docking request has been accepted` |
| `cargo_full` | (notify) | `MODULE has completed operations. Ship's cargo hold is full.` |
| `ship_stopping` | (notify) | `Ship stopping` |
| `gamelog_raw` | misc | Unmatched lines of recognized type |

**Discarded (returns `None`):** `(info)`, `(question)`, `(warning)`, `(hint)`, speed/proximity noise, blank lines.

**Chatlog events produced:**

| Type | Trigger |
|------|---------|
| `system_change` | `Channel changed to Local : SYSTEM_NAME` |
| `chat` | Any other sender > message line |

HTML tags (`<color=...>`, `<font ...>`, `<b>`, etc.) are stripped before pattern matching.

---

### `log-agent/session_tracker.py` — Session Aggregation

**`SessionTracker`** is thread-safe (lock-protected). Absorbs raw events, emits summaries when sessions close.

**`CombatSession`** — timeout: 60s inactivity
- Tracks: damage out/in, enemies (name → hit count), hit qualities, weapons used, misses
- Closes on: system_change, docking, or 60s timeout
- Emits `combat_summary`:
```json
{
  "type": "combat_summary",
  "system": "Ersetu",
  "duration_s": 90,
  "enemies": {"Faulty Scout Drone": 3},
  "damage_out": 1240,
  "damage_in": 280,
  "hits_out": {"Penetrates": 5, "Grazes": 2},
  "hits_in": {"Penetrates": 4},
  "weapons_used": ["Tier 3 Coilgun (S)"],
  "misses_out": 1,
  "misses_in": 0
}
```

**`MiningSession`** — timeout: 120s inactivity
- Tracks: materials (name → units), cargo_full count
- Emits `mining_summary`:
```json
{
  "type": "mining_summary",
  "system": "UTR-SN4",
  "duration_s": 2040,
  "materials": {"Carbonaceous Ore": 847, "Hermetite": 312},
  "total_units": 1159,
  "cargo_fulls": 2
}
```

**`SessionTracker` methods:**

| Method | Returns | Purpose |
|--------|---------|---------|
| `process(event)` | `list[dict]` | Absorb event; return any outputs (summaries + pass-throughs) |
| `flush_stale()` | `list[dict]` | Close timeout-expired sessions; return summaries |
| `flush()` | `list[dict]` | Force-close all sessions (on shutdown) |
| `snapshot()` | `list[dict]` | In-progress snapshots without closing |
| `current_system` | `Optional[str]` | Thread-safe read |

**Pass-through events** (returned immediately, not absorbed): `chat`, `autopilot`, `undock`, `ship_stopping`, `gamelog_raw`, `system_change` (after closing sessions), `docking` (after closing sessions).

---

## `route_planned` Event Type

Posted by the **client-side RouteCalculator** (`log-agent/route_calculator.py`) to `/log/ingest` after computing a route.

```json
{
  "type": "route_planned",
  "path": ["utr-sn4", "i.59r.8j2", "morioka"],
  "jumps": 2,
  "est_time_min": 14,
  "warnings": ["high temp at i.59r.8j2"]
}
```

**Fields:**

| Field | Type | Notes |
|-------|------|-------|
| `path` | `list[str]` | Ordered system names, lowercase, origin to destination inclusive |
| `jumps` | `int` | `len(path) - 1` |
| `est_time_min` | `int \| null` | Optional pilot-provided or formula-derived estimate |
| `warnings` | `list[str]` | Hazards on the route (high temp systems, sec status flags, etc.) |

**Server handling:**
- Routed through normal `log_buffer.add()` (stored in ring buffer for history)
- Additionally sets `log_buffer.current_route = event`
- `current_route` persists until a new `route_planned` event replaces it
- `context_builder.py` injects it as a `ROUTE PLANNED:` line in every Claude prompt

**No server-side route calculation is performed.** The server only stores and relays what the client sends.

---

## End-to-End Event Flow

```
[ 2025.08.28 21:08:29 ] (combat) 136 to Bihepopths - Tier 3 Coilgun (S) - Grazes
  ↓ parse_gamelog_line
{"type": "combat_out", "damage": 136, "target": "Bihepopths", "weapon": "Tier 3 Coilgun (S)", "hit": "Grazes"}
  ↓ tracker.process
CombatSession absorbs event → output: []    (no POST yet)

[ 2025.08.29 15:00:00 ] Keeper > Channel changed to Local : UTR-SN4
  ↓ parse_chatlog_line
{"type": "system_change", "system": "UTR-SN4", "sender": "Keeper"}
  ↓ tracker.process
CombatSession closes → emits combat_summary
tracker.current_system = "UTR-SN4"
output: [combat_summary, system_change]
  ↓ send_event (POST /log/ingest × 2)

Server:
  combat_summary → log_buffer.add()
  system_change  → log_buffer.add() + update current_system
                 + background: world_api.get_system("UTR-SN4")

Meanwhile — RouteCalculator computes a route:
  POST /log/ingest {"type": "route_planned", "path": ["UTR-SN4", "I.59R.8J2", "Morioka"], "jumps": 2, ...}
  → log_buffer.add() + log_buffer.current_route = event

Meanwhile — HeartbeatEmitter fires every 30s:
  tracker.flush_stale() → summaries for timed-out sessions
  tracker.snapshot()    → in_progress snapshots of open sessions
  Both POSTed with in_progress: True → log_buffer.set_live()

Chat request: POST /chat {"message": "What's the situation?", "history": [...]}
  system_data   = await world_api.get_system("UTR-SN4")       # from cache
  context       = build_context_block(system_data, recent_events, "UTR-SN4", live_sessions, current_route)
  # context = "LOCATION: UTR-SN4 | security: 0.3\nROUTE PLANNED: UTR-SN4 → I.59R.8J2 → Morioka (2 jumps)\n..."

  for chunk in claude.stream(message, history, context):
      yield f"data: {json.dumps({'text': chunk})}\n\n"
  yield "data: [DONE]\n\n"

  → index.html SSE listener renders chunks to terminal UI
  → overlay.dll WinHTTP SSE client streams chunks to companion panel inside EVE Frontier
```

---

## Test Coverage (Ship AI)

| File | Count | What it covers |
|------|-------|----------------|
| `log-agent/tests/test_parsers.py` | 31 | All event types, edge cases, HTML stripping, discarded lines |
| `log-agent/tests/test_session_tracker.py` | 25 | Absorption, timeouts, flush, snapshot, pass-throughs |
| `tests/test_log_buffer.py` | 9 | Ring buffer cap, FIFO, system tracking, live store TTL |
| `tests/test_context_builder.py` | 33 | All context lines, live override, 2000-char cap, transitions cap, route planned, ship profile, PLAYER STRUCTURE lines (present/absent/capped/fuel+svc) |
| `tests/test_claude_client.py` | 6 | System prompt, message windowing, context prepend |
| `tests/test_world_api.py` | 16 | Pagination, case-insensitive lookup, caching, TTL, error handling, `get_killmails` |
| `tests/test_auth.py` | 4 | Valid/missing/wrong token; no-token dev mode |
| `tests/test_main.py` | 1 | Health endpoint |
| `tests/test_integration.py` | 2 | system_change triggers world_api warm; others do not |
| `tests/test_route_engine.py` | 6 | A* correctness, alternative route, hot-system detection |
| `tests/test_ef_map_comparison.py` | — | Golden dataset vs ef-map.com (1 confirmed: UR8-K7K=36.9°) |
| `tests/test_ship_profile.py` | 9 | SHIPS table, range/budget formulas, cargo, adaptive, red zone |

### Token Authentication Tests

New test files added for token auth:

- `tests/test_token_manager.py` — TokenManager JWT generation/validation
  - Test: RSA key generation and persistence
  - Test: JWT token issuance and expiration
  - Test: Token validation with signature verification

- `tests/test_auth_endpoints.py` — /auth/token endpoint
  - Test: Token issuance with valid agent_id
  - Test: Token validation on protected endpoints
  - Test: 401 response for invalid/missing tokens
  - Test: Malformed header handling

- `tests/test_integration_auth.py` — End-to-end token flow
  - Test: Full flow (request token → use token → access protected endpoint)
  - Test: JWT structure and expiration
  - Test: Error handling for invalid tokens

**Run all server tests:**
```bash
cd /opt/eve-frontier
.venv/bin/pytest tests/ -q
```

**Run token auth tests only:**
```bash
pytest tests/test_*auth*.py -v
```

**Note:** `test_context_builder.py` now covers route planned, ship profile, and PLAYER STRUCTURE lines.
