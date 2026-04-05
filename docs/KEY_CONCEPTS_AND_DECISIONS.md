# Key Concepts and Architectural Decisions

This document covers the decisions and trade-offs behind the current architecture — both deliberate choices and things that were built a particular way for MVP speed. An engineer extending the system should understand which is which.

---

## The backend is stateful

The backend persists data to disk continuously. It is not stateless.

File-based state includes: per-pilot sessions, per-structure event memory, per-system log intel, the kill feed, and the system knowledge graph. All writes go to `data/{env}/` on the local filesystem.

What IS per-request (not cached) is **access tier resolution**: every companion chat request re-reads the on-chain AccessRegistry to determine the pilot's tier (OWNER / TRIBE / VETTED / NONE). There is no session token that elevates access between requests. This is not a deliberate zero-trust security design — it is simply how it was built. The practical effect is that tier changes (e.g. a pilot added to the vetted list) take effect on the next request with no cache invalidation needed.

---

## Multi-tenant architecture

Two EVE Frontier environments exist: `utopia` (test) and `stillness` (staging/live). A single running server instance handles one environment, selected by the `DEPLOYMENT_ENV` environment variable.

`DEPLOYMENT_ENV` controls:
- Which World API base URL is used
- Which Sui package IDs are used for contract reads
- Where in `data/` runtime files are stored (`data/utopia/` vs `data/stillness/`)

If the env var is missing or unknown, the backend falls back to `utopia`. Frontend passes a `tenant` parameter on most requests so the backend can route correctly even if `DEPLOYMENT_ENV` differs.

---

## Data format choices

Three formats are used. The choice in each case was practical rather than principled:

**SQLite** — used where structured queries are needed: the galaxy database (geography lookups, system search) and the system knowledge graph (cross-system enemy/ore aggregation). Galaxy DB is read-only at runtime; system_knowledge uses WAL mode for concurrent access.

**JSONL** — used for append-only event streams: the kill feed (`killmails.jsonl`) and per-structure memory. New records are appended; nothing is updated in place. Simple, grep-able, no schema migration needed.

**Flat JSON files** — used for small, infrequently-written sets: structure configs (`data/structures/*.json`) and per-pilot sessions (`data/{env}/sessions/*.json`). One file per entity. Simple to inspect, trivial to edit manually.

None of these preclude a future migration to a proper database. There is no PostgreSQL dependency to add — the existing SQLite schema in `system_knowledge.py` is the closest thing to a real schema and would translate directly.

---

## Log parser: unknown lines are dropped

The log parsers (`src/log_parsers.py`) use strict format validators. Any line that does not match a known pattern is silently dropped before events reach Claude.

This serves two purposes:
1. **Security boundary:** Raw chat messages and unrecognized log content never reach the AI.
2. **Quality gate:** Claude only sees structured, typed events — no free-text noise.

The practical limitation is that the game generates log lines for entity types the parser doesn't know yet: other players, player ships, player-owned structures. These are currently dropped rather than parsed. The approach for handling this is incremental: as unknown entity samples are collected in production, they are categorized and the parser is updated to cover them. The parser is not considered finished.

---

## SSE over WebSockets for chat streaming

Companion chat responses are streamed via Server-Sent Events (SSE) on `POST /companion/stream`. SSE is unidirectional (server → client), which is sufficient for chat: the client sends one request, the server streams one response.

WebSockets were not used. SSE is simpler to implement, works over standard HTTP, and is natively supported in the in-game Chromium browser. This was an MVP simplicity choice, not a capability limit. WebSockets remain an option if bidirectional push is needed in the future (e.g. real-time alerts without a dedicated watcher stream).

---

## Unsigned PTBs: why the backend never signs

The backend builds unsigned Sui programmable transaction blocks (PTBs) for game actions. The wallet signs and submits — the backend does not.

This is a Sui architecture constraint, not a deliberate security decision. The backend has no wallet private keys and cannot sign on behalf of a user. The `src/tx_builders/` module constructs the transaction structure and returns it to the frontend; the user's connected wallet approves and submits it.

The same pattern applies to any future on-chain writes.

---

## Claude model is a variable

The Claude model used for companion chat and log analysis defaults to `claude-sonnet-4-6`. It is configurable via the `CLAUDE_MODEL` environment variable. This is not a fixed choice — model selection will be revisited to optimize cost as the system matures. Smaller or cheaper models may be used for lower-stakes calls (log summarization, news generation) while reserving more capable models for companion chat.

---

## The dapp-kit boundary

`@evefrontier/dapp-kit` is the official EVE Frontier React SDK. It owns all access to game object state: assembly data, ownership, fuel, type metadata. **The backend does not re-implement these.** There is a documented history of backend code duplicating dapp-kit functionality — this is a known failure mode. See `docs/DAPP_KIT_BOUNDARY.md` for the full decision table before adding any new data access code.

The backend owns: AI chat, galaxy geography, derived fuel metrics (hours remaining, burn rate), social boards, and session management. dapp-kit cannot do any of these.

---

## Known areas flagged for change

These are not bugs — they are MVP decisions that work but will be revisited:

| Area | Current state | Known direction |
|------|--------------|-----------------|
| **UI components** | TerminalUI, TurretUI, GateUI are functional | Likely to be substantially revised or rebuilt. Sizes, layout, and visual design are all in scope for change. |
| **Log parser** | Drops unknown entity types | Incrementally improved as new entity samples are discovered in production. |
| **Claude model selection** | `claude-sonnet-4-6` everywhere | Will be tuned per use-case for cost. |
| **Feature completeness** | All features are WIP | Closest to done: recon, route planning, log ingest. All need polish. |
| **Single VPS** | No HA, no redundancy | Sufficient for current scale. Not designed to be permanent. |
| **Access tier caching** | Per-request Sui reads | No caching today. May become a bottleneck at scale. |
