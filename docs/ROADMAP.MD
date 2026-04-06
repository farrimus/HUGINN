# HUGINN Development Roadmap — Post-Hackathon (April 2026 onward)

---

## 1. Executive Summary

HUGINN is an AI-powered field intelligence companion embedded in EVE Frontier Smart Storage Units, delivering accumulated pilot knowledge through a natural language terminal interface in the in-game browser. The hackathon MVP delivered every planned feature — AI chat, on-chain access control, route planning, log upload, kill feed, SSU watcher, courier board, and tribe presence — across a dual-environment (utopia/stillness) deployment. As of April 2026, the system is functional in production but no feature is considered finished. The most critical gap is structural: the core intelligence premise — "every log upload adds to a shared, permanent knowledge base" — is currently false. Log data is being collected and immediately siloed in per-wallet files with no read path into companion chat. Phase 1 closes this gap before any other development amplifies it. All phases after that compound on a functioning flywheel rather than a broken one.

---

## 2. Current State Assessment

> This roadmap distills the five foundational documents (`PROJECT_OVERVIEW.md`, `ARCHITECTURE_SUMMARY.md`, `KEY_CONCEPTS_AND_DECISIONS.md`, `TECH_STACK_AND_DEPENDENCIES.md`, `REPO_STRUCTURE.md`) plus the six targeted analysis documents produced in our post-hackathon work (`docs/roadmap/strategic-priorities.md` through `docs/roadmap/log-parser-intelligence-evolution.md`).

**Branch note:** The hackathon submission branch is frozen pending judge review (verdict expected ~April 15, 2026). All Phase 1+ work must target the `post-hackathon` branch.

### What is functional

| Feature | Status | Key files |
|---------|--------|-----------|
| AI companion chat (SSE streaming) | Functional | `endpoints/companion.py`, `ai_tools.py`, `context_builder.py` |
| On-chain access control | Functional, has known bug | Per-request Sui RPC; OWNER/TRIBE/VETTED/NONE |
| Route planner | Most complete feature | `route_engine.py` + `data/gate_graph.json` |
| Recon (system intel) | Functional | World API + Galaxy DB; kill context injected via `context_builder.py` |
| Kill feed sync | Functional | Hourly from Sui events; `blockchain_killmails.py` |
| Log upload | Write path functional; read path absent | Parse + summarize + store works; `log_intel_store.py` has no AI tool |
| SSU watcher | Functional | `ssu_watcher_task.py` SSE alert streams |
| Courier board | Functional | `endpoints/courier.py` |
| Tribe presence board | Functional | `endpoints/tribe.py`, `endpoints/tribe_posts.py` |
| Huginn Signal | Functional but narrow | Reads kills + structure state only; no log intel, no field reports |
| Multi-tenant (utopia/stillness) | Functional | `config.py`; dapp-kit patch for dual-registry cache |
| AccessRegistry Move contract | Deployed | Testnet; `move/access_registry/` |

### What was built for hackathon velocity

Source: `KEY_CONCEPTS_AND_DECISIONS.md` § "The backend is stateful" and "Known areas flagged for change."

- **Per-request Sui RPC for access tier** — acknowledged as "simply how it was built," not deliberate zero-trust. Adds 100–400ms to every companion chat turn and makes Sui Testnet degradation a companion chat hard failure.
- **`log_intel` keyed by wallet, not system** — data is indexed by who contributed it, not what was observed. Cross-pilot aggregation requires an O(pilots) file scan per query call.
- **`claude-sonnet-4-6` for all Claude API calls** — log summarization, NONE-tier lobby chat, and Huginn Signal do not require sonnet capability or cost.
- **`structures/*.json` requires a developer commit** — every new structure owner triggers a developer action and server restart.
- **File-based persistence, single VPS, no HA** — appropriate for MVP; not designed for scale.
- **No backup automation** — total data loss on disk failure. Acceptable now; a strategic risk as the knowledge graph accumulates irreplaceable pilot data.

### Active bugs

Source: `strategic-priorities.md` § "Active bug."

- **Session/register timing** — `visitorName` from async dapp-kit call delays tier resolution; `tier` stays `NONE` and `/admin` is blocked for all structure owners.
- **GateUI 422** — `character_name` missing from register call; GateUI session registration is broken for all pilots.

### Intelligence pipeline gaps

Source: `intelligence-pipeline-analysis.md` § "Disconnected Silos"; `data-layer-architecture.md` § "Store Inventory."

| Store | Format | AI read path | Compounds? |
|-------|--------|-------------|-----------|
| `intel_store.py` field reports | Flat JSON per structure | Yes (`query_intel` tool) | Per-structure only |
| `log_intel_store.py` log uploads | JSONL per wallet | **Not wired** | Zero |
| `killmails.jsonl` | Append-only JSONL | Partial (`context_builder.py`) | Yes — only automated source |
| `memory_store/` event memory | JSONL + rolling summary | Unknown — unconfirmed | Per-structure only |
| `system_knowledge.db` | SQLite WAL | No tools exist | Nothing feeds it |

### Known areas flagged for change

Source: `KEY_CONCEPTS_AND_DECISIONS.md` § "Known areas flagged for change."

