# Roadmap: Tiered Model Routing

## Problem

Every Claude API call uses claude-sonnet-4-6 regardless of call type, access tier, or quality requirement. Log summarization, NONE-tier lobby chat, and Huginn Signal are all priced at sonnet rates when cheaper models are sufficient. At scale, this is the dominant cost lever.

---

## Decision Table

| Call type | Tier | Model | Condition |
|-----------|------|-------|-----------|
| Companion chat | OWNER / TRIBE | sonnet-4-6 | Always |
| Companion chat | VETTED | sonnet-4-6 | Always (tool reliability required) |
| Companion chat | NONE | haiku-4-5 | Always — no tools, lobby persona only |
| Log summarization | Any (stillness) | haiku-4-5 | ≤100 events/system |
| Log summarization | Any (stillness) | sonnet-4-6 | >100 events/system — complex sequences, permanent storage |
| Log summarization | Any (utopia) | haiku-4-5 | Always — test env, not production intel |
| Huginn Signal | Any | haiku-4-5 | Kill count ≤ 2× 7-day rolling hourly average |
| Huginn Signal | Any | sonnet-4-6 | Kill count > 2× average, or any structure destruction event |

**Fallback:** If tier is unknown/resolution fails, always use sonnet-4-6. Never fail open to NONE routing.

**NONE tier:** Pass an empty tool list, not a restricted one. Tools cannot be called if not defined.

---

## Hard Prerequisites

**1. Access tier caching must land first.** Tier is currently resolved via blocking Sui RPC per request (100–400ms). Model routing keyed on tier inherits that latency. The access-tier-caching roadmap removes RPC from the hot path — routing should run on cached tier, not live RPC. Do these in sequence: tier caching → routing.

**2. The single `CLAUDE_MODEL` env var must become three.** The current single global config is a blocker. Need independently configurable: `CLAUDE_MODEL_COMPANION`, `CLAUDE_MODEL_LOG`, `CLAUDE_MODEL_SIGNAL`.

---

## Prompt Engineering Rules

**For haiku on NONE tier:**
- Derive from prompts/companion.md but: strip all tool-use sections, add explicit length constraints (1–4 sentences max), replace stylistic persona guidance with explicit rule statements.
- Core identity block must be character-for-character identical to the sonnet variant. Persona consistency across tiers depends on this.
- Negative constraints must be explicit: "Do not offer unsolicited help. Do not summarize prior context. Do not use filler phrases."

**For haiku on log summarization:**
- Strict output schema, not open-ended summarization. Enumerate fields, constrain value types. Schema validation at application layer before writing to intel store.
- A log summarization that fails schema is discarded, not written. Bad intel is permanent.

**For haiku on Huginn Signal:**
- Explicit format template with per-section character limits. Haiku holds format constraints; it drifts on stylistic guidance.

---

## Cost Impact

Approximate current scale (~50 active pilots/day):

| Line | All-sonnet $/mo | With routing $/mo | Saving |
|------|----------------|------------------|--------|
| Companion chat | ~$90 | ~$70 | ~$20 |
| Log uploads | ~$18 | ~$5 | ~$13 |
| Huginn Signal | ~$13 | ~$4 | ~$9 |
| **Total** | **~$121** | **~$79** | **~$42 (35%)** |

Savings widen with scale. Log upload cost scales with pilot count; Huginn Signal cost scales with active environments. At 10× scale (500 pilots/day): ~$350–400/month saved.

---

## Quality Risks

**Log intel accuracy is permanent.** Haiku misattributing entities or dropping kill events writes bad data to the knowledge base indefinitely. It gets cited by future queries from any pilot. Mitigate: schema validation before write, sonnet escalation above event-count threshold.

**NONE-tier persona break destroys top-of-funnel.** NONE is the first thing a new pilot sees. One generic-feeling response ends the session. Tight, validated system prompt before shipping haiku to NONE on stillness.

**Tool discipline on VETTED must not regress.** The routing table keeps VETTED on sonnet precisely because tool call failures are silent — the model returns no error, it just returns wrong or missing data. Do not route VETTED to haiku without a working message-intent classifier.

---

## Phased Rollout

**Phase 0 — Telemetry (immediate)**
Emit structured log entry per Claude API call: `{call_type, tier, model_used, tokens_in, tokens_out, tool_calls_count, latency_ms, environment}`. No routing changes. Establish baseline. This data gates every subsequent decision.

**Phase 1 — Log summarization → haiku**
Safest change. No player-facing impact. Validate on 10–20 manual comparisons (haiku vs. sonnet on identical input). Schema compliance check. Ship to stillness only after validation. Target: ~35% reduction in log processing cost.

**Phase 2 — Huginn Signal → haiku with sonnet escalation**
Define kill-spike threshold from kill feed data before implementing. Test 2–3 Signal cycles manually. Gate on OWNER feedback — they see Signal quality directly.

**Phase 3 — NONE tier companion → haiku**
Requires tight NONE-tier prompt variant. Test on utopia first. Gate to stillness after 48h clean behavior on utopia. Monitor: session depth (turn count), repeat-question rate. Tier caching must be in production before this ships.

**Phase 4 — VETTED routing experiment (conditional)**
Only if Phase 1–3 telemetry confirms haiku quality is consistent AND a reliable query-intent classifier exists. Smallest payoff, highest operational risk. Skip if volume doesn't justify the complexity.

---

## Constraints

- Hackathon submission branch frozen. All work on post-hackathon branch.
- Do not modify AccessRegistry contract, frontend, or dapp-kit integration.
- Never route to haiku any call that writes permanently to the knowledge base without schema validation in the write path.
- VETTED escalation to haiku is Phase 4 only — do not conflate with Phase 3.
