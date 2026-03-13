# EVE Frontier Ship AI + Structure AI Companion — Codebase Reference

**Purpose:** Onboarding document for developers and LLMs. Covers every file, how they connect, and the full event flow from game client to Claude response.

**Hackathon deadline:** March 31, 2026.

**Last updated:** 2026-03-13 (Structure AI backend complete)

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
                                                       └── structure_client.py (Structure AI Claude streaming)
                                                               ↑ JWT auth (Sui wallet, EVEVault)
                                                         static/structure.html  (SSU in-game browser UI — pending)
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

## Status — 2026-03-13

| Component | Status |
|---|---|
| Server (FastAPI, VPS) | ✓ Running on port 8745 |
| Log agent (Windows PC) | ✓ Deployed, watching Gamelogs/ + Chatlogs/ |
| `static/index.html` | ✓ Updated — Tailwind + clamp() + ResizeObserver + SSE reconnect |
| DX12 overlay | ✓ Working — injected into EVE Frontier, ImGui running in-game |
| Companion panel (chat UI in overlay) | ✓ Working — streaming chat confirmed end-to-end with Claude |
| Universe data (`data/systems.json`) | ✓ Built from ResFiles — 24,426 systems, x/y/z, gate links, star types |
| Gate data (`data/gates.json`) | ✓ 3,438 unique gate pairs, 231 disconnected clusters (max 39 systems each) |
| Route engine (server-side) | ✓ BFS (gate-only) + A* hybrid (gate + direct jump with ship params) |
| Ship profile (`GET/POST /ship-profile`) | ✓ Persistent profile + per-request overrides for hypothetical routes |
| Chat intent → auto-route | ✓ Navigation phrases in chat trigger route calculation before Claude responds |
| Structure AI backend | ✓ Built — auth, tier resolution, profile, Claude streaming, alert bridge |
| Structure auth endpoints (`/auth/challenge`, `/auth/verify`) | ✓ Built — Sui ed25519 + JWT |
| `static/structure.html` | Pending — SSU browser frontend deferred |
| Ship stat auto-extraction | Future — manual input required for now (see Future Thinking below) |
| ImGui navigation panel | Planned — pending ship params UX decision |

---

## Directory Tree

```
/opt/eve-frontier/
├── main.py                         # FastAPI server entry point
├── requirements.txt                # Server dependencies
├── pytest.ini                      # asyncio_mode=auto
├── .env / .env.example             # Server environment config
├── start.sh                        # Server startup script
│
├── src/
│   ├── __init__.py
│   ├── log_buffer.py               # Ring buffer + live session store + current_route
│   ├── context_builder.py          # Formats context block for Claude (2000 char cap)
│   ├── claude_client.py            # Claude API streaming client
│   ├── world_api.py                # EVE World API client + system index builder
│   ├── route_engine.py             # BFS (gate-only) + A* hybrid router + spatial index
│   ├── ship_profile.py             # ShipProfile dataclass + persistence + fuel formulas
│   ├── auth.py                     # X-Server-Token header validation
│   ├── structure_auth.py           # NonceStore, Sui ed25519 sig verify, JWT issue/decode, character lookup
│   ├── nova_client.py              # Sui JSON-RPC client, AccessRegistry, tier resolver
│   ├── structure_profile.py        # StructureProfile dataclass + tier-filtered view + persistence
│   └── structure_client.py         # Structure AI Claude streaming client + context builder + alert detection
│
├── log-agent/                      # Runs on Windows gaming PC
│   ├── log_agent.py                # File watcher + bootstrap + heartbeat loop
│   ├── parsers.py                  # Line-level log parsing → structured event dicts
│   ├── session_tracker.py          # Stateful session aggregation (combat / mining)
│   ├── conftest.py                 # pytest config for log-agent subtree
│   ├── requirements.txt            # Client dependencies
│   ├── .env.example                # Template for Windows agent config
│   ├── analyze_logs.py             # Diagnostic: catalog gamelog structure
│   ├── diagnose.py                 # Diagnostic: chatlog encoding debugger
│   └── tests/
│       ├── test_parsers.py         # 31 tests — parsing correctness
│       └── test_session_tracker.py # 25 tests — session aggregation + timeouts
│
├── tests/                          # Server-side tests
│   ├── test_main.py                # Health endpoint
│   ├── test_log_buffer.py          # Ring buffer + live store
│   ├── test_context_builder.py     # Context formatting (all event types)
│   ├── test_claude_client.py       # Message building + windowing
│   ├── test_world_api.py           # Index, caching, lookups
│   ├── test_auth.py                # Token accept/reject
│   ├── test_integration.py        # system_change triggers world_api warm
│   ├── test_structure_auth.py      # 9 tests — nonce lifecycle, Sui sig verification, JWT
│   ├── test_nova_client.py         # 6 tests — AccessRegistry fetch + tier resolution
│   ├── test_structure_profile.py   # 7 tests — profile CRUD, tier filtering, path traversal guard
│   └── test_structure_client.py    # 9 tests — context building, alert detection, stream messages
│
├── static/
│   ├── index.html                  # In-game browser chat UI (Tailwind, SSE, auto-reconnect)
│   └── structure.html              # [PENDING] SSU browser Structure AI chat UI
│
├── data/
│   ├── system_index.json           # 24,501 systems: name (lowercase) → system_id (from world API)
│   ├── systems.json                # 24,426 systems: full data from ResFiles (x/y/z, gates, star type)
│   ├── gates.json                  # 3,438 unique undirected gate pairs
│   ├── starmapcache.json           # Raw ResFiles dump (source for systems.json — not served)
│   ├── type_names_all.json         # Type ID → name map (source for star type names — not served)
│   ├── ship_profile.json           # [generated] Persisted ship profile (created on first POST /ship-profile)
│   ├── gate_graph.json             # Legacy — world API gate data (empty gateLinks, superseded by systems.json)
│   └── structures/                 # [generated] Per-structure JSON profiles (created on first OWNER auth)
│       └── {structure_id}.json
│
└── docs/
    ├── CODEBASE.md                 # This file
    ├── log-pipeline.md             # Canonical design doc — pipeline architecture
    └── superpowers/
        ├── plans/
        │   ├── 2026-03-11-ship-ai-companion.md
        │   └── 2026-03-13-structure-ai.md
        └── specs/
            ├── 2026-03-11-ship-ai-companion-design.md
            ├── 2026-03-11-blockchain-research.md
            └── 2026-03-13-structure-ai-design.md
```

