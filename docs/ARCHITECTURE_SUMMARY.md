# Architecture Summary — HUGINN

## System Context

Players access HUGINN through EVE Frontier's in-game Chromium browser by opening a Smart Storage Unit (SSU) that has HUGINN configured. The browser loads the app with URL parameters (`?itemId=...&tenant=...`) that identify the specific assembly and game environment.

```
┌────────────────────────────────────────────────────────────────┐
│  EVE Frontier Game Client                                      │
│    └── In-game browser (Chromium 122)                         │
│          └── HUGINN React App (TypeScript + DApp Kit)         │
│                ↕  HTTP / SSE (port 8745)                      │
│          HUGINN Backend (FastAPI, Python 3.12)                │
│                ├──► Claude API        (AI responses)          │
│                ├──► World API         (live game state)       │
│                ├──► Sui Testnet RPC   (killmails, tier)       │
│                └──► Galaxy DB         (local SQLite)          │
└────────────────────────────────────────────────────────────────┘

External: Sui blockchain hosts the AccessRegistry contract and
          EVE Frontier game contracts (kill events, assembly state).
```

---

## Containers

| Container | Technology | Responsibility |
|-----------|-----------|----------------|
| React Frontend | TypeScript, React 19, Vite, `@evefrontier/dapp-kit` | In-game UI, wallet auth, SSE rendering |
| FastAPI Backend | Python 3.12, uvicorn, port 8745 | API routing, AI orchestration, data persistence |
| Claude API | Anthropic `claude-sonnet-4-6` | AI responses, tool call decisions |
| World API | EVE Frontier (utopia / stillness) | Live solar systems, ship types, tribe data |
| Sui Testnet | GraphQL + RPC | Assembly state, ownership, access control, killmails |
| Galaxy DB | SQLite (local, pre-built) | 24,426 systems, gate topology, celestials |
| AccessRegistry | Sui Move contract | Per-structure on-chain access control |

---

## Major Components (Backend)

```
src/
 ├── endpoints/          HTTP route handlers — one file per feature area
 ├── ai_tools.py         Claude tool registry: definitions, schemas, handlers
 ├── context_builder.py  Assembles the AI context block per request
 ├── world_api.py        EVE Frontier World API client
 ├── galaxy_db.py        SQLite query interface for universe data
 ├── route_engine.py     Dijkstra pathfinding over gate graph
 ├── blockchain_killmails.py  Incremental killmail sync from Sui events
 ├── blockchain_queries.py    Sui RPC: tier resolution, registry reads
 ├── entity_resolver.py  Resolves entity names/types; prewarms from Sui GraphQL
 ├── graphql_queries.py  Named GraphQL queries + per-tenant config
 ├── intel_store.py      Pilot-reported per-structure intelligence (write/read)
 ├── log_intel_store.py  Per-system intel accumulated from log uploads
 ├── log_analysis.py     Log parsing: timeline builder, event annotator
 ├── log_parsers.py      Strict format validators; unknown lines are dropped
 ├── memory_store.py     Per-structure event memory (JSONL + rolling summary)
 ├── session_store.py    Per-pilot session state
 ├── ssu_poller.py       Background SSU state polling
 ├── huginn_news_task.py Periodic Huginn Signal (AI broadcast) generation
 ├── threat_assessment.py Threat scoring for systems and entities
 ├── ship_profile.py     Ship + fuel catalog; jump range and budget calc
 ├── config.py           Network config; maps DEPLOYMENT_ENV → URLs and package IDs
 └── tx_builders/        Unsigned Sui PTB construction (gate link/unlink)
```

---

## Key Data Flows

### Companion chat (primary flow)

```
Pilot types a message
  → POST /companion/stream
  → Backend reads Sui AccessRegistry → resolves tier (OWNER/TRIBE/VETTED/NONE)
  → context_builder.py assembles context block:
        current location, structure fuel/status, recent kills,
        pilot session history, access tier
  → Claude API receives: system prompt + context + tool definitions + message history
  → Claude replies in-character; may call tools:
        get_system_intel   → World API + Galaxy DB
        assess_threat      → threat_assessment.py
        plan_route         → route_engine.py
        query_intel        → intel_store.py (field reports from pilots)
        log_intel          → write a new field report
  → Tool results injected; Claude continues
  → Response streamed via SSE back to frontend
  → Frontend renders chunks incrementally in terminal UI
```

