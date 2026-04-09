# Key Concepts and Architectural Decisions

---

## The backend is stateful

The backend persists data to disk continuously. It is not stateless.

File-based state includes: per-pilot sessions, per-structure event memory, per-system log intel, the kill feed, and the system knowledge graph. All writes go to `data/{env}/` on the local filesystem.

**Access tier resolution is per-request:** every companion chat request re-reads the on-chain AccessRegistry to determine the pilot's tier (OWNER / TRIBE / VETTED / NONE). There is no session token that elevates access between requests. Tier changes (e.g. a pilot added to the vetted list) take effect on the next request with no cache invalidation needed.

---

## Multi-tenant architecture

Two EVE Frontier environments exist: `utopia` (test) and `stillness` (staging/live). A single running server instance handles one environment, selected by the `DEPLOYMENT_ENV` environment variable.

`DEPLOYMENT_ENV` controls:
- Which World API base URL is used
- Which Sui package IDs are used for contract reads
- Where in `data/` runtime files are stored (`data/utopia/` vs `data/stillness/`)

If the env var is missing or unknown, the main application falls back to `utopia`. Exception: the background tasks `huginn_news_task.py` and `blockchain_killmails.py` default to `stillness` when `DEPLOYMENT_ENV` is unset. Frontend passes a `tenant` parameter on most requests so the backend can route correctly even if `DEPLOYMENT_ENV` differs.

---

## Data format choices

Three formats are in use:

**SQLite** — where structured queries are needed: the galaxy database (geography lookups, system search) and the system knowledge graph (cross-system enemy/ore aggregation). Galaxy DB is read-only at runtime; system_knowledge uses WAL mode for concurrent access.

**JSONL** — append-only event streams: the kill feed (`killmails.jsonl`) and per-structure memory. New records are appended; nothing is updated in place.

**Flat JSON files** — small, infrequently-written sets: structure configs (`data/structures/*.json`) and per-pilot sessions (`data/{env}/sessions/*.json`). One file per entity.

---

## Log parser: unknown lines are dropped

The log parsers (`src/log_parsers.py`) use strict format validators. Any line that does not match a known pattern is silently dropped before events reach Claude.

This serves two purposes:
1. **Security boundary:** Raw chat messages and unrecognized log content never reach the AI.
2. **Quality gate:** Claude only sees structured, typed events — no free-text noise.

The practical limitation is that the game generates log lines for entity types the parser doesn't know yet: other players, player ships, player-owned structures. These are currently dropped rather than parsed. The approach for handling this is incremental: as unknown entity samples are collected in production, they are categorized and the parser is updated to cover them.

---

## SSE for chat streaming

Companion chat responses are streamed via Server-Sent Events (SSE) on `POST /companion/stream`. SSE is unidirectional (server → client): the client sends one request, the server streams one response.

---

## Unsigned PTBs

The backend builds unsigned Sui programmable transaction blocks (PTBs) for game actions. The wallet signs and submits — the backend does not and cannot: it holds no private keys. The `src/tx_builders/` module constructs the transaction structure and returns it to the frontend; the user's connected wallet approves and submits it.

---

## Claude model

The Claude model used for companion chat and log analysis defaults to `claude-sonnet-4-6`. Configurable via the `CLAUDE_MODEL` environment variable.

---

## The dapp-kit boundary

`@evefrontier/dapp-kit` is the official EVE Frontier React SDK. It owns all access to game object state: assembly data, ownership, fuel, type metadata. **The backend does not re-implement these.** The decision table is in `CLAUDE.md` — Data Layer Boundary section.

The backend owns: AI chat, galaxy geography, derived fuel metrics (hours remaining, burn rate), social boards, and session management. dapp-kit cannot do any of these.

