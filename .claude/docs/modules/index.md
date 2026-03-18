# Module Documentation Index

**Last Updated:** 2026-03-18
**Total Modules:** 20

## Core AI & Chat

| Module | Purpose |
|--------|---------|
| [claude_client](claude_client.md) | Ship AI streaming client; enforces lore-grounded persona |
| [context_builder](context_builder.md) | Assembles [SHIP SENSORS] context block for Claude |
| [structure_client](structure_client.md) | Structure AI streaming client; separate prompt + context |

## State Management

| Module | Purpose |
|--------|---------|
| [log_buffer](log_buffer.md) | Ring buffer of game events; tracks location, route, live snapshots |
| [memory_store](memory_store.md) | Persistent Structure AI memory (events, summaries, pilot notes) |

## Game Data & Navigation

| Module | Purpose |
|--------|---------|
| [world_api](world_api.md) | Public World API client; caches systems, gates, structures |
| [route_engine](route_engine.md) | BFS pathfinding with temperature-aware constraints; spatial indexing |
| [ship_profile](ship_profile.md) | Ship physics: jump range, fuel budget, heat dissipation |
| [location_index](location_index.md) | Assembly ID to coordinates mapping; fast spatial lookups |
| [galaxy_db](galaxy_db.md) | Static galaxy data (systems, constellations, regions) |
| [type_names](type_names.md) | Type ID to human-readable name conversion |
| [radius_search](radius_search.md) | Spatial queries: systems within radius, nearest neighbors |

## Structure Management

| Module | Purpose |
|--------|---------|
| [structure_profile](structure_profile.md) | Structure state (fuel, shields, services, docked pilots) |
| [structure_auth](structure_auth.md) | Access control (Nova registry + server-side fallback) |
| [nova_client](nova_client.md) | Sui blockchain client; fetches AccessRegistry objects |
| [ssu_poller](ssu_poller.md) | Background polling of SSU telemetry; triggers low-fuel alerts |

## Authentication & Configuration

| Module | Purpose |
|--------|---------|
| [auth](auth.md) | Simple X-Server-Token header validation |
| [token_manager](token_manager.md) | RSA key generation; JWT token issuance and validation |

## API Infrastructure

| Module | Purpose |
|--------|---------|
| [endpoints](endpoints.md) | FastAPI route handlers organized into sub-routers |

## Marketplace

| Module | Purpose |
|--------|---------|
| [deal_store](deal_store.md) | Persistent deal/contract storage and CRUD |

---

## Progressive Disclosure

Each module doc is ≤150 lines and answers: *"When should an agent use this module?"*

Heavy implementation details, algorithms, and examples live in:
- `/opt/eve-frontier/.claude/docs/references/` — architectural details
- `/opt/eve-frontier/.claude/docs/assets/` — data formats, constants, diagrams
- `/opt/eve-frontier/docs/ref/` — user-facing reference documentation

## Navigation

**Lost?** See [nav.md](nav.md) for reading paths based on what you need to do.

**Looking for details?** See [REGISTRY.md](REGISTRY.md) for cross-references from each module to:
- Detailed reference documentation (`/docs/ref/`)
- Design specifications (`/docs/superpowers/specs/`)
- Implementation plans (`/docs/superpowers/plans/`)

## Quick Links

- **How to navigate:** See [nav.md](nav.md) (5 paths to different doc types)
- **Module registry:** See [REGISTRY.md](REGISTRY.md) (all modules → reference docs → artifacts)
- **Architecture:** See `/docs/CODEBASE.md` for overview, diagram, directory tree
- **Log Pipeline:** See `/docs/log-pipeline.md` for event flow
- **Routing:** See `/docs/ref/routing.md` for algorithm, heat formula, ship physics
- **Lore & Intent:** See `/intent.md` for voice, values, worldbuilding guidelines