### Session bootstrap

```
Player opens SSU in-game
  → Browser loads /?itemId=...&tenant=...
  → DApp Kit derives Sui object ID from itemId (BCS encoding, src/bcs_encoding.py)
  → Sui GraphQL: assembly state + owner character (single query, polled every 10s)
  → Frontend: POST /session/register (wallet address, character name)
  → Backend: create or load session, return initial context
```

### Intel accumulation (log upload)

```
Pilot uploads game logs (Gamelogs/ and Chatlogs/ files)
  → POST /logs/upload
  → log_parsers.py: strict validators extract recognized events (unknown lines dropped)
  → log_analysis.py: build per-system timeline, annotate event types
  → Claude summarizes events per system
  → log_intel_store.py: persist per-system intelligence keyed by wallet address
  → Future: query_intel tool surfaces this data automatically in companion chat
```

### Kill feed sync (background, hourly)

```
killmail_refresh_loop() (started at server startup)
  → Sui RPC: query KillmailCreatedEvent from EVE Frontier package
  → Incremental: load known event keys, fetch newest-first, stop at first known
  → Append new killmails to data/{env}/killmails.jsonl
```

### SSU state watcher (background)

```
ssu_watcher_task.run_forever()
  → Polls on-chain SSU state at configured interval
  → Compares to last known state
  → On change: pushes alert to SSE queues of subscribed clients
```

---

## External Integrations

| Service | Direction | What it provides |
|---------|-----------|-----------------|
| World API (utopia / stillness) | Backend reads | Solar system metadata, ship types, tribe data, player location (JWT-gated) |
| Sui Testnet GraphQL | Frontend (DApp Kit) + Backend | Assembly state, ownership, fuel, entity types |
| Sui Testnet RPC | Backend reads | KillmailCreatedEvent stream, AccessRegistry object |
| AccessRegistry (Move contract) | Backend reads | Pilot access tier per structure |
| Claude API | Backend writes | AI responses and tool call orchestration |

**Transaction building:** The backend has a `/tx/build` endpoint that constructs unsigned Sui PTBs (programmable transaction blocks) for game actions (currently: gate link/unlink). The wallet on the frontend signs and submits — the backend never holds private keys.

---

## Blockchain Role

HUGINN is built on Sui. The integration has two parts:

**Reading (active):** The backend reads Sui for kill events, assembly state, and access control tier resolution. The frontend reads assembly and ownership data via DApp Kit's GraphQL hooks. All reads are unauthenticated (public chain state).

**Writing (in development):** A deployed Move smart contract (`move/access_registry/`) manages per-structure access lists on-chain. Structure owners currently manage this directly via their Sui wallets. The backend has transaction-building infrastructure (`src/tx_builders/`) for future admin UI support. Future versions will expand on-chain writes.

---

## Access Control Model

Access tier is resolved per-request from the on-chain AccessRegistry. No session token elevates access — every call is independently checked.

| Tier | Who | What they can access |
|------|-----|---------------------|
| OWNER | The wallet that owns the SSU | Full access, all tools, all data |
| TRIBE | Addresses in the owner's tribe list | Full vitals and intel |
| VETTED | Addresses explicitly added by owner | Read access |
| NONE | Everyone else | Public geography, lobby persona only |

---

## Deployment

Single VPS. FastAPI serves both the API and the built frontend as static files.

```
python main.py          # starts uvicorn on port 8745
                        # serves /static/companion/ → built React app
                        # serves /app/ → frontend/dist/
```

Frontend build:
```
cd frontend && npm run build && cp -r dist/* ../static/companion/
```

Two environments are supported via `DEPLOYMENT_ENV` in `.env`:
- `utopia` — EVE Frontier test environment
- `stillness` — EVE Frontier staging/live environment
