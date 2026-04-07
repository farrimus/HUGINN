# Repository Structure

## Entry Points

| Entry point | Purpose |
|-------------|---------|
| `main.py` | Backend: FastAPI app, startup/lifespan, all router registration |
| `frontend/src/main.tsx` | Frontend: React entry point, provider setup |

---

## Directory Tree

```
/
├── main.py                          App entry point. Startup sequence, all routers registered here.
├── CLAUDE.md                        Claude Code project instructions (AI assistant rules).
├── PHILOSOPHY.md                    Product philosophy, north star, and engineering principles (Musk's Algorithm).
├── requirements.txt                 Python dependencies.
├── .env.example                     Environment variable template (copy to .env).
├── build_universe.py                One-time script: builds Galaxy DB from World API + starmap data.
├── build_gate_graph.py              One-time script: builds gate topology from World API.
│
├── src/                             All Python backend source.
│   │
│   ├── endpoints/                   FastAPI route handlers. One file per feature area.
│   │   ├── companion.py             POST /companion/stream, /companion/chat — primary AI chat (SSE).
│   │   ├── session.py               Session registration and per-pilot state.
│   │   ├── navigation.py            POST /route — pathfinding. GET /systems/names.
│   │   ├── search.py                Structure list and radius search.
│   │   ├── structures.py            GET /structure/{id} — structure profile.
│   │   ├── logs.py                  POST /logs/upload — game log analysis and intel extraction.
│   │   ├── watcher.py               SSU state change alerts (SSE streams + watch rules).
│   │   ├── courier.py               Hauling contract board (CRUD).
│   │   ├── tribe.py                 Tribe presence heartbeat and snapshot.
│   │   ├── tribe_posts.py           Tribe posts.
│   │   ├── news.py                  GET /news/latest — Huginn Signal broadcast.
│   │   ├── transactions.py          POST /tx/build — unsigned Sui PTB builder.
│   │   ├── admin.py                 Admin panel endpoints (OWNER-gated).
│   │   ├── entity.py                Entity resolution endpoints.
│   │   ├── game_data.py             Game data passthrough endpoints.
│   │   ├── system_knowledge.py      System knowledge graph endpoints (in progress).
│   │   └── ui.py                    UI config endpoints.
│   │
│   ├── ai_tools.py                  Claude tool registry: all tool definitions, schemas, and handlers.
│   ├── context_builder.py           Assembles the AI context block (location, tier, fuel, kills).
│   ├── world_api.py                 EVE Frontier World API client (solar systems, ships, tribes).
│   ├── galaxy_db.py                 SQLite query interface for the pre-built universe database.
│   ├── route_engine.py              Dijkstra pathfinding over gate topology.
│   ├── blockchain_killmails.py      Hourly incremental kill feed sync from Sui chain events.
│   ├── blockchain_queries.py        Sui RPC: reads AccessRegistry, resolves tier.
│   ├── entity_resolver.py           Resolves entity names and types; prewarmed from Sui GraphQL.
│   ├── graphql_queries.py           Named GraphQL query strings + per-tenant (utopia/stillness) config.
│   ├── bcs_encoding.py              BCS encoding utilities (Sui object ID derivation from itemId).
│   ├── intel_store.py               Pilot-reported per-structure intelligence (read/write).
│   ├── log_intel_store.py           Per-system intel accumulated from player log uploads.
│   ├── log_analysis.py              Parses game logs into a per-system event timeline.
│   ├── log_parsers.py               Strict format validators. Unrecognised lines are dropped.
│   ├── memory_store.py              Per-structure event memory (rolling JSONL + summary).
│   ├── session_store.py             Per-pilot session state (ship profile, history).
│   ├── structure_persistence.py     Structure profile (fuel, tier registry ID, system, etc.).
│   ├── structure_loader.py          Loads structure configs from data/structures/ at startup.
│   ├── ssu_poller.py                Background SSU state polling (per-structure).
│   ├── ssu_watcher_task.py          Delivers state-change alerts to SSE clients.
│   ├── huginn_news_task.py          Periodic Huginn Signal generation (background task).
│   ├── huginn_news.py               Huginn Signal content builder.
│   ├── threat_assessment.py         Threat scoring for systems and entities.
│   ├── ship_profile.py              Ship + fuel catalog; jump range and fuel budget calculation.
│   ├── config.py                    Network config; maps DEPLOYMENT_ENV to URLs and package IDs.
│   ├── schemas.py                   Shared Pydantic models.
│   ├── system_knowledge.py          Global system→enemy/ore knowledge graph (in progress).
│   ├── tx_builders/                 Unsigned Sui PTB construction (future admin UI).
│   │   └── gate_builder.py          Gate link/unlink transaction builder.
│   └── tools/                       AI tool implementation modules (threat, route, memory, etc.).
│
├── frontend/                        React TypeScript app.
│   ├── src/
│   │   ├── main.tsx                 Entry point: EveFrontierProvider + QueryClientProvider setup.
│   │   ├── App.tsx                  Root component and structure-type routing.
│   │   └── components/              All UI panels and associated hooks.
│   │       ├── TerminalUI.tsx       Main terminal interface (SSU / default assembly type).
│   │       ├── GateUI.tsx           Gate-specific interface.
│   │       ├── TurretUI.tsx         Turret-specific interface.
│   │       ├── InfoPanel.tsx        Structure info and status display.
│   │       ├── RoutePanel.tsx       Route planning UI.
│   │       ├── LogUploadPanel.tsx   Game log upload interface.
│   │       ├── HuginnNewsPanel.tsx  Huginn Signal display.
│   │       ├── BoardPanel.tsx       Courier contract board UI.
│   │       ├── NetworkMapPanel.tsx  Connected assembly network display.
│   │       ├── AdminPanel.tsx       Admin management UI (OWNER only).
│   │       ├── useCompanionStream.ts Hook: streaming AI chat via SSE.
│   │       ├── useWatcherAlerts.ts  Hook: SSU state change alert stream.
│   │       └── ...                  Other panels and utility components.
│   ├── vite.config.ts               Sets base: '/static/companion/' — required for deploy.
│   └── package.json
│
├── prompts/                         AI system prompts loaded at runtime.
│   ├── companion.md                 HUGINN persona: identity, tier enforcement, tool discipline.
│   └── tools.yaml                   Tool definitions and usage rules.
│
├── move/                            Sui Move smart contracts.
│   └── access_registry/             Per-structure access control contract (deployed on Sui testnet).
│       └── sources/access_registry.move
│
├── data/                            Runtime data. Gitignored. Generated by build scripts and runtime.
│   ├── eve_universe.db              Galaxy SQLite database (24,426 systems, gates, celestials).
│   ├── gate_graph.json              Gate topology for pathfinding.
│   ├── structures/                  Per-structure config JSON files (one per registered SSU).
│   ├── utopia/                      Utopia-environment runtime data.
│   └── stillness/                   Stillness-environment runtime data.
│       ├── killmails.jsonl          Kill feed (incrementally synced from Sui).
│       ├── sessions/                Per-pilot session state files.
│       ├── memory/                  Per-structure event memory.
│       ├── log_intel/               Per-system intel from player log uploads.
│       └── system_knowledge.db      Global system knowledge graph (in progress).
│
├── docs/                            Technical documentation.
├── scripts/                         Utility and backfill scripts.
├── static/                          FastAPI static file serving. Built frontend is deployed here.
│   └── companion/                   Destination for `cp -r frontend/dist/* static/companion/`.
├── config/                          Token configuration.
└── debug/                           Per-session debug log files (generated at runtime).
```

---

## What is Generated vs Committed

| Path | Committed? | How to generate |
|------|-----------|-----------------|
| `data/eve_universe.db` | No | `python build_universe.py` |
| `data/gate_graph.json` | No | `python build_gate_graph.py` |
| `data/{env}/killmails.jsonl` | No | Auto-synced at runtime |
| `data/{env}/sessions/` | No | Created at runtime |
| `frontend/dist/` | No | `cd frontend && npm run build` |
| `static/companion/` | No | `cp -r frontend/dist/* static/companion/` |
| `data/structures/*.json` | Yes (per SSU) | Manual configuration |
| `prompts/` | Yes | Edited manually |
| `move/` | Yes | Deployed to Sui testnet |
