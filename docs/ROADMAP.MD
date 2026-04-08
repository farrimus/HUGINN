# HUGINN Development Roadmap — Post-Hackathon

This is a pre-alpha hobby project. One developer. One real tester. The hackathon MVP shipped every planned feature — AI chat, on-chain access control, route planning, log upload, kill feed, SSU watcher, courier board, tribe presence — across two environments (utopia/stillness). Nothing is finished.

The one thing that matters most right now: the core intelligence premise — "every log upload adds to a shared, permanent knowledge base" — is currently false. Log data is collected and immediately siloed in per-wallet files with no read path into companion chat. That's the central problem this document is organized around.

The supporting analysis in `docs/roadmap/` explains why things are structured the way they are. Read those when working on the relevant area.

---

## Current State

### What is functional

| Feature | Status | Key files |
|---------|--------|-----------|
| AI companion chat (SSE streaming) | Functional | `endpoints/companion.py`, `ai_tools.py`, `context_builder.py` |
| On-chain access control | Functional, has known bug | Per-request Sui RPC; OWNER/TRIBE/VETTED/NONE |
| Route planner | Most complete feature | `route_engine.py` + `data/gate_graph.json` |
| Recon (system intel) | Functional | World API + Galaxy DB; kill context injected via `context_builder.py` |
| Kill feed sync | Functional | Hourly from Sui events; `blockchain_killmails.py` |
| Log upload | Write path functional; read path absent | Parse + summarize + store works; no AI tool to query it |
| SSU watcher | Functional | `ssu_watcher_task.py` SSE alert streams |
| Courier board | Functional | `endpoints/courier.py` |
| Tribe presence board | Functional | `endpoints/tribe.py`, `endpoints/tribe_posts.py` |
| Huginn Signal | Functional but narrow | Reads kills + structure state only; no log intel, no field reports |
| Multi-tenant (utopia/stillness) | Functional | `config.py`; dapp-kit patch for dual-registry cache |
| AccessRegistry Move contract | Deployed | Testnet; `move/access_registry/` |

### What was built for hackathon velocity

- **Per-request Sui RPC for access tier** — adds 100–400ms to every companion chat turn; Sui Testnet degradation is a hard failure.
- **`log_intel` keyed by wallet, not system** — cross-pilot aggregation requires an O(pilots) file scan per query.
- **`claude-sonnet-4-6` for all Claude API calls** — log summarization and Signal don't need sonnet.
- **`structures/*.json` requires a developer commit** — new structure owner = developer action + server restart.
- **File-based persistence, single VPS** — appropriate for MVP.
- **No backup automation** — acceptable now; becomes a concern before sharing with anyone who cares about losing their data.

### Active bugs

None known.

### Intelligence pipeline gaps

| Store | Format | AI read path | Compounds? |
|-------|--------|-------------|-----------|
| `intel_store.py` field reports | Flat JSON per structure | Yes (`query_intel` tool) | Per-structure only |
| `log_intel_store.py` log uploads | JSONL per wallet | **Not wired** | Zero |
| `killmails.jsonl` | Append-only JSONL | Partial (`context_builder.py`) | Yes — only automated source |
| `memory_store/` event memory | JSONL + rolling summary | Unconfirmed | Per-structure only |
| `system_knowledge.db` | SQLite WAL | No tools exist | Nothing feeds it |

### Known areas flagged for change

| Area | Current state |
|------|--------------|
| UI (TerminalUI, TurretUI, GateUI) | Functional but unfinished — sizes, layout, visual design all in scope |
| Log parser | Drops unknown entity types (players, ships, player structures) |
| Claude model selection | `claude-sonnet-4-6` everywhere — per-use-case routing would reduce cost |
| Feature completeness | All features WIP — Recon, route planning, and log ingest closest to done |

---

## What to Work on Next

### Wire the broken read path

Log uploads accumulate in per-wallet JSONL files and are never queried by the AI. The `log_intel_store.py` has no tool in `ai_tools.py` and no read path into `context_builder.py`. Until this is fixed, every log a pilot uploads has zero effect on what HUGINN knows.

These tasks should be done together — the temporal columns must exist before new records are written, and the re-key should happen before more wallet-keyed records accumulate.

| Task | Files | Note |
|------|-------|------|
| Add `get_log_intel(system_id)` tool to `ai_tools.py` | `ai_tools.py`, `log_intel_store.py` | Do simultaneously with temporal columns |
| Add `first_seen_at`, `last_seen_at`, `observation_count` to `log_intel_store.py` | `log_intel_store.py`, `system_knowledge.py` | Records written before this are permanently undateable |
| Re-key `log_intel` store from wallet to system | `log_intel_store.py`, `scripts/` | One-time offline migration script; make it idempotent |
| Audit `query_intel` scope — cross-pilot or personal-only? | `ai_tools.py`, `intel_store.py` | If personal-only, collective intel doesn't exist at all |
| Audit `memory_store.py` → `context_builder.py` connection | `memory_store.py`, `context_builder.py` | Confirm before assuming it's another broken pipe |

