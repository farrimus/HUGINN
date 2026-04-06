# Data Layer Architecture — Post-Hackathon

## Store Inventory

| Store | Format | Key | AI Access | Compounds? |
|-------|--------|-----|-----------|------------|
| `system_knowledge.db` | SQLite WAL | system_name | No tools yet | Designed to — nothing feeds it |
| `memory_store/` | JSONL + rolling JSON | structure_id | Unknown | Per-structure only |
| `log_intel/` | JSONL | **wallet** (wrong) | Not wired | Zero — siloed by pilot |
| `sessions/` | Flat JSON | wallet | N/A (infra) | N/A |
| `structures/*.json` | Flat JSON | git commit | N/A (config) | N/A |

---

## Per-Store Findings

### `system_knowledge.db`
- Best-designed store. WAL mode correct for concurrent-read / occasional-write. Schema is clean; KEY_CONCEPTS notes direct PostgreSQL translation path.
- Nothing feeds it yet. Strategic ceiling is highest in the system — indexed SQL enables cross-system queries no other store can answer.
- SQLite single-writer ceiling matters only if multiple background tasks write simultaneously at volume. Not a current risk.

### Per-Structure Memory (`memory_store/`)
- Dual-format (raw JSONL + rolling summary) creates divergence risk if summarization is interrupted. No automated consistency check.
- Huginn Signal synthesis reads all structure memories — O(structures) full-file scan on every broadcast. No bound unless Signal scopes to active structures.
- Concurrent companion chat + SSU watcher touching the same structure's summary JSON = read-modify-write race. Untested.
- Intelligence siloed per structure. Cross-structure queries require full directory scan.

### `log_intel/` (per-wallet JSONL)
- **This is the most misaligned store.** Data is keyed by *who contributed it*, not by *what was observed*.
- `query_intel` tool must answer "what do pilots know about System X?" — that requires scanning every wallet file. O(pilots) per tool call.
- Every additional log upload increases the migration cost. Delay compounds the debt.
- The collection mechanism (parsing, Claude summarization) is correct. The storage topology is wrong.

### Sessions
- Access tier resolved via Sui RPC on every `/companion/stream` request. External dependency on critical path. Sui testnet degradation = companion chat failure.
- Read-modify-write on session JSON is not atomic. Two simultaneous requests for the same pilot = lost update. Plausible under async load.
- No TTL cleanup. Dead sessions accumulate.

### `structures/*.json`
- Git-commit-to-register is the right model for a single owner-operator. It is a growth ceiling: every new structure owner requires a developer action.
- Read-only at runtime. No concurrency risk. Trivial migration to a SQLite table when self-service registration becomes needed.

---

## Evolutionary Path

**1. Re-key `log_intel` from wallet to system.**
Structural inversion. Must be fixed before `query_intel` tool is implemented, or that tool degrades proportionally with pilot count. One-time offline transformation — read all wallet files, reorganize by system, write new structure. No downtime required.

**2. Cache access tier in session at registration.**
Eliminates Sui RPC from hot path. 2–5 minute TTL in session file. No new infrastructure. Tradeoff — tier changes take up to TTL to propagate — is acceptable because the current per-request model is explicitly not zero-trust security.

**3. Move `structures/*.json` to a SQLite table.**
`system_knowledge.db` is the natural home. Import existing JSON files as initial state. Enables self-service structure registration without developer involvement. Prerequisite for organic network growth.

**4. Wire `log_intel` and per-structure memory into `system_knowledge.db`.**
Incremental. One table at a time, old files retained as backup during transition. Enables cross-store queries. Prerequisite for Huginn Signal rewire.

**5. Add session TTL cleanup.**
Background maintenance task. Lowest urgency — defer until pilot count makes dead session accumulation visible.

---

## Risk Table

| Risk | Before | After |
|------|--------|-------|
| `query_intel` tool: O(pilots) scan per call | Scales linearly with pilot count | Single indexed lookup |
| Sui RPC on every chat message | External latency + testnet outage = chat failure | Cache hit >95%; Sui outages no longer block |
| Structure owner self-registration blocked | All onboarding requires developer commit + restart | Self-serve via API |
| Huginn Signal O(structures) fan-out | Degrades linearly with structure count | Queryable SQLite replaces per-file reads |
| Per-structure memory/summary race | Untested edge case under concurrent load | SQLite WAL serializes all writes atomically |

---

## Strategic Questions

**1. Is cross-pilot system intelligence (`query_intel`) the primary value driver?**
If yes, log_intel re-keying is a blocker and migration cost grows every week. If secondary to route planning and recon, urgency is lower.

**2. What is expected structure and pilot count at 60 and 120 days?**
Fast growth (dozens of structures, hundreds of pilots) makes the Sui RPC bottleneck and Signal fan-out urgent simultaneously. Slow growth makes them sequential.

**3. Is Huginn Signal scoped to active/subscribed structures, or does it read all?**
If bounded by subscription, the O(structures) fan-out problem may never materialize. If it reads all structures, it is an unbounded I/O accumulation. Current documentation does not answer this.

---

## Watch Items (Not Urgent)

- **dapp-kit boundary:** 9 known violations. Each one adds data access surface not owned by the authoritative layer. Enforce the boundary document under post-hackathon velocity pressure.
- **SQLite write ceiling:** If killmail sync + log processing + SSU polling + Signal generation all write to `system_knowledge.db` concurrently at volume, WAL serialization latency becomes visible. Mitigation: write batching, not store migration.
- **No backup automation:** All stores are local files on a single VPS. Total data loss on disk failure. Acceptable at MVP; becomes a strategic risk as the knowledge graph accumulates value.
