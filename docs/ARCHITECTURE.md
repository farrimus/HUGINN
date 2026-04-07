# Architecture — HUGINN

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

## Backend (FastAPI / Python)

**Entry point:** `main.py`
**Source:** `src/`

### Endpoint Routers

| Router file | Key endpoints |
|-------------|--------------|
| `companion.py` | `POST /companion/stream` — primary AI chat (SSE), `POST /companion/chat` — non-streaming |
| `structures.py` | `GET /structure/{id}`, `PATCH /structure/{id}`, `GET /structure/{id}/onchain`, location management |
| `search.py` | `GET /structures` — list, `POST /search/radius` |
| `navigation.py` | `POST /route` — pathfinding, `GET /systems/names` |
| `session.py` | Session management per wallet |
| `watcher.py` | Structure state change alerts |
| `courier.py` | Hauling contract board |
| `tribe.py` / `tribe_posts.py` | Tribe presence and posts |
| `logs.py` | Game client log upload and analysis |
| `news.py` | Huginn signal broadcast |
| `admin.py` | Admin panel endpoints (OWNER-gated) |
| `transactions.py` | `POST /tx/build` — unsigned Sui PTB builder |

### Key Modules

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

### AI Tools

Registered in `src/ai_tools.py`. Claude may call these mid-conversation:
- `get_system_intel` — Galaxy DB + World API for a solar system
- `query_intel` / `log_intel` — Read/write pilot-reported intel
- `assess_threat` — Threat assessment for a system or entity
- `plan_route` — Pathfinding between two systems

---

## Prompt Layer

All prompt content lives in `prompts/`. Five files with distinct jobs:

| File | Purpose |
|------|---------|
| `prompts/companion.md` | HUGINN system prompt: persona, tier enforcement, tool discipline, output style. Loaded at startup; passed as `system` to the Claude API on every request. |
| `prompts/tools.yaml` | Per-tool prompt fragments. Loaded live on each request. Overrides hardcoded descriptions in `ai_tools.py`. Falls back to hardcoded values if a section is absent. |
| `prompts/TOOLS_YAML_GUIDE.md` | Builder's guide for `tools.yaml` — documents every field, the full tool access pipeline, and the procedure for adding new tools. Read this before editing the tool system. |
| `prompts/huginn_news.md` | System prompt for the Huginn Signal broadcast (AI-generated news). Used by `huginn_news.py`. |
| `prompts/logs.md` | System prompt for game log analysis. Used when parsing player-uploaded Gamelogs. |

### Tool access pipeline

Before Claude sees any tool, three gates apply in order:

1. **`src/tier_capabilities.py`** — primary access gate. `blocked_tools(tier, all_names)` returns every tool name not in that tier's `tools` list. A tool absent from the tier's list is completely invisible to Claude. `default_enabled` in `ai_tools.py` is a documentation hint only.
2. **`disabled_tools`** in the request body — tools the frontend has toggled off (via `frontend/src/features/featureFlags.ts` → `getDisabledTools()`). Added to the blocked set.
3. **`get_tools_for_claude(disabled=combined_blocked)`** — builds the final schema list sent to Claude.

To add a new tool: register it in `ai_tools.py` → add it to tier lists in `tier_capabilities.py` → add a section in `tools.yaml`. See `prompts/TOOLS_YAML_GUIDE.md` for the complete procedure.

### tools.yaml fields

Each tool entry in `tools.yaml` may have up to four fields:

| Field | Where it goes | Effect |
|-------|--------------|--------|
| `description` | Claude's tool schema | Controls when Claude decides to call this tool. Overrides the hardcoded description in `ai_tools.py`. |
| `response_guidance` | Prepended to the tool result | Injected at `companion.py:688–690` before the result is sent back to Claude. Shapes how Claude formats and uses the tool output. This is the output enrichment layer — not the system prompt. |
| `no_result` | Returned as tool result | What Claude receives when a tool finds nothing. Used by `assess_threat` and `query_intel`. |
| `no_system` | Returned as tool result | What Claude receives when no system context is set. Used by `get_system_intel`, `radius_search`, `plan_route`. |

### Why response_guidance is not in the system prompt

The system prompt sets persona and doctrine once. `response_guidance` is per-tool and per-result — it tells Claude how to present *this specific data* from *this specific call*. Putting per-tool formatting rules in the system prompt makes it unreadable and harder to tune independently.

### Live-reload behavior

`tools.yaml` is read on every request — no restart needed to change tool behavior. Edit `prompts/tools.yaml` and the next request picks up the change.

