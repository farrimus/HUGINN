# Documentation Navigation

Use this file to find the right document for a given question. One document per topic — do not read multiple docs looking for the same answer.

---

## Question → Document

| Question | Read |
|----------|------|
| What is HUGINN and what problem does it solve? | `docs/PROJECT_OVERVIEW.md` |
| What is the product philosophy and north star? | `PHILOSOPHY.md` (root) |
| What is the engineering philosophy? | `PHILOSOPHY.md` → Engineering: The Algorithm |
| How does the system work end-to-end? | `docs/ARCHITECTURE.md` |
| What are the key data flows (chat, log upload, kill feed)? | `docs/ARCHITECTURE.md` → Key Data Flows |
| What is the access control model? | `docs/ARCHITECTURE.md` → Access Control Model |
| How does the blockchain integration work? | `docs/ARCHITECTURE.md` → Blockchain Role |
| Why was X designed this way? | `docs/KEY_CONCEPTS_AND_DECISIONS.md` |
| How does HUGINN's tool output formatting work? | `docs/FRONTEND_UI.md` → Panel Rendering System |
| Where do I edit tool descriptions or response style? | `prompts/tools.yaml` — see `docs/ARCHITECTURE.md` → Prompt Layer |
| How does the React UI render AI tool output? | `docs/FRONTEND_UI.md` → AI Tool Output Data Flow |
| What does each frontend component do? | `docs/FRONTEND_UI.md` → Component Map |
| How is the frontend CSS organized? | `docs/FRONTEND_UI.md` → CSS Architecture |
| What are the frontend color variables? | `docs/FRONTEND_UI.md` → CSS Architecture → Color variables |
| How do feature flags and tier access work? | `docs/FRONTEND_UI.md` → Tier and Feature System |
| How do I add a new AI tool output panel? | `docs/FRONTEND_UI.md` → Adding a New Tool Output Type |
| What are the Python/frontend dependencies and why? | `docs/TECH_STACK_AND_DEPENDENCIES.md` |
| How is the dapp-kit multi-tenant cache structured? | `docs/TECH_STACK_AND_DEPENDENCIES.md` → dapp-kit multi-tenant cache |
| What does dapp-kit own vs backend? | `CLAUDE.md` — Data Layer Boundary section |
| Where is file X and what does it do? | `docs/REPO_STRUCTURE.md` |
| What are the data schemas (structures, sessions, etc.)? | `docs/DATA_REFERENCE.md` |
| How do I set up the project locally? | `docs/SETUP.md` |
| How does Sui object ID derivation work? | `docs/ARCHITECTURE.md` → Assembly Data (handled by dapp-kit via `@mysten/bcs`) |
| What dapp-kit hooks and APIs are available? | `docs/DAPP_KIT_API.md` |
| What did we evaluate from the official UI components library? What should we adopt? | `docs/roadmap/eval-ui-components-library.md` |
| How should documentation be written, maintained, and structured? | `docs/DOC_STANDARDS.md` |
| What language patterns work best for directing AI agents? | `docs/DOC_STANDARDS.md` → Writing for Agents |
| When and how should a doc be updated? | `docs/DOC_STANDARDS.md` → Maintenance Workflow |

---

## Document Index

| File | Purpose | Audience |
|------|---------|----------|
| `PHILOSOPHY.md` | Product vision + engineering principles (Engineering: The Algorithm) | All |
| `CLAUDE.md` | Claude Code rules, data layer boundary, standing preferences | AI agents |
| `docs/NAVIGATION.md` | This file — maps questions to documents | AI agents |
| `docs/PROJECT_OVERVIEW.md` | Mission, feature list, current status | All |
| `docs/ARCHITECTURE.md` | System design, components, data flows, deployment | Developers |
| `docs/KEY_CONCEPTS_AND_DECISIONS.md` | Design decisions and trade-offs | Developers |
| `docs/TECH_STACK_AND_DEPENDENCIES.md` | Package versions, rationale, dapp-kit patch | Developers |
| `docs/REPO_STRUCTURE.md` | Every file, every directory, every entry point | Developers / AI agents |
| `docs/DATA_REFERENCE.md` | Data schemas: structures, sessions, killmails, intel | Developers |
| `docs/DAPP_KIT_API.md` | Full dapp-kit hook and API reference | Frontend developers |
| `docs/FRONTEND_UI.md` | React component map, panel rendering, CSS architecture, data flow | Frontend developers |
| `docs/SETUP.md` | Local development setup | Developers |
| `docs/roadmap/eval-ui-components-library.md` | Evaluation of official EVE Frontier UI components — what to adopt, copy, or skip | Frontend developers |
| `docs/DOC_STANDARDS.md` | How to write, maintain, and audit all project documentation | All / AI agents |

---

## What is NOT in docs/

- **Prompts:** `prompts/` directory — AI system prompts and builder guides. See `docs/ARCHITECTURE.md` → Prompt Layer for the full file list.
- **Move contract:** `move/access_registry/` — the on-chain access control contract source.
- **Build scripts:** `build_universe.py`, `build_gate_graph.py` — one-time data generation scripts.
- **Test suite:** `tests/` — pytest unit and integration tests.