| Area | Current state | Known direction |
|------|--------------|-----------------|
| UI (TerminalUI, TurretUI, GateUI) | Functional but unfinished | Sizes, layout, and visual design all in scope for revision |
| Log parser | Drops unknown entity types (players, ships, player structures) | Incrementally improved as quarantine drives discovery |
| Claude model selection | `claude-sonnet-4-6` everywhere | Per-use-case routing to reduce cost |
| Feature completeness | All features WIP | Recon, route planning, and log ingest closest to done |
| Single VPS | No HA, no redundancy | Not designed to be permanent |
| Access tier caching | Per-request Sui reads | No caching today. May become a bottleneck at scale. |

---

## 3. Strategic Priorities & North-Star Principles

1. **Close the loop before expanding it.** The intelligence flywheel cannot compound if writes are not readable. Every feature that writes to a store without a read path is technical debt measured in wasted pilot logs. Fix read paths before adding new write paths.

2. **Stability of the foundation gates everything above it.** Sui Testnet on the hot path, O(pilots) file scans, no rate limiting, and no backup are risk accumulation. Each one is a failure mode that worsens with growth. Harden the foundation before building on it.

3. **Cost discipline is a product decision, not an ops concern.** Sonnet for companion chat with trusted pilots; haiku for summarization and broadcast. But haiku that writes permanent intel without schema validation at the write path is worse than no haiku — misattributed intelligence is cited by every future pilot who asks about that system.

4. **Parser coverage determines intelligence fidelity.** PvP systems are the most dangerous and the most informationally blind — highest player activity produces the most dropped log lines. Capturing player, ship, and player-structure entity types is the difference between a knowledge base that compounds and one that plateaus.

5. **Persona is the product.** As the knowledge layer deepens, HUGINN risks sounding like a database. Confidence scores, observation counts, and temporal metadata feed the prompt — they never appear verbatim in responses. Every data enrichment must be paired with a corresponding update to `prompts/companion.md`.

---

## 4. Phased Roadmap

---

### Phase 1 — Close the Loop and Fix Active Blockers

**Objective:** Wire log intelligence into companion chat, fix the active session bugs, and establish the temporal schema foundation that all later intelligence work depends on.

**Success Criteria:**
- A pilot asking about a system receives intel accumulated from prior log uploads, not just the kill feed.
- The `/admin` panel is accessible to all structure owners.
- GateUI session registration succeeds without a 422.
- All new intel records carry `first_seen_at`, `last_seen_at`, `observation_count`.
- `query_intel` scope (cross-pilot vs. personal-only) is confirmed and corrected if needed.

**Key Deliverables**

| Task | Dependency | Why It Matters | Owner Guidance |
|------|-----------|---------------|----------------|
| 1. Wire `log_intel_store.py` → companion chat: add `get_log_intel(system_id)` tool to `ai_tools.py` | None — first unlock | Core mission claim is currently false. All accumulated log data is unqueryable. | `ai_tools.py`, `log_intel_store.py` |
| 2. Audit `query_intel` scope — confirm cross-pilot or personal-only | None — read-only audit | If personal-only, collective intel doesn't exist at all. Determines whether a scope fix is urgent. | `ai_tools.py`, `intel_store.py` |
| 3. Audit `memory_store.py` → `context_builder.py` connection | None — read-only audit | Per-structure event history may be another unwired store. Confirm before assuming. | `memory_store.py`, `context_builder.py` |
| 4. Fix session/register timing bug — resolve tier before blocking on `visitorName` | None — active bug | `/admin` is blocked for all structure owners on every session. | `endpoints/session.py`, dapp-kit call ordering in frontend |
| 5. Fix GateUI 422 — include `character_name` in register call | None — active bug | GateUI session registration is broken for all pilots. | `frontend/src/components/GateUI.tsx` |
| 6. Add temporal columns — `first_seen_at`, `last_seen_at`, `observation_count` to `log_intel_store.py` and `system_knowledge.py` | Must ship simultaneously with or before Task 1 | Records written without timestamps are permanently undateable. Stale intel is indistinguishable from fresh. | `log_intel_store.py`, `system_knowledge.py` |
| 7. Re-key `log_intel` store from wallet to system | Task 6 (schema must be set before migration) | Current O(pilots) scan per `get_log_intel` call degrades directly with pilot count. One-time offline transformation — read all wallet files, reorganize by system. Migration script lives in `scripts/` and must be idempotent (safe to re-run; consistent with `REPO_STRUCTURE.md` § "What is Generated vs Committed"). | `log_intel_store.py`, `scripts/` |

**Risks & Mitigations**
- **Migration cost grows weekly.** Every additional log upload before Task 7 runs increases the re-keying cost. Do not defer.
- **Existing records are undateable.** Accept that pre-Task-6 records have no timestamps; add TTL-based fallback aging for undated records rather than back-filling.
- **`query_intel` audit (Task 2) may reveal personal-only scope.** If so, there is no collective intel mechanism at all — escalate the scope fix to top priority before proceeding with Phase 2.

**Effort:** Hours to days per task. Task 7 (re-key migration) is 1–2 days including offline script.

---

### Phase 2 — Instrument and Harden

**Objective:** Remove Sui Testnet from the companion chat hot path, establish cost and coverage telemetry, and close the Claude token exposure risk.

**Success Criteria:**
- Companion chat first-token latency is not gated by a Sui RPC call.
- Sui Testnet degradation serves a stale tier rather than failing companion chat.
- Every Claude API call emits a structured telemetry log entry (call type, tier, model, tokens, latency).
- Parser drop rates by entity type are visible to structure owners in the admin panel.
- Rate limiting is enforced on `/companion/stream` and `/logs/upload`.

