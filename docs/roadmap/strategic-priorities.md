# Strategic Priorities — Post-Hackathon

## State of the Mission

Core knowledge pipeline is operational. Log uploads write to `system_knowledge.db` via `log_intel_store.merge_upload()`. AI tools exist for field observations (`record_field_observation`), system queries (`query_system_knowledge`), and per-structure intel (`query_intel`, `log_intel`). Huginn Signal runs daily with KILL FEED and NETWORK DELTA blocks.

| Store | Has AI read path? | Compounds? |
|-------|------------------|------------|
| `intel_store.py` field reports | Yes (`query_intel`) | Per-structure only |
| `log_intel_store.py` log uploads | Yes (via `system_knowledge`) | Writes to global graph |
| `killmails.jsonl` | Partial (context_builder) | Yes — automated |
| `memory_store.py` event memory | Unaudited | Unknown |
| `system_knowledge.db` | Yes (`query_system_knowledge`) | Wired from log uploads |

---

## Open Items

| Rank | Item | Key files |
|------|------|-----------|
| 1 | Add temporal decay to intel stores (`first_seen_at`, `last_seen_at`, `observation_count`) | `log_intel_store.py`, `system_knowledge.py` |
| 2 | Audit `query_intel` scope — cross-pilot or personal only? | `ai_tools.py`, `intel_store.py` |
| 3 | Audit `memory_store.py` → `context_builder.py` connection | `memory_store.py`, `context_builder.py` |
| 4 | Access tier caching (resolve at register, cache in session, TTL refresh) | `session_store.py`, `endpoints/session.py`, `endpoints/companion.py` |
| 5 | Claude API telemetry (structured log per call: type, tier, model, tokens, latency) | `endpoints/companion.py`, `endpoints/logs.py`, `huginn_news_task.py` |
| 6 | Parser drop count observability (aggregate `gamelog_raw` by `msg_type`, admin endpoint) | `log_analysis.py`, `endpoints/logs.py`, `endpoints/admin.py` |
| 7 | Rate limiting on `/companion/stream` and `/logs/upload` | middleware or `endpoints/companion.py` |
| 8 | Wire killmail system visit count into `system_knowledge.db` | `blockchain_killmails.py`, `system_knowledge.py` |
| 9 | Backfill `system_knowledge.db` from existing log intel files | New: `scripts/backfill_system_knowledge.py` |
| 10 | Bridge `intel_store.py` field reports → `system_knowledge.db` | `intel_store.py`, `system_knowledge.py` |
| 11 | Proactive system summary injection into `context_builder.py` | `context_builder.py` |
| 12 | `/provemylocation` — POD export verification (Path A, no CCP needed) | `endpoints/session.py` or new endpoint, `world_api.py` |
| 13 | Warehouse receipts — backend PTB builders + vault state queries | `endpoints/transactions.py`, new endpoint file |
| 14 | Warehouse receipts — frontend deposit/redeem UI | `frontend/src/components/` |
| 15 | Warehouse receipts — AI tools (`check_receipts`, `deposit_item`, `redeem_receipt`) | `ai_tools.py` |
| 16 | Model routing: log summarization → haiku (requires #4 + #5 first) | `log_analysis.py`, `config.py` |
| 17 | Model routing: Huginn Signal → haiku with sonnet escalation | `huginn_news_task.py` |
| 18 | Model routing: NONE tier → haiku (requires tight prompt variant + #4) | `endpoints/companion.py`, `prompts/companion.md` |
| 19 | Log parser quarantine store (3–5 samples/msg_type, TTL 30d, dev-only) | New: `log_quarantine.py` |
| 20 | Candidate hostiles extraction from `gamelog_raw combat` | `log_analysis.py`, `log_intel_store.py` |
| 21 | Huginn Signal rewire to read `system_knowledge.db` (requires #11) | `huginn_news.py`, `huginn_news_task.py` |
| 22 | Contribution → VETTED tier pathway | `session_store.py`, AccessRegistry integration |
| 23 | UI revision (TerminalUI / GateUI / TurretUI) | `frontend/src/components/` |

---

## Sequencing Waves

**Wave 1 — Audit and harden the data layer** (items 1–3)
Temporal decay columns must go in before any more data is written — records without timestamps are unmigrateable. Audit the two unknown store connections before assuming they're broken.

**Wave 2 — Instrument and harden** (items 4–7)
Tier caching removes 100–400ms from every chat turn and eliminates Sui Testnet SLA as a companion chat hard dependency. Telemetry and parser observability gate all cost and coverage decisions downstream. Rate limiting closes the Claude token exposure.

**Wave 3 — Complete the knowledge graph** (items 8–11)
Wire remaining ingest paths (killmails, field report bridge). Run backfill. Enable proactive context injection. This is the prerequisite for Signal rewire and contribution incentives.

**Wave 4 — Verified location + item custody** (items 12–15)
Path A verified location is entirely auth-free and implementable now. Warehouse receipts require ~6 days total but unlock on-chain courier contracts.

**Wave 5 — Cost optimization** (items 16–18, requires Wave 2)
~35% cost reduction at 50 pilots/day (~$42/month). Do not route haiku to any call that writes permanently to intel stores without schema validation at the write path.

| Line | All-sonnet $/mo | With routing | Saving |
|------|----------------|-------------|--------|
| Companion chat | ~$90 | ~$70 | ~$20 |
| Log uploads | ~$18 | ~$5 | ~$13 |
| Huginn Signal | ~$13 | ~$4 | ~$9 |
| **Total** | **~$121** | **~$79** | **~$42** |

**Wave 6 — Deepen the parser** (items 19–20)
Quarantine store first (observability gate), then candidate extraction. PvP systems are the most blind — highest combat activity = most `gamelog_raw combat` events dropped.

**Wave 7 — Platform and polish** (items 21–23)
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
| Stale intel indistinguishable from fresh — no temporal decay | High | Item 1 |
| Sui Testnet degradation = companion chat failure | High | Item 4 |
| No rate limiting — Claude tokens exposed | High | Item 7 |
| PvP systems most blind (combat events dropped) | High | Items 19–20 |
| Haiku writing permanent bad intel | High | Schema validation, Wave 5 rule |
| No backup — disk failure loses all intel | Medium | Snapshot strategy |
| dapp-kit version bump breaks patched behavior | Medium | Verify on every `npm install` |
