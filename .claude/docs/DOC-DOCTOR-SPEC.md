# Doc-Doctor Skill Specification

**Status:** Requirements & Implementation Guide (2026-03-18)

This document specifies the expected behavior of the doc-doctor skill to maintain the integrated documentation system across agent docs, reference docs, and superpowers artifacts.

---

## Overview

Doc-doctor is responsible for:
1. **Generating** agent-facing module documentation (`.claude/docs/modules/`)
2. **Indexing** reference documentation (`/docs/ref/`)
3. **Cataloging** superpowers artifacts (`/docs/superpowers/specs/` and `/docs/superpowers/plans/`)
4. **Maintaining** cross-reference metadata (REGISTRY.md, audit trail)
5. **Validating** quality and consistency across all three systems

---

## Scope: What Doc-Doctor Manages

### GENERATE (Auto-Maintained)
```
.claude/docs/
├── modules/
│   ├── index.md                          [GENERATE]
│   ├── auth.md                           [GENERATE from src/auth.py]
│   ├── claude_client.md                  [GENERATE from src/claude_client.py]
│   ├── context_builder.md                [GENERATE from src/context_builder.py]
│   ├── deal_store.md                     [GENERATE from src/deal_store.py]
│   ├── endpoints.md                      [GENERATE from src/endpoints/]
│   ├── galaxy_db.md                      [GENERATE from src/galaxy_db.py]
│   ├── location_index.md                 [GENERATE from src/location_index.py]
│   ├── log_buffer.md                     [GENERATE from src/log_buffer.py]
│   ├── memory_store.md                   [GENERATE from src/memory_store.py]
│   ├── nova_client.md                    [GENERATE from src/nova_client.py]
│   ├── radius_search.md                  [GENERATE from src/radius_search.py]
│   ├── route_engine.md                   [GENERATE from src/route_engine.py]
│   ├── ship_profile.md                   [GENERATE from src/ship_profile.py]
│   ├── ssu_poller.md                     [GENERATE from src/ssu_poller.py]
│   ├── structure_auth.md                 [GENERATE from src/structure_auth.py]
│   ├── structure_client.md               [GENERATE from src/structure_client.py]
│   ├── structure_profile.md              [GENERATE from src/structure_profile.py]
│   ├── token_manager.md                  [GENERATE from src/token_manager.py]
│   ├── type_names.md                     [GENERATE from src/type_names.py]
│   └── world_api.md                      [GENERATE from src/world_api.py]
├── REGISTRY.md                            [GENERATE from mapping]
├── nav.md                                 [MAINTAIN (user-provided template)]
├── MANIFEST.md                            [GENERATE]
└── doc-map.md                             [GENERATE audit trail]
```

### READ & INDEX (Not Modified)
```
/docs/ref/
├── routing.md                             [READ: extract sections]
├── ship-ai.md                             [READ: extract sections]
├── structure-ai.md                        [READ: extract sections]
├── radius-search.md                       [READ: extract sections]
├── ui.md                                  [READ: extract sections]
├── ops.md                                 [READ: extract sections]
├── overlay.md                             [READ: extract sections]
└── structure-debug.md                     [READ: extract sections]

/docs/
├── CODEBASE.md                            [READ: for cross-references]
└── log-pipeline.md                        [READ: for cross-references]

/docs/superpowers/
├── specs/
│   ├── 2026-03-11-ship-ai-companion-design.md      [CATALOG]
│   ├── 2026-03-11-blockchain-research.md           [CATALOG]
│   ├── 2026-03-13-structure-ai-design.md           [CATALOG]
│   ├── 2026-03-15-nav-computer-design.md           [CATALOG]
│   ├── 2026-03-15-structure-ai-context-design.md   [CATALOG]
│   └── 2026-03-17-secure-token-architecture.md     [CATALOG]
└── plans/
    ├── 2026-03-11-ship-ai-companion.md             [CATALOG]
    ├── 2026-03-13-structure-ai.md                  [CATALOG]
    ├── 2026-03-13-zklogin-auth.md                  [CATALOG]
    ├── 2026-03-14-context-enrichment.md            [CATALOG]
    ├── 2026-03-15-structure-ai-context-enrichment.md [CATALOG]
    ├── 2026-03-16-nav-computer.md                  [CATALOG]
    ├── 2026-03-16-inventory-via-sui-rpc.md         [CATALOG]
    ├── 2026-03-17-deal-mechanic.md                 [CATALOG]
    └── 2026-03-17-radius-search.md                 [CATALOG]
```

**Never modify** `/docs/superpowers/` structure — only read and catalog.

---

## Detailed Tasks

### Task 1: Generate Agent Module Docs

**Input:** Source files in `src/`
**Output:** `.claude/docs/modules/[name].md` (≤150 lines each)
**Checksum:** Track MD5 of source file to detect changes