**Key Deliverables**

| Task | Dependency | Why It Matters | Owner Guidance |
|------|-----------|---------------|----------------|
| 8. Access tier caching Phase 1 — resolve tier at `/session/register`, add `resolved_tier` + `tier_resolved_at` to session model, read from session on `/companion/stream` (no TTL yet) | Phase 1 bugs fixed (sessions must be stable before caching is layered on) | Removes 100–400ms from every chat turn. Sui Testnet no longer blocks companion chat. Phase 1 alone (no TTL) eliminates the RPC from the hot path for all returning pilots. | `session_store.py`, `endpoints/session.py`, `endpoints/companion.py` |
| 9. Access tier caching Phase 2 — TTL expiry check; serve stale tier immediately on expiry, dispatch background re-resolution, write result back to session | Task 8 | Makes the cache production-safe with an explicit consistency window (default 5 minutes). | `endpoints/companion.py`, `endpoints/session.py` |
| 10. Access tier caching Phase 3 — OWNER-gated endpoint to invalidate and refresh tier cache for active sessions on a structure | Task 9 | Handles ownership transfers and emergency revocations without waiting for TTL. | `endpoints/admin.py`, `session_store.py` |
| 11. Claude API telemetry — emit structured log entry per call: `{call_type, tier, model_used, tokens_in, tokens_out, tool_calls_count, latency_ms, environment}` | Task 8 (tier must be cached to be logged accurately) | Gates all cost-optimization decisions downstream. Every cost estimate in this roadmap is an estimate; telemetry is truth. | `endpoints/companion.py`, `endpoints/logs.py`, `huginn_news_task.py` |
| 12. Parser drop count observability — aggregate `gamelog_raw` counts by `msg_type` per upload, persist server-side aggregates, expose in OWNER-gated admin endpoint | Phase 1 complete (admin must be accessible) | Quantifies what intelligence is being lost. PvP systems may be returning `hostiles=[]` silently. | `log_analysis.py`, `endpoints/logs.py`, `endpoints/admin.py` |
| 13. Rate limiting on `/companion/stream` and `/logs/upload` | None — independent of all other tasks | No rate limiting means unlimited Claude token exposure. Does not wait for telemetry. | FastAPI middleware or per-endpoint logic |

**Tier caching consistency windows** (source: `access-tier-caching.md` § "Consistency Window"):

| Scenario | Impact | Severity |
|----------|--------|----------|
| Pilot added to vetted mid-session | Waits up to TTL for access grant | Low — can re-register session |
| Pilot removed from vetted mid-session | Retains VETTED access for up to TTL | Low — intel data, not key material |
| SSU ownership transfer | Old owner retains OWNER access for up to TTL | Medium — mitigated by Task 10 invalidation endpoint |
| Sui RPC degraded during refresh | Stale tier served | Better than current (current: hard failure) |

**Risks & Mitigations**
- **dapp-kit 0.1.7 patch breaks on version bump.** `patches/@evefrontier+dapp-kit+0.1.7.patch` must be verified on every `npm install`. Add a build-time check or comment in `package.json` `postinstall` script to catch silent failures.

**Effort:** 1 week.

---

### Phase 3 — Unify the Knowledge Graph

**Objective:** Route all intelligence ingest paths into `system_knowledge.db` as the single aggregation target, expose it to the AI with tools, and inject system summaries proactively into every companion chat context block.

**Success Criteria:**
- Log uploads, killmail sync, and field reports all write to `system_knowledge.db`.
- At minimum one AI tool (`get_system_knowledge`) queries it.
- Per-system summary is injected into every companion chat context block automatically — not gated on a tool call.
- Cross-system queries answer in O(1) (indexed SQL) not O(pilots) (file scan).
- Huginn Signal reads from `system_knowledge.db`.
- Self-service structure registration does not require a developer commit.

**Key Deliverables**

