# Documentation Navigation Guide

**Auto-maintained by doc-doctor.** Last updated: 2026-03-18

---

## Choose Your Path

### Path 1: "I need to use a module"

1. Find the module name in [modules/index.md](modules/index.md) (categorized by function)
2. Open the module doc (≤150 lines, answers: "When should I use this?")
3. Check "Integration Points" section for data flow
4. If you need algorithm details, use Path 2

**Example:** Using `route_engine` to calculate a route?
→ Read `modules/route_engine.md` (public API, behavior) → Check REGISTRY.md for reference docs

---

### Path 2: "I need to understand an algorithm or design"

Choose by topic:

| Topic | Reference Doc | What's Inside |
|-------|---------------|---------------|
| **Routing & Navigation** | `/docs/ref/routing.md` | A* algorithm, heat formula, ship physics, jump range calculations |
| **Ship AI & Companion** | `/docs/ref/ship-ai.md` | Log parsing, context assembly, Claude integration, event flow |
| **Structure AI & Access** | `/docs/ref/structure-ai.md` | Structure state, access control, Sui integration, telemetry |
| **Spatial Queries** | `/docs/ref/radius-search.md` | Spatial indexing, range queries, performance characteristics |
| **UI & Browser** | `/docs/ref/ui.md` | index.html, debug.html, in-game browser environment |
| **Operations & Config** | `/docs/ref/ops.md` | Configuration, startup, known gaps, lore reference |
| **DX12 Overlay** | `/docs/ref/overlay.md` | C++ overlay modules, rendering, integration with game |

---

### Path 3: "I need to understand the whole system"

1. Start with `/docs/CODEBASE.md` — architecture overview and directory tree
2. Read `/docs/log-pipeline.md` — canonical log event flow
3. Then dive into specific modules (Paths 1–4)

---

## Structure Summary

```
.claude/docs/
├── nav.md (this file — navigation)
├── REGISTRY.md (module → reference → artifact mappings)
├── MANIFEST.md (documentation system description)
├── modules/
│   ├── index.md (quick TOC, categorized)
│   └── [module].md (20 files, ≤150 lines each)
├── references/ (deferred heavy content from modules)
└── assets/ (data formats, constants, diagrams)

/docs/
├── CODEBASE.md (architecture, directory tree)
├── log-pipeline.md (canonical log design)
├── ref/
│   ├── routing.md (algorithm, heat, physics)
│   ├── ship-ai.md (log parsing, context, Claude)
│   ├── structure-ai.md (state, access, telemetry)
│   ├── radius-search.md (spatial indexing)
│   ├── ui.md (HTML, browser, in-game)
│   ├── ops.md (config, startup, gaps)
│   ├── overlay.md (C++ overlay)
│   └── structure-debug.md (diagnostics)
└── superpowers/ (skill-managed, never modify)
    ├── specs/ (design docs, why)
    └── plans/ (task breakdowns, status)

/intent.md (lore, voice, values — foundational)
```

---

## Reading Order (First Time)

1. `/intent.md` — understand companion voice and values
2. `/docs/CODEBASE.md` — system architecture
3. `.claude/docs/modules/index.md` — what modules exist
4. This file — how to navigate
5. [REGISTRY.md](REGISTRY.md) — map modules to details
6. Then follow one of Paths 1–3 based on what you need to do

---

## Tips for Agents

- **Don't load everything:** Use REGISTRY.md to find exactly what you need
- **Token budgeting:** Agent docs (~2KB each), ref docs (~5–10KB)
- **Skip superpowers artifacts by default:** They're archived skill-managed documents in `/docs/superpowers/`. Read only if redesigning or stuck.
- **Navigation is: module doc → reference doc → code.** That covers 95% of use cases.

---

## Feedback

If you find:
- A module doc that's unclear → fix the source module, run `/doc-doctor`
- A missing cross-reference → check REGISTRY.md, might need updating
- A reference doc that's stale → update it and run `/doc-doctor` to re-index
