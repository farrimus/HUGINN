# Documentation Registry

**Auto-maintained by doc-doctor.** Last updated: 2026-03-18 (10 missing docs regenerated)
**Git Hash:** 83a6403df85f5a8bb96c5225b6d9ced2d23a7fcd

Maps every module to its agent doc and reference documentation.

---

## Core AI & Chat

### claude_client
- **Agent Doc:** [modules/claude_client.md](modules/claude_client.md) (Ship AI streaming client; enforces lore-grounded persona)
- **Reference:** `/docs/ref/ship-ai.md`
- **Related Modules:** context_builder, log_buffer, claude_client (intra-chat state)
- **Tests:** `/opt/eve-frontier/tests/test_claude_client.py`

### context_builder
- **Agent Doc:** [modules/context_builder.md](modules/context_builder.md) (Assembles [SHIP SENSORS] context block for Claude)
- **Reference:** `/docs/ref/ship-ai.md`
- **Related Modules:** log_buffer, world_api, ship_profile, location_index, structure_profile
- **Tests:** `/opt/eve-frontier/tests/test_context_builder.py`

### structure_client
- **Agent Doc:** [modules/structure_client.md](modules/structure_client.md) (Structure AI streaming client; separate prompt + context)
- **Reference:** `/docs/ref/structure-ai.md`
- **Related Modules:** context_builder, memory_store, structure_profile, structure_auth
- **Tests:** `/opt/eve-frontier/tests/test_structure_client.py`

---

## State Management

### log_buffer
- **Agent Doc:** [modules/log_buffer.md](modules/log_buffer.md) (Ring buffer of game events; tracks location, route, live snapshots)
- **Reference:** `/docs/log-pipeline.md` (canonical log event design and flow)
- **Reference:** `/docs/ref/ship-ai.md`
- **Related Modules:** context_builder, ship_profile, route_engine
- **Tests:** `/opt/eve-frontier/tests/test_log_buffer.py`

### memory_store
- **Agent Doc:** [modules/memory_store.md](modules/memory_store.md) (Persistent Structure AI memory: events, summaries, pilot notes)
- **Reference:** `/docs/ref/structure-ai.md`
- **Related Modules:** structure_client, structure_profile
- **Tests:** `/opt/eve-frontier/tests/test_memory_store.py`

---

## Game Data & Navigation

### world_api
- **Agent Doc:** [modules/world_api.md](modules/world_api.md) (Public World API client; caches systems, gates, structures)
- **Reference:** `/docs/ref/routing.md`
- **Reference:** `/docs/ref/ship-ai.md`
- **Related Modules:** route_engine, location_index, galaxy_db, radius_search, structure_profile
- **Tests:** `/opt/eve-frontier/tests/test_world_api.py`

### route_engine
- **Agent Doc:** [modules/route_engine.md](modules/route_engine.md) (BFS pathfinding with temperature-aware constraints; spatial indexing)
- **Reference:** `/docs/ref/routing.md` (full file: A* algorithm, heat formula, ship physics, performance analysis)
- **Related Modules:** ship_profile, location_index, world_api, galaxy_db
- **Tests:** `/opt/eve-frontier/tests/test_route_engine.py`

### ship_profile
- **Agent Doc:** [modules/ship_profile.md](modules/ship_profile.md) (Ship physics: jump range, fuel budget, heat dissipation)
- **Reference:** `/docs/ref/routing.md`
- **Related Modules:** route_engine, context_builder
- **Tests:** `/opt/eve-frontier/tests/test_ship_profile.py`

### location_index
- **Agent Doc:** [modules/location_index.md](modules/location_index.md) (Sui chain LocationRevealedEvent tracking; maps assembly_id to coordinates and structure metadata)
- **Reference:** `/docs/ref/structure-ai.md`
- **Related Modules:** world_api, structure_profile, structure_client
- **Tests:** `/opt/eve-frontier/tests/test_location_index.py`

### galaxy_db
- **Agent Doc:** [modules/galaxy_db.md](modules/galaxy_db.md) (Static galaxy data: systems, constellations, regions)
- **Reference:** `/docs/ref/routing.md`
- **Related Modules:** world_api, location_index, route_engine
- **Tests:** `/opt/eve-frontier/tests/test_galaxy_db.py`

### type_names
- **Agent Doc:** [modules/type_names.md](modules/type_names.md) (Type ID to human-readable name conversion)
- **Reference:** `/docs/ref/ship-ai.md`
- **Related Modules:** context_builder, world_api
- **Tests:** `/opt/eve-frontier/tests/test_type_names.py`

