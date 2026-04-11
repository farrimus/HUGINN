# Agentic Engineering — Workflow Improvements

Future considerations for improving how work is delegated to Claude Code and iterated on.
Based on Andrej Karpathy's "agentic engineering" framing (April 2026).

---

## 1. Acceptance criteria in task specs

Current task opening prompts (in `memory/`) define intent and order of work, but not explicit
pass/fail criteria per step. This causes fuzzy "confirm it works" handoffs.

**What to add:** a one-line "Definition of done" per implementation step.

Examples:
- Backfill step done = run script twice, counts don't change
- `query_system()` done = returns `{found: True, enemies: [...], ores: [...]}` for a known system
- Rename done = `grep radius_scan src/ prompts/` returns zero hits

This is low-effort to add when writing the opening prompt. High payoff during implementation.

---

## 2. Fixed eval set for `tools.yaml` iteration

`tools.yaml` is live-reload, no restart needed. It's already architected as the mutable
iteration layer (see `docs/ARCHITECTURE.md` → Prompt Layer). What's missing is a fixed set
of test inputs to iterate against.

**What to build:** a small eval set — 8–12 real pilot queries covering the main tool paths:

| Query | Expected tool | Pass criteria |
|-------|--------------|---------------|
| "what lives in UTR-SN4?" | `query_system_knowledge` | Returns enemy + ore data, in-character |
| "plan a route to [system]" | `plan_route` | Valid hop count, no apology prefix |
| "am I safe here?" | `assess_threat` | Threat level returned, no hedge |
| "what have other pilots reported?" | `query_intel` | Cites field reports if any exist |
| ... | ... | ... |

**How to use:** when iterating `tools.yaml`, run the eval set before and after a change.
Keep changes that improve pass rate. Revert those that don't. This is the ratchet.

This eval set could live as a script in `scripts/eval_tools.py` that hits `/companion/chat`
with each query and prints pass/fail against the criteria — or just as a manual checklist
in `prompts/TOOLS_YAML_GUIDE.md`.

---

## What doesn't apply

- AutoResearch itself — designed for GPU-bound ML experiments, not a web app
- Parallel agent grids — implementation steps here are sequential with dependencies
- The 80/20 code-writing flip — already the current workflow
