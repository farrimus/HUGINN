# RadiusSearch

## Overview
Spatial index and search engine for EVE Frontier structures. Loads system data and structure locations from disk, calculates 3D Euclidean distances, and returns filtered results within a given radius. Supports multi-filter queries (planets, killmails, heat, structures) with intelligent thresholding to prevent context explosion.

## When Should an Agent Use This Module?
- Agent needs to find systems near a player's current location (radius-based discovery)
- Player asks "what's nearby?" with filter interests (planets, activity, danger zones)
- Structure locations need to be queried or recorded
- Distance calculations between systems are required
- Heat classification and safety assessment needed for a region

## Key API
| Symbol | Type | Purpose | Agent Instruction | Gotchas |
|--------|------|---------|-------------------|---------|
| `RadiusSearch(systems_path=None, structure_locations_path=None)` | Constructor | Initialize spatial index; loads systems.json and structure_locations.json | Always construct once at startup, reuse instance | Paths default to `data/systems.json` and `data/structure_locations.json` relative to module |
| `search(center_system, radius_ly, filters=None, killmail_hours=24, top_n=10, skip_heat_traps=False)` | async method → dict | Find systems within radius and apply filters; returns structured result with all matching systems per filter | Await this; most powerful API for player queries | Thresholding kicks in at >=20 systems: limits to top_n per filter |
| `find_systems_within_radius(center_name, radius_ly)` | method → List[dict] | Find all systems within radius from center; each includes calculated `distance_ly` | Use for raw distance queries without filters | Returns empty list if center not found or has no coordinates |
| `get_system(name_or_id)` | method → Optional[dict] | Lookup system by name (case-insensitive) or ID (int/str) | Use to resolve player input to system data | Case-insensitive name matching; tries ID first, then name |
| `classify_heat(system)` | method → str | Classify system as "cool" (<70°), "warm" (70–89°), or "hot" (>=90°) | Use for heat-based narrative/risk assessment | Returns classification based on `safe_jump_temp` field |
| `count_planets(system)` | method → int | Count planets in a system from `planet_ids` array | Use in planet-discovery narratives | Returns 0 if `planet_ids` missing or empty |
| `is_heat_trap(system)` | method → bool | Return True if system is warm or hot (>=70°) | Use to flag dangerous systems | Simple boolean: safe_jump_temp >= 70 |
| `get_killmails_for_system(system_id, hours=24)` | async method → list | Fetch killmails for a system and filter by recency; returns top 10 sorted by timestamp desc | Await this; use for PvP/activity context | Returns empty list on API errors; requires world_api_client initialized |
| `filter_killmails_by_recency(killmails, hours)` | method → list | Filter killmails by timestamp within hours window; sorts by recency (newest first) | Utility for custom killmail filtering | Handles both Unix seconds and milliseconds automatically |
| `get_most_recent_killmail_timestamp(killmails)` | method → Optional[float] | Get most recent killmail timestamp from list | Use to compute time-since-last-kill for narrative | Returns None if list empty or no valid timestamps |
| `_load_systems()` | private | Load systems from disk (called in `__init__`) | Internal; do not call | Logs warnings if file missing or invalid JSON |
| `_load_structure_locations()` | private | Load structure locations from disk (called in `__init__`) | Internal; do not call | Gracefully handles missing file; initializes empty dict |
| `_filter_planets(systems, top_n)` | private | Filter systems by planet count (highest first); returns dict with count and systems list | Internal filter implementation | Sorted descending by planet count |
| `_filter_killmails(systems, top_n, hours)` | async private | Filter systems by recent killmails (most kills first); returns dict with count and systems list | Internal filter implementation | Async; queries world_api_client for each system |
| `_filter_heat(systems, top_n)` | private | Filter systems by heat level (warm/hot only); returns dict with count and systems list | Internal filter implementation | Only includes systems with safe_jump_temp >= 70 |
| `_filter_structures(systems, top_n)` | private | Filter systems that have recorded structures; returns dict with count and systems list | Internal filter implementation | Matches by system_name (case-insensitive) |
| `_save_structure_locations()` | async private | Write structure locations to disk with built_at timestamp | Internal; called after structure recording | Creates parent directory if needed; logs success/error |
| `_hours_since(timestamp)` | private | Return hours elapsed since timestamp, rounded to 1 decimal place | Internal utility | Returns None if timestamp is None or 0 |
| `_distance_ly(sys_a, sys_b)` | private | Calculate 3D Euclidean distance between systems in light-years | Internal calculation | EVE coordinates in meters; 1 LY = 9.461e15 m |
| `systems_path` | instance variable | Path to loaded systems.json file | Internal; set in `__init__` | Defaults to `data/systems.json` relative to module |
| `structure_locations_path` | instance variable | Path to loaded structure_locations.json file | Internal; set in `__init__` | Defaults to `data/structure_locations.json` relative to module |
| `systems` | instance variable dict | Dict of all loaded systems: `{system_id: {name, x, y, z, ...}}` | Internal; read-only | Populated by `_load_systems()` at init |
| `structure_locations` | instance variable dict | Dict of recorded structures: `{structure_id: {system_name, reported_by, tribe, ...}}` | Internal; read-only | Populated by `_load_structure_locations()` at init |
| `world_api_client` | instance variable | Reference to world_api singleton for killmail queries | Internal | Must be initialized before `get_killmails_for_system()` called |
| `structure_locations_path` (module-level) | string constant | Backward-compatibility export of default structure locations path | Reference only | Equals `data/structure_locations.json` relative to src/ |

