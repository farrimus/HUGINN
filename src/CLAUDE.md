# src/ -- Python Backend

Entry point: `main.py` (project root) -- FastAPI app, lifespan startup, router registration.

## Core AI

| File | Purpose |
|------|---------|
| ai_tools.py | Claude tool registry: definitions, schemas, handlers (largest file) |
| context_builder.py | Assembles per-request AI context (location, tier, fuel, kills, alerts) |
| prompt_loader.py | Reads prompt templates from prompts/ (hot-reload) |
| tier_capabilities.py | Per-tier tool access, nav items, permissions |

## Game Data

| File | Purpose |
|------|---------|
| world_api.py | EVE Frontier World API client (system index, jumps) |
| galaxy_db.py | SQLite interface for eve_universe.db (24,426 systems, gates) |
| ship_profile.py | Ship + fuel catalog, jump range, fuel budget calculations |
| entity_resolver.py | Assembly/character resolution from Sui GraphQL |
| type_names.py | Type ID to display name mapping |
| datahub_types.py | Datahub type catalog (categories, volumes, icons) |
| eve_types.py | EVE Frontier game data type models |

## Blockchain

| File | Purpose |
|------|---------|
| blockchain_killmails.py | Hourly kill feed sync from Sui events |
| blockchain_queries.py | Sui JSON-RPC: AccessRegistry reads, tier resolution |
| sui_adapter.py | Sui chain adapter with caching (30s/5min TTLs) |
| location_index.py | Assembly location indexing from chain events |

## Persistence

| File | Purpose |
|------|---------|
| session_store.py | Per-pilot session state (JSON, wallet-keyed) |
| memory_store.py | Per-structure event memory (rolling JSONL + summary) |
| structure_persistence.py | Structure profile (fuel, tier, system) |
| structure_loader.py | Loads structure configs from data/structures/ at startup |
| intel_store.py | Per-structure field intelligence |
| log_intel_store.py | Per-system intel from log uploads |
| system_knowledge.py | Global system knowledge graph (SQLite) |
| lore_store.py | Lore content (SQLite FTS5) |
| courier_store.py | Courier contract persistence |
| vouch_store.py | Tier override store (admin vouches) |
| admin_config_store.py | Per-env admin config (feature flags, tool toggles) |

## Background Tasks

| File | Purpose |
|------|---------|
| ssu_poller.py | Per-structure state polling (60s interval) |
| ssu_watcher_task.py | State-change alert delivery to SSE subscribers |
| huginn_news_task.py | Periodic signal generation task |
| huginn_news.py | Signal content builder |

## Domain Logic

| File | Purpose |
|------|---------|
| route_engine.py | Dijkstra pathfinding over gate topology |
| radius_search.py | Spatial query: structures within LY radius |
| build_calculator.py | Structure build order recommendations |
| threat_assessment.py | Kill pattern analysis, risk scoring |
| log_analysis.py | Game log parsing into event timeline |
| log_parsers.py | Strict format validators (unknown lines dropped) |
| tribe_board.py | Ephemeral tribe presence (5-min TTL) |
| tribe_posts.py | Tribe post persistence + SSE streaming |

## Shared

| File | Purpose |
|------|---------|
| config.py | Network config: DEPLOYMENT_ENV -> URLs, package IDs, data paths |
| schemas.py | Shared Pydantic models |
| utils.py | FastAPI utilities, require_token auth helper |
| token_manager.py | RSA key management, JWT signing |
| tx_builders/ | Unsigned Sui PTB construction (base.py, gate_builder.py) |

## Key Patterns

- All endpoints live in `src/endpoints/`. Never add routes to main.py directly.
- All runtime state persists to `data/{env}/` (utopia or stillness). See `data/CLAUDE.md`.
- Prompt templates live in `prompts/`. Hot-reloaded by prompt_loader.py -- no server restart needed.
- Tier resolution: blockchain query per request via blockchain_queries.py.

## Deep Reference

- System architecture and data flows: `docs/ARCHITECTURE.md`
- Design decisions and rationale: `docs/KEY_CONCEPTS_AND_DECISIONS.md`
- Data schemas and external APIs: `docs/DATA_REFERENCE.md`
