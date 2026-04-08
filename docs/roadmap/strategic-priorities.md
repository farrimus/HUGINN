# Strategic Priorities — Post-Hackathon

## State of the Mission

The core promise: "Every log upload adds to a shared, permanent knowledge base." **This is currently false.**

| Store | Has AI read path? | Compounds? |
|-------|------------------|------------|
| `intel_store.py` field reports | Yes (`query_intel`) | Per-structure only |
| `log_intel_store.py` log uploads | **No** | Zero |
| `killmails.jsonl` | Partial (context_builder) | Yes — only automated source |
| `memory_store.py` event memory | Unknown | Unknown |
| `system_knowledge.db` | **No** — no feeders, no tools | Zero |

**Active bug:** Session/register timing → `tier` stays `NONE` → `/admin` blocked. GateUI 422 (`character_name` missing from register call).

---

## Priority Ranking

| Rank | Item | Key files |
|------|------|-----------|
| 1 | Wire `log_intel_store.py` → companion chat (add `get_log_intel` tool) | `ai_tools.py` |
| 2 | Fix session/register timing bug (admin panel + GateUI 422) | `endpoints/session.py` |
| 3 | Add temporal decay to intel stores (`first_seen_at`, `last_seen_at`, `observation_count`) | `log_intel_store.py`, `system_knowledge.py` |
| 4 | Audit `query_intel` scope — cross-pilot or personal only? | `ai_tools.py`, `intel_store.py` |
| 5 | Audit `memory_store.py` → `context_builder.py` connection | `memory_store.py`, `context_builder.py` |
| 6 | Access tier caching (resolve at register, cache in session, TTL refresh) | `session_store.py`, `endpoints/session.py`, `endpoints/companion.py` |
| 7 | Claude API telemetry (structured log per call: type, tier, model, tokens, latency) | `endpoints/companion.py`, `endpoints/logs.py`, `huginn_news_task.py` |
| 8 | Parser drop count observability (aggregate `gamelog_raw` by `msg_type`, admin endpoint) | `log_analysis.py`, `endpoints/logs.py`, `endpoints/admin.py` |
| 9 | Rate limiting on `/companion/stream` and `/logs/upload` | middleware or `endpoints/companion.py` |
| 10 | Bridge `intel_store.py` field reports → `system_knowledge.db` | `intel_store.py`, `system_knowledge.py` |
| 11 | Complete `system_knowledge.db` (wire all ingest, add AI tools) | `system_knowledge.py`, `ai_tools.py`, `log_analysis.py`, `blockchain_killmails.py` |
| 12 | Proactive system summary injection into `context_builder.py` | `context_builder.py` |
| 13 | Model routing: log summarization → haiku (requires #6 + #7 first) | `log_analysis.py`, `config.py` |
| 14 | Model routing: Huginn Signal → haiku with sonnet escalation | `huginn_news_task.py` |
| 15 | Model routing: NONE tier → haiku (requires tight prompt variant + #6) | `endpoints/companion.py`, `prompts/companion.md` |
| 16 | Log parser quarantine store (3–5 samples/msg_type, TTL 30d, dev-only) | New: `log_quarantine.py` |
| 17 | Candidate hostiles extraction from `gamelog_raw combat` | `log_analysis.py`, `log_intel_store.py` |
| 18 | Huginn Signal rewire to read `system_knowledge.db` (requires #11) | `huginn_news.py`, `huginn_news_task.py` |
| 19 | Contribution → VETTED tier pathway | `session_store.py`, AccessRegistry integration |
| 20 | UI revision (TerminalUI / GateUI / TurretUI) | `frontend/src/components/` |

---

## Sequencing Waves

**Wave 1 — Close the loop** (items 1–5, hours to days)
Wire log intel into chat. Fix active bugs. Add temporal columns at the same time as the read wire-up — records written before this are undateable and unmigrateable. Audit the two unknown store connections before assuming they're broken.

**Wave 2 — Instrument and harden** (items 6–9, 1 week)
Tier caching removes 100–400ms from every chat turn and eliminates Sui Testnet SLA as a companion chat hard dependency. Telemetry and parser observability gate all cost and coverage decisions downstream. Rate limiting closes the Claude token exposure.

**Wave 3 — Unify the knowledge graph** (items 10–12, 2–3 weeks)
All ingest paths write to `system_knowledge.db`. Context injection becomes always-on. This is the architectural prerequisite for Signal rewire, contribution incentives, and temporal/confidence scoring.

**Wave 4 — Cost optimization** (items 13–15, requires Wave 2)
~35% cost reduction at 50 pilots/day (~$42/month). Scales to ~$350–400/month savings at 500 pilots/day. **Do not route haiku to any call that writes permanently to intel stores without schema validation at the write path.** Bad intel is permanent.

| Line | All-sonnet $/mo | With routing | Saving |
|------|----------------|-------------|--------|
| Companion chat | ~$90 | ~$70 | ~$20 |
| Log uploads | ~$18 | ~$5 | ~$13 |
| Huginn Signal | ~$13 | ~$4 | ~$9 |
| **Total** | **~$121** | **~$79** | **~$42** |

**Wave 5 — Deepen the parser** (items 16–17)
Quarantine store first (observability gate), then candidate extraction. PvP systems are currently the most blind — heaviest combat activity = most `gamelog_raw combat` events dropped. This closes that gap incrementally.

**Wave 6 — Platform and polish** (items 18–20)
Signal rewire after system_knowledge has real data. Contribution incentives after the flywheel is demonstrably spinning. UI after the intelligence layer has substance.

---

## Hard Rules

1. **No haiku writes to `system_knowledge.db` or `log_intel_store.py` without schema validation at the write path.** Misattributed intel is permanent and cited forever.
2. **Temporal columns from the start.** Any new intel record without `first_seen_at`/`last_seen_at` requires a migration to age out.
3. **Tier caching before model routing.** Routing keyed on tier inherits the Sui RPC latency otherwise.
4. **Telemetry baseline before any routing decision.** Cost estimates are estimates.
5. **`gamelog_raw` text has no path to any Claude-facing function.** Inviolable security boundary.
6. **dapp-kit boundary check before any new data access code.** See `CLAUDE.md` — Data Layer Boundary section.

---

## Key Risks

| Risk | Severity | Mitigation |
|------|---------|-----------|
| Mission claim false — log intel not queryable | Critical | Item 1 (hours of work) |
| Active admin/GateUI bug blocks owner use | Critical | Item 2 |
| Sui Testnet degradation = companion chat failure | High | Item 6 |
| No rate limiting — Claude tokens exposed | High | Item 9 |
| PvP systems most blind (combat events dropped) | High | Items 16–17 |
| Haiku writing permanent bad intel | High | Schema validation, Wave 4 rule |
| No temporal decay — stale intel indistinguishable from fresh | High | Item 3 |
| dapp-kit 0.1.7 patch breaks on version bump | Medium | Verify on every `npm install` |
| No backup — disk failure loses all intel | Medium | Snapshot strategy (not in ranking above; add if deploying to production) |
