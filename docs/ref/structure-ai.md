# Structure AI — Modules Reference

**Last updated:** 2026-03-16 (on-chain asset data — Phase 1/2/3)
**What this covers:** Sui/Nova deployment, all Structure AI server modules, build_types.py

The Structure AI is a second Claude node running in the EVE Frontier SSU (Smart Storage Unit) in-game browser at `http://vps-ip:8745/static/structure.html?id=<structure-id>`. Auth is wallet-based (Sui/EVEVault), not shared-secret. Urgent alerts bridge to the Ship AI via `log_buffer.pending_structure_alerts`.

---

## Sui / Nova Deployment

| Item | Value |
|------|-------|
| Network | Sui testnet (`https://fullnode.testnet.sui.io`) |
| Package ID | `0xf33568afc1a24e7b5de4db95d01b5db1d0ef6a99269251fb9a355dde844255b9` |
| AccessRegistry `keep-7a` (owner `0x442f...`) | `0x89e9b9b90acc3b7b576c7fe81015e0a6d333d9ae3e69133c8b1786c826f05dc0` |
| AccessRegistry `keep-7a` (owner `0xff09...`) | `0xf5ceffdbe44bb38e4796d7b885d0d95c5047fd2fe2e2a4e62eb5865512f64708` |
| Deployer address (server keypair) | `0x9a3e759f11844fd9f03afd9a51237c027bfaf50c7bf944a6c58ca4091c01f8a7` |
| Sui config on VPS | `/root/.sui/sui_config/client.yaml` |

**Structure AI URL pattern:**
```
http://<VPS_IP>:8745/static/structure.html?id=<structure_id>&registry=<object_id>
```

