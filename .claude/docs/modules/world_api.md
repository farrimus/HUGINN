# world_api

## Overview

EVE Frontier universe cache and gate graph builder. Maintains a persistent system index (24,501 systems) and builds adjacency graphs for route calculation. Caches API responses to reduce load.

## When Should an Agent Use This Module?

Use **world_api** when you need to:
- Look up solar system IDs by name (case-insensitive)
- Fetch full system metadata (security, location, recent kills)
- Retrieve killmail data for a system (threat assessment)
- Build or rebuild the system index from the World API
- Persist/load cached indices to disk

## Key API

| Symbol | Type | Purpose | Agent Instruction | Gotchas |
|--------|------|---------|-------------------|---------|
| `world_api` | `WorldAPIClient` (singleton) | Global instance for all World API calls | Use this; instantiate only in tests | Always await async methods |
| `load_index_from_disk()` | `bool` | Load system index from `data/system_index.json` | Call at startup; check return value | Returns False if file missing |
| `save_index_to_disk()` | `None` | Persist current index to disk | Called automatically by rebuild; rarely needed | No return value; check logs for errors |
| `load_or_build_index()` → `int` | async | Load from disk or rebuild from API; returns count | Call at startup in lifespan | Blocks until complete; retries on network failure |
| `rebuild_index(retries=5, retry_delay=3.0)` → `int` | async | Force full rebuild from API; persists both `system_index.json` and `gate_graph.json` | Use when game adds systems; returns count | Pagination limit=1000; checks gateLinks for adj data |
| `resolve_system_id(name: str)` → `Optional[int]` | sync | Case-insensitive system name → ID lookup | Use before calling `get_system()` | Returns None if name not in index |
| `get_system(system_name: str)` → `Optional[dict]` | async | Fetch full system data by name (cached, 30s TTL) | Use in context builder for metadata | Resolves name to ID internally; returns None on error |
| `get_killmails(system_id: int)` → `list` | async | Fetch recent killmails for a system | Use in context/threat assessment | Returns [] on error; handles both list and {data: [...]} response shapes |

## Critical Gotchas & Pitfalls

• **Always await async methods** — `load_or_build_index()` and `rebuild_index()` are async. Use `await` or they'll return a coroutine, not the result.

• **Gate links may be missing** — If `rebuild_index()` finds `adj` empty, bulk `/v2/solarsystems` endpoint may not include `gateLinks`. Fall back to individual system fetches if needed.

• **System index is lowercase keys** — `system_index.json` stores names as `"utr-sn4"`, `"jita"`. Always call `resolve_system_id()` for case-insensitive lookup; never assume casing.

• **`get_system()` resolves name internally** — Don't call `resolve_system_id()` before `get_system()`. The method handles it. Call `resolve_system_id()` only if you need the ID directly.

• **TTL is per-request, not global** — Cache TTL (default 30s) is on a per-endpoint-params basis. Different param sets create separate cache entries.

## Architecture

**System Index** (`data/system_index.json`):
```json
{
  "built_at": "2026-03-11T16:31:15Z",
  "count": 24501,
  "index": { "utr-sn4": 1001, "jita": 1002, ... }
}
```

**Gate Graph** (`data/gate_graph.json`):
```json
{
  "built_at": "2026-03-13T10:00:00Z",
  "adj": {
    "utr-sn4": ["i.59r.8j2", "some-neighbor"],
    ...
  },
  "meta": {
    "utr-sn4": { "id": 30001001, "security": 0.3, "location": {"x": 1.5e14, "y": -2.1e13, "z": 8.7e13} },
    ...
  }
}
```

All keys are **lowercase system names**. Adjacency edges are bidirectional.

## Agent Guidance

**Primary Workflow**
1. At server startup (lifespan): call `await world_api.load_or_build_index()`
2. When a player changes systems: call `await world_api.get_system(current_system_name)` to warm cache
3. When building context: pass result to context_builder
4. If game adds systems: POST `/admin/rebuild-index` to force rebuild

**Best Practices & Anti-Patterns**
- Always use `await` on async methods; coroutines are not values
- Call `get_system()` by name, not ID; it handles lookup internally
- Use `resolve_system_id()` only when you need the ID directly (e.g., for killmail queries)
- Never parse system names from user input without normalizing to lowercase
- Rely on caching; don't poll the same system repeatedly within 30s
- On network errors, `get_system()` returns None gracefully; the Ship AI continues with incomplete context

**Cross-Module Dependencies**
- **Consumed by:** `context_builder.py` (for system metadata), `ssu_poller.py` (for structure location checks)
- **Route lookups:** `structure_client` handles adjacency lookups separately; route_engine loads from disk
- **Input from:** `/admin/rebuild-index` endpoint (forces rebuild)
- **Output to:** Ring buffer and context block (system data flows to Claude)

## Progressive Disclosure

Read this file by default. Load deeper files only when needed:
- Gate adjacency algorithm → `docs/ref/routing.md`
- Full World API endpoint reference → EVE Frontier World API documentation (external)