---

## Server: File-by-File

### `main.py` — FastAPI Entry Point

Binds all modules together. Runs on port 8745.

**Endpoints:**

| Route | Method | Auth | Purpose |
|-------|--------|------|---------|
| `/health` | GET | No | Returns `{status, systems_indexed}` |
| `/log/ingest` | POST | Token | Receives events from log agent (including `route_planned`) |
| `/chat` | POST | Token | Streaming chat; auto-plots route on navigation intent; returns SSE |
| `/debug` | GET | Token | Full pipeline state dump |
| `/admin/rebuild-index` | POST | Token | Force rebuild system index from world API |
| `/data/gate-graph` | GET | Token | Serve legacy `gate_graph.json` (ETag + 304 support) |
| `/route` | POST | Token | Compute route (BFS or A* hybrid); store in `current_route` |
| `/ship-profile` | GET | Token | Return current ship profile + computed jump range + fuel budget |
| `/ship-profile` | POST | Token | Update stored ship profile (partial updates supported) |
| `/static/*` | GET | No | Serves `index.html` |
| `/auth/challenge` | POST | None | Issue nonce for wallet signing. Returns `{nonce, structure_id, expires_in_seconds: 300}` |
| `/auth/verify` | POST | None | Consume nonce, verify Sui ed25519 sig, resolve tier from Nova AccessRegistry, return JWT |
| `/structure/{id}` | GET | JWT (≥VETTED) | Return tier-filtered structure profile |
| `/structure/{id}` | POST | JWT (OWNER) | Update structure profile fields |
| `/structure-chat` | POST | JWT (≥VETTED) | Structure AI streaming chat (SSE). Detects alerts, routes urgent to log_buffer, streams Claude response |

**`require_structure_jwt()` dependency:** Validates `Authorization: Bearer <jwt>` header. Decodes with `structure_auth.decode_jwt()`. Returns payload dict `{structure_id, address, tier, character_id, character_name}`. Used by all `/auth/verify`-issued JWT-protected structure endpoints.

**Ingest routing logic:**
- `in_progress: True` → `log_buffer.set_live([event])` (heartbeat snapshot)
- Regular event → `log_buffer.add(event)` + `clear_live(session_type)` if session closed
- `system_change` event → background task fires `world_api.get_system(name)` to warm cache
- `route_planned` event → `log_buffer.add(event)` (which also sets `log_buffer.current_route`)

**Chat flow:**
1. Fetch `world_api.get_system(current_system)`
2. `build_context_block(system_data, recent_events, current_system, live_sessions, current_route, structure_alerts=log_buffer.pop_structure_alerts())`
3. `claude.stream(message, history, context_block)` → yield SSE chunks

**`/data/gate-graph` endpoint:**
- Returns `gate_graph.json` as JSON with `ETag` header set to `"built_at"` value
- Supports `If-None-Match` → 304 Not Modified when client already has the latest
- `Cache-Control: public, max-age=3600`
- Returns HTTP 503 if the file hasn't been built yet (trigger rebuild first)

**Lifespan:** On startup, launches `world_api.load_or_build_index()` as a background task (non-blocking).

---

### `src/log_buffer.py` — Ring Buffer + Live Store

In-memory state. Bridges real-time heartbeat snapshots, finalized summaries, and planned routes.

**Class `LogBuffer`:**

| Field | Type | Updated by |
|-------|------|------------|
| `events` | `deque(maxlen=50)` | `add()` — all events |
| `current_system` | `Optional[str]` | `add()` when `type == "system_change"` |
| `current_route` | `Optional[dict]` | `add()` when `type == "route_planned"` |
| `_live` | `list` | `set_live()` — in-progress heartbeat snapshots |
| `pending_structure_alerts` | `list` | `add_structure_alert()` — urgent alerts from Structure AI |