For each module:
1. **Cross-reference `/docs/ref/`** — For modules listed in reference docs, read the relevant section FIRST to understand actual behavior and APIs. This is the ground truth.
2. **Scan source file** for docstrings, classes, public functions
3. **Validate documented APIs** — For every function/class/method documented, verify it exists in source code. Do NOT invent APIs or guess return types.
4. **Generate section:** "When Should an Agent Use This Module?" (decision tree)
5. **Generate section:** "Public API" (function/class signatures with exact types from source)
6. **Generate section:** "Behavior" (state transitions or truth tables, grounded in source code)
7. **Generate section:** "Integration Points" (inputs, outputs, dependencies)
8. **Validate:** ≤150 lines, no missing sections, all APIs exist in source
9. **Store checksum** in doc-map.md for next run

**Critical Rule:** Never generate API documentation without reading the actual source code. Validate every documented method exists. If unsure, check reference docs or ask for clarification.

**Format reference:** See `.claude/docs/modules/context_builder.md` for example.

---

### Task 2: Generate & Update Registry

**Input:**
- All 20 module docs (paths and names)
- All reference docs in `/docs/ref/` (extract section names)
- All superpowers artifacts in `/docs/superpowers/`
- Mapping rules (see below)

**Output:** `.claude/docs/REGISTRY.md`

**Mapping rules:**

For each module, determine cross-references:

| Module | Reference Doc | Design Spec | Plan |
|--------|---------------|-------------|------|
| `auth` | `ops.md`, `structure-ai.md` | `secure-token-architecture.md` | `zklogin-auth.md` |
| `claude_client` | `ship-ai.md` | `ship-ai-companion-design.md` | `ship-ai-companion.md` |
| `context_builder` | `ship-ai.md`, `log-pipeline.md` | `ship-ai-companion-design.md` | `context-enrichment.md` |
| `deal_store` | `structure-ai.md` | None | `deal-mechanic.md` |
| `endpoints` | `CODEBASE.md`, `ship-ai.md`, `structure-ai.md` | None | None |
| `galaxy_db` | `routing.md` | None | None |
| `location_index` | `structure-ai.md` (section: "Structure Location Resolution") | None | None |
| `log_buffer` | `log-pipeline.md`, `ship-ai.md` | `ship-ai-companion-design.md` | None |
| `memory_store` | `structure-ai.md` | `structure-ai-context-design.md` | `structure-ai-context-enrichment.md` |
| `nova_client` | `structure-ai.md` | `blockchain-research.md`, `secure-token-architecture.md` | `inventory-via-sui-rpc.md` |
| `radius_search` | `radius-search.md` | None | `radius-search.md` (plan) |
| `route_engine` | `routing.md` | `nav-computer-design.md` | `nav-computer.md` |
| `ship_profile` | `routing.md` | `nav-computer-design.md` | `nav-computer.md` |
| `structure_auth` | `structure-ai.md` | `secure-token-architecture.md` | `zklogin-auth.md` |
| `structure_client` | `structure-ai.md` | `structure-ai-design.md` | `structure-ai.md` |
| `structure_profile` | `structure-ai.md` | `structure-ai-design.md` | `structure-ai-context-enrichment.md` |
| `ssu_poller` | `structure-ai.md` | `structure-ai-design.md` | `structure-ai-context-enrichment.md` |
| `token_manager` | `structure-ai.md` | `secure-token-architecture.md` | `zklogin-auth.md` |
| `type_names` | `ship-ai.md` | None | None |
| `world_api` | `routing.md`, `ship-ai.md` | None | None |

**Schema for REGISTRY.md:**

For each module:
```
### [module_name]
- **Agent Doc:** [link to .claude/docs/modules/[name].md]
- **Reference:** `/docs/ref/[file].md` (section: "[section name]")
- **Related Modules:** [comma-separated list]
- **Design Artifact:** `/docs/superpowers/specs/[date]-[topic].md` (answers: "Why?")
- **Plan Artifact:** `/docs/superpowers/plans/[date]-[topic].md` (answers: "How? Blockers?")
- **Tests:** `/opt/eve-frontier/tests/test_[module].py`
```

Plus summary tables for superpowers specs and plans (see current REGISTRY.md for format).

---

### Task 3: Build Module Index

**Input:** All module docs in `.claude/docs/modules/`
**Output:** `.claude/docs/modules/index.md`

Organize modules by category (Core AI, State Management, Game Data, Structure, Auth, API, Marketplace) with brief descriptions and links. Reference nav.md and REGISTRY.md at the bottom.

---

### Task 4: Update Navigation Guide

**Input:** User-provided template at `.claude/docs/nav.md`
**Output:** Validate & ensure links are correct

