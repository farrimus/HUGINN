# docs/ -- Deep Reference

Read these on demand, not by default. The CLAUDE.md in each source directory is sufficient for everyday work.

## Reference Docs

| Document | When to read |
|----------|-------------|
| ARCHITECTURE.md | Full system design, container diagram, data flows, deployment |
| KEY_CONCEPTS_AND_DECISIONS.md | Why something was designed a specific way |
| DATA_REFERENCE.md | Schemas: World API, Sui types, Galaxy DB tables and queries |
| DAPP_KIT_API.md | dapp-kit hook signatures, parameters, workflows (1,400 lines -- load sections, not the whole file) |
| FRONTEND_UI.md | Panel rendering pipeline, CSS architecture, component deep dive |
| TECH_STACK_AND_DEPENDENCIES.md | Package versions, dependency rationale, dapp-kit multi-tenant patch |
| SETUP.md | Local dev setup, build galaxy data, deploy frontend |

## Roadmap

`docs/roadmap/` contains future feature designs. Not committed work. Read only when explicitly working on a roadmap item. `roadmap/strategic-priorities.md` is the index.

## What is NOT in docs/

- AI prompts: `prompts/` directory
- Move contracts: `move/access_registry/`
- Build scripts: `build_universe.py`, `build_gate_graph.py`
- Tests: `tests/`

## Documentation Rules

- A document is correct only when it matches current codebase state. Outdated is wrong.
- One fact, one document. Never duplicate facts across files.
- Remove on sight: "Fixed on [date]", "Previously X, now Y", "Now uses", "As of [date]", TODO in reference docs.
- Present-tense imperatives. Tables over prose. Constraints first.
- Context budget: every line costs tokens. If a line does not prevent a specific mistake or answer a specific question, delete it.
