# Tech Stack and Dependencies

This document covers what the project uses, what versions are pinned, and — where known — why. Most choices were made under hackathon velocity constraints and are not fixed architectural decisions. Where a choice is genuinely open to change, that is noted.

---

## Backend (Python)

| Package | Version | Purpose |
|---------|---------|---------|
| `fastapi` | 0.115.0 | HTTP framework. Async, auto-generates OpenAPI, straightforward route registration. |
| `uvicorn[standard]` | 0.30.0 | ASGI server. Runs FastAPI. `[standard]` adds websocket and HTTP/2 support. |
| `httpx` | 0.27.0 | Async HTTP client. Used for all outbound calls: World API, Sui RPC. |
| `anthropic` | 0.34.0 | Official Anthropic SDK. Streaming tool-use calls to Claude API. |
| `python-dotenv` | 1.0.0 | Loads `.env` file into environment at startup. |
| `pyjwt` | 2.9.0 | JWT decoding. World API requires a JWT for player location endpoint. |
| `cryptography` | ≥42.0.0 | JWT signature verification dependency. |
| `python-multipart` | 0.0.9 | Required by FastAPI for `multipart/form-data` (log file uploads). |
| `pytest` | 8.3.0 | Test runner. |
| `pytest-asyncio` | 0.23.8 | Async test support for FastAPI endpoint tests. |

**Python version:** 3.12

**Why FastAPI over Flask/Django:** Selected during hackathon development. Async-native and lightweight — suited to a project with several concurrent background tasks (SSU poller, killmail sync, news task) and SSE streaming endpoints.

---

## Frontend (TypeScript / React)

| Package | Version | Purpose |
|---------|---------|---------|
| `react` | 19.2.4 | UI framework. |
| `react-dom` | 19.2.4 | DOM rendering. |
| `@evefrontier/dapp-kit` | ^0.1.0 | **Official EVE Frontier React SDK.** Wallet connection, Sui GraphQL hooks for assembly data, DApp-Kit-standard access patterns. This is not a discretionary choice — it is the prescribed integration point for EVE Frontier dApps. |
| `@tanstack/react-query` | ^5.0.0 | Server-state caching and async data fetching. Required peer dependency of dapp-kit. |
| `vite` | ^8.0.1 | Build tool and dev server. |
| `typescript` | ~5.9.3 | Type checking. |
| `patch-package` | ^8.0.1 | Applies local patches to `node_modules` packages. See note below. |

**Why React 19:** Current stable at the time of development. No alternative frameworks were evaluated.

### dapp-kit patch

`patch-package` is present because dapp-kit 0.1.7 shipped with a single-tenant assumption in its assembly registry cache (`getObjectId`). The registry address was stored in a single module-level variable, which meant the second tenant's registry would overwrite the first.

The patch (`patches/@evefrontier+dapp-kit+0.1.7.patch`) changes the cache to a `Record<string, string>` keyed by package ID, so utopia and stillness can coexist in the same session without collision. Applied automatically via the `postinstall` script.

---

## Data Layer

No external database server is required. All persistence is file-based.

| Store | Format | Used for |
|-------|--------|---------|
| `data/eve_universe.db` | SQLite | Galaxy geography: 24,426 solar systems, gate topology, celestials. Pre-built by `build_universe.py`. Read-only at runtime. |
| `data/{env}/system_knowledge.db` | SQLite (WAL mode) | Global system → enemy/ore knowledge graph. In progress. |
| `data/{env}/killmails.jsonl` | JSONL (append-only) | Kill feed, synced hourly from Sui. |
| `data/{env}/memory/` | JSONL + JSON (rolling) | Per-structure event memory and summary. |
| `data/{env}/log_intel/` | JSONL per wallet | Per-system intel accumulated from log uploads. |
| `data/{env}/sessions/` | JSON per pilot | Per-pilot session state: ship profile, interaction history, watch list. |
| `data/structures/*.json` | JSON | Per-SSU structure configuration. Committed; one file per registered structure. |
| `data/gate_graph.json` | JSON | Gate topology for pathfinding. Pre-built by `build_gate_graph.py`. |

SQLite was chosen where structured querying is needed. JSONL was chosen for append-only event streams. Flat JSON files were chosen for small, infrequently-written config sets. All choices reflect MVP constraints — no external DB server is a deployment simplicity win on a single VPS.

---

## External Services

| Service | How accessed | Notes |
|---------|-------------|-------|
| **Claude API** | `anthropic` SDK, streaming | Model: `claude-sonnet-4-6` by default. Configurable via `CLAUDE_MODEL` env var. Model selection will be revisited to optimize cost — `claude-sonnet-4-6` is not a fixed choice. |
| **EVE Frontier World API** | `httpx` async GET | Two base URLs: utopia / stillness, selected by `DEPLOYMENT_ENV`. Player location endpoint requires a JWT. Other endpoints are open. |
| **Sui Testnet GraphQL** | dapp-kit (frontend) + `httpx` (backend) | Assembly state, ownership, access control reads. Backend queries incrementally for killmail events. |
| **Sui Testnet RPC** | `httpx` | `KillmailCreatedEvent` stream. AccessRegistry object reads. |

---

## Infrastructure

Single VPS. FastAPI serves both the API (port 8745) and the built frontend as static files. No reverse proxy, no container orchestration, no CDN. Sufficient for current scale; not designed for high availability.

```
python main.py   # starts uvicorn on 0.0.0.0:8745
```

Frontend is built with Vite and served from `/static/companion/`. No Node.js process at runtime.