`companion.md` is loaded at startup (`COMPANION_SYSTEM_PROMPT` constant in `companion.py`). Changes require a restart.

### The rule for coding agents

If you want to change how HUGINN responds after a tool call — edit `tools.yaml`. Do not add formatting logic to `ai_tools.py`, do not add per-tool rules to `companion.md`. The YAML is the right layer.

---

## Frontend (React / TypeScript)

**Source:** `frontend/src/`
**Entry point:** `frontend/src/main.tsx`
**Build:** `npm run build` → `frontend/dist/` → copied to `static/companion/`
**Served by:** FastAPI `StaticFiles` at `/static/companion/`

### Setup (main.tsx)

```typescript
import { EveFrontierProvider } from '@evefrontier/dapp-kit';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';

createRoot(root).render(
  <QueryClientProvider client={queryClient}>
    <EveFrontierProvider queryClient={queryClient}>
      <App />
    </EveFrontierProvider>
  </QueryClientProvider>
);
```

### Wallet Connection

Uses `@evefrontier/dapp-kit` — the official EVE Frontier React SDK. The in-game browser exposes the EVE Frontier Client Wallet via the Wallet Standard. DApp Kit discovers and connects to it automatically.

```typescript
const { connect, disconnect, currentAccount } = useConnection();
```

No `window.ethereum`. No custom auth. DApp Kit handles everything.

### Assembly Data

When the URL includes `?itemId=...&tenant=...`, `EveFrontierProvider` automatically:
1. Reads the URL params
2. Derives the Sui object ID (via BCS encoding)
3. Fetches assembly + owner character in one GraphQL call
4. Polls for updates every **10 seconds**
5. Provides data via `useSmartObject()` hook

```typescript
const { assembly, assemblyOwner, loading, error } = useSmartObject();
```

### Source Structure

```
frontend/src/
├── main.tsx              — App entry point, provider setup
├── App.tsx               — Root component, routing
├── components/           — UI panels (TerminalUI, GateUI, TurretUI, InfoPanel, etc.)
├── hooks/                — Custom hooks (useCompanionStream, useWatcherAlerts, useToolOutput, useTribePosts, useSystemNames, useSession)
├── context/              — EntityContext and other shared state
├── styles/               — CSS files (terminal theme, panels)
├── types/                — TypeScript type definitions
├── constants/            — App-wide constants (viewport-calibrated divider strings, etc.)
├── features/             — Feature flags
└── data/                 — Static data assets
```

### Build and Deployment

```bash
cd frontend
npm install
npm run build                        # Compiles to dist/
cp -r dist/* ../static/companion/    # Deploy to FastAPI static mount
```

**Critical:** `vite.config.ts` sets `base: '/static/companion/'` so all asset paths are correct after deploy.

---

## Data Sources

| Source | What it provides | Auth |
|--------|-----------------|------|
| World API (utopia/stillness) | Solar systems, types, ships, tribes, player jumps | None / Bearer JWT for jumps |
| Sui GraphQL (testnet) | Assembly on-chain state, ownership, fuel | None (public) |
| `@evefrontier/dapp-kit` | Assembly + character data via React hooks | SDK-managed |
| Galaxy DB (`data/eve_universe.db`) | Pre-built: 24,426 systems, gate topology, celestials | Local SQLite |

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
  → query_intel tool surfaces this data automatically in companion chat
```

### Kill feed sync (background, hourly)

```
killmail_refresh_loop() — started at server startup
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

**Reading (active):** The backend reads Sui for kill events, assembly state, and access control tier resolution. The frontend reads assembly and ownership data via DApp Kit's GraphQL hooks. All reads are unauthenticated (public chain state).

**Writing (in development):** A deployed Move smart contract (`move/access_registry/`) manages per-structure access lists on-chain. Structure owners currently manage this directly via their Sui wallets. The backend has transaction-building infrastructure (`src/tx_builders/`) for future admin UI support.

---

## AI Context Pipeline

```
Pilot sends message
    ↓
context_builder.py assembles context block:
    - Current location (system, region, security status)
    - Structure state (fuel, online/offline, assembly types)
    - Recent alerts and killmails
    - Pilot identity and access tier
    ↓
Claude API receives: system prompt + context + tool definitions + message history
    ↓
Claude responds in-character, optionally calling tools for live data
    ↓
Response streams via SSE to frontend
    ↓
Frontend renders chunks incrementally in terminal UI
```

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
