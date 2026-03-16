# Structure AI — Context & Memory System Design

**Date:** 2026-03-15
**Deadline:** March 31, 2026 (hackathon)
**Status:** Approved for implementation planning

---

## Scope

This spec covers the full data pipeline feeding the Structure AI (SSU caretaker agent): static universe data, live on-chain state, killmail feeds, memory persistence, pilot profiles, and lore archive. It does not cover the Ship AI, overlay, or log-agent pipeline.

---

## Sub-projects (implementation order)

Hackathon-required items must ship by March 31. Optional items are skipped if time runs short.

| # | Sub-project | Hackathon required? |
|---|-------------|-------------------|
| 1 | Data curation | Yes |
| 2 | Memory system | Yes |
| 3 | Tier-based AI | Yes |
| 4 | Context enrichment | Yes |
| 5 | Lore archive | Optional |
| 6 | UX loading states | Optional — no interface defined, deferred entirely |

---

## Existing Code — Key References

**`src/structure_profile.py`** — `StructureProfile` dataclass. Fields: `structure_id` (str), `owner_address`, `structure_name`, `structure_type`, `system_name`, `owner_character_id`, `nova_registry_object_id`, `created_at`, `shield_pct`, `fuel_pct`, `services_online`, `services_total`, `docked_count`, `routine_alerts`. Persisted as JSON to `data/structures/{structure_id}.json`. New fields must be added: `region_name: str = ""` and `system_id: int = 0`.

**Migration:** Existing profile JSON files will load fine because the new fields default to `""` / `0`. On first `auth_verify` after the update, if `profile.system_id == 0` and `STRUCTURE_SYSTEM_NAME` is set, backfill `system_id` and `region_name` from `galaxy_db` and save the profile. This runs once per existing profile.

**`src/structure_client.py`** — `build_structure_context()`, `detect_alerts()`, `StructureClient`. `CONTEXT_CAP = 1500` — must be updated to `2000`.

**`structure_id`** — short alphanumeric slug (e.g. `"keep-7a"`), set via `NOVA_REGISTRY_STRUCTURE_ID` env var. Already established in production.

---

## Data Sources

### Canonical rule
> **API endpoints** → live/identity data only (character names, type catalog, system index)
> **ResFiles / `eve_universe.db`** → all structural universe data (orbits, L-points, planet details, star stats)
> **`data/` folder** → pre-built derived datasets from both

### Static universe data (`eve_universe.db`)

Single SQLite file at `data/eve_universe.db`. Source of truth for all universe structure. **Solar system detailed data is only available here — not in any API endpoint.**

| Table | Key fields | Count |
|-------|-----------|-------|
| Regions | regionId, name, centerX/Y/Z | 284 |
| Constellations | constellationId, name, regionId | 2,213 |
| SolarSystems | solarSystemId, name, regionId, constellationId, centerX/Y/Z, star_spectral_class, star_temperature, star_luminosity, star_radius, star_mass, frost_line, habitable_zone_* | 24,426 |
| Planets | planetId, name, solarSystemId, typeDescription, orbitRadius, temperature, radius, density, pressure, surfaceGravity | 83,257 |
| Moons | moonId, name, planetId, solarSystemId, same physical cols as Planets | 147,060 |
| LagrangePoints | id, solarSystemId, planetId, pointType (L1–L5), centerX/Y/Z | 416,285 |
| Jumps | fromSystemId, toSystemId, jumpType | 6,876 |
| NpcStations | stationId, name, solarSystemId, typeId | 98 |
| Types | typeId, typeName, groupId, description, mass, volume | 370 |

Access via `src/galaxy_db.py` (new file) — a thin wrapper. No existing code changed.

**`src/galaxy_db.py` interface:**

