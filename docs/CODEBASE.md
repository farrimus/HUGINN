# EVE Frontier Companion — Codebase Index

**Hackathon deadline:** March 31, 2026.
**Last updated:** 2026-03-16 (structure-debug dev console)

This file is the entry point. It contains the architecture diagram, status table, and directory tree. Detailed reference is in `docs/ref/`.

---

## Architecture Overview

```
Gaming PC (Windows)                                    Server (Linux VPS, port 8745)
───────────────────                                    ─────────────────────────────
Gamelogs/ + Chatlogs/ (EVE Frontier client)
  │
  ↓ watchdog file watcher
log_agent.py
  ├── parsers.py              (line → event dict)
  ├── session_tracker.py      (event → summary)
  ├── PeriodicBootstrap       (retries system detection on startup)
  └── HeartbeatEmitter        (30s snapshots of open sessions)
        │
        ↓ HTTP POST /log/ingest (events + route_planned)
                                                       main.py (FastAPI)
                                                         ├── log_buffer.py      (ring buffer + live store + current_route)
                                                         ├── context_builder.py (formats context for Claude)
                                                         ├── claude_client.py   (streaming Claude API)
                                                         ├── world_api.py       (EVE universe data + gate graph builder)
                                                         └── auth.py            (token validation)
                                                               │
                                                               ↓ SSE stream (text/event-stream)
                                                         static/index.html      (in-game browser UI, Chromium 122)
                                                         overlay.dll            (DX12 overlay companion panel)

                                                       ├── structure_auth.py   (nonce store, Sui ed25519 sig verify, JWT)
                                                       ├── nova_client.py      (Sui JSON-RPC, AccessRegistry tier resolve)
                                                       ├── structure_profile.py(per-structure JSON profiles)
                                                       ├── structure_client.py (Structure AI Claude streaming + LobbyClient)
                                                       ├── galaxy_db.py        (SQLite wrapper for eve_universe.db)
                                                       ├── memory_store.py     (file-backed event log + pilot profiles)
                                                       ├── ssu_poller.py       (async background tasks: SSU state, killmails, Sui events, turrets, inventory, player structures)
                                                       ├── type_names.py       (type_id → name resolver, loaded from data/type_names_all.json)
                                                       └── ssu_poller.py       (inventory + player structures via Sui dynamic fields RPC)
                                                               ↑ JWT auth (Sui wallet, EVEVault)
                                                         static/structure.html  (SSU in-game browser UI)
                                                         SSU Browser (EVE Frontier Smart Storage Unit)

Structure AI → urgent alerts → log_buffer.pending_structure_alerts → Ship AI context (STRUCTURE ALERT lines)

[PLANNED — client side, runs on gaming PC]
RouteCalculator (Python, Windows)
  ├── Downloads data/systems.json from GET /data/systems (once, ETag-cached, ~7 MB)
  ├── Runs A* hybrid router locally (gate hops free, direct jumps cost fuel)
  └── POSTs route_planned event to /log/ingest → context_builder picks it up

[DEV/DEBUG — server side, not for production use]
POST /route → route_engine.py A* (CPU cost on VPS — avoid under load)
/chat intent detection → same, for verbal route queries only
```

---

## Status — 2026-03-17

