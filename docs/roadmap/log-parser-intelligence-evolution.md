# Roadmap: Log Parser Intelligence Evolution

## Current Architecture (Accurate State)

The docs describe a "strict drop" policy. The actual implementation has two layers:

**Layer 1 — `log_parsers.py`:** Only `_DISCARD_TYPES` (`info`, `question`, `warning`, `hint`) and untagged non-undock lines return `None`. Every other unrecognized typed line emits `{"type": "gamelog_raw", "msg_type": ..., "text": ...}` — the text is preserved.

**Layer 2 — `log_analysis.py:168`:** `summarize_for_huginn` explicitly excludes `gamelog_raw` events from the Claude-facing output (prompt injection risk). This is the real security boundary, not Layer 1.

**The gap:** `gamelog_raw` events exist in memory during the upload request, then vanish. They never reach `merge_upload`, `_update_known_types`, or `system_knowledge.record_from_upload`. Unknown entity types — other players, ships, player-owned structures — contribute zero intelligence to the shared knowledge base.

---

## Core Problem

The described feedback loop (KEY_CONCEPTS_AND_DECISIONS.md: "as unknown entity samples are collected in production, they are categorized and the parser is updated") has no technical implementation. There is no collection mechanism. Discovery requires a developer to manually intercept a live upload. Parser coverage grows discontinuously — only when someone happens to look.

In a PvP-first game, systems with heavy player activity are exactly where the parser is most blind. `hostiles=[]` for the most dangerous systems is the failure mode.

---

## Strategic Moves

Three independent levers, ordered by risk and effort:

### 1. Make blind spots visible (no behavior change)
Count `gamelog_raw` events by `msg_type` per upload. Persist aggregate drop counts (not text) server-side. Expose in an OWNER-gated admin endpoint. This costs nothing on the security boundary and immediately quantifies what's being lost.

### 2. Quarantine store (low risk, high discovery value)
Persist 3–5 anonymized text samples per unrecognized `msg_type` per environment, TTL-capped at 30 days. Developer-visible only — no connection to any AI tool or prompt path. This converts the "collect samples" loop from aspirational to mechanical. Without it, the parser can only grow when a developer is watching live traffic.

**Hard constraint:** Quarantine data must have no code path to any Claude-facing function. This is the one rule that cannot be traded off.

### 3. Candidate hostiles extraction (medium risk, high intel value)
For `gamelog_raw combat` events, run a lightweight heuristic name extractor at upload time — producing structured entity name strings, not free text. Store results under a separate `candidate_hostiles` key in the intel store, clearly flagged as unverified. This recovers intelligence from the exact events that matter most (player encounters) without touching the security boundary.

Shadow parser approach: apply candidate regexes against quarantine samples server-side. If a candidate matches >N samples across >K distinct wallets, flag for parser promotion.

---

## Phased Roadmap

**Phase 1 — Observability**
- Add `gamelog_raw` drop counts (by `msg_type`) to upload response
- Persist aggregate counts server-side
- Admin endpoint: parser coverage stats over time

**Phase 2 — Quarantine**
- Persist 3–5 raw text samples per unrecognized `msg_type` per env (TTL 30 days)
- Developer CLI: apply candidate regexes against quarantine, report match rates
- Target: one new entity type promoted per week instead of per incident

**Phase 3 — Candidate intel extraction**
- Heuristic name extractor runs against `gamelog_raw combat` at upload time
- `candidate_hostiles` added to intel store schema (separate from `hostiles`)
- `format_for_huginn` labels them distinctly — Claude knows they're unverified
- Target: player encounter data reaches the knowledge base for the first time

**Phase 4 — Tiered intel quality**
- `_known_types.json` gains entity category tags: `npc`, `player`, `structure`
- `system_knowledge` stores per-category hostile counts
- Recon tool surfaces entity categories separately to pilots

---

## Success Metrics

| Metric | Direction |
|--------|-----------|
| % of typed log lines yielding structured events (not `gamelog_raw`) | >85% across active player base |
| Parser update cycle | Weekly (data-driven) vs. incident-triggered |
| Systems with >3 verified hostiles in `system_knowledge` | Doubles per month once player combat captured |
| Time from "new entity type appears in production" to "parser updated" | Days, not weeks |

---

## Files Affected

| File | Change area |
|------|-------------|
| `src/log_parsers.py` | New entity patterns as quarantine drives discovery |
| `src/log_analysis.py` | Candidate extraction hook; drop count instrumentation |
| `src/log_intel_store.py` | `candidate_hostiles` field; quarantine write path |
| `src/system_knowledge.py` | Accept candidate hostiles; entity category tagging |
| `src/endpoints/logs.py` | Return drop counts in upload response |
| New: `src/log_quarantine.py` | Quarantine store (samples + expiry) |

---

## Constraints

- Security boundary is inviolable: `gamelog_raw` text never reaches any Claude-facing function.
- All phases are independent — Phase 1 ships alone without committing to Phase 2+.
- Hackathon submission branch frozen. All work on `post-hackathon` or later branches.