```python
class GalaxyDB:
    def __init__(self, db_path: str):
        """db_path is resolved relative to CWD at runtime.
        Standard call: GalaxyDB(os.path.join(os.path.dirname(__file__), "..", "data", "eve_universe.db"))
        """

    def get_system(self, name_or_id: str | int) -> dict | None:
        """Return SolarSystems row joined with region/constellation names.
        Searches by solarSystemId (int) or name (str, case-insensitive).
        """

    def get_region(self, region_id: int) -> dict | None: ...
    def get_constellation(self, constellation_id: int) -> dict | None: ...
    def get_planet(self, planet_id: int) -> dict | None: ...
    def get_moon(self, moon_id: int) -> dict | None: ...
    def get_station(self, station_id: int) -> dict | None: ...

    def get_celestials_in_system(self, system_id: int) -> dict:
        """Return {"planets": [...], "moons": [...], "stations": [...], "lagrange_points": [...]}
        Each item is a full row dict from the respective table.
        """

    def search_systems(self, pattern: str) -> list[dict]:
        """Case-insensitive substring match on name, returns list of system rows."""

    def get_jumps_from_system(self, system_id: int) -> list[dict]:
        """Return list of {toSystemId, jumpType} dicts."""

    def run_sql(self, sql: str, params: tuple = ()) -> list[dict]:
        """Escape hatch for arbitrary queries. Returns list of row dicts."""
```

### Existing JSON files (do not modify)

| File | Used by | Status |
|------|---------|--------|
| `data/systems.json` | `route_engine.py` | Keep — routing only |
| `data/gates.json` | route engine | Keep |
| `data/gate_graph.json` | route engine | Keep |
| `data/starmapcache.json` | `build_universe.py` | Superseded by `eve_universe.db` — keep until Phase 3 migration |
| `data/type_names_all.json` | Nothing after curation | Rename to `.DEPRECATED` only after `grep -r type_names_all src/` confirms no imports remain |

**`gate_graph.json` schema** (existing file):
```json
{
  "JITA": ["PERIMETER", "NEW CALDARI", "URLEN"],
  "PERIMETER": ["JITA", "URLEN"]
}
```
Keys and values are system names (strings), uppercase. Used for the GATES line in the sensors block: look up `gate_graph[system_name.upper()]` → list of neighbor names. If system not found, omit the GATES line.

### World API

Base URL controlled by `WORLD_API_ENV` env var:
```
WORLD_API_ENV=utopia    → https://world-api-utopia.uat.pub.evefrontier.com  (hackathon default)
WORLD_API_ENV=stillness → https://world-api-stillness.live.tech.evefrontier.com
```

Existing `WORLD_API_BASE_URL` env var override still works. **Precedence:** `WORLD_API_BASE_URL` (if set) overrides `WORLD_API_ENV`.

| Endpoint | Returns | Use |
|---------|---------|-----|
| `GET /v2/solarsystems` | id, name, regionId, constellationId, x/y/z | System index |
| `GET /v2/smartcharacters?address={addr}` | character id, name | Auth pilot lookup |
| `GET /v2/killmails` | killmail list | Nearby kill feed |
| `GET /v2/killmails/{id}` | full killmail | Detail lookup |
| `GET /v2/types` | 370 EVE Frontier types, full schema | Type catalog |

**Not available from World API:** security ratings, pilot counts, smart assembly details, planet/orbital data.

### Sui RPC (direct — no third-party dependency)

All Sui data accessed directly via `NOVA_RPC_URL` (default: `https://fullnode.testnet.sui.io`).

| Method | Purpose | Polling interval |
|--------|---------|-----------------|
| `sui_getObject` | SSU state: fuel, anchor status, inventory | 60s |
| `sui_getObject` | Turret state (only if `TURRET_OBJECT_IDS` set) | 60s |
| `suix_queryEvents` | Structure events on SSU ID | 60s |
| `suix_queryEvents` | Gate transit events — deferred; requires a gate object ID env var not yet defined. Omit from initial implementation. | — |
| `sui_subscribeEvent` | Real-time push — progressive enhancement only; fall back to polling if unavailable | — |

**`suix_queryEvents` filter:** `{"Sender": "<SSU_OBJECT_ID>"}`. Pagination: use `nextCursor` from each response as the `cursor` in the next call. Store cursor in memory between polls; on first poll, use `null` cursor (returns most recent events). Request `limit: 50` per page.

**`suix_queryEvents` response envelope:** `{"result": {"data": [...], "nextCursor": {...} | null, "hasNextPage": bool}}`. Each event object contains `{"type": "<module>::<EventType>", "sender": "0x...", "parsedJson": {...}, "timestampMs": "..."}`. The `parsedJson` field contains the event payload — exact fields depend on the EVE Frontier Sui contract and must be confirmed from a live response on first implementation. Log the full response on first poll.