| Method | Signature | Behavior |
|--------|-----------|----------|
| `add` | `(event: dict)` | Appends to ring buffer. Sets `current_system` on system_change, `current_route` on route_planned. |
| `get_recent` | `(n: int) → list` | Last n events from ring buffer. |
| `set_live` | `(snapshots: list)` | Replaces live list. Stamps each entry with `_ts = time.time()`. |
| `get_live` | `() → list` | Returns entries younger than 120s (LIVE_TTL_S). Evicts stale. |
| `clear_live` | `(session_type: str)` | Removes live entries of that type when real summary arrives. |
| `add_structure_alert` | `(event: dict)` | Appends urgent structure alert to `pending_structure_alerts`. Never evicted by TTL. |
| `pop_structure_alerts` | `() → list` | Returns and clears all pending structure alerts. Called by Ship AI `/chat` handler. |

**`current_route`** persists until replaced by a new `route_planned` event. It is never evicted by TTL — the last planned route is always available to the context builder.

**Alert bridge:** When the Structure AI (`/structure-chat`) detects an urgent alert (shield < 20% or fuel < 10%), it calls `log_buffer.add_structure_alert()`. The next Ship AI `/chat` call pops these via `log_buffer.pop_structure_alerts()` and passes them to `build_context_block()` as `STRUCTURE ALERT [name]: message` lines prepended before LOCATION.

**Global singleton:**
```python
log_buffer = LogBuffer(max_size=50)
```

---

### `src/context_builder.py` — Context Formatter

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
) -> str
```

**Output example (with route planned):**
```
LOCATION: UTR-SN4 | security: 0.3 | 2 recent kill(s) in system
ROUTE PLANNED: UTR-SN4 → I.59R.8J2 → Morioka (2 jumps, est 14 min) | WARNINGS: high temp at I.59R.8J2
MINING (ongoing): Carbonaceous Ore ×847, Hermetite ×312 over 34 min | cargo full ×2
JUMPED TO: UTR-SN4
LOCAL CHAT: zaroot, ikeee active
```

**Output order:**
1. `STRUCTURE ALERT [name]: message` — when `structure_alerts` is non-empty (prepended before everything for visibility)
2. `LOCATION` — always next
3. `ROUTE PLANNED` — when `current_route` is set (from RouteCalculator → route_planned event)
4. `MINING` / `COMBAT` — most recent session summaries
5. Transition events (jumps, dock, undock, autopilot) — last 5
6. `LOCAL CHAT` — active pilot count

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

### `src/claude_client.py` — Claude Streaming Client

**Model:** `claude-sonnet-4-6`

**System prompt identity:** Dry, functional ship computer. No name. Refers to itself as "this unit" or "ship systems." No pleasantries, no filler.

**Two-tier knowledge model (core of the system prompt):**

The system prompt explicitly distinguishes two types of knowledge and instructs Claude to handle them differently:

| Tier | Source | How the companion handles it |
|------|--------|------------------------------|
| **Sensor data** | Client logs, World API, gate graph | Only assert what appears in `[SHIP SENSORS]`. If absent, say so plainly. Never invent. |
| **Lore** | EVE Frontier history, factions, the Collapse, item lore | Fragmentary by CCP's design. Speculate in-character from known fragments. Frame uncertainty authentically: "Records from before the Collapse are incomplete." Never claim to resolve what the universe left deliberately open. |

This distinction exists because EVE Frontier's lore is intentionally incomplete — new fragments are drip-fed via items, ruins, and player discoveries. The companion reflects that design: it knows what the sensors saw with precision, and knows the lore the way a machine with incomplete archives would.

**Route instructions in system prompt:**
> When a ROUTE appears in [SHIP SENSORS], report it as: "Plotting course: N jumps. [list of systems]." Dry, functional. If no ROUTE is in sensors but the pilot asks for navigation, state that navigation data is not available for that query.

**Key methods:**

| Method | Purpose |
|--------|---------|
| `build_messages(user_message, history, context_block)` | Formats request. Windowed to last 40 history entries. Prepends `[SHIP SENSORS]\n{context}\n\n[PILOT]\n{message}`. |
| `stream(user_message, history, context_block)` | Yields text chunks via `messages.stream()`. |

**Global singleton:**
```python
claude = ClaudeClient()
```

---

### `src/world_api.py` — EVE Universe Cache + Gate Graph Builder

**API base:** `https://world-api-stillness.live.tech.evefrontier.com`

**Key methods:**

| Method | Purpose |
|--------|---------|
| `load_or_build_index()` | Load from disk; rebuild from API if missing. |
| `rebuild_index(retries=5)` | Paginated fetch of `/v2/solarsystems` (limit=1000). Saves `system_index.json` AND `gate_graph.json` in one pass. |
| `_save_gate_graph(adj, meta)` | Writes `data/gate_graph.json` (adj + meta dicts). |
| `resolve_system_id(name)` | Case-insensitive name → ID lookup. |
| `get_system(system_name)` | Fetch `/v2/solarsystems/{id}` with 30s cache TTL. Returns `None` on failure. |
| `get_system_by_id(system_id)` | Fetch by ID directly. **Currently unused (dead code).** |

**System index (`data/system_index.json`):**
```json
{
  "built_at": "2026-03-11T16:31:15Z",
  "count": 24501,
  "index": { "utr-sn4": 1001, "jita": 1002, ... }
}
```

**Gate graph (`data/gate_graph.json`):**