| Task | Dependency | Why It Matters | Owner Guidance |
|------|-----------|---------------|----------------|
| 14. Wire log upload into `system_knowledge.db` — `log_analysis.py` writes per-system entity/ore records on ingest | Phase 1 (temporal columns must exist) | The store has the best schema; nothing feeds it. Log upload is the highest-volume ingest path. | `system_knowledge.py`, `log_analysis.py` |
| 15. Wire killmail sync into `system_knowledge.db` — `blockchain_killmails.py` upserts kill entity records | Task 14 (schema must be established) | Kill feed is the only currently compounding source; it should write to the central store. | `blockchain_killmails.py`, `system_knowledge.py` |
| 16. Bridge `intel_store.py` field reports → `system_knowledge.db` — pilot-reported system observations upsert into the global graph | Task 14 | Field reports are currently per-structure only. Cross-structure system knowledge requires this bridge. | `intel_store.py`, `system_knowledge.py` |
| 17. Add AI tools for `system_knowledge.db` — at minimum `get_system_knowledge(system_id)` in `ai_tools.py` | Tasks 14–16 (store must have data before exposing a tool) | The store has no AI read path. Schema must include confidence weighting (`observation_count` → calibrated confidence score) — flagged as a quality ceiling in `intelligence-pipeline-analysis.md`. | `ai_tools.py`, `endpoints/system_knowledge.py` |
| 18. Inject proactive system summary into `context_builder.py` — pre-computed 3–5 sentence system summary from `system_knowledge.db` in every context block | Task 17 (store and tool must exist) | Converts opt-in tool call to always-on awareness. Pre-computed text, not per-request synthesis — controls context cost. | `context_builder.py`, `system_knowledge.py` |
| 19. Audit and rewire Huginn Signal — audit what `huginn_news_task.py` actually reads, then wire to read from `system_knowledge.db` | Tasks 14–16 (store must have data before Signal reads it) | Signal currently reads kills + structure state only. Audit must precede implementation — determines whether this is wiring or rewrite. | `huginn_news.py`, `huginn_news_task.py` |
| 20. Resolve Huginn Signal O(structures) fan-out — audit whether Signal is scoped to active/subscribed structures or reads all | Task 19 audit | If unbounded, Signal I/O degrades linearly with structure count. If subscription-scoped, problem may never materialize. Current documentation does not answer this. | `huginn_news_task.py`, `huginn_news.py` |
| 21. Move `structures/*.json` to a SQLite table | Independent of Tasks 14–17; `system_knowledge.db` must exist (Phase 3 prerequisite); can ship in parallel with ingest wiring | Removes the "developer commit + restart" anti-pattern flagged in `KEY_CONCEPTS_AND_DECISIONS.md` § "Data format choices": "There is no PostgreSQL dependency to add — the existing SQLite schema...would translate directly." Import existing JSON files as initial state; retain originals as backup during transition. | `structure_persistence.py`, `structure_loader.py`, `data/structures/` |
| 22. Session TTL cleanup — background task purging dead session files | None — independent; low urgency | Dead sessions accumulate indefinitely. Only visible at scale. | `session_store.py` or new `src/maintenance.py` |

**Risks & Mitigations**
- **`memory_store.py` dual-format divergence.** JSONL + rolling summary creates inconsistency if summarization is interrupted. Make JSONL the source of truth; treat the summary as a derived cache regenerated on read if stale. Source: `data-layer-architecture.md` § "Per-Structure Memory."
- **SQLite concurrent write contention.** Killmail sync + log processing + Signal generation may all write `system_knowledge.db` concurrently. WAL mode handles this; watch for latency under volume. Mitigation: write batching before storage migration.
- **Huginn Signal persona risk.** As Signal gains richer data sources, it risks reading like a metrics report. Update `prompts/companion.md` and Signal-specific prompts in parallel with every new data source addition.

**Effort:** 2–3 weeks.

---

### Phase 4 — Cost Optimization via Model Routing

**Objective:** Route Claude API calls by use-case and access tier to reduce operating cost approximately 35% at current scale without degrading intelligence quality or the pilot persona.

**Hard prerequisites:** Phase 2 (tier caching) and Phase 2 (telemetry baseline) must both be complete. Model routing keyed on tier must run on cached tier, not live RPC. Commit to no routing decisions before telemetry from Task 11 establishes a real baseline.

**Success Criteria:**
- Log summarization and Huginn Signal use `claude-haiku-4-5`.
- NONE-tier companion chat uses `claude-haiku-4-5` with an empty tool list (not restricted — empty, so tools cannot be called at all).
- Schema validation blocks any haiku write to `system_knowledge.db` or `log_intel_store.py`.
- Observed cost at 50 pilots/day is approximately $79/month vs. the $121/month all-sonnet baseline.

**Model routing decision table** (source: `model-routing.md` § "Decision Table"):

| Call type | Tier | Model | Condition |
|-----------|------|-------|-----------|
| Companion chat | OWNER / TRIBE | sonnet-4-6 | Always |
| Companion chat | VETTED | sonnet-4-6 | Always — tool reliability required |
| Companion chat | NONE | haiku-4-5 | Always — no tools, lobby persona only |
| Log summarization | Any (stillness) | haiku-4-5 | ≤100 events/system |
| Log summarization | Any (stillness) | sonnet-4-6 | >100 events/system — complex sequences, permanent storage |
| Log summarization | Any (utopia) | haiku-4-5 | Always — test env, not production intel |
| Huginn Signal | Any | haiku-4-5 | Kill count ≤ 2× 7-day rolling hourly average |
| Huginn Signal | Any | sonnet-4-6 | Kill count > 2× average, or any structure destruction event |
| Fallback | Any | sonnet-4-6 | Tier unknown or resolution failed — never fail open to NONE routing |

**Key Deliverables**