**`sui_getObject` response envelope:** `{"result": {"data": {"content": {"fields": {...}}}}}`. The `fields` dict contains the object's Move fields. SSU fields (fuel, anchor status, services) and turret fields are EVE Frontier contract-specific. Log the full response on first poll and map fields to the event schema during implementation. If expected fields are absent, log a warning and skip the event write.

**Turret IDs:** optional. Set `TURRET_OBJECT_IDS=0xabc,0xdef` (comma-separated Sui object IDs). If unset, turret polling is skipped entirely. Multiple turrets polled individually via `sui_getObject`.

**EF-Map WebSocket not used** — deprecated, not Sui-integrated. All event handling done directly against Sui RPC.

### WatchTower webhooks (optional, non-blocking)

`POST /webhook/watchtower` receives HMAC-signed push events. Failure never blocks the AI; system falls back to polling.

**HMAC contract:** `X-Watchtower-Signature: sha256=<hex>` header, computed as `HMAC-SHA256(WATCHTOWER_SECRET, raw_request_body)`. Validation rejects any request where the computed digest does not match.

**`WATCHTOWER_SECRET` unset behavior:** if env var is not set, `POST /webhook/watchtower` returns `501 Not Implemented` and is not active. Do not register the route as an always-on endpoint.

**Response contract:**
- `200 OK` `{"status": "ok"}` — event accepted and written to events.jsonl
- `400 Bad Request` `{"error": "invalid signature"}` — HMAC mismatch
- `422 Unprocessable Entity` `{"error": "unknown event type"}` — payload received but not handled
- `501 Not Implemented` — `WATCHTOWER_SECRET` not configured
- `500 Internal Server Error` — unexpected failure (logged, server continues)

---

## Sub-project 1 — Data Curation

### Type catalog

Script: `build_types.py` (new file, run once or on game patch).

**Inputs:** `GET /v2/types?page=N` from World API (`N` starts at 1). Response is a top-level JSON array. Increment page until the response array is empty (length 0).
**Output:** `data/types.json` — array of objects with fields: `id`, `name`, `description`, `mass`, `radius`, `volume`, `portionSize`, `groupName`, `groupId`, `categoryName`, `categoryId`, `iconUrl`.

**Killmail response fields** (World API `/v2/killmails`): response is a top-level JSON array. Each killmail object uses: `id` (→ `kill_id`), `time` (ISO8601, → timestamp filter), `victimName` or `victim.name` (→ `victim_name`; confirm field name from live response), `victimShip` or `victim.ship` (→ `victim_ship`), `attackers[].name` (→ `attacker_names`), `totalValue` or `value` (→ `value_isk`). Confirm exact field names from the API docs at `https://world-api-utopia.uat.pub.evefrontier.com/docs/index.html` during implementation.
**On completion:** rename `data/type_names_all.json` → `data/type_names_all.DEPRECATED.json` only after confirming no live imports with `grep -r type_names_all src/`.

### Region filtering
`data/Allowed_regions.txt` contains 273 EVE Frontier region names, one name per line, UTF-8. Lines are stripped of leading/trailing whitespace; blank lines and lines starting with `#` are ignored. `eve_universe.db` `Regions` table has names and IDs. Map names → IDs, filter `systems.json` rebuild to only include systems in allowed regions.

### `systems.json` rebuild (deferred — after routing verified)
New `build_universe.py` reads from `eve_universe.db` instead of `starmapcache.json`. Adds: region name, constellation name, star spectral class, planet counts by type. Existing route engine unchanged until verified.

**"Routing verified" criterion:** existing `tests/test_route_engine.py` suite passes with the rebuilt `systems.json` as input.

### `data/README.md`
Documentation deliverable only — lists every file in `data/`: source, schema, freshness, how to query. Content is author-defined at write time; not subject to implementation review.

---

## Sub-project 2 — Memory System

### Directory structure
```
data/memory/{structure_id}/
  summary.json       — rolling 7-day summary, rebuilt after each session
  events.jsonl       — append-only timestamped event log
  pilots/
    {address}.json   — one file per authenticated wallet
```