Built in the same paginated pass as the system index. Populated only if the API includes `gateLinks` in bulk responses. If `gateLinks` is absent from the bulk endpoint, `adj` will be empty and the endpoint will serve the file with a 503 note. Trigger `POST /admin/rebuild-index` to regenerate.

```json
{
  "built_at": "2026-03-13T10:00:00Z",
  "adj": {
    "utr-sn4": ["i.59r.8j2", "some-neighbor"],
    "i.59r.8j2": ["utr-sn4", "morioka"]
  },
  "meta": {
    "utr-sn4": { "id": 30001001, "security": 0.3, "location": {"x": 1.5e14, "y": -2.1e13, "z": 8.7e13} },
    "i.59r.8j2": { "id": 30001002, "security": 0.1, "location": null }
  }
}
```

- All keys in `adj` and `meta` are **lowercase system names**.
- `location` is `null` if the bulk API response doesn't include coordinates for that system.
- `adj` edges are bidirectional (each end lists the other) — no deduplication needed at query time.

**Gate link extraction during rebuild:**
```python
gate_links = s.get("gateLinks") or []
# Handles both: list of ints (IDs) or list of dicts with "solarSystemId"/"id" key
```

After all pages load, `id → name` inversion maps raw IDs to lowercase names for the final `adj` dict.

**System data fields (individual system endpoint):** `id`, `name`, `security` (0.0–1.0), `kills` (recent list), `gateLinks` (array of neighbor IDs or dicts).

---

### `src/auth.py` — Token Validation

FastAPI `Depends` on `require_token()`. Checks `X-Server-Token` header against env `SERVER_TOKEN`. Returns HTTP 403 on mismatch. If `SERVER_TOKEN` not set → open access (local dev).

---

## Structure AI Modules

The Structure AI is a second Claude node that runs in the EVE Frontier SSU (Smart Storage Unit) in-game browser at `http://vps-ip:8745/static/structure.html?id=<structure-id>`. Auth is wallet-based (Sui/EVEVault), not shared-secret. It can bridge urgent alerts to the Ship AI via `log_buffer.pending_structure_alerts`.

### `src/structure_auth.py` — Nonce Store, Sui Signature Verification, JWT

**`NonceStore`** — in-memory, single-use nonce store with TTL (default 300s). Thread-safe via GIL dict ops.

| Method | Behavior |
|--------|----------|
| `issue() → str` | Generate 32-byte random hex nonce; store with `expires_at = now + ttl`. Auto-evicts expired entries. |
| `consume(nonce) → bool` | Pop nonce; return True only if present and not expired. |

**`verify_sui_personal_message(message_bytes, signature_b64, expected_address) → bool`**

Verifies a `signPersonalMessage` Sui compact signature (97 bytes: `flag(1) || sig(64) || pubkey(32)`, base64-encoded). Only `flag=0x00` (ed25519) supported. Intent prefix `[3, 0, 0]` + BCS-encoded message (u32-LE length + raw bytes). Address derived as `blake2b-256(0x00 || pubkey)`. Raises `ValueError` on format errors, `InvalidSignature` on mismatch.

> NOTE: Verify against a real EVEVault `signPersonalMessage` output before relying on it — the exact format has not been confirmed with a live test vector.

**JWT helpers:**

| Function | Behavior |
|----------|----------|
| `issue_jwt(payload) → str` | HS256, 24h expiry. Uses `JWT_SECRET` env var (warns if unset). |
| `decode_jwt(token) → dict` | Decode + verify; raises on expiry or tampering. |

**`lookup_character(address) → dict`** — async; calls World API `/v2/smartcharacters?address={address}`; returns `{id, name}` or `{}` on failure. Gracefully degrades if World API is unavailable.

**Global:** `nonce_store = NonceStore()`

---

### `src/nova_client.py` — Sui JSON-RPC, AccessRegistry, Tier Resolver

Reads `AccessRegistry` shared objects on the Nova chain (EVE Frontier builder sandbox) to determine access tier for a wallet address. Endpoint configured via `NOVA_RPC_URL` env var.

**`AccessRegistry` dataclass:**

| Field | Type |
|-------|------|
| `owner` | `str` — wallet address |
| `tribe` | `list[str]` — co-owner addresses |
| `vetted` | `list[str]` — vetted outsider addresses |

**`NovaClient` methods:**

| Method | Behavior |
|--------|----------|
| `get_access_registry(object_id) → Optional[AccessRegistry]` | Calls `sui_getObject` JSON-RPC with `showContent: True`. Parses `result.data.content.fields`. Returns `None` on any RPC error. |
| `resolve_tier(address, registry) → str` | Returns `OWNER`, `TRIBE`, `VETTED`, or `NONE`. Case-insensitive address comparison. |

**Tier semantics:** OWNER and TRIBE see all structure vitals. VETTED sees identity only. NONE is rejected by all protected endpoints.

**Global:** `nova_client = NovaClient()`

---

### `src/structure_profile.py` — StructureProfile Dataclass + Persistence

**`StructureProfile` dataclass:**

