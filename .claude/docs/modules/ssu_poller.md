# ssu_poller

## Overview
Background polling tasks for Structure AI. Polls Sui RPC for SSU (StorageUnit) state, events, turret state, inventory, connected assemblies, and World API for killmails. All failures are logged and swallowed — server never crashes due to poller errors.

## When Should an Agent Use This Module?
- Launching background SSU/structure polling from FastAPI startup
- Getting cached player structure summaries for nearby context
- Understanding SSU/turret/inventory polling lifecycle

## Key API
| Symbol | Type | Purpose | Agent Instruction |
|--------|------|---------|------------------|
| `start_background_tasks(structure_id, ssu_object_id, system_id)` | function | Launch all polling loops async tasks | Call once from FastAPI lifespan startup |
| `poll_ssu_state(structure_id, ssu_object_id)` | async function | Fetch SSU fuel/services from Sui chain | Called automatically by _ssu_loop; do not call directly |
| `poll_sui_events(ssu_object_id, structure_id, system_id)` | async function | Poll Sui events, append to memory store | Called automatically by _ssu_loop |
| `poll_connected_assemblies(structure_id, assembly_ids)` | async function | Resolve connected assembly types/status | Called automatically by _ssu_loop |
| `poll_killmails(structure_id, system_id)` | async function | Poll World API killmails, append to memory | Called automatically by _killmail_loop |
| `poll_turret(turret_object_id, structure_id, system_id)` | async function | Fetch turret state from Sui chain | Called automatically by _turret_loop |
| `poll_ssu_inventory(structure_id, ssu_object_id)` | async function | Fetch SSU inventory from Sui dynamic fields | Called automatically by _inventory_loop |
| `poll_player_structure(assembly_id)` | async function | Fetch player-owned structure state, cache it | Called automatically by _player_structure_loop |
| `get_player_structures_in_system(system_name)` | function | Return cached player structure summaries | Use in context_builder to list nearby structures |

### Constants
```python
SSU_POLL_INTERVAL = 60           # Hop 1+2 + events + assemblies
KILLMAIL_POLL_INTERVAL = 300     # 5 minutes
TURRET_POLL_INTERVAL = 60        # seconds
INVENTORY_POLL_INTERVAL = 300    # 5 minutes
PLAYER_STRUCTURE_POLL_INTERVAL = 120  # 2 minutes
```

## Critical Gotchas & Pitfalls for Agents
• **Call start_background_tasks, not raw functions:** Each polling function runs in an infinite loop. Call `start_background_tasks()` once at startup to launch all loops via asyncio.create_task().
• **No stop_polling function:** There is no graceful shutdown function. Tasks run until server exits. Graceful shutdown happens via signal handlers outside this module.
• **Lazy imports:** `nova_client` and `structure_profile` are imported at first use, not at module load, to avoid circular dependencies.
• **All errors swallowed:** RPC failures, missing profiles, and malformed responses are logged but don't crash the server.
• **Turrets and player structures configured via env vars:** Set `TURRET_OBJECT_IDS` (comma-separated) and `PLAYER_STRUCTURE_IDS` (comma-separated); if unset, those polls don't start.

## Architecture
```
Startup (main.py lifespan):
  start_background_tasks(structure_id, ssu_object_id, system_id)
    ↓
Launch 6 concurrent async task loops (if configured):
  _ssu_loop(ssu_object_id, structure_id, system_id)
    → poll_ssu_state() every 60s (2-hop RPC)
    → poll_sui_events() every 60s (event pagination)
    → poll_connected_assemblies() every 60s (resolve types/status)
  _killmail_loop(structure_id, system_id)
    → poll_killmails() every 5 min
  _turret_loop(turret_ids, structure_id, system_id) [if TURRET_OBJECT_IDS set]
    → poll_turret() per turret every 60s
  _inventory_loop(structure_id, ssu_object_id) [if ssu_object_id set]
    → poll_ssu_inventory() every 5 min
  _player_structure_loop(player_ids) [if PLAYER_STRUCTURE_IDS set]
    → poll_player_structure() per assembly every 2 min
    → results cached in _player_structure_cache
```

## Agent Guidance
**Primary Workflow**
1. At server startup (main.py lifespan): `start_background_tasks(structure_id, ssu_object_id, system_id)`
2. Background loops run continuously, updating state on intervals
3. To fetch nearby structures: `structures = get_player_structures_in_system(system_name)`
4. Use returned summaries in `context_builder` for [STRUCTURE SENSORS]

**Best Practices & Anti-Patterns**
- Always / Call `start_background_tasks()` once at server init (main.py startup hook)
- Always / Set environment variables: SSU_OBJECT_ID, TURRET_OBJECT_IDS (comma-separated), PLAYER_STRUCTURE_IDS (comma-separated)
- Always / Use cached results from `get_player_structures_in_system()` — don't poll manually
- Never / Call polling functions directly in request handlers (they run in background)
- Never / Assume poll results are fresh — cache is refreshed on interval, not on-demand

**Cross-Module Dependencies**
- Depends on: `nova_client` (Sui RPC), `world_api` (killmail data), `structure_profile` (state storage), `memory_store` (event append)
- Used by: `context_builder` (nearby structures), startup hook in `main.py`

## Progressive Disclosure
**Read this main file by default.**

**Load deeper files ONLY when:**
- You need poll interval details: read top of `ssu_poller.py` for `*_POLL_INTERVAL` constants (lines 28-32)
- You need SSU data flow: read `/docs/ref/structure-ai.md` section on telemetry