| Task | Dependency | Why It Matters | Owner Guidance |
|------|-----------|---------------|----------------|
| 23. Split `CLAUDE_MODEL` env var into three independent vars: `CLAUDE_MODEL_COMPANION`, `CLAUDE_MODEL_LOG`, `CLAUDE_MODEL_SIGNAL` | None — blocker for all routing | Single global config prevents per-use-case routing. | `config.py`, `.env.example` |
| 24. Add schema validation at write path for log intel — reject haiku output that fails schema before writing to `log_intel_store.py` | Task 23, before Task 25 ships | Haiku misattributing entities or dropping kill events writes permanent bad data, cited forever by any future pilot. This is a prerequisite, not a subsequent step. | `log_intel_store.py`, `log_analysis.py` |
| 25. Route log summarization → `claude-haiku-4-5` (stillness only, with schema validation gate active) | Tasks 23 + 24 + telemetry baseline | Safest change — no player-facing impact. Validate on 10–20 manual comparisons before shipping to stillness. | `log_analysis.py`, `config.py` |
| 26. Route Huginn Signal → `claude-haiku-4-5` with sonnet escalation | Task 23 + Signal rewire from Phase 3 + kill-spike threshold defined from kill feed data | Second-safest change. Test 2–3 Signal cycles manually; gate to stillness after OWNER feedback on utopia. | `huginn_news_task.py`, `config.py` |
| 27. Route NONE-tier companion chat → `claude-haiku-4-5` | Task 23 + tight NONE-tier prompt variant + tier caching in production (Phase 2) | NONE is the first thing a new pilot sees. One generic-feeling response ends the session. Test on utopia first; gate to stillness after 48 hours of clean behavior on utopia. | `endpoints/companion.py`, `prompts/companion.md` |
| 28. VETTED routing experiment (conditional) | Tasks 25–27 complete + reliable query-intent classifier confirmed | Smallest payoff, highest operational risk — haiku tool failures are silent. Skip if volume doesn't justify the complexity. | `endpoints/companion.py` |

**Cost model** (source: `model-routing.md` § "Cost Impact"; `strategic-priorities.md` § "Wave 4"):

| Line | All-sonnet $/mo | With routing $/mo | Saving |
|------|----------------|------------------|--------|
| Companion chat | ~$90 | ~$70 | ~$20 |
| Log uploads | ~$18 | ~$5 | ~$13 |
| Huginn Signal | ~$13 | ~$4 | ~$9 |
| **Total** | **~$121** | **~$79** | **~$42 (35%)** |

At 10× scale (500 pilots/day): ~$350–400/month saved.

**Risks & Mitigations**
- **Permanent bad intel from haiku.** Schema validation at the write path (Task 24) is non-negotiable and must precede Task 25. Source: `strategic-priorities.md` Hard Rule 1.
- **NONE-tier persona break destroys top-of-funnel.** The core identity block in the haiku prompt must be character-for-character identical to the sonnet variant. Source: `model-routing.md` § "Prompt Engineering Rules."
- **VETTED tool call failures are silent.** Haiku returns no error on tool failure — just missing or wrong data. Do not route VETTED without a working query-intent classifier.

**Effort:** 1–2 weeks (after Phase 2 is complete).

---

### Phase 5 — Deepen Parser Coverage

**Objective:** Make parser blind spots visible, establish a mechanical sample-collection loop, and begin extracting player-entity intelligence from combat log events.

**Context:** The log parser has two layers (source: `log-parser-intelligence-evolution.md` § "Current Architecture"). Layer 1 (`log_parsers.py`) drops only explicit discard types and untagged lines; everything else becomes a `gamelog_raw` event. Layer 2 (`log_analysis.py:168`) excludes all `gamelog_raw` events from the Claude-facing prompt (the real security boundary). The gap: `gamelog_raw` events exist in memory during upload then vanish. There is no collection mechanism. Parser growth requires a developer to manually intercept live uploads. PvP systems — highest player activity — are the most blind.

**Success Criteria:**
- OWNER admin panel shows parser drop rates by entity type over time.
- Unknown entity type text samples are captured automatically (quarantine store, TTL-capped, developer-visible only — no AI path).
- Parser promotion cycle is data-driven and weekly, not incident-triggered.
- `candidate_hostiles` field exists in the intel store and is surfaced to HUGINN as clearly unverified.
- % of typed log lines yielding structured events (not `gamelog_raw`) approaches 85%+ across active players.

**Key Deliverables**

| Task | Dependency | Why It Matters | Owner Guidance |
|------|-----------|---------------|----------------|
| 29. Parser drop count observability — log `gamelog_raw` counts per `msg_type`; persist aggregates; OWNER admin endpoint | Phase 2 (admin panel accessible) | Quantifies what is being lost. Prerequisite for all other parser work — cannot measure improvement without a baseline. Covered in Phase 2 as Task 12; confirm it shipped there. | `log_analysis.py`, `endpoints/logs.py`, `endpoints/admin.py` |
| 30. Quarantine store — persist 3–5 anonymized text samples per unrecognized `msg_type`, TTL 30 days, developer-visible only | Task 29 | Converts the sample-collection loop from aspirational to mechanical. No code path to any Claude-facing function — inviolable. | New: `src/log_quarantine.py` |
| 31. Developer CLI — apply candidate regexes against quarantine, report match rates | Task 30 | Target: one new entity type promoted to `log_parsers.py` per week instead of per incident. | `scripts/` |
| 32. Candidate hostile name extraction — lightweight heuristic name extractor runs against `gamelog_raw combat` events at upload time; results stored under `candidate_hostiles` key, clearly flagged as unverified | Tasks 29–30 (observability and quarantine must precede extraction) | Recovers player-encounter intelligence from exactly the events that matter most without touching the security boundary. | `log_analysis.py`, `log_intel_store.py` |
| 33. Shadow parser promotion — apply candidate regexes against quarantine samples server-side; promote to `log_parsers.py` if match rate exceeds threshold across multiple distinct wallets | Task 32 | Closes the feedback loop automatically. Parser coverage becomes data-driven. | `src/log_quarantine.py`, `src/log_parsers.py` |
| 34. Entity category tagging — `_known_types.json` gains entity category tags (`npc`, `player`, `structure`); `system_knowledge.db` stores per-category hostile counts; recon surfaces categories separately | Task 33 (parser must be mature enough for categorization) | Enables pilots to distinguish NPC threats from player threats — different tactical implications. | `src/log_parsers.py`, `system_knowledge.py`, `ai_tools.py` |