Every additional log upload before the re-key runs increases migration cost. Do not defer.

### Finish the three near-done features

**Recon** is functional. After the read path is wired, wire `system_knowledge.db` so cross-system queries work in O(1) instead of O(pilots) file scan. That's the main remaining gap.

**Log ingest** write path works. The read path above is the only gap. After that's done, log ingest is functionally complete for current scale.

**Route Planner** is the most complete feature already. Walk through it end-to-end and note any remaining gaps.

---

## Things That Matter Later

These are real concerns. None of them matter right now with one tester and near-zero traffic. Revisit when the trigger applies.

**Access tier caching** — when Sui Testnet degradation actually causes problems or when the 100–400ms per-chat-turn latency becomes noticeable. Resolve tier once at `/session/register`, cache in session, lazy TTL refresh. Full design: `docs/roadmap/access-tier-caching.md`.

**Rate limiting on `/companion/stream` and `/logs/upload`** — before sharing the URL publicly with people you don't know.

**Claude model routing** — when the monthly Claude bill is high enough to care. Haiku for log summarization and Huginn Signal; sonnet for companion chat. Hard rule before routing: haiku never writes to `system_knowledge.db` or `log_intel_store.py` without schema validation at the write path. Full decision table: `docs/roadmap/model-routing.md`.

**Unify the knowledge graph into `system_knowledge.db`** — after the read path is working and pilot data is actually accumulating. Wire log upload, killmail sync, and field reports into one SQLite database. Add `get_system_knowledge` tool. Inject per-system summary proactively into `context_builder.py`. Not worth doing while the stores are empty.

**Parser coverage** — when there are enough real log uploads to have a meaningful signal on what's being dropped. Build the quarantine store, candidate hostile extraction, and developer CLI then. Full design: `docs/roadmap/log-parser-intelligence-evolution.md`.

**Self-service structure registration** — when someone other than the developer wants to add a structure. Move `structures/*.json` to a SQLite table; add registration flow in the admin panel.

**Backup** — before sharing with anyone who'd care about losing their data.

**HTTPS / TLS** — before any public URL shared beyond the current testers.

**Huginn Signal enrichment** — after `system_knowledge.db` has real data. Not worth enriching a broadcast that reads from empty stores.

**Contribution → VETTED tier pathway** — after there are enough users to make the flywheel worth incentivizing.

**UI revision** — TerminalUI, GateUI, TurretUI sizes, layout, and visual design are all in scope. Do this after the intelligence layer has substance. Redesigning a display before the data exists is wasted work.

**PostgreSQL / multi-VPS / HA** — if this ever becomes something people depend on.

---

## Hard Rules

These apply now, not later.

1. **No haiku writes to `system_knowledge.db` or `log_intel_store.py` without schema validation at the write path.** Misattributed intelligence is permanent and cited by every future pilot. This applies before haiku routing is even enabled.

2. **Temporal columns from the start.** Any new intel record without `first_seen_at`, `last_seen_at`, `observation_count` at write time is permanently undateable. Do not add a store without them.

3. **`gamelog_raw` text has no path to any Claude-facing function. Inviolable.** Raw log text is attacker-controlled. This applies to the quarantine store and all derivative data.

4. **Before writing any new data access code, check the dapp-kit boundary in `CLAUDE.md`.** Nine known boundary violations exist.

As the knowledge layer deepens, HUGINN risks sounding like a database. Confidence scores, observation counts, and temporal metadata feed the prompt — they never appear verbatim in responses. Every data enrichment must be paired with a corresponding update to `prompts/companion.md`.

---

## Supporting Documents

The `docs/roadmap/` directory contains detailed analysis written post-hackathon. They are accurate background. Read them when working on the relevant area.

- `access-tier-caching.md` — full design for resolving tier at registration, TTL strategy, consistency window
- `data-layer-architecture.md` — store inventory, structural problems, evolutionary path
- `intelligence-pipeline-analysis.md` — why log intel is siloed and how to fix it
- `log-parser-intelligence-evolution.md` — quarantine store, candidate hostile extraction, entity category tagging
- `model-routing.md` — full routing decision table, rollout sequence, prompt engineering rules
- `strategic-priorities.md` — priority ranking and sequencing waves (predates this document)