| Field | Type | Notes |
|-------|------|-------|
| `structure_id` | `str` | Used as filename; validated against `^[a-zA-Z0-9_\-]{1,64}$` |
| `owner_address` | `str` | Wallet address set on first OWNER auth |
| `structure_name` | `str` | Defaults to `structure_id` if not set |
| `structure_type` | `str` | Default: `"Smart Storage Unit"` |
| `system_name` | `str` | |
| `owner_character_id` | `int` | |
| `nova_registry_object_id` | `str` | Sui object ID of AccessRegistry for this structure |
| `created_at` | `str` | ISO8601, set on first save |
| `shield_pct` | `float` | Default 100.0 |
| `fuel_pct` | `float` | Default 100.0 |
| `services_online` | `int` | |
| `services_total` | `int` | |
| `docked_count` | `int` | |
| `routine_alerts` | `list` | Queued maintenance items |

**`as_dict_for_tier(tier) → dict`:** Filters fields by access tier before returning to caller.
- `OWNER` / `TRIBE`: full dict
- `VETTED`: hides vitals (`shield_pct`, `fuel_pct`, `services_*`, `docked_count`, `nova_registry_object_id`, `routine_alerts`, `owner_*`)
- `NONE`: bare identity only (`structure_id`, `structure_name`, `structure_type`, `system_name`)

**Persistence functions:** `load_profile(structure_id)`, `save_profile(profile)`, `profile_path(structure_id)`.
- Files stored in `data/structures/{id}.json`; directory auto-created on first save.
- `profile_path()` validates `structure_id` against the safe-ID regex — raises `ValueError` on path-traversal attempts.

---

### `src/structure_client.py` — Structure AI Claude Streaming Client

Separate from `claude_client.py` — different system prompt and context format.

**`build_structure_context(profile, tier, local_kills, local_pilots) → str`**

Builds the `[STRUCTURE SENSORS]` block (1500 char cap). Lines included:
- Always: `STRUCTURE: name | type | system`, `LOCAL: N pilots | kills last 1h`
- OWNER / TRIBE only: `STATUS: shield | fuel | services`, `DOCKED: N ship(s)`, up to 3 `PENDING:` routine alerts

**`detect_alerts(profile) → list`**

Evaluates structure state and returns alert dicts (`type`, `structure_id`, `structure_name`, `severity`, `message`, `ts`):
- Urgent: `shield_pct < 20%` or `fuel_pct < 10%`
- Routine: `fuel_pct < 25%` (only if not already urgent for fuel)

Urgent alerts from this function are routed to `log_buffer.add_structure_alert()` by the `/structure-chat` endpoint and delivered to the Ship AI on its next `/chat` call.

**`StructureClient` methods:**

| Method | Purpose |
|--------|---------|
| `build_system_prompt(profile, tier, character_name, character_id) → str` | Formats `STRUCTURE_SYSTEM_PROMPT` template with structure identity and session info. |
| `stream(message, history, context_block, profile, tier, character_name, character_id)` | Yields text chunks. Same streaming pattern as `claude_client.py` — `messages.stream()`, `max_tokens=1024`, `claude-sonnet-4-6`. |
| `_build_messages(user_message, history, context_block)` | Windowed to last 40 history entries. Prepends `[STRUCTURE SENSORS]\n{context}\n\n[PILOT]\n{message}`. |

**System prompt identity:** The structure AI knows the structure intimately. Loyal to owner, functional to tribe, terse with vetted. No pleasantries. References itself as "{structure_name} systems."

**Global:** `structure_client = StructureClient()`

---

## Log Agent: File-by-File

### `log-agent/log_agent.py` — File Watcher + Threads

**Entry point for the Windows client.**

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

**`PeriodicBootstrap(threading.Thread)`:**
Daemon thread. Runs `bootstrap_system()` every 30s until `tracker.current_system` is set. Exits cleanly once known.

**`HeartbeatEmitter(threading.Thread)`:**
Daemon thread. Every 30s:
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

## New Event Type: `route_planned`

Posted by the **client-side RouteCalculator** (Python, Windows) to `/log/ingest` after it computes a route.

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

**SSE keep-alive:** Server should send a `: keep-alive\n\n` comment every 15–20 seconds to prevent embedded-view timeout. **This is not yet implemented.** Add it to the `event_stream()` generator in `main.py` when connection stability issues appear in live testing.

---

## `static/index.html` — In-Game Browser UI

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

**No polling fallback.** SSE is confirmed native in Chromium 122. Polling was considered and explicitly dropped (2026-03-13).

---

## Overlay — File-by-File

Source: `overlay/` (built on Windows, deployed to gaming PC as `overlay.dll` + `injector.exe`)

### `overlay_core/dllmain.cpp`
DLL entry point. On `DLL_PROCESS_ATTACH`, queues a worker thread via `QueueUserWorkItem` to avoid loader-lock. Worker calls `hook::initialize()`.

### `overlay_core/hook.cpp`
MinHook setup. Creates dummy D3D12 device/queue/swap chain to read vtable addresses, then installs three hooks:

| Hook | Vtable slot | Purpose |
|---|---|---|
| `hookPresent` | IDXGISwapChain slot 8 | Calls `frame::renderOverlay` before original Present |
| `hookResizeBuffers` | IDXGISwapChain slot 13 | Invalidates + recreates render targets around resize |
| `hookECL` | ID3D12CommandQueue slot 10 | Captures the game's primary DIRECT command queue |