**Hard constraint:** `gamelog_raw` text has no code path to any Claude-facing function, under any circumstances. This is inviolable and applies to the quarantine store and all derivative data. Source: `log-parser-intelligence-evolution.md` § "Hard constraint."

**Risks & Mitigations**
- **Quarantine prompt injection.** Raw log text is attacker-controlled. Quarantine data must have zero code path to AI functions, ever.
- **`candidate_hostiles` accuracy.** Label explicitly as unverified. HUGINN must present them distinctly from confirmed hostiles in all output. Do not write to `system_knowledge.db` as verified entities.

**Effort:** 2–3 weeks.

---

### Phase 6 — Platform, Incentives, and UI

**Objective:** Establish the contribution-to-access incentive loop, revise the UI now that the intelligence layer has substance, and complete remaining feature polish.

**Success Criteria:**
- Pilots who contribute log uploads have an in-lore pathway to VETTED tier access.
- UI is revised to reflect the depth of intelligence HUGINN now carries.
- All advertised features meet their intended behavior.
- `prompts/companion.md` governs in-lore citation of accumulated knowledge.

**Key Deliverables**

| Task | Dependency | Why It Matters | Owner Guidance |
|------|-----------|---------------|----------------|
| 35. Contribution → VETTED tier pathway — in-lore reward for log uploads using existing `AccessRegistry` + `session_store.py` | Phase 3 complete (flywheel must be demonstrably spinning before incentivizing it) | Incentivizes the exact behavior that makes HUGINN more valuable to every pilot. No new mechanics needed — existing infrastructure. | `session_store.py`, `blockchain_queries.py`, AccessRegistry integration |
| 36. `prompts/companion.md` revision for knowledge-layer depth | Phase 3 (intelligence layer must have substance first) | As accumulated data deepens, HUGINN risks sounding like a database. Prompt must govern how it cites multi-pilot observations in-lore. | `prompts/companion.md` |
| 37. UI revision — TerminalUI, GateUI, TurretUI sizes, layout, and visual design | Phase 3 complete (data layer must warrant the display) | Sizes, layout, and visual design are all in scope. Do not revise UI before the intelligence layer has substance. Source: `KEY_CONCEPTS_AND_DECISIONS.md`. | `frontend/src/components/` |
| 38. Feature completion audit — review each WIP feature against intended behavior, close gaps | All prior phases complete | Recon, route planning, and log ingest are closest to done; courier board and tribe presence need polish validation. | All `src/endpoints/` |

**Effort:** 2–4 weeks (parallel tracks: incentives, prompts, UI, feature audit).

---

### Long-term / Horizon 2 — Scale, HA, and New Intelligence Vectors

**Objective:** Evolve infrastructure to support network growth, add new intelligence acquisition vectors, and support multiple concurrent structure deployments.

| Area | Description | Trigger |
|------|-------------|---------|
| **Backup automation** | Snapshot `data/{env}/` to cold storage on a schedule. Total data loss on VPS disk failure is acceptable at MVP scale; becomes a strategic risk as the knowledge graph accumulates irreplaceable pilot data. | Before 100 pilots or before launch on stillness live environment |
| **HTTPS + reverse proxy** | No reverse proxy or TLS today. Required before any public launch. | Before public launch on stillness |
| **Multi-VPS / HA** | Single VPS has no redundancy. Horizontal scaling requires session state migration from flat JSON to SQLite — noted as the natural evolution path in `KEY_CONCEPTS_AND_DECISIONS.md`. | When uptime SLA is required by structure owners |
| **PostgreSQL migration** | `system_knowledge.db` schema translates directly to PostgreSQL (noted in `KEY_CONCEPTS_AND_DECISIONS.md`). Migrate when concurrent write volume exceeds SQLite WAL capacity or when multi-VPS requires shared state. | When SQLite write latency becomes visible under load |
| **Self-service structure registration** | Phase 3 Task 21 (structures to SQLite) is the prerequisite. Add self-service registration flow in the admin panel. Eliminates all developer involvement in structure onboarding. | When new structures require developer action more than once per week |
| **Player location (`/v2/characters/me/jumps`)** | World API JWT-gated endpoint. Full backend endpoint + React hook + slash command planned. Auth challenge documented in `givelocation_implementation.md`. | After Phase 3 (context builder is the natural home for this data) |
| **Move contract expansion** | AccessRegistry only today. Future: on-chain intel curation (staking verified reports), on-chain contribution tracking for VETTED tier pathway. | After Phase 6 (incentive system designed and running) |
| **New Sui event streams** | Kill events are the only Sui stream tapped today. Structure destruction events, gate activations, and other EVE Frontier contract events are available. | After core intelligence pipeline is stable |
| **Cost modeling at 500+ pilots/day** | Phase 4 routing achieves ~$79/month at 50 pilots/day. At 500 pilots/day, revisit log summarization batching and pre-computed offline summary strategies. | When pilot count consistently exceeds 100/day |

---

## 5. Cross-Cutting Concerns

### Technical Debt Backlog