**Bootstrap:** On server startup, if `data/memory/{structure_id}/` does not exist, create it with an empty `events.jsonl` and a default `summary.json` (`{"last_updated": null, "text": ""}`). The `pilots/` subdirectory is created on first pilot auth.

### `events.jsonl` schema

One JSON object per line. Required fields on every event:

```json
{
  "ts": "2026-03-15T14:32:00Z",
  "type": "killmail | gate_transit | ssu_state | access_change | turret_state | docking",
  "system_id": 30000142,
  "data": { ... }
}
```

`system_id` is always `StructureProfile.system_id` — use it for all event types including SSU-local events (`ssu_state`, `access_change`, `turret_state`, `docking`). Use `0` if `system_id` is not yet set on the profile.

`data` contents by type:
- `killmail` — `{kill_id, victim_name, victim_ship, attacker_names: [], value_isk}`
- `gate_transit` — `{gate_object_id, pilot_address, direction: "inbound|outbound"}` (deferred — gate object ID not yet configured)
- `ssu_state` — `{fuel_pct, anchor_status, services_online, services_total}`
- `access_change` — `{action: "add|remove", pilot_address, tier}`
- `turret_state` — `{turret_id, target_priorities: []}`
- `docking` — `{pilot_address, character_name}`

### Layer 1 — Always-on summary

`summary.json` injected as `[STRUCTURE MEMORY]` block every session. Soft cap of 300 chars within the 2000-char total context budget (see Context Assembly).

**Summary rebuild algorithm:** rule-based template, not AI-generated. Runs after each user session ends (after SSE stream closes via `Request.is_disconnected()` or generator exhaustion). Reads the last 7 days of `events.jsonl`, counts by type, formats:
```
Last 7 days: {docking_count} dockings | {kill_count} kills | {fuel_events} fuel deliveries | {access_count} access changes
```
Truncated to 300 chars if longer. Stored as `{"last_updated": "<ISO8601>", "text": "<summary>"}`.

**Summary rebuild location:** in a `finally` block inside the SSE route handler in `main.py`, after the streaming generator is exhausted or the request disconnects. This keeps it out of `structure_client.py` and ensures it runs after each session regardless of normal/error path.

**Concurrent sessions:** no file locking. Last writer wins. Acceptable for hackathon — concurrent sessions on one SSU are rare and the summary is non-critical.

### Layer 2 — Event log with tool retrieval

Tool: `search_events(keyword: str, days: int) -> list[dict]`

**Matching:** case-insensitive substring search across the entire JSON line as a string. Searches only events within `days` days of now. Returns up to 20 matching events (most recent first), each as a full event dict.

### Pilot profiles

`data/memory/{structure_id}/pilots/{address}.json`

Fields: `address`, `character_name`, `character_id`, `tier`, `first_seen`, `last_seen`, `visit_count`.

**Creation and update:** both SSU profile creation and pilot profile upsert happen in `auth_verify` in `main.py`. They are two separate steps in the same function:
1. Load SSU profile via `load_profile(structure_id)`. If `None`, create a new `StructureProfile` and save.
2. Load pilot profile from `data/memory/{structure_id}/pilots/{address}.json`. Upsert as described below.

Pilot profile upsert:
- If file does not exist: create with `first_seen = last_seen = now`, `visit_count = 1`, `tier = current_tier`.
- If file exists: update `last_seen = now`, `visit_count += 1`, `tier = current_tier`.

Injected into system prompt each session:
```
Pilot: Markús (ID: 12345) | Tier: OWNER | Visits: 14 | First seen: 2026-03-01
```

Tool: `get_pilot_profile(address: str) -> dict | None` — returns full profile dict, or `None` if address unknown.

---

## Sub-project 3 — Tier-based AI

| Tier | AI type | Context visible |
|------|---------|----------------|
| OWNER | Full structure AI, all tools | All blocks |
| TRIBE | Full structure AI, all tools | All blocks |
| VETTED | Lobby agent — no tools | Structure identity + local kills only. No STATUS, no MEMORY, no PENDING |
| NONE | Access denied | — |

