# Intelligence Pipeline Analysis — Post-Hackathon

## The Core Problem

The mission claims "every log upload adds to a shared, permanent knowledge base." This is not currently true.

Log uploads complete the write step, then stop. `log_intel_store.py` data has **no read path into companion chat**. `ARCHITECTURE_SUMMARY.md` explicitly marks this as "Future." Every log ever uploaded is sitting in per-wallet JSONL files that nothing queries.

`system_knowledge.db` — the intended global aggregation layer — is "in progress" with no feeders and no AI tools pointing at it.

---

## What Actually Works

- Kill feed: automated, continuous, blockchain-verified. The only source that compounds without pilot action.
- `intel_store.py` field reports: wired via `query_intel` tool. Works per-structure.
- Route planning: complete, self-contained.
- Access tier model: sound foundation for tiered intel distribution.

---

## Disconnected Silos

| Store | Scope | AI Access |
|-------|-------|-----------|
| `intel_store.py` field reports | Per-structure | Wired (`query_intel`) |
| `log_intel_store.py` log intel | Per-wallet JSONL | **Not wired** |
| `killmails.jsonl` | Global append-only | Partial (context_builder) |
| `memory_store.py` event memory | Per-structure | Unknown |
| `system_knowledge.db` | Global | In progress — no tools |

No synthesis layer exists across these. The AI must query each independently and currently cannot reach two of the five.

---

## Quality Ceilings

**Temporal decay: none.** 3-month-old intel equals 5-minute-old intel.

**Confidence scoring: none.** One pilot report equals fifty pilot reports.

**Cross-pilot aggregation: none.** 50 pilots uploading logs about System X = 50 separate files, not one enriched record. Queries require O(pilots) file scans.

**Parser coverage gap:** Player ships, other pilots, and player-owned structures are dropped by `log_parsers.py`. These are the highest-value intelligence targets in a PvP sandbox. Every dropped line is permanently lost.

**Huginn Signal is informationally narrow.** Signal input sources are undocumented, but architecture suggests it only sees kills and structure state — no log intel, no field reports, no system knowledge.

---

## Five Open Questions (Answer These Before Roadmapping)

1. **Is `log_intel_store.py` data accessible anywhere?** "Future" in docs — verify that it's truly zero read paths, not just undocumented ones.
2. **Does `query_intel` aggregate across all wallets, or only the current pilot's?** If it's personal memory only, collective intel doesn't exist at all.
3. **What does `huginn_news_task.py` actually read?** Determines how much Signal work is wiring vs. rewrite.
4. **Does `memory_store.py` feed `context_builder.py`?** If not, per-structure event history is another unwired store.
5. **What is the actual volume of `data/{env}/log_intel/`?** File-scan performance concern is theoretical below ~50 pilots, real above it.

---

## Ranked Improvements

### Tier 1 — Close the Loop (Low effort, immediate impact)
1. **Wire `log_intel_store.py` into companion chat** — add `get_log_intel(system_id)` tool in `ai_tools.py`. Unlocks all accumulated log data instantly.
2. **Inject system context into `context_builder.py` proactively** — pre-computed 3–5 sentence system summary from `system_knowledge.db` in every context block. Converts opt-in tool call to always-on.

### Tier 2 — Unify the Graph (Medium effort, foundational)
3. **Complete `system_knowledge.db` as aggregation target** — all sources write into it on ingest: log uploads, killmails, field reports. Enables O(1) per-system queries.
4. **Add temporal columns** — `first_seen_at`, `last_seen_at`, `observation_count` per entity-system row. No new data needed, timestamps already exist.

### Tier 3 — Elevate the Signal (Depends on Tier 2)
5. **Rewire `huginn_news_task.py`** to read from `system_knowledge.db` — notable changes since last broadcast, kill deltas, new sightings.
6. **Bridge `intel_store.py` field reports into `system_knowledge.db`** — pilot reports that reference a system upsert into the global graph.

### Tier 4 — Coverage and Incentive (Longer horizon)
7. **Unknown entity accumulator in `log_parsers.py`** — route dropped player-entity lines to a passive corpus. Enables parser improvement without losing production data.
8. **Contribution → VETTED tier pathway** — in-lore reward for log uploads using existing `AccessRegistry` + `session_store.py`. No new mechanics.

---

## Claude API Cost Model

At scale, all-`claude-sonnet-4-6` is the wrong split:

| Use case | Correct model |
|----------|--------------|
| Companion chat | `claude-sonnet-4-6` (keep) |
| Log summarization (`log_analysis.py`) | `claude-haiku-4-5` |
| Huginn Signal generation | `claude-haiku-4-5` |
| Pre-computed system summaries | Pre-computed offline, not per-request |

Context window costs also grow as system intel is injected into every request. Pre-computed summaries (generated once on write, stored as text) are the cost control.

---

## Persona Risk

As the knowledge layer deepens, HUGINN risks sounding like a database. The mitigation is prompt design: "Multiple scouts confirm Drifter activity — last sighting 36 hours ago" not "4 observations, confidence=0.87." Confidence scores feed the prompt; in-lore language leaves it. This distinction belongs in `prompts/companion.md` as the knowledge layer grows.