| Debt Item | Severity | Source | Resolved in |
|-----------|---------|--------|------------|
| `log_intel` keyed by wallet — O(pilots) scan per query | High | `data-layer-architecture.md` | Phase 1, Task 7 |
| No rate limiting on `/companion/stream` | High | `strategic-priorities.md` | Phase 2, Task 13 |
| No backup automation | High | `data-layer-architecture.md` | Horizon 2 |
| Sui Testnet on companion chat hot path | High | `access-tier-caching.md` | Phase 2, Task 8 |
| No temporal decay on intel records | High | `intelligence-pipeline-analysis.md` | Phase 1, Task 6 |
| `memory_store.py` JSONL + summary divergence risk | Medium | `data-layer-architecture.md` | Phase 3 |
| Session read-modify-write not atomic | Medium | `data-layer-architecture.md` | Phase 3 (SQLite migration) |
| dapp-kit 0.1.7 patch breaks on version bump | Medium | `TECH_STACK_AND_DEPENDENCIES.md` | Ongoing — verify every `npm install` |
| No HTTPS / reverse proxy | Medium | `TECH_STACK_AND_DEPENDENCIES.md` | Horizon 2 (before public launch) |
| Dead session accumulation (no TTL cleanup) | Low | `data-layer-architecture.md` | Phase 3, Task 22 |
| Huginn Signal input sources undocumented | Low | `intelligence-pipeline-analysis.md` | Phase 3 audit (Task 19) |
| 9 known dapp-kit boundary violations | Ongoing | `docs/DAPP_KIT_BOUNDARY.md` | Enforce continuously |

### Claude Model Strategy

Source: `KEY_CONCEPTS_AND_DECISIONS.md` § "Claude model is a variable"; `model-routing.md`.

The single `CLAUDE_MODEL` env var is a blocker for cost optimization. Phase 4 Task 23 splits it into three independently configurable vars: `CLAUDE_MODEL_COMPANION`, `CLAUDE_MODEL_LOG`, `CLAUDE_MODEL_SIGNAL`. Routing rules are in the Phase 4 decision table above.

**Non-negotiable rule:** Haiku never writes to `system_knowledge.db` or `log_intel_store.py` without schema validation at the write path. Misattributed intelligence is permanent and cited by every future pilot.

### UI Revision Strategy

UI revision is deliberately deferred to Phase 6. TerminalUI, GateUI, and TurretUI are all in scope for substantial change — sizes, layout, and visual design (`KEY_CONCEPTS_AND_DECISIONS.md`). Do not invest in UI before the intelligence layer has substance. The display is a function of the data.

### Deployment Evolution

Current: single VPS, `python main.py` on port 8745, static frontend served by FastAPI. No reverse proxy, no TLS, no container orchestration, no backup.

Evolution sequence: reverse proxy + TLS → backup automation → session SQLite migration → horizontal scale. Each step is independent and triggered by demand signals defined above in Horizon 2.

### dapp-kit Boundary Discipline

Source: `CLAUDE.md`; `docs/DAPP_KIT_BOUNDARY.md`; `feedback_dappkit_drift.md`.

Nine known boundary violations exist. Before writing any new data access code, consult `docs/DAPP_KIT_BOUNDARY.md`. The boundary is:
- **dapp-kit owns:** assembly data, ownership, fuel, type metadata, status parsing, Sui GraphQL queries.
- **Backend owns:** AI chat, galaxy geography, derived fuel metrics (hours remaining, burn rate), social boards, session management.

### Monitoring and Observability Targets

Tasks 11 and 12 (Phase 2) establish the first systematic signals. Subsequent targets for later phases:
- Per-session turn depth and repeat-question rate (haiku quality proxy for NONE tier)
- Kill feed sync lag (time from Sui event to local record)
- `system_knowledge.db` write latency under concurrent background task load
- SSE client counts for watcher streams
- `candidate_hostiles` promotion rate (parser coverage health)

---

## 6. Risks & Open Architectural Questions

### Risk Register

| Risk | Severity | Resolved in | Mitigation |
|------|---------|------------|-----------|
| Core mission claim is false — log intel not queryable | Critical | Phase 1, Task 1 | Hours of work |
| Active admin/GateUI bug blocks owner and gate use | Critical | Phase 1, Tasks 4–5 | Active bugs |
| Sui Testnet degradation = companion chat hard failure | High | Phase 2, Task 8 | Tier caching — stale tier on degradation, not failure |
| No rate limiting — Claude token exposure | High | Phase 2, Task 13 | Immediate, independent of other tasks |
| PvP systems most blind — combat events dropped silently | High | Phase 5, Tasks 29–32 | Quarantine + candidate extraction |
| Haiku writing permanent bad intel | High | Phase 4, Task 24 | Schema validation gate — prerequisite, not optional |
| No temporal decay — stale intel indistinguishable from fresh | High | Phase 1, Task 6 | Temporal columns from start; cannot be back-filled |
| `query_intel` scope personal-only (collective intel absent entirely) | High | Phase 1, Task 2 | Audit confirms or escalates scope fix |
| No backup — disk failure loses irreplaceable pilot knowledge | Medium | Horizon 2 | Snapshot automation before public launch |
| dapp-kit 0.1.7 patch breaks on version bump | Medium | Ongoing | Verify every `npm install`; add build-time check |
| Session read-modify-write not atomic under concurrent load | Medium | Phase 3 | SQLite migration serializes writes |
| Huginn Signal O(structures) fan-out unbounded | Medium | Phase 3, Task 20 | Audit scope; add subscription filter if unbounded |
| `memory_store.py` JSONL + summary divergence on interrupted summarization | Medium | Phase 3 | JSONL as source of truth; summary as derived cache |