| Component | Status |
|---|---|
| Server (FastAPI, VPS) | ✓ Running on port 8745 |
| Log agent (Windows PC) | ✓ Deployed, watching Gamelogs/ + Chatlogs/ |
| `static/index.html` | ✓ Updated — Tailwind + clamp() + ResizeObserver + SSE reconnect |
| DX12 overlay | ✓ Working — injected into EVE Frontier, ImGui running in-game |
| Companion panel (chat UI in overlay) | ✓ Working — streaming chat confirmed end-to-end with Claude |
| Universe data (`data/systems.json`) | ✓ Built from ResFiles — 24,426 systems, x/y/z, gate links, star types, safe_jump_temp |
| Gate data (`data/gates.json`) | ✓ 3,438 unique gate pairs, 231 disconnected clusters (max 39 systems each) |
| Route engine (server-side) | ✓ Heat-aware A* hybrid; alternative route when hot intermediates (≥70°); LY spatial index |
| Ship profile (`GET/POST /ship-profile`) | ✓ 13-ship SHIPS table; ship_type, extra_cargo_kg; LY range + fuel budget formulas |
| `/route/activate` | ✓ Swaps current_route ↔ pending_alternative atomically |
| Chat `/route` command | ✓ A* route; alternative route stored in pending_alternative; per-hop breakdown |
| Chat `/profile` command | ✓ `/profile ship|fuel|level|cargo` subcommands with validation |
| Context block SHIP line | ✓ `SHIP: <type> | <fuel> | range <X> LY | budget <Y> LY` appended to context |
| Overlay route panel | ✓ Two-route display (primary + alternative) with USE buttons → POST /route/activate |
| Overlay ship profile panel (F7) | ✓ 5 inputs (ship, fuel, units, adaptive, cargo), computed range + budget, SAVE button |
| Structure AI backend | ✓ Built — auth, tier resolution, profile, Claude streaming, alert bridge |
| Structure auth endpoints (`/auth/challenge`, `/auth/verify`) | ✓ Working — zkLogin (0x05) passthrough, registry ID server-configured |
| `static/structure.html` | ✓ Built — amber terminal UI, auth gate, info panel, SSE chat |
| `static/structure-debug.html` | ✓ Built — amber dev console: live logs, profile editor, structure AI chat, pipeline + alert panels |
| `/structure-debug/{id}` GET/POST, `/structure-debug/chat` | ✓ Token-gated dev endpoints (no JWT); profile read/write/create, OWNER-tier AI stream |
| `/debug` `pending_structure_alerts` field | ✓ Non-destructive peek at pending structure alerts added to `/debug` response |
| Move contract (`AccessRegistry`) | ✓ Deployed to Sui testnet — package `0xf335...55b9` |
| AccessRegistry `keep-7a` (owner `0x442f`) | ✓ Object `0x89e9...dc0` |
| AccessRegistry `keep-7a` (owner `0xff09`) | ✓ Object `0xf5ce...708` |
| EVEVault wallet injection in SSU browser | ✓ Working — Chrome + SSU browser confirmed, URL truncation fix applied |
| `src/galaxy_db.py` | ✓ SQLite wrapper for `eve_universe.db` (24k systems, 83k+ planets, moons, stations, Lagrange points) |
| `src/memory_store.py` | ✓ File-backed event log (`events.jsonl`) + pilot profiles per structure |
| `src/ssu_poller.py` | ✓ Background tasks: SSU state (60s), killmails (5min), Sui events (60s), turrets (60s), connected assembly resolution (60s), SSU inventory (5min), player structures (2min) |
| `src/type_names.py` | ✓ Type ID → name resolver — loaded once from `data/type_names_all.json` at import |
| `src/ssu_poller.py` — inventory + player structures | ✓ Now on Sui dynamic fields RPC (`suix_getDynamicFields` + `sui_getObject`). No gateway needed. |
| Context enrichment | ✓ STAR/PLANETS/LAGRANGE from galaxy_db, GATES from gate_graph, `[STRUCTURE MEMORY]` block, ASSEMBLIES + INVENTORY (Structure AI), PLAYER STRUCTURE (Ship AI) |
| VETTED routing → LobbyClient | ✓ VETTED tier gets restricted lobby Claude (no internal structure data) |
| Pilot profiles | ✓ Every auth creates/updates pilot profile in `data/memory/{id}/pilots/` |
| Auth backfill | ✓ On auth, existing profiles with missing `system_id`/`region_name` are resolved via galaxy_db |
| `build_types.py` | ✓ One-shot script: fetches `/v2/types` from World API → `data/type_names_all.json` |
| Ship stat auto-extraction | Future — manual input via F7 panel for now |
| Client-side RouteCalculator (`log-agent/route_calculator.py`) | ✓ Built — BFS, ETag-cached `systems.json` download, warnings + highlights, wired into log agent |
| Radius search calculator | ✓ Server + client, filtering by planets/killmails/heat/structures |

---

## Directory Tree