Do not auto-generate nav.md — it's user-curated. But verify:
- All paths are navigable (no 404s)
- All links in Path 2, 3, 4 sections are valid
- Table of reference docs matches files in `/docs/ref/`

---

### Task 5: Maintain Audit Trail

**Output:** `.claude/docs/doc-map.md`

Track for each module:
- Source file path
- Source file MD5 checksum
- Last doc generation date
- Status (new, updated, unchanged, orphaned)

Also track:
- Total modules documented
- Line count violations (>180 hard max)
- Missing required sections
- Index creation status

---

### Task 6: Generate MANIFEST

**Output:** `.claude/docs/MANIFEST.md`

Describe the documentation system (what doc-doctor does, directory structure, format rules, maintenance guidelines).

---

## Quality Gates

Run validation after each generation. Fail if:

1. **Module docs:**
   - Line count > 180 (hard limit)
   - Missing "When Should an Agent Use This Module?" section
   - Missing "Integration Points" section
   - Missing "Public API" section

2. **Registry:**
   - Any module not mapped
   - Broken links to reference docs
   - Broken links to superpowers artifacts
   - Duplicate entries

3. **Index:**
   - Missing any module
   - Broken links to module docs
   - Navigation links broken

4. **Checksums:**
   - Source files with new/changed checksums → regenerate doc
   - Docs with no corresponding source file → mark orphaned, offer to delete

---

## Triggers

Doc-doctor should run:
1. **Explicitly:** When user invokes `/doc-doctor` skill
2. **Implicitly:**
   - After a module source file is added/modified (checksum change)
   - After `/docs/ref/` files are modified
   - After `/docs/superpowers/` files are added (new spec/plan)

**Never run** implicitly while a user is editing doc-doctor scope — only on explicit invocation to avoid conflicts.

---

## Implementation Gaps (As of 2026-03-18)

Current doc-doctor (from MANIFEST.md):
- ✅ Generates module docs (≤150 lines, required sections)
- ✅ Tracks checksums (doc-map.md)
- ✅ Audits quality (line count, sections)
- ❌ Does NOT read `/docs/ref/` (should cross-reference)
- ❌ Does NOT catalog `/docs/superpowers/` (should track specs/plans)
- ❌ Does NOT generate REGISTRY.md (NEW artifact)
- ❌ Does NOT validate navigation guide (nav.md)
- ❌ Does NOT link modules to reference docs & artifacts

**To implement:** Update doc-doctor skill.md to add Tasks 2, 4, 5, 6 above.

---

## Example: What doc-doctor Should Output (2026-03-18)

After running `/doc-doctor`:

```
✓ Scanning src/ for modules...
  Found 20 modules (19 files, 1 directory)

✓ Generating module docs...
  auth.md (120 lines) — no changes
  claude_client.md (145 lines) — regenerated
  context_builder.md (135 lines) — regenerated
  [... 17 more]

✓ Reading /docs/ref/ for cross-references...
  routing.md (12 sections)
  ship-ai.md (8 sections)
  structure-ai.md (10 sections)
  [... 5 more]

✓ Cataloging /docs/superpowers/...
  specs/ (6 artifacts)
  plans/ (9 artifacts)

✓ Generating REGISTRY.md...
  20 modules linked to references
  18/20 modules linked to design specs
  15/20 modules linked to implementation plans

✓ Validating navigation guide (nav.md)...
  All paths navigable ✓
  All links valid ✓

✓ Updating audit trail (doc-map.md)...
  Checksums updated
  New modules: 0
  Updated: 2
  Unchanged: 18
  Orphaned: 0

✓ Generating MANIFEST.md...

QUALITY AUDIT:
✓ Line counts: all ≤150 (worst: 145)
✓ Required sections: all present
✓ Cross-references: all valid
✓ Registry: complete
✓ Navigation: all paths valid

Summary:
- 20 modules documented
- 8 reference docs cross-linked
- 15 superpowers artifacts cataloged
- Status: ALL PASS

Generated: 2026-03-18T15:23:45Z
Commit: (ready to git add)
```

---

## Next Steps

1. **Current state:** REGISTRY.md and nav.md are manually created (working templates)
2. **To complete:** Update doc-doctor skill.md to auto-generate REGISTRY.md and validate nav.md
3. **Validation:** Run `/doc-doctor` to test that it:
   - Generates module docs ✓ (already working)
   - Generates REGISTRY.md ✅ (new requirement)
   - Validates nav.md ✅ (new requirement)
   - Audits all three systems ✅ (new requirement)

---

## References

- `.claude/docs/nav.md` — Navigation guide for agents
- `.claude/docs/REGISTRY.md` — Current registry (template, should be auto-generated)
- `.claude/docs/MANIFEST.md` — System description
- `/intent.md` — Foundational values and lore
