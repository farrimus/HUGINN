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
| How does HUGINN's tool output formatting work? | `docs/ARCHITECTURE.md` → Prompt Layer |
| Where do I edit tool descriptions or response style? | `prompts/tools.yaml` — see `docs/ARCHITECTURE.md` → Prompt Layer |
| What are the Python/frontend dependencies and why? | `docs/TECH_STACK_AND_DEPENDENCIES.md` |
| How is the dapp-kit multi-tenant cache structured? | `docs/TECH_STACK_AND_DEPENDENCIES.md` → dapp-kit multi-tenant cache |
| What does dapp-kit own vs backend? | `CLAUDE.md` — Data Layer Boundary section |
| Where is file X and what does it do? | `docs/REPO_STRUCTURE.md` |
| What are the data schemas (structures, sessions, etc.)? | `docs/DATA_REFERENCE.md` |
| How do I set up the project locally? | `docs/SETUP.md` |
| How does BCS encoding / Sui object ID derivation work? | `docs/BCS_ENCODING.md` |
| What dapp-kit hooks and APIs are available? | `docs/DAPP_KIT_API.md` |

---

## Document Index

| File | Purpose | Audience |
|------|---------|----------|
| `PHILOSOPHY.md` | Product vision + engineering principles (Musk's Algorithm) | All |
| `CLAUDE.md` | Claude Code rules, data layer boundary, standing preferences | AI agents |
| `docs/NAVIGATION.md` | This file — maps questions to documents | AI agents |
| `docs/PROJECT_OVERVIEW.md` | Mission, feature list, current status | All |
| `docs/ARCHITECTURE.md` | System design, components, data flows, deployment | Developers |
| `docs/KEY_CONCEPTS_AND_DECISIONS.md` | Design decisions and trade-offs | Developers |
| `docs/TECH_STACK_AND_DEPENDENCIES.md` | Package versions, rationale, dapp-kit patch | Developers |
| `docs/REPO_STRUCTURE.md` | Every file, every directory, every entry point | Developers / AI agents |
| `docs/DATA_REFERENCE.md` | Data schemas: structures, sessions, killmails, intel | Developers |
| `docs/DAPP_KIT_API.md` | Full dapp-kit hook and API reference | Frontend developers |
| `docs/BCS_ENCODING.md` | Sui BCS encoding, object ID derivation | Blockchain / backend |
| `docs/SETUP.md` | Local development setup | Developers |

---

## What is NOT in docs/

- **Prompts:** `prompts/` directory — AI system prompts and builder guides. See `docs/ARCHITECTURE.md` → Prompt Layer for the full file list.
- **Move contract:** `move/access_registry/` — the on-chain access control contract source.
- **Build scripts:** `build_universe.py`, `build_gate_graph.py` — one-time data generation scripts.
- **Test suite:** `tests/` — pytest unit and integration tests.