**Routing in `main.py` `/structure-chat` endpoint:** after tier resolution, if `tier == "VETTED"` use `lobby_client` (see below); if tier is `"OWNER"` or `"TRIBE"` use `structure_client`; if `"NONE"` return 403 before reaching chat.

**`LobbyClient`:** new class in `src/structure_client.py`. Same streaming interface as `StructureClient.stream()` — takes `message, history, profile, character_name` and yields text chunks. Uses `LOBBY_SYSTEM_PROMPT` (see below) formatted with `structure_name`, `structure_type`, `system_name`. Instantiated as module-level `lobby_client = LobbyClient()` alongside existing `structure_client`.

**Lobby agent system prompt template (`LOBBY_SYSTEM_PROMPT`):**
```
You are the automated registry system of {structure_name}.
You do not have access to internal structure data.
Answer only: who owns this structure, what type it is, and what system it is in.
If asked about internal operations, fuel, or access lists, say: "That information is restricted."
Keep responses under 2 sentences.
```
Interpolation variables: `structure_name`, `structure_type`, `system_name`. No pilot line. No tools. No context blocks beyond bare identity.

---

## Sub-project 4 — Context Assembly

Final context block built per request in `build_structure_context()` in `src/structure_client.py`.

**System prompt (fixed):**

`STRUCTURE_SYSTEM_PROMPT` in `src/structure_client.py` — add `{region_name}` to the first line:
```
You are the intelligence of {structure_name}, a {structure_type} in {system_name}, {region_name}.
```

Add `region_name` field to the `.format()` call in `build_system_prompt()`.

**`region_name` on `StructureProfile`:** add `region_name: str = ""` to the dataclass. Set at profile creation time (in `auth_verify` when profile does not exist):
```python
system = galaxy_db.get_system(STRUCTURE_SYSTEM_NAME)
region_name = system["regionName"] if system else "Unknown Region"
```
If lookup fails, `region_name = "Unknown Region"` — not a fatal error. Env var `STRUCTURE_SYSTEM_NAME` is read at module load time. If unset, `region_name` remains `""`.

**`[STRUCTURE SENSORS]` block (built fresh per request):**
```
STRUCTURE: KEEP-7A | type: SSU | system: JITA | region: The Forge
STAR: G2 (Yellow) | PLANETS: 2× Temperate, 3× Barren | LAGRANGE: 12 points
GATES: PERIMETER, NEW CALDARI, URLEN
STATUS: fuel: 64% | anchor: active | services: 2/4
KILLS NEARBY: 3 in system (2h)
PENDING: Fuel at 64%. Plan resupply.
```

- **STAR / PLANETS / LAGRANGE:** queried from `eve_universe.db` via `galaxy_db.get_system()` and `get_celestials_in_system()`. Planet counts aggregated by `typeDescription`.
- **GATES:** `gate_graph[system_name]`. If system not found, omit line.
- **KILLS NEARBY:** World API `/v2/killmails?solarSystemId={system_id}`, first page only (no pagination). Filter client-side by `killmail.time` field (ISO8601) to last 2 hours. On API error, omit the KILLS line entirely (do not fail the request). `system_id` from `StructureProfile.system_id` (new int field). If `system_id == 0`, omit the KILLS line.
- **STATUS:** from `StructureProfile` fields (existing).
- **PENDING:** from `detect_alerts(profile)` → `profile.routine_alerts` (existing logic). PENDING lines come from stored `routine_alerts`.
- **Remove:** `LOCAL: {local_pilots} pilots in system | kills last 1h: {local_kills}` line — these are always 0, removed.

**`[STRUCTURE MEMORY]` block (from summary.json):** injected after SENSORS. Capped at 300 chars soft limit.

**Total context cap:** 2000 chars hard limit. Truncation priority order:
1. If total exceeds 2000: truncate MEMORY block first (set to empty).
2. If still over: truncate SENSORS block from the bottom (remove lines from end).
3. System prompt preamble is never truncated.

Update `CONTEXT_CAP = 1500` → `CONTEXT_CAP = 2000` in `src/structure_client.py`.

**New `StructureProfile` fields required:**
- `region_name: str = ""`
- `system_id: int = 0`