```
/opt/eve-frontier/
├── main.py                         # FastAPI server entry point
├── requirements.txt                # Server dependencies
├── pytest.ini                      # asyncio_mode=auto
├── .env / .env.example             # Server environment config
├── start.sh                        # Server startup script
├── build_universe.py               # ResFiles → systems.json + gates.json
├── build_types.py                  # One-shot: World API /v2/types → data/type_names_all.json
│
├── src/
│   ├── __init__.py
│   ├── endpoints/                  # Authorization endpoints
│   │   ├── __init__.py
│   │   └── auth.py                 # Token auth endpoints (/auth/token, /auth/verify)
│   ├── auth.py                     # X-Server-Token header validation
│   ├── token_manager.py            # JWT generation/validation, key management
│   ├── location_index.py           # Location indexing for context enrichment
│   ├── radius_search.py            # Radius search: planets, killmails, heat, structures
│   ├── deal_store.py               # Deal/contract persistence
│   ├── log_buffer.py               # Ring buffer + live session store + current_route
│   ├── context_builder.py          # Formats context block for Claude (2000 char cap)
│   ├── claude_client.py            # Claude API streaming client
│   ├── world_api.py                # EVE World API client + system index builder; utopia default
│   ├── route_engine.py             # BFS (gate-only) + A* hybrid router + spatial index
│   ├── ship_profile.py             # ShipProfile dataclass + persistence + fuel formulas
│   ├── structure_auth.py           # NonceStore, Sui ed25519 sig verify, JWT issue/decode, character lookup
│   ├── nova_client.py              # Sui JSON-RPC client, AccessRegistry, tier resolver, _rpc() helper
│   ├── structure_profile.py        # StructureProfile dataclass + tier-filtered view + persistence
│   ├── structure_client.py         # Structure AI Claude streaming + LobbyClient (VETTED) + enriched context
│   ├── galaxy_db.py                # Read-only SQLite wrapper for eve_universe.db; module-level singleton
│   ├── memory_store.py             # File-backed event log + pilot profiles per structure
│   ├── ssu_poller.py               # Async background tasks: SSU state, killmails, Sui events, turrets, assembly resolution, inventory, player structures
│   └── type_names.py               # Type ID → name resolver; loaded once from data/type_names_all.json
│
├── log-agent/                      # Runs on Windows gaming PC
│   ├── __init__.py
│   ├── log_agent.py                # File watcher + bootstrap + heartbeat loop
│   ├── parsers.py                  # Line-level log parsing → structured event dicts
│   ├── session_tracker.py          # Stateful session aggregation (combat / mining)
│   ├── route_calculator.py         # Client-side BFS router; ETag-cached systems.json; POSTs route_planned
│   ├── dpapi_wrapper.py            # Windows DPAPI token encryption wrapper
│   ├── ship_ai_client.py           # Ship AI HTTP client + streaming response handler
│   ├── auth_flow.py                # Client-side token acquisition flow
│   ├── token_store.py              # Secure token storage (DPAPI-backed)
│   ├── radius_calculator.py        # Client-side radius search calculator
│   ├── conftest.py                 # pytest config for log-agent subtree
│   ├── requirements.txt            # Client dependencies
│   ├── .env.example                # Template for Windows agent config
│   ├── analyze_logs.py             # Diagnostic: catalog gamelog structure
│   ├── diagnose.py                 # Diagnostic: chatlog encoding debugger
│   └── tests/
│       ├── test_parsers.py         # 31 tests — parsing correctness
│       ├── test_session_tracker.py # 25 tests — session aggregation + timeouts
│       ├── test_auth_flow.py       # Auth flow integration tests
│       ├── test_token_store.py     # Token storage + DPAPI tests
│       └── test_radius_calculator.py # Radius search computation tests
│
├── tests/                          # Server-side tests
│   ├── test_main.py                # Health + endpoint coverage
│   ├── test_log_buffer.py          # Ring buffer + live store
│   ├── test_context_builder.py     # Context formatting (all event types + SHIP profile line)
│   ├── test_claude_client.py       # Message building + windowing
│   ├── test_world_api.py           # 16 tests — index, caching, lookups, get_killmails
│   ├── test_auth.py                # Token accept/reject
│   ├── test_integration.py         # system_change triggers world_api warm
│   ├── test_structure_auth.py      # 9 tests — nonce lifecycle, Sui sig verification, JWT
│   ├── test_nova_client.py         # 6 tests — AccessRegistry fetch + tier resolution
│   ├── test_structure_profile.py   # Profile CRUD, tier filtering, path traversal, region_name/system_id fields
│   ├── test_structure_client.py    # 24 tests — enriched context, alert detection, LobbyClient, ASSEMBLIES/INVENTORY lines
│   ├── test_type_names.py          # 4 tests — known IDs, string key, unknown, None
│   ├── test_galaxy_db.py           # 15 tests — real DB data (system, region, planet, celestials, jumps)
│   ├── test_memory_store.py        # 12 tests — event append, search, summary, pilot profiles
│   ├── test_main_auth.py           # auth_verify backfill + pilot upsert integration test
│   ├── test_ship_profile.py        # 9 tests — SHIPS table, range/budget formulas, cargo, adaptive, red zone
│   ├── test_route_engine.py        # 6 tests — A* correctness, alternative route, hot-system detection
│   ├── test_ef_map_comparison.py   # Golden dataset framework vs ef-map.com
│   └── test_ssu_poller.py          # 20 tests — two-hop fuel, services, connected_assembly_ids, poll_connected_assemblies, inventory dynamic fields, poll_player_structure
│
├── static/
│   ├── index.html                  # In-game browser chat UI (Tailwind, SSE, auto-reconnect)
│   ├── structure.html              # SSU browser Structure AI chat UI (amber terminal, wallet auth, SSE chat)
│   ├── structure-debug.html        # Structure AI dev console (amber, token-auth: logs, profile editor, AI chat, alerts)
│   └── debug.html                  # Ship AI dev console (three-column: logs, nav computer, pipeline state)
│
├── data/
│   ├── system_index.json           # 24,501 systems: name (lowercase) → system_id (from world API)
│   ├── systems.json                # 24,426 systems: full data from ResFiles (x/y/z, gates, star type, safe_jump_temp)
│   ├── gates.json                  # 3,438 unique undirected gate pairs
│   ├── starmapcache.json           # Raw ResFiles dump (source for systems.json — not served)
│   ├── type_names_all.json         # Type ID → name map (loaded at import for name resolution)
│   ├── eve_universe.db             # SQLite DB: Regions, Constellations, SolarSystems, Planets, Moons, Stations, Lagrange, Jumps, Types
│   ├── ship_profile.json           # [generated] Persisted ship profile
│   ├── gate_graph.json             # Legacy — world API gate data (empty gateLinks, superseded by systems.json)
│   ├── structures/                 # [generated] Per-structure JSON profiles
│   └── memory/                     # [generated] Per-structure memory (events.jsonl, summary.json, pilots/)
│
├── scripts/
│   └── check_temps.py              # CLI tool: print safe_jump_temp + jump ranges for named systems
│
├── move/
│   └── access_registry/            # Sui Move package — deployed to testnet
│
└── docs/
    ├── CODEBASE.md                 # This file — index only
    ├── log-pipeline.md             # Pipeline design doc — canonical narrative (why + how)
    ├── ref/
    │   ├── ship-ai.md              # Ship AI server modules + log agent + event flow + test coverage
    │   ├── structure-ai.md         # Structure AI modules + Sui deployment + auth endpoints
    │   ├── structure-debug.md      # Structure AI dev console — endpoints, UI layout, /debug field
    │   ├── routing.md              # Routing architecture — algorithm, data structures, response format
    │   ├── overlay.md              # DX12 overlay C++ modules
    │   ├── ui.md                   # index.html + debug.html + in-game browser environment
    │   └── ops.md                  # Configuration, running, diagnostics, known gaps, lore reference
    ├── future-features/
    │   └── blend-routing.md        # Deferred: compare+blend time-optimized routing design
    └── superpowers/
        ├── plans/                  # Implementation plans (completed)
        └── specs/                  # Design specs
```

