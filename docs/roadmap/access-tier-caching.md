# Roadmap: Access Tier Caching

## Problem

Every `/companion/stream` request (primary companion chat flow) makes a blocking Sui Testnet RPC call to resolve the pilot's access tier (OWNER/TRIBE/VETTED/NONE) before `context_builder.py` runs. This is the single item in the pre-Claude hot path that is an external network call.

- Adds ~100–400ms to first-token latency on every chat turn, felt by the pilot as a stall before each response
- Sui Testnet has no SLA — degradation or downtime breaks companion chat entirely
- At N concurrent pilots, generates N×M RPC calls per unit time (N pilots × M messages per session)
- Acknowledged in KEY_CONCEPTS_AND_DECISIONS.md as "simply how it was built," not a deliberate zero-trust design

The current design is not zero-trust: the wallet address is self-reported by the client at session registration and trusted thereafter. The per-request RPC checks a public access list against that trusted address — it does not cryptographically re-verify identity per request. Caching does not reduce the security model.

Tier data changes on a timescale of hours to days. Checking it on every chat message is a frequency mismatch.

---

## Recommended Fix

**Resolve tier once at `/session/register`. Cache it in the session file. Serve from session on `/companion/stream`. Expire by TTL with lazy background refresh.**

### Why this approach

- `/session/register` is the natural wallet-identity join point — pilot wallet address is already established there
- Session files (`data/{env}/sessions/*.json`) already hold pilot-scoped state (ship profile, history). Tier is pilot-scoped state — it belongs there
- No new data structures, no new background tasks, no new files
- Zero changes to: AccessRegistry contract, frontend flows, session model, on-chain model
- Inspectable: any session JSON can be read to see the cached tier and its timestamp
- Survives server restart (tier is in the session file, not only in-process RAM)

### What changes

- `session_store.py`: add `resolved_tier` and `tier_resolved_at` fields to session model
- `/session/register` handler: call `blockchain_queries.py` to resolve tier, write into session
- `/companion/stream` handler: read tier from session instead of calling `blockchain_queries.py`
- TTL logic: on expiry, serve stale tier and fire background re-resolution (FastAPI background task); write result back to session file

---

## Consistency Window

Default TTL: 5 minutes. Shorter for OWNER-tier reads if needed.

| Scenario | Impact | Severity |
|----------|--------|----------|
| Pilot added to vetted mid-session | Waits up to TTL for access grant | Low — can re-register session |
| Pilot removed from vetted mid-session | Retains VETTED access for up to TTL | Low — intel data, not key material |
| SSU ownership transfer | Old owner retains OWNER access for up to TTL | Medium — rare event; mitigate with session purge endpoint |
| Sui RPC degraded during refresh | Stale tier continues to be served | Better than current (current: hard failure) |
| Server restart | Session files survive; timestamps may indicate expired, triggering one re-resolution | No regression vs current |

---

## Implementation Phases

**Phase 1 — Remove RPC from hot path**
Add `resolved_tier` + `tier_resolved_at` to session model. Resolve at `/session/register`. Read from session on `/companion/stream`. No TTL logic yet — any cached tier is served. This alone eliminates the RPC from the hot path for all returning pilots.

**Phase 2 — TTL and lazy refresh**
Add TTL expiry check on `/companion/stream`. On expiry: serve stale tier immediately, dispatch background re-resolution, write result back to session file. This makes the behavior production-safe with an explicit consistency window.

**Phase 3 — Owner-triggered invalidation**
Add OWNER-gated endpoint to purge and refresh tier cache for active sessions on a given structure. Handles ownership transfers and emergency revocations without waiting for TTL.

**Phase 4 — Observability**
Surface `resolved_tier` and `tier_resolved_at` in admin panel and debug session logs. Data already exists in session files; this is just display.

**Phase 5 — Future only if multi-VPS**
If session storage migrates from per-pilot JSON to SQLite (natural evolution path noted in KEY_CONCEPTS_AND_DECISIONS.md), `resolved_tier` becomes a column. Mechanical migration, no logic change.

---

## Files Affected (Phases 1–2)

| File | Change |
|------|--------|
| `src/session_store.py` | Add `resolved_tier`, `tier_resolved_at` fields |
| `src/endpoints/session.py` | Call tier resolution at registration, write to session |
| `src/endpoints/companion.py` | Read tier from session instead of calling `blockchain_queries.py` |
| `src/blockchain_queries.py` | No structural change — still owns RPC logic, just called less frequently |

No other files require changes for Phases 1–2.

---

## Constraints

- Hackathon submission branch is frozen (deadline March 31, 2026). All work on a new post-hackathon branch.
- Single VPS, single process — no shared cache needed. In-process session state is sufficient.
- Do not modify the AccessRegistry Move contract, the frontend session bootstrap, or dapp-kit integration.
