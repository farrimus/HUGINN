# Architecture — EVE Frontier Companion

## System Overview

```
In-game browser
    └── React app (TypeScript + DApp Kit)
            └── FastAPI backend (Python 3.12, port 8745)
                    ├── Claude API  — AI responses, streaming, tool calls
                    ├── World API   — Live EVE Frontier game state
                    └── Galaxy DB   — 24,426 systems, gate topology (SQLite)
```

When a pilot opens an assembly in-game, the browser navigates to the app with `?itemId=...&tenant=...`. The React app loads, connects the wallet via DApp Kit, and begins streaming AI context.

---

## Backend (FastAPI / Python)

**Entry point:** `main.py`
**Source:** `src/`

### Endpoint Routers

| Router file | Key endpoints |
|-------------|--------------|
| `companion.py` | `POST /companion/stream` — primary AI chat (SSE), `POST /companion/chat` — non-streaming |
| `structures.py` | `GET /structure/{id}`, `POST /structure-chat` |
| `search.py` | `GET /structures` — list, `POST /search/radius` |
| `navigation.py` | `POST /route` — pathfinding, `GET /systems/names` |
| `session.py` | Session management per wallet |
| `watcher.py` | Structure state change alerts |
| `courier.py` | Hauling contract board |
| `tribe.py` / `tribe_posts.py` | Tribe presence and posts |
| `logs.py` | Game client log upload and analysis |
| `news.py` | Huginn signal broadcast |

### Key Modules

- `src/claude_client.py` — Prompt construction, tool registration, streaming to Claude API
- `src/context_builder.py` — Assembles game state into AI context block (≤2000 chars)
- `src/world_api.py` — EVE Frontier World API client (solar systems, ships, tribes, jumps)
- `src/galaxy_db.py` — SQLite query interface for pre-built universe database
- `src/route_engine.py` — BFS/Dijkstra pathfinding over gate topology
- `src/intel_store.py` — Pilot-reported field intelligence, per-structure JSON

### AI Tools

Registered in `src/ai_tools.py`. Claude may call these mid-conversation:
- `get_system_intel` — Galaxy DB + World API for a solar system
- `query_intel` / `log_intel` — Read/write pilot-reported intel
- `assess_threat` — Threat assessment for a system or entity
- `plan_route` — Pathfinding between two systems

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
├── hooks/                — Custom hooks (useCompanionStream, useStructureChat, etc.)
├── context/              — EntityContext and other shared state
├── styles/               — CSS files (terminal theme, panels)
├── types/                — TypeScript type definitions
├── constants/            — App-wide constants
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

## Security Model

Access to structure data is tiered:
- **OWNER** — full access, all tools available
- **TRIBE** — same tribe as owner, read access
- **VETTED** — explicitly listed, read access
- **NONE** — minimal public data only

The tier is determined per-request from the on-chain `AccessRegistry` object associated with each assembly.