**Critical detail:** `hookECL` captures `g_capturedQueue` only on the **first** DIRECT ECL call (`g_capturedQueue == nullptr` guard). This is required because Dear ImGui 1.91.5 creates its own temporary `ID3D12CommandQueue` during font upload (`ImGui_ImplDX12_NewFrame` first call). Without the guard, hookECL overwrites `g_capturedQueue` with the temp queue pointer, which ImGui then destroys, leaving a dangling pointer that causes `DXGI_ERROR_ACCESS_DENIED` at the next ECL call.

### `overlay_core/imgui_init.cpp`
Initializes ImGui on the first Present call. Gets device from the captured queue (`g_capturedQueue->GetDevice`), creates SRV + RTV descriptor heaps, creates render targets for each back buffer, calls `ImGui_ImplWin32_Init` + `ImGui_ImplDX12_Init`. Strips SRGB from RTV format (flip swap chains reject SRGB RTVs). Subclasses the game window for input via `SetWindowLongPtrW`.

### `overlay_core/frame.cpp`
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

### `overlay_core/input.cpp`
WndProc subclass (`overlayWndProc`). F8 toggle fires first (`ui::visible = !ui::visible`). Then passes messages to `ImGui_ImplWin32_WndProcHandler`. Blocks mouse/keyboard messages from reaching the game when ImGui wants capture.

### `overlay_ui/config.h`
Compile-time constants: `SERVER_HOST`, `SERVER_HOST_W`, `SERVER_PORT`, `SERVER_TOKEN`, `CHAT_PATH`. Edit before building on Windows.

### `overlay_ui/http_client.h` / `http_client.cpp`
WinHTTP SSE client. `http::postChat()` runs synchronously on the caller's thread — always called from a background `std::thread`. Streams SSE `data:` lines via callbacks (`onChunk`, `onDone`). Handles partial-line buffering across `WinHttpReadData` calls. Plain HTTP (no TLS). Sends `X-Server-Token` header from `config::SERVER_TOKEN`.

### `overlay_ui/companion_panel.h` / `companion_panel.cpp`
Chat panel state and ImGui draw loop. Module-static state: message vector, input buffer, mutex, scroll flag, status line. `send()` pushes user + streaming assistant messages, spawns a detached `std::thread` that calls `http::postChat()` and appends chunks to the last message under mutex. `draw()` renders fixed-position panel (right side, 400×600px, dark terminal aesthetic, green text) every frame.

### `overlay_ui/render.cpp`
UI entry point called every frame from `frame.cpp`. Checks `ui::visible`; if true, calls `companion_panel::draw()`.

---

## Routing Architecture (2026-03-13)

### Design

Routing must run **client-side on the Windows gaming PC**.

**Why not server-side:**
- The VPS is a Hetzner 2 vCPU / 4 GB instance — a shared, low-spec machine running multiple services
- A* over 24,426 systems with spatial range queries is CPU-intensive and will block FastAPI's event loop or spike load for other users
- The gaming PC has orders of magnitude more CPU headroom and sits next to the game process
- Ship parameters (mass, temp, fuel) change constantly — the client has them, the server doesn't

**Current state:** `src/route_engine.py` and `src/ship_profile.py` exist on the server as a **reference implementation and dev/test tool**. `POST /route` and `GET/POST /ship-profile` are functional but should not be used in production routing — they are useful for debugging and for Claude to verbally describe a hypothetical route when asked.

**Target architecture:** A Python `RouteCalculator` process on Windows loads `systems.json` once, runs A* locally, and POSTs the result as a `route_planned` event to `/log/ingest`. The server only stores and relays the result — zero compute on the VPS.

### Data flow (target)

```
[Windows — RouteCalculator process]
  1. On startup: GET /data/systems (downloads systems.json, ~7 MB, cached with ETag)
  2. Builds in-memory graph + spatial index
  3. On route request (pilot input or chat trigger):
     - Reads ship params from local profile / user input
     - Runs A* locally (gaming CPU — fast)
     - POST /log/ingest {"type": "route_planned", "path": [...], "jumps": N, ...}

[Server]
  4. log_buffer stores result in current_route
  5. Next Claude prompt includes "ROUTE PLANNED: ..." line automatically
  6. Claude responds verbally, aware of the computed route
```

### Data flow (current — dev/debug only)

```
POST /route {"destination": "X"}  → server-side A* (avoid in production, CPU cost on VPS)
POST /chat "fly to X"             → regex match → server-side route → Claude responds
```

The chat intent detection (`_extract_route_destination`) and server `/route` endpoint remain useful for demos and for Claude to handle simple verbal route queries — but heavy production routing belongs on the client.

### Jump mechanics (from ef-map.com/ai-facts)

**Single-jump range (meters):**
```
range = ((150 - ext_temp) × specific_heat × hull_mass) / (3 × current_mass)
```

**Total fuel budget (meters):**
```
budget = (fuel_quantity × fuel_quality) / (1e-7 × current_mass)
```

**External temp from star (blocks jumping if ≥ 90):**
```
H(D) = 100 × (2/π) × arctan(100 × 2π × √(L / L_sun) / D)
```

**Fuel quality table:** D1=10%, D2=15%, SOF-40/EU-40=40%, SOF-80=80%, EU-90=90%

### Router algorithm

`route_engine.py` provides two modes:

1. **`bfs(origin, dest)`** — gate-only, free, no ship params. Finds shortest gate-hop path within a connected cluster. Fast (< 5ms). Falls back to this if A* fails.

2. **`route(origin, dest, profile)`** — A* hybrid. Gate hops cost 0; direct jumps cost distance in meters. Spatial index (`_SpatialIndex`) narrows range candidates via sorted X + binary search before exact distance check. Tracks total distance vs fuel budget. Falls back to BFS if result is None.

### Universe data structure

`data/systems.json` — built from EVE Frontier ResFiles via `build_universe.py`:
```json
{
  "built_at": "...",
  "systems": {
    "30000001": {
      "id": 30000001, "name": "system-name",
      "x": -5.1e18, "y": -4.4e17, "z": 1.3e18,
      "region_id": 10000001, "constellation_id": 20000001,
      "sun_type_id": 45031, "sun_type": "Sun K7 (Orange)", "spectral_class": "K7",
      "planet_ids": [...],
      "gate_links": [30000004, 30000005]
    }
  }
}
```

**Gate network facts:**
- 3,438 unique gate pairs, 231 disconnected clusters, largest = 39 systems
- ~2,878 systems have gates; ~21,548 are unreachable by gate alone
- Gate hops are free (fuel cost 0) — used as zero-cost edges in A*

### Ship profile

Stored in `data/ship_profile.json`, managed via `src/ship_profile.py`:

| Field | Description |
|---|---|
| `hull_mass` | Base hull mass (kg) |
| `current_mass` | Hull + fuel + cargo (kg) — pilot must account for cargo |
| `specific_heat` | Ship thermal capacity stat (from ship info panel) |
| `adaptive_level` | Adaptive upgrade level (0 = none) |
| `fuel_type` | D1 / D2 / SOF-40 / EU-40 / SOF-80 / EU-90 |
| `fuel_quantity` | Units of fuel loaded |
| `external_temp` | Override for temp (default 0 = deep space) |

**Default profile** is a placeholder — real in-game values required before routes work correctly.

**Per-request overrides:** Any field can be passed to `POST /route` to compute a hypothetical route without changing the stored profile.

### Route response format

```json
{
  "path": ["system-a", "system-b", "system-c"],
  "jumps": 2,
  "gate_hops": 1,
  "direct_jumps": 1,
  "total_distance_m": 4.7e18,
  "total_distance_ly": 497.3,
  "fuel_used": 87.4,
  "fuel_remaining": 412.6,
  "warnings": ["system-b is null-sec"]
}
```

### Future thinking: ship stat auto-extraction

Currently, ship parameters (`hull_mass`, `specific_heat`, etc.) require manual input via `POST /ship-profile`. This is the primary UX friction point for routing.