---

## Quick Reference

| What you need | Where to look |
|---------------|---------------|
| Ship AI pipeline details (modules, event flow, tests) | `docs/ref/ship-ai.md` |
| Pipeline narrative + design rationale | `docs/log-pipeline.md` |
| Structure AI + Sui auth + blockchain | `docs/ref/structure-ai.md` |
| Structure AI dev console (token-gated endpoints + UI) | `docs/ref/structure-debug.md` |
| Routing algorithm, heat formula, ship profile, response format | `docs/ref/routing.md` |
| Radius search (planets, killmails, heat, structures) | `docs/ref/radius-search.md` |
| DX12 overlay C++ modules | `docs/ref/overlay.md` |
| index.html, debug.html, in-game browser env | `docs/ref/ui.md` |
| Config, ops commands, known gaps, lore reference | `docs/ref/ops.md` |
| Blend routing (deferred feature design) | `docs/future-features/blend-routing.md` |
| System temp cross-check vs ef-map.com | `scripts/check_temps.py` |
| SQLite schema reference for `eve_universe.db` | `data/PROGRAMMER_GUIDE.md` |
| Nav computer design spec | `docs/superpowers/specs/2026-03-15-nav-computer-design.md` |
| Structure AI design spec | `docs/superpowers/specs/2026-03-13-structure-ai-design.md` |
| Context enrichment data catalog | `docs/superpowers/plans/2026-03-14-context-enrichment.md` |
| Log agent test examples | `log-agent/tests/` |
| Context block output format examples | `tests/test_context_builder.py` |
| Galaxy DB query patterns | `tests/test_galaxy_db.py` |
| Memory store usage | `tests/test_memory_store.py` |

---

## Token Authentication (Phase 1)

### Architecture
- Server issues RS256-signed JWT tokens (24-hour lifetime)
- Log-agent stores token securely and includes in Authorization headers
- Stateless validation (server validates signature only, no state needed)

### Files
- `src/token_manager.py` — JWT generation/validation, key management
- `src/endpoints/auth.py` — `/auth/token` endpoint
- `src/endpoints/auth.py` — Token validation decorator (validate_token)
- `log-agent/src/auth_flow.py` — Client-side token acquisition
- `log-agent/src/token_store.py` — Secure token storage

### Configuration
- `config/token_config.json` — Token settings (lifetime, algorithm, key directory)

### Next Phases
- Phase 2: Refresh tokens + revocation list
- Phase 3: Device approval UI for initial token issuance