⚠️ **Gotcha:** `load_structures()` is a stub and raises `NotImplementedError`. Use the `/radius` endpoints instead for production.

## Critical Gotchas & Pitfalls

• **Heat classification not a filter—requires explicit check:** `classify_heat()` returns a string, but the `search()` method's `"heat"` filter only finds systems with `safe_jump_temp >= 70`. Cool systems are excluded from heat filter results. Use `skip_heat_traps=True` to exclude all warm/hot systems upfront.

• **Killmails async only:** `get_killmails_for_system()` and `_filter_killmails()` are async. Must `await` them. Without await, you get a coroutine object, not data.

• **Center system lookup is strict:** `find_systems_within_radius()` returns empty list if center system not found or lacks x/y/z coordinates. Validate with `get_system()` first if uncertain.

• **Thresholding silently limits results:** When >=20 systems match, each filter returns max `top_n` results (default 10). A 200 LY search may find 300 systems but return only 10 per filter. Check `total_systems` vs actual returned count.

• **Structure locations not auto-loaded from API:** Structures must be explicitly recorded via `/structures/record` endpoint or manually added to `structure_locations.json`. No live sync with World API structures.

• **Planet count from planet_ids only:** Systems without `planet_ids` field return 0 planets even if they have planets. Data completeness varies by World API version.

• **Distance calculation uses euclidean 3D:** Not pathfinding. Returns straight-line distance, not actual jump distance or gate distance. Use for spatial discovery, not routing.

• **Killmail timestamps in mixed formats:** Timestamps may be Unix seconds or milliseconds. `filter_killmails_by_recency()` normalizes them (>100B assumed ms). However, edge cases may exist; log any abnormal values.

## Architecture

RadiusSearch is a stateful class that loads system and structure data on initialization, then provides query methods for spatial discovery and filtering.

```
┌─────────────────────────────────────────┐
│ RadiusSearch Instance                   │
├─────────────────────────────────────────┤
│ __init__(systems_path, struct_path)     │
│  ├─ _load_systems()     → systems {}    │
│  └─ _load_structure_locations() → {}   │
├─────────────────────────────────────────┤
│ Public APIs                              │
│  ├─ search() (async)        [main entry]│
│  ├─ find_systems_within_radius()        │
│  ├─ get_system()                        │
│  ├─ classify_heat()                     │
│  ├─ is_heat_trap()                      │
│  ├─ count_planets()                     │
│  └─ get_killmails_for_system() (async)  │
├─────────────────────────────────────────┤
│ Filter Implementations (private)         │
│  ├─ _filter_planets()                   │
│  ├─ _filter_killmails() (async)         │
│  ├─ _filter_heat()                      │
│  └─ _filter_structures()                │
├─────────────────────────────────────────┤
│ Utilities (private)                      │
│  ├─ _distance_ly()                      │
│  ├─ _hours_since()                      │
│  └─ _save_structure_locations() (async) │
└─────────────────────────────────────────┘
```

**Data Flow for search():**
1. Resolve center_system name → system dict via `get_system()`
2. Call `find_systems_within_radius()` → all systems within radius with distances
3. Apply `skip_heat_traps` filter if requested
4. For each filter in filters list:
   - Call private filter method (_filter_planets, etc.)
   - Each returns dict: `{ "count": N, "systems": [...] }`
5. Return combined result dict with all filters

**Thresholding Logic:**
- If total_systems < 20: return all matching systems per filter (no truncation)
- If total_systems >= 20: limit to top_n per filter (default 10)

## Agent Guidance

**Primary Workflow**

1. Create instance at startup (once): `searcher = RadiusSearch()`
2. Resolve player's current system: `center_sys = searcher.get_system("UR8-K7K")`
3. Execute multi-filter search: `result = await searcher.search("UR8-K7K", radius_ly=100, filters=["planets", "heat", "killmails"])`
4. Parse result dict for each filter and weave into narrative
5. For heat safety, use `skip_heat_traps=True` or check each system's `safe_jump_temp`

**Best Practices & Anti-Patterns**

- Always **await** async methods (`search()`, `get_killmails_for_system()`, `_filter_killmails()`)
- Never assume a system has coordinates—check `find_systems_within_radius()` return value
- Use `classify_heat()` for narrative color ("hot region," "cool sanctuary"); it's not a filter
- Check `total_systems` in response to understand thresholding applied (if >=20 systems, results truncated to top_n per filter)
- **Do not** call private methods (_filter_*, _load_*, etc.) directly; use public API only
- For player-visible error messages, always check for empty `filters` dict or 0 `total_systems`
- Never assume `structure_locations` is complete; it's user-reported data, not authoritative

**Cross-Module Dependencies**

- **world_api:** `RadiusSearch.get_killmails_for_system()` requires `world_api_client` singleton initialized. If not present, returns empty list with warning.
- **data/systems.json:** Must exist at configured path; missing file logs warning and returns empty systems dict
- **data/structure_locations.json:** Optional; missing file is handled gracefully (empty dict)

## Progressive Disclosure

Read this file by default. Load deeper files only when told above.

- **Deep internals, algorithm rationale, testing:** `/opt/eve-frontier/docs/ref/radius-search.md`
- **Server endpoints, response formats, curl examples:** `/opt/eve-frontier/docs/ref/radius-search.md` (Server Endpoints section)
- **Client-side variant (log-agent):** `/opt/eve-frontier/log-agent/radius_calculator.py` (simplified copy; planets and heat filters only)
- **Module tests:** `/opt/eve-frontier/tests/test_radius_search*.py`