**Add tribe/vetted members** (must be called from the owner's wallet):
```bash
sui client call \
  --package 0xf33568afc1a24e7b5de4db95d01b5db1d0ef6a99269251fb9a355dde844255b9 \
  --module registry --function add_tribe \
  --args <REGISTRY_OBJECT_ID> <WALLET_ADDRESS> \
  --gas-budget 5000000
```

**Known issue:** EVEVault wallet injection into the SSU browser for external URLs is untested. If `window.__suiWallets` is empty on connect, the wallet is not being injected — check EVE Frontier builder Discord for SSU browser wallet injection requirements.

---

## Endpoints (from `main.py`)

| Route | Method | Auth | Purpose |
|-------|--------|------|---------|
| `/auth/challenge` | POST | None | Issue nonce for wallet signing. Returns `{nonce, structure_id, expires_in_seconds: 300}` |
| `/auth/verify` | POST | None | Consume nonce, verify Sui ed25519 sig, resolve tier from Nova AccessRegistry, return JWT |
| `/structure/{id}` | GET | JWT (≥VETTED) | Return tier-filtered structure profile |
| `/structure/{id}` | POST | JWT (OWNER) | Update structure profile fields |
| `/structure-chat` | POST | JWT (≥VETTED) | Structure AI streaming chat (SSE). Detects alerts, routes urgent to log_buffer, streams Claude response |

**`require_structure_jwt()` dependency:** Validates `Authorization: Bearer <jwt>` header. Decodes with `structure_auth.decode_jwt()`. Returns payload dict `{structure_id, address, tier, character_id, character_name}`.

**`/structure-chat` flow:**
1. Fetch `mem_store = get_memory_store(structure_id)`; `memory_text = mem_store.get_summary()`
2. Fetch `kills_nearby` via `world_api.get_killmails(profile.system_id)` — filtered to last 2h
3. `build_structure_context(profile, tier, memory_text=memory_text, kills_nearby=kills_nearby)`
4. VETTED tier → routes to `lobby_client.stream()` (restricted, no internal structure data)
5. OWNER/TRIBE → `structure_client.stream(...)` as before
6. `event_stream()` finally block: yields `[DONE]`, calls `mem_store.rebuild_summary()`

**`auth_verify` logic:**
- On first OWNER profile creation: reads `STRUCTURE_SYSTEM_NAME` env var, resolves `system_id` and `region_name` via `galaxy_db`, writes them to the new profile
- Backfills existing profiles where `system_id == 0` or `region_name == ""` using the same lookup
- After JWT decode: calls `mem.upsert_pilot(address, name, character_id, tier)` to create/update the pilot profile

---

## `src/structure_auth.py` — Nonce Store, Sui Signature Verification, JWT

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

## `src/nova_client.py` — Sui JSON-RPC, AccessRegistry, Tier Resolver

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
| `_rpc(method: str, params: list) → dict` | Generic async JSON-RPC helper. POSTs to `self._rpc_url` (from `NOVA_RPC_URL` env var). Returns the full JSON response dict. Used internally by `ssu_poller.py` for `suix_queryEvents`. |

**Tier semantics:** OWNER and TRIBE see all structure vitals. VETTED sees identity only. NONE is rejected by all protected endpoints.

**Global:** `nova_client = NovaClient()`

---

## `src/structure_profile.py` — StructureProfile Dataclass + Persistence

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
| `connected_assembly_ids` | `list` | Raw Sui object IDs from NetworkNode — written by `poll_ssu_state` each 60s cycle |
| `connected_assemblies` | `list` | Resolved `[{object_id, type_name, status}]` — written by `poll_connected_assemblies` |
| `ssu_inventory` | `list` | `[{type_name, quantity}]` — written by `poll_ssu_inventory` every 5min |
| `region_name` | `str` | Default `""` — resolved via `galaxy_db` on first OWNER auth; backfilled if missing |
| `system_id` | `int` | Default `0` — resolved via `galaxy_db` on first OWNER auth; backfilled if missing |

**`as_dict_for_tier(tier) → dict`:** Filters fields by access tier before returning to caller.
- `OWNER` / `TRIBE`: full dict
- `VETTED`: hides vitals (`shield_pct`, `fuel_pct`, `services_*`, `docked_count`, `nova_registry_object_id`, `routine_alerts`, `owner_*`, `connected_assembly_ids`, `connected_assemblies`, `ssu_inventory`)
- `NONE`: bare identity only (`structure_id`, `structure_name`, `structure_type`, `system_name`)

**Persistence functions:** `load_profile(structure_id)`, `save_profile(profile)`, `profile_path(structure_id)`.
- Files stored in `data/structures/{id}.json`; directory auto-created on first save.
- `profile_path()` validates `structure_id` against the safe-ID regex — raises `ValueError` on path-traversal attempts.
- `load_profile()` filters unknown JSON keys before constructing `StructureProfile` — forward/backward compatible with field additions.

---

## `src/structure_client.py` — Structure AI Claude Streaming Client

Separate from `claude_client.py` — different system prompt and context format.

**`build_structure_context(profile, tier, memory_text="", kills_nearby=0) → str`**

Builds the `[STRUCTURE SENSORS]` block (`CONTEXT_CAP = 2000` chars). Lines included (in order):
- Always: `STRUCTURE: name | type | system, region`
- OWNER/TRIBE + `system_id` set: `STAR: K7 (Orange) | PLANETS: 2× Gas, 3× Barren | LAGRANGE: N points` (from `galaxy_db`)
- Always (if `system_name` set): `GATES: PERIMETER, NEW CALDARI` (from `gate_graph.json`)
- OWNER/TRIBE only: `STATUS: shield | fuel | services`
- OWNER/TRIBE only (if `kills_nearby > 0`): `KILLS NEARBY: N in system (2h)`
- OWNER/TRIBE only (if `connected_assemblies` non-empty): `ASSEMBLIES: Smart Gate (ONLINE) | Smart Turret ×2 (1 ONLINE)`
- OWNER/TRIBE only (if `ssu_inventory` non-empty): `INVENTORY: 500× Tritanium | 10× Fuel Block` (capped at 6 items)
- OWNER/TRIBE only (up to 3): `PENDING: <routine alert message>`
- Memory (OWNER/TRIBE only): `[STRUCTURE MEMORY]\n{memory_text}` (capped at 300 chars)

Removed from context: `LOCAL: N pilots` and `local_kills` (always 0, never available from API).

**ASSEMBLIES line format:** Types grouped; single instance shows `(ONLINE)`/`(OFFLINE)`; multiple shows `×N (K ONLINE)` where K < N.

**INVENTORY line format:** `{qty}× {type_name}` items separated by ` | `, capped at 6 items.

**`detect_alerts(profile) → list`**

Evaluates structure state and returns alert dicts (`type`, `structure_id`, `structure_name`, `severity`, `message`, `ts`):
- Urgent: `shield_pct < 20%` or `fuel_pct < 10%`
- Routine: `fuel_pct < 25%` (only if not already urgent for fuel)

Urgent alerts are routed to `log_buffer.add_structure_alert()` and delivered to the Ship AI on its next `/chat` call.

**`StructureClient` methods:**

| Method | Purpose |
|--------|---------|
| `build_system_prompt(profile, tier, character_name, character_id) → str` | Formats `STRUCTURE_SYSTEM_PROMPT` template. First line: `"You are the intelligence of {structure_name}, a {structure_type} in {system_name}, {region_name}."` |
| `stream(message, history, context_block, profile, tier, character_name, character_id)` | Yields text chunks. Same streaming pattern as `claude_client.py` — `messages.stream()`, `max_tokens=1024`, `claude-sonnet-4-6`. |
| `_build_messages(user_message, history, context_block)` | Windowed to last 40 history entries. Prepends `[STRUCTURE SENSORS]\n{context}\n\n[PILOT]\n{message}`. |

**System prompt identity:** The structure AI knows the structure intimately. Loyal to owner, functional to tribe, terse with vetted. No pleasantries. References itself as "{structure_name} systems."

**`LobbyClient`** — restricted Claude client for VETTED tier:
- Uses `LOBBY_SYSTEM_PROMPT` — mentions the structure by name and type but reveals no fuel/shield/docked data
- `stream(message, history, context_block) → AsyncIterator[str]` — same yield pattern as `StructureClient.stream`
- VETTED users get helpful public-facing responses without exposure to owner vitals

**Globals:** `structure_client = StructureClient()`, `lobby_client = LobbyClient()`

---

## `src/galaxy_db.py` — SQLite Universe DB Wrapper

Read-only wrapper for `data/eve_universe.db` (SQLite, ~100 MB). Used by `structure_client.py` to enrich structure context with star type, planet counts, Lagrange points; and by `main.py` `auth_verify` to resolve `system_id` / `region_name`.

**DB path:** `os.path.join(os.path.dirname(__file__), "..", "data", "eve_universe.db")`

**Schema (key tables):**

| Table | Key columns |
|-------|-------------|
| `Regions` | `regionId`, `name`, `centerX/Y/Z` |
| `Constellations` | `constellationId`, `name`, `regionId` |
| `SolarSystems` | `solarSystemId`, `name`, `regionId`, `constellationId`, `star_spectral_class`, `star_temperature`, `star_age`, … |
| `Planets` | `planetId`, `name`, `solarSystemId`, `typeId`, `typeDescription`, `radius`, `density`, … |
| `Moons` | `moonId`, `name`, `planetId`, `solarSystemId`, `typeId`, … |
| `NpcStations` | `stationId`, `name`, `solarSystemId`, `planetId`, `typeId`, … |
| `LagrangePoints` | `id`, `solarSystemId`, `planetId`, `pointType` (L1–L5), `centerX/Y/Z` |
| `Jumps` | `fromSystemId`, `toSystemId`, `jumpType` |
| `Types` | `typeId`, `typeName`, `groupId`, `mass`, `volume`, … |

**`GalaxyDB` methods:**

| Method | Returns |
|--------|---------|
| `get_system(name_or_id)` | `dict` with full system row + `regionName`, `constellationName`. Returns `None` on miss. |
| `get_region(region_id)` | `dict` or `None` |
| `get_constellation(constellation_id)` | `dict` or `None` |
| `get_planet(planet_id)` | `dict` or `None` |
| `get_moon(moon_id)` | `dict` or `None` |
| `get_station(station_id)` | `dict` or `None` |
| `get_celestials_in_system(system_id)` | `{"planets": [...], "moons": [...], "stations": [...], "lagrange_points": [...]}` |
| `search_systems(pattern)` | `list[dict]` — LIKE search on name |
| `get_jumps_from_system(system_id)` | `list[dict]` — all jump rows where `fromSystemId` or `toSystemId` matches |
| `run_sql(sql, params)` | `list[dict]` — raw SQL passthrough |

**Error handling:** All errors are caught, logged, and return `None` / empty list / empty dict. Never re-raises.

**Module-level singleton:** `galaxy_db = GalaxyDB()`

**Tests:** `tests/test_galaxy_db.py` — 15 tests using real DB data (`REAL_SYSTEM_ID=30000004`, `REAL_SYSTEM_NAME="O3H-1FN"`, `REAL_REGION_NAME="653-Y-21"`, `REAL_PLANET_ID=40000005`).

---

## `src/memory_store.py` — Event Log + Pilot Profiles

File-backed persistent memory per structure. Stores game events for context and AI summary; also tracks every pilot who has authenticated.

**Storage layout:** `data/memory/{structure_id}/`
- `events.jsonl` — append-only JSONL, one event per line: `{"ts": "...", "type": "...", "system_id": ..., "data": {...}}`
- `summary.json` — Claude-condensed summary: `{"last_updated": "...", "text": "..."}`
- `pilots/{safe_address}.json` — pilot profile: `{"address": "...", "name": "...", "character_id": ..., "tier": "...", "last_seen": "..."}`

**`MemoryStore` class:**

| Method | Behavior |
|--------|----------|
| `bootstrap()` | Creates all required directories and files if missing. Safe to call multiple times. |
| `append_event(type, system_id, data)` | Appends one event to `events.jsonl`. |
| `search_events(keyword, days=7)` | Returns up to 20 matching events (newest-first) from the last N days. |
| `rebuild_summary()` | Reads recent events, calls Claude to condense into ≤300 chars, writes `summary.json`. Called in `event_stream()` finally block after every `/structure-chat` response. |
| `get_summary() → str` | Returns `summary.json` text, or `""` if missing. |
| `upsert_pilot(address, name, character_id, tier)` | Creates or updates pilot profile JSON. Called by `auth_verify` on every successful auth. |
| `get_pilot(address) → dict` | Returns pilot profile dict, or `{}` if not found. |
| `format_pilot_line(address) → str` | Returns `"name (tier)"` for context injection. |

**Constants:** `SUMMARY_CAP = 300`

**Factory:**
```python
def get_memory_store(structure_id: str) -> MemoryStore:
    store = MemoryStore(structure_id)
    store.bootstrap()
    return store
```

---

## `src/ssu_poller.py` — Async Background Tasks

Long-running asyncio tasks started at server startup (via FastAPI lifespan). Polls external sources and writes updates to the structure profile and memory store.

**Constants:**

| Name | Value | Purpose |
|------|-------|---------|
| `SSU_POLL_INTERVAL` | 60s | SSU state + connected assembly resolution |
| `KILLMAIL_POLL_INTERVAL` | 300s | Killmail polling |
| `TURRET_POLL_INTERVAL` | 60s | Turret state polling |
| `INVENTORY_POLL_INTERVAL` | 300s | SSU inventory via Sui dynamic fields RPC |
| `PLAYER_STRUCTURE_POLL_INTERVAL` | 120s | Player-owned structure summaries |

**Poll functions:**

| Function | Source | Updates |
|----------|--------|---------|
| `poll_ssu_state(structure_id, ssu_object_id)` | `nova_client._rpc("sui_getObject", ...)` two-hop | `profile.fuel_pct`, `profile.services_online`, `profile.connected_assembly_ids` |
| `poll_connected_assemblies(structure_id, assembly_ids)` | `nova_client._rpc("sui_getObject", ...)` per assembly (cap 10) | `profile.connected_assemblies` — `[{object_id, type_name, status}]` |
| `poll_ssu_inventory(structure_id, ssu_object_id)` | `nova_client._rpc("suix_getDynamicFields", ...)` + `sui_getObject` per field | `profile.ssu_inventory` — `[{type_name, quantity}]` |
| `poll_player_structure(assembly_id)` | `nova_client._rpc("sui_getObject", ...)` two-hop (same pattern as `poll_ssu_state`) | `_player_structure_cache[assembly_id]` |
| `poll_killmails(structure_id, system_id)` | `world_api.get_killmails(system_id)` | Appends new kills to `memory_store.append_event("killmail", ...)` |
| `poll_sui_events(structure_id, ssu_object_id)` | `nova_client._rpc("suix_queryEvents", ...)` ascending, cursor-tracked | Appends on-chain events to memory store |
| `poll_turret(structure_id, turret_object_id)` | `nova_client._rpc("sui_getObject", ...)` | Appends turret state events to memory store |

**Module-level cache:**
```python
_player_structure_cache: dict[str, dict]
# {assembly_id: {assembly_id, type_name, status, fuel_pct}}
```

**Accessor:** `get_player_structures_in_system(system_name: str) → list[dict]` — returns all cached entries. `system_name` parameter retained for API compatibility but not used for filtering — location is a hashed game mechanic and `system_name` is not available on-chain. Called by `main.py` `/chat` handler.

**Assembly type labels** (`_TYPE_LABELS`): Confirmed real on-chain struct names (verified 2026-03-16 against live Sui testnet):

| On-chain struct | Human label |
|-----------------|-------------|
| `Gate` | `Smart Gate` |
| `Turret` | `Smart Turret` |
| `StorageUnit` | `SSU` |
| `MiningLaser` | `Mining Laser` |

Legacy `SmartX` keys retained for compatibility. Unknown struct names pass through as-is (e.g. `NetworkNode` → `"NetworkNode"`).

**Self-reference:** The SSU's own object ID appears in the NetworkNode's `connected_assembly_ids` list. `_ssu_loop` filters it out before calling `poll_connected_assemblies` so the ASSEMBLIES context line doesn't show the SSU listed among its own connected assemblies.

**`start_background_tasks(structure_id, ssu_object_id, system_id)`:**
- Skips all tasks if `structure_id` is empty
- Starts `_killmail_loop` only if `system_id > 0`
- Starts `_ssu_loop` (SSU state + assembly resolution) only if `ssu_object_id` is set
- Reads `TURRET_OBJECT_IDS` env var (comma-separated); starts one `_turret_loop`
- Starts `_inventory_loop` if `ssu_object_id` is set (5min interval)
- Reads `PLAYER_STRUCTURE_IDS` env var (comma-separated); starts `_player_structure_loop` if set (2min interval)
- Called from `main.py` lifespan

**`_ssu_loop` sequence per cycle:** `poll_ssu_state` → `poll_sui_events` → reload profile → `poll_connected_assemblies` (IDs minus ssu_object_id) if IDs present → sleep.

**WatchTower webhook:** Not implemented (deferred post-hackathon). Would send shield/fuel alerts to Discord/Slack.

---

## `src/type_names.py` — Type ID → Name Resolver

Loads `data/type_names_all.json` once at import time and exposes a single lookup function.

**`get_type_name(type_id) → str`** — accepts int or str type_id. Returns the human-readable name (e.g. `"Thermal Composites"`) or `"Unknown"` if not found or `None` is passed.

**Global:** `_TYPE_NAMES: dict` — loaded from `data/type_names_all.json` at module import.

---

## Live Chain Field Paths (Verified 2026-03-16)

Verified against SSU object `0x51b84c...` on Sui testnet. Use as ground truth for field parsing.

**StorageUnit (hop 1):**
```
result.data.type        → "0x...::storage_unit::StorageUnit"
result.data.content.fields.energy_source_id  → bare string "0x..."  (NOT nested)
result.data.content.fields.status.fields.status.variant → "ONLINE" | "OFFLINE"
result.data.content.fields.inventory_keys    → [object_id, ...]  (owner cap + others; NOT inventory items)
```

**NetworkNode (hop 2, via energy_source_id):**
```
result.data.content.fields.fuel.fields.quantity      → string, e.g. "932"
result.data.content.fields.fuel.fields.max_capacity  → string, e.g. "100000"
result.data.content.fields.connected_assembly_ids    → ["0x...", ...]  (plain string array)
  NOTE: includes the SSU's own object ID — filter before passing to poll_connected_assemblies
```

**Connected assemblies (each individual sui_getObject call):**
```
result.data.type  → "0x...::gate::Gate" | "0x...::turret::Turret" | "0x...::storage_unit::StorageUnit"
result.data.content.fields.status.fields.status.variant → "ONLINE" | "OFFLINE"
```

**SSU Inventory (suix_getDynamicFields + sui_getObject, verified 2026-03-16):**
```
suix_getDynamicFields(ssu_object_id) →
  result.data[].objectType  → filter for "inventory" in type string
  result.data[].objectId    → object ID to fetch

sui_getObject(inv_object_id, {showContent: true}) →
  result.data.content.fields.value.fields.items.fields.contents[] →
    .fields.key              → type_id string (e.g. "88561")
    .fields.value.fields.type_id    → type_id (alternate path)
    .fields.value.fields.quantity   → quantity (int or string)
```
Type IDs resolved via `src/type_names.py` (loads `data/type_names_all.json`):
- `78502` → `"Velocity CD82"`
- `88561` → `"Thermal Composites"`

**Known live values (testnet, 2026-03-16):**
- SSU: OFFLINE, fuel 0.9% (932/100000) → triggers urgent fuel alert immediately
- Connected to: 1× Turret (OFFLINE), 2× Gate (OFFLINE) [after filtering SSU self-reference]
- Inventory: 1× Velocity CD82 (78502), 34× Thermal Composites (88561)

---

## `build_types.py` — World API Type Catalog Fetcher

One-shot CLI script. Fetches all pages of `/v2/types` from the World API and writes `data/types.json`.

**Usage:**
```bash
python build_types.py
# Output: data/types.json
```

**API base:** Same environment switching as `world_api.py` — `WORLD_API_BASE_URL` > `WORLD_API_ENV` > `utopia`.

---

## Test Coverage (Structure AI)

| File | Count | What it covers |
|------|-------|----------------|
| `tests/test_structure_auth.py` | 9 | Nonce issue/consume/expiry/double-consume, unsupported sig flag, JWT round-trip |
| `tests/test_nova_client.py` | 6 | AccessRegistry fetch (happy path, RPC error, missing fields), tier resolution (OWNER/TRIBE/VETTED/NONE) |
| `tests/test_structure_profile.py` | — | Profile save/load, tier-filtered dict, VETTED/NONE field hiding, path traversal, `region_name`/`system_id` fields, unknown-key filtering |
| `tests/test_structure_client.py` | 24 | Enriched context (STAR/PLANETS/LAGRANGE/GATES/memory), alert detection, LobbyClient prompt, ASSEMBLIES line (OWNER/VETTED/empty), INVENTORY line |
| `tests/test_galaxy_db.py` | 15 | `get_system` (by ID, by name, JOIN region name), `get_region`, `get_planet`, `get_celestials_in_system`, `get_jumps_from_system`, miss cases |
| `tests/test_memory_store.py` | 12 | `append_event`, `search_events`, `get_summary`, `rebuild_summary`, `upsert_pilot`, `get_pilot` |
| `tests/test_type_names.py` | 4 | Known type IDs, string key, unknown ID, None |
| `tests/test_ssu_poller.py` | 20 | Two-hop fuel, services, `connected_assembly_ids`, `poll_connected_assemblies`, inventory dynamic fields (populate/empty/no-fields), `poll_player_structure` (cache/RPC-failure), `get_player_structures_in_system` (all returned) |
| `tests/test_main_auth.py` | — | `auth_verify` backfills `system_id`/`region_name` on existing profiles, calls `upsert_pilot` |