### radius_search
- **Agent Doc:** [modules/radius_search.md](modules/radius_search.md) (Spatial queries: systems within radius, nearest neighbors)
- **Reference:** `/docs/ref/radius-search.md` (full file: spatial indexing, range query algorithms, performance)
- **Related Modules:** world_api, location_index, context_builder
- **Tests:** `/opt/eve-frontier/tests/test_radius_search.py`

---

## Structure Management

### structure_profile
- **Agent Doc:** [modules/structure_profile.md](modules/structure_profile.md) (Structure state: fuel, shields, services, docked pilots)
- **Reference:** `/docs/ref/structure-ai.md`
- **Related Modules:** structure_client, memory_store, ssu_poller, structure_auth
- **Tests:** `/opt/eve-frontier/tests/test_structure_profile.py`

### structure_auth
- **Agent Doc:** [modules/structure_auth.md](modules/structure_auth.md) (Sui wallet auth: nonce store, signature verification, JWT issuance)
- **Reference:** `/docs/ref/structure-ai.md`
- **Related Modules:** deal_store, memory_store, structure_client
- **Tests:** `/opt/eve-frontier/tests/test_structure_auth.py`

### nova_client
- **Agent Doc:** [modules/nova_client.md](modules/nova_client.md) (Sui blockchain client; fetches AccessRegistry objects)
- **Reference:** `/docs/ref/structure-ai.md`
- **Related Modules:** structure_auth, token_manager
- **Tests:** `/opt/eve-frontier/tests/test_nova_client.py`

### ssu_poller
- **Agent Doc:** [modules/ssu_poller.md](modules/ssu_poller.md) (Background polling of SSU telemetry; triggers low-fuel alerts)
- **Reference:** `/docs/ref/structure-ai.md`
- **Related Modules:** structure_profile, memory_store, structure_client
- **Tests:** `/opt/eve-frontier/tests/test_ssu_poller.py`

---

## Authentication & Configuration

### auth
- **Agent Doc:** [modules/auth.md](modules/auth.md) (Simple X-Server-Token header validation)
- **Reference:** `/docs/ref/ops.md`
- **Related Modules:** token_manager, endpoints
- **Tests:** `/opt/eve-frontier/tests/test_auth.py`

### token_manager
- **Agent Doc:** [modules/token_manager.md](modules/token_manager.md) (RSA key generation; JWT token issuance and validation)
- **Reference:** `/docs/ref/structure-ai.md`
- **Related Modules:** auth, structure_auth, nova_client
- **Tests:** `/opt/eve-frontier/tests/test_token_manager.py`

---

## API Infrastructure

### endpoints
- **Agent Doc:** [modules/endpoints.md](modules/endpoints.md) (FastAPI route handlers organized into sub-routers)
- **Reference:** `/docs/CODEBASE.md` (section: "API Endpoints & Routes")
- **Reference:** `/docs/ref/ship-ai.md`
- **Reference:** `/docs/ref/structure-ai.md`
- **Related Modules:** auth, context_builder, claude_client, structure_client, log_buffer
- **Tests:** `/opt/eve-frontier/tests/test_endpoints.py`

---

## Marketplace

### deal_store
- **Agent Doc:** [modules/deal_store.md](modules/deal_store.md) (Persistent deal/contract storage and CRUD)
- **Reference:** `/docs/ref/structure-ai.md`
- **Related Modules:** structure_client, memory_store
- **Tests:** `/opt/eve-frontier/tests/test_deal_store.py`

---

## Generation Audit

| Metric | Result |
|--------|--------|
| Total modules documented | 20 (19 files, 1 dir) |
| Module docs generated | 20/20 ✓ |
| Modules linked to reference docs | 20/20 ✓ |
| Total reference docs indexed | 8 ✓ |
| Cross-references verified | all valid ✓ |

**Status:** Registry complete. All 20 modules mapped to agent docs and reference documentation. Scope hierarchy established: agent docs (quick) → reference docs (deep).

---

## How to Update This Registry

- **New module added:** Run `/doc-doctor` to auto-generate agent doc and update registry
- **Reference doc updated:** Run `/doc-doctor` to rescan `/docs/ref/` and update cross-references
- **Manual correction needed:** Edit this file directly, then run `/doc-doctor` to verify

**Note:** Superpowers artifacts (specs and plans in `/docs/superpowers/`) are archived skill-managed documents kept for reference/audit purposes. They are not indexed in this registry — navigation focuses on module docs and reference documentation.