### Open Architectural Questions

Source: `data-layer-architecture.md` § "Strategic Questions"; `intelligence-pipeline-analysis.md` § "Five Open Questions."

**1. Is cross-pilot system intelligence the primary value driver?**
If yes, `log_intel` re-keying (Phase 1, Task 7) is the single most urgent task and migration cost grows weekly. If secondary to route planning and recon, urgency decreases. This question should be answered before Phase 1 begins.

**2. What does `huginn_news_task.py` actually read?**
Determines whether Phase 3 Signal work is a wiring task or a rewrite. Must be audited before starting Task 19. Source: `intelligence-pipeline-analysis.md` Open Question 3.

**3. Does `memory_store.py` feed `context_builder.py`?**
If not, per-structure event history is a third unwired store. Audit (Phase 1, Task 3) answers this definitively. Source: `intelligence-pipeline-analysis.md` Open Question 4.

**4. Is Huginn Signal scoped to active/subscribed structures or does it read all structures?**
If bounded by subscription, the O(structures) fan-out may never materialize. If it reads all, I/O accumulation is unbounded. Current documentation does not answer this. Source: `data-layer-architecture.md` § "Strategic Questions."

**5. What is the expected structure and pilot count at 60 and 120 days?**
Fast growth (dozens of structures, hundreds of pilots) makes the Sui RPC bottleneck, Signal fan-out, and `log_intel` O(pilots) scan urgent simultaneously. Slow growth makes them sequential. This forecast directly affects Phase 3 priority ordering.

**6. What is the actual volume of `data/{env}/log_intel/` today?**
O(pilots) file scan performance is theoretical below ~50 pilots and real above it. Check current count before assuming re-keying urgency. Source: `intelligence-pipeline-analysis.md` Open Question 5.

---

## 7. Success Metrics & Player-Value Tracking

HUGINN is delivering compounding intelligence when these metrics move in the stated direction:

| Metric | Baseline | Target | Phase |
|--------|---------|--------|-------|
| Core mission claim true (log intel queryable in companion chat) | False | True | Phase 1 |
| `/admin` accessible to structure owners | 0% of sessions (blocked by active bug) | 100% | Phase 1 |
| `get_log_intel` tool calls per companion session | 0 (tool doesn't exist) | >0 within 1 week of Phase 1 | Phase 1 |
| `query_intel` confirmed cross-pilot scope | Unknown | Confirmed | Phase 1 |
| Companion chat first-token latency | Baseline from Task 11 | Reduced 100–400ms | Phase 2 |
| Claude API cost at 50 pilots/day | ~$121/month | ~$79/month | Phase 4 |
| Systems in `system_knowledge.db` with ≥3 verified hostiles | 0 (no feeders) | Doubles per month once player combat captured | Phase 3 + 5 |
| Parser update cycle | Infinite (no collection mechanism) | Weekly (data-driven) | Phase 5 |
| % typed log lines yielding structured events (not `gamelog_raw`) | Unknown (Task 12 establishes baseline) | >85% across active player base | Phase 5 |
| Time from "new entity type in production" to "parser updated" | Weeks to never | Days | Phase 5 |
| Structure owner onboarding without developer action | 0% (all require commit) | 100% self-serve | Phase 3 (Task 21) / Horizon 2 |

**Leading indicators of the flywheel spinning:**
- Pilot count uploading logs per week (volume signal)
- Per-system observation count growth in `system_knowledge.db` (accumulation signal)
- `get_log_intel` tool call frequency in companion sessions (engagement signal)
- Repeat pilot rate (return value signal — pilots come back because HUGINN remembered)

---

## Next Action

Before writing any code:

1. **Check live data volume.** On the stillness instance, count the files in `data/stillness/log_intel/` and confirm the state of `data/stillness/system_knowledge.db`. If log_intel volume is already non-trivial (tens of wallet files or more), Task 7 (re-key migration) urgency increases — as noted in `intelligence-pipeline-analysis.md` Open Question 5, O(pilots) scan performance is theoretical below ~50 pilots and real above it. Volume determines sequencing.

2. **Run the three read-only audits** — Tasks 2 (query_intel scope), 3 (memory_store connection), and the Signal input audit (precursor to Phase 3 Task 19). These take under an hour combined and determine whether Phase 1 scope is correct or needs adjustment before a single line is written.

Then implement Task 1 (wire `log_intel_store.py` → `get_log_intel` tool in `ai_tools.py`) and Task 6 (temporal columns to `log_intel_store.py` and `system_knowledge.py`) together — they share code paths and the columns must exist before any new records are written. This is the highest-impact, lowest-effort unlock in the entire roadmap. It is also the work that makes the mission claim true for the first time.

---

## Version History

- v1.0 — locked April 2026 after final validation against all eleven source documents (`PROJECT_OVERVIEW.md`, `ARCHITECTURE_SUMMARY.md`, `KEY_CONCEPTS_AND_DECISIONS.md`, `TECH_STACK_AND_DEPENDENCIES.md`, `REPO_STRUCTURE.md` + the six `/docs/roadmap` analysis documents).