Both fields are set in `auth_verify` in `main.py` on profile creation. Profile creation occurs in `auth_verify` when `load_profile(structure_id)` returns `None` (first owner auth). If `STRUCTURE_SYSTEM_NAME` is set, `system_id` and `region_name` are backfilled from `galaxy_db`; if the env var is unset or the lookup fails, they remain `""` / `0`. On subsequent startups, if `profile.system_id == 0` and `STRUCTURE_SYSTEM_NAME` is set, backfill and save once.

**Tools available (OWNER/TRIBE only):**
- `search_events(keyword, days)`
- `get_pilot_profile(address)`
- `search_lore(keyword)` *(only if Sub-project 5 is implemented)*

---

## Sub-project 5 — Lore Archive *(optional — post-hackathon if time runs short)*

```
data/lore/
  collapse/          — The Collapse lore
  factions/          — EVE Frontier factions (NOT EVE Online)
  systems/           — system-specific notes
  structures/        — structure history notes
  events/            — AI-generated event notes
```

Three authoring layers:
1. **Human-curated base** — owner-written and verified EVE Frontier lore only
2. **Owner annotations** — notes added via authenticated `POST /structure/{id}/lore`
3. **AI-generated event notes** — written after significant events — factual records only, no lore assertions

**Hard constraint:** AI only asserts lore found in `data/lore/`. Never from training data. Enforced in system prompt: *"Lore: only assert what appears in [LORE ARCHIVE]. If absent: 'Records from before the Collapse are incomplete.'"*

Tool: `search_lore(keyword: str) -> list[dict]` — case-insensitive substring scan of all `.md` files in `data/lore/` at request time. Returns up to 10 matches as `[{"file": "path/relative/to/data/lore", "excerpt": "<text>"}]`.

**Excerpt extraction:** find the match position in the file text. Take `max(0, match_start - 50)` to `min(len(text), match_start + len(keyword) + 50)` as the excerpt window (roughly 100 chars centered on the match start). If the keyword is longer than 100 chars, include the full keyword plus 25 chars on each side. No ellipsis padding is added.

**`POST /structure/{id}/lore`:** out of scope for hackathon — no interface defined. Deferred entirely.

---

## Sub-project 6 — UX *(optional — no interface defined, deferred entirely post-hackathon)*

During tool calls, the browser UI will display cycling status messages (`SEARCHING ARCHIVES...`, `QUERYING RECORDS...`, `GATHERING DATA...`) with an animated icon. No server/browser protocol is defined for this sprint.

---

## Background Tasks (server)

All non-blocking. Failures logged, never crash the server. Implemented as `asyncio` tasks launched from the FastAPI lifespan context manager (`@asynccontextmanager` on `app`).

| Task | Interval | Action |
|------|----------|--------|
| SSU state poll | 60s | `sui_getObject` on `SSU_OBJECT_ID` → append `ssu_state` event to events.jsonl |
| Turret poll | 60s | `sui_getObject` on each ID in `TURRET_OBJECT_IDS` (if set) → append `turret_state` event |
| On-chain events poll | 60s | `suix_queryEvents` filter `{"Sender": SSU_OBJECT_ID}`, `limit: 50`, cursor stored in memory → append events. Gate transit events deferred (no gate object ID env var). |
| Killmail poll | 5min | World API `/v2/killmails?solarSystemId={system_id}` → append `killmail` events |
| Summary rebuild | After each session | Rebuild summary.json from last 7 days of events.jsonl |

Killmail poll uses `StructureProfile.system_id`. If `system_id == 0`, skip killmail poll.

---

## Environment Variables (additions)

```
WORLD_API_ENV=utopia                          # utopia | stillness (default: utopia)
NOVA_RPC_URL=https://fullnode.testnet.sui.io  # Sui fullnode RPC endpoint
SSU_OBJECT_ID=0x...                           # Sui object ID of the SSU assembly
TURRET_OBJECT_IDS=0x...,0x...                 # Optional: comma-separated turret object IDs
STRUCTURE_SYSTEM_NAME=JITA                    # System name — sets system_id and region_name at profile creation
WATCHTOWER_SECRET=...                         # HMAC secret for webhook validation (optional — webhooks disabled if unset)
```