**Potential future approaches:**
- Parse ship stats from game log lines (if EVE Frontier logs undock/loadout events with stats)
- Query the World API for ship type stats by `typeID` (if endpoint exists or is added)
- Read directly from game memory via overlay DLL (technically possible, high complexity)
- Community-maintained ship stat database (similar to EVE Online's pyfa/ESI)

Until one of these is available, the pilot tells the AI their ship details in chat or via API, and the profile is updated accordingly.

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

## Test Coverage

| File | Count | What it covers |
|------|-------|----------------|
| `log-agent/tests/test_parsers.py` | 31 | All event types, edge cases, HTML stripping, discarded lines |
| `log-agent/tests/test_session_tracker.py` | 25 | Absorption, timeouts, flush, snapshot, pass-throughs |
| `tests/test_log_buffer.py` | 9 | Ring buffer cap, FIFO, system tracking, live store TTL |
| `tests/test_context_builder.py` | 21 | All context lines, live override, 2000-char cap, transitions cap |
| `tests/test_claude_client.py` | 6 | System prompt, message windowing, context prepend |
| `tests/test_world_api.py` | 9 | Pagination, case-insensitive lookup, caching, TTL, error handling |
| `tests/test_auth.py` | 4 | Valid/missing/wrong token; no-token dev mode |
| `tests/test_main.py` | 1 | Health endpoint |
| `tests/test_integration.py` | 2 | system_change triggers world_api warm; others do not |
| `tests/test_structure_auth.py` | 9 | Nonce issue/consume/expiry/double-consume, unsupported sig flag, JWT round-trip |
| `tests/test_nova_client.py` | 6 | AccessRegistry fetch (happy path, RPC error, missing fields), tier resolution (OWNER/TRIBE/VETTED/NONE) |
| `tests/test_structure_profile.py` | 7 | Profile save/load, tier-filtered dict, VETTED/NONE field hiding, path traversal rejection |
| `tests/test_structure_client.py` | 9 | Context lines by tier, alert detection thresholds, message building |

**Note:** `test_context_builder.py` does not yet cover the `current_route` / ROUTE PLANNED line. Add tests when `route_planned` event handling is verified end-to-end.

**Run all server tests:**
```bash
cd /opt/eve-frontier
.venv/bin/pytest tests/ -q
```

---

## Configuration

### Server `.env`
```
ANTHROPIC_API_KEY=sk-ant-...
WORLD_API_BASE_URL=https://world-api-stillness.live.tech.evefrontier.com
SERVER_TOKEN=<random secret — must match overlay config.h and log-agent .env>
PORT=8745
```

### Log Agent `log-agent/.env` (Windows)
```
SERVER_URL=http://your-vps-ip:8745
SERVER_TOKEN=change-this-to-match-server
LOG_BASE_PATH=C:\Users\Markus\Documents\Frontier\logs
```

---

## Running the System

### Server
```bash
cd /opt/eve-frontier
source .venv/bin/activate
./start.sh
# or: uvicorn main:app --host 0.0.0.0 --port 8745
```

### Build gate graph (one-time after deploy)
```bash
curl -X POST -H "X-Server-Token: $SERVER_TOKEN" http://localhost:8745/admin/rebuild-index
# Generates data/gate_graph.json alongside data/system_index.json
```

### Log Agent (Windows)
```bash
cd log-agent
python -m venv venv && venv\Scripts\activate
pip install -r requirements.txt
copy .env.example .env   # edit LOG_BASE_PATH, SERVER_URL, SERVER_TOKEN
python log_agent.py
```

### Diagnostics
```bash
# Full pipeline state
curl -H "X-Server-Token: $SERVER_TOKEN" http://localhost:8745/debug | jq

# Gate graph availability
curl -H "X-Server-Token: $SERVER_TOKEN" http://localhost:8745/data/gate-graph | jq '.built_at, (.adj | length)'

# Analyze gamelog structure (Windows)
python analyze_logs.py "C:\...\Frontier\logs\Gamelogs"

# Debug chatlog encoding (Windows)
python diagnose.py
```

---

## Known Gaps & TODOs

| Area | Gap | Priority |
|------|-----|----------|
| `static/structure.html` | Structure AI browser frontend not built — backend complete, UI deferred | **High** |
| Nova RPC URL | `NOVA_RPC_URL` defaults to `fullnode.devnet.sui.io` placeholder — real Nova/Stillness endpoint needed for live tier resolution | **High** |
| Sui signature test vector | `verify_sui_personal_message` lacks a real EVEVault `signPersonalMessage` output for validation — format unconfirmed | **High** |
| Client-side RouteCalculator | Not built — server-side engine exists as reference but must not run in production (VPS too small) | **High** |
| Ship stat auto-extraction | Manual profile input required — see Future Thinking in Routing section | **High** |
| ImGui navigation panel | Not started — "Route to:" input in overlay, triggers client-side route then POST /log/ingest | High |
| Route engine calibration | Default `ShipProfile` values are placeholder — needs real in-game stats to verify formulas | **High** |
| `GET /data/systems` endpoint | Not yet added — client-side RouteCalculator needs to download `systems.json` from server | Medium |
| `test_context_builder.py` | Missing coverage for `current_route` / ROUTE PLANNED context line | Medium |
| Route engine tests | No tests for `route_engine.py` or `ship_profile.py` | Medium |
| SSE keep-alive | Server does not send `: keep-alive` comments. Add to `event_stream()` if drops appear. | Low |
| `world_api.get_system_by_id()` | Defined but never called — dead code | Low |
| `/debug`, `/health` endpoints | No test coverage | Low |
| Buffer persistence | In-memory only — `current_route` and ring buffer lost on server restart | Low |
| Multi-user | Single shared buffer — designed for one player | Out of scope |
| `LogFileHandler` encoding fixes | Integration-level only; no unit tests | Low |
| `PeriodicBootstrap` / `HeartbeatEmitter` | No unit tests (side-effect threads) | Low |
| Star temperature in routing | `external_temp` defaults to 0 (deep space). For accuracy near hot stars, compute H(D) from `sun_type` luminosity + ship position. Not yet implemented. | Low |

---

## Lore Reference (use verbatim in responses and prompts)

- **Systems:** alphanumeric (UTR-SN4, I.59R.8J2)
- **Enemies:** "Faulty" drones — Scout, Analyzer, Repair (corrupted pre-Collapse automation)
- **Weapons:** Coilgun, Autocannon, Mass Driver, Railgun
- **Hit qualities:** Penetrates, Smashes, Hits, Grazes, Glances Off
- **Materials:** Carbonaceous Ore, Hermetite, Aestasium, Feldspar Crystals, Iridosmine Nodules
- **Structures:** Keep, Fabricator, Citadel, Stellar Constructions
- **Currency:** LUX
- **Keeper:** NPC AI entity — sends `Channel changed to Local` messages in chat (triggers system_change)

---

## Quick Reference

| Where to look | What you'll find |
|---------------|-----------------|
| `docs/log-pipeline.md` | Canonical design doc — pipeline architecture, event formats, session rules |
| `docs/superpowers/specs/2026-03-11-ship-ai-companion-design.md` | Product spec — UI design, terminal aesthetic, in-game browser notes |
| `docs/superpowers/plans/2026-03-11-ship-ai-companion.md` | Implementation plan — what's built, what's next |
| `docs/superpowers/specs/2026-03-11-blockchain-research.md` | World API + blockchain research |
| `docs/superpowers/specs/2026-03-13-structure-ai-design.md` | Structure AI product spec — auth, tier model, UI design |
| `docs/superpowers/plans/2026-03-13-structure-ai.md` | Structure AI implementation plan — what's built, what's next |
| `log-agent/tests/` | Best examples of how parsers and tracker behave |
| `tests/test_context_builder.py` | Best examples of context block output format |
