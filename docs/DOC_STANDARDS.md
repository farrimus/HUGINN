# Documentation Standards

This document defines how documentation is written and maintained in this project. It applies to all `.md` files in `docs/`, root-level docs (`CLAUDE.md`, `PHILOSOPHY.md`, `README.md`), and `prompts/`. Read it before touching any documentation.

---

## The Core Law

**A document is correct only when it matches the current state of the codebase. An outdated document is wrong — not stale, not legacy, wrong.**

Git is the history record. Commit messages, blame, and log own the past. Docs own only the present.

Any line in a document that describes what the system used to do, what was fixed, what changed, or what is planned — is a line that does not belong in a reference document.

---

## What Documents Are and Are Not

**Documents are:**
- A description of how the system works right now
- A decision table: "I need X, so I do Y"
- The single canonical answer to a specific class of questions

**Documents are not:**
- A changelog or fix history
- An aspirational description of what the system will become
- A record of past bugs, workarounds, or architectural regrets
- A tutorial (use `SETUP.md` for setup; use `PHILOSOPHY.md` for reasoning)

**History belongs in:**
- Git commit messages (why a change was made)
- `docs/roadmap/` (planned future features, not committed yet)
- Architecture Decision Records if a decision warrants one

---

## Scrub Rules

Remove these patterns on sight. They are wrong regardless of context.

| Pattern | Problem | Fix |
|---------|---------|-----|
| "Fixed on [date]" | History | Delete the note; describe current behavior only |
| "Previously used X, now uses Y" | Records a transition | Write: "Uses Y." |
| "No longer does X" | References removed past state | Write only what it does do |
| "Was changed to" / "has been updated to" | Changelog language | State the current fact |
| "Now uses" / "now works" | "Now" implies a before | Remove "now"; state the fact |
| "As of [date]" | Will rot immediately | State the fact without the date |
| "TODO: migrate to X" in a reference doc | Aspirational content | Move to `docs/roadmap/` or delete |
| "Temporary workaround:" | Acknowledges debt without resolving it | Fix it or delete the note |
| `[DEPRECATED]` sections left in place | Zombie content | Delete entirely |
| "Note: this was added because..." | History prose in a reference | Move to a git commit message |
| "We plan to" / "will support" in non-roadmap docs | Aspirational | Move to `docs/roadmap/` or delete |

---

## Ownership Rules

One fact, one document. `NAVIGATION.md` is the routing table.

**Before writing anything:**
1. Check `NAVIGATION.md` — does a document already own this question?
2. If yes: edit that document in place.
3. If the question has no canonical home: add it to `NAVIGATION.md`, then add the content to the most appropriate existing document.

Never duplicate facts across documents. If the same fact appears in two places, one of them is wrong. Put the fact in its authoritative document and remove it from the other.

---

## When to Create a New Document

Almost never. Ask first: can this be a section in an existing document?

**Create a new document only when:**
- The topic cannot be a section in any existing doc without making that doc incoherent
- The audience is clearly distinct (e.g., blockchain-only reference doesn't belong in general architecture)
- The content is large enough that adding it to an existing doc buries existing content

**Never create:**
- A "corrected" version of an existing doc — edit in place
- A "v2" or "ARCHITECTURE_NEW.md" — one authoritative version exists
- A catch-all notes file for miscellaneous facts
- A doc that mirrors what the code already makes obvious

---

## Maintenance Workflow

### When to update

Update a document when any of the following are true:
- Code it describes was added, removed, or changed
- A schema, endpoint, or data field it references was modified
- A dependency or tool it mentions was added or removed
- An architectural decision it records was reversed
- An agent or developer asked a question this document should answer and couldn't find it

### How to update

1. Find the canonical document via `NAVIGATION.md`
2. Read the full document before editing
3. Edit in place — do not create a new file
4. Apply scrub rules while editing — remove any past-tense or historical language found in the surrounding content, not just the section you're changing
5. Verify: re-read the edited section and compare it to the current code

### What not to do

- Do not add "Updated [date]" headings or footers
- Do not add a changelog section to a reference document
- Do not leave old content with a strikethrough
- Do not write "see above for the old behavior"
- Do not create a companion file alongside the original

---

## Writing for Agents

AI agents parse structure before prose. These patterns consistently produce fewer errors.

### Use imperative present tense

Agents follow instructions better when written as directives, not descriptions.

| Write this | Not this |
|------------|----------|
| "Use `getAssemblyWithOwner()` for assembly data." | "Assembly data can be retrieved using `getAssemblyWithOwner()`." |
| "Never call the World API directly from the frontend." | "The frontend generally uses dapp-kit for World API access." |
| "Run `pytest tests/` before marking any backend task complete." | "Tests should be run to verify changes." |

### Put critical constraints first

Agents lose focus as context fills. A rule buried on page 3 is a rule that will be missed. If a constraint is non-negotiable, it goes at the top of the relevant section, not at the bottom.

### Use tables for decision mappings

Tables are faster to parse than equivalent prose. When a section answers "I need X, use Y," format it as a table.

```markdown
| If you need... | Use this |
|----------------|----------|
| Assembly data  | `useSmartObject()` |
| Character data | `getWalletCharacters()` |
```

### Reference exact file paths and function names

```markdown
Good:  "Configure tier resolution in `src/tier_capabilities.py`."
Avoid: "Configure tier resolution in the capabilities module."
```

### State constraints explicitly — never imply them

Agents cannot reliably infer constraints from context. A rule that is "obvious" to a developer is ambiguous to an agent.

```markdown
Good:  "Do not add new endpoints to `main.py`. All endpoints belong in `src/endpoints/`."
Avoid: "The project uses a modular endpoint structure."
```

### Include verification criteria for non-obvious tasks

When documenting a workflow, tell agents how they know they succeeded:

```markdown
Run `npm run build` from `/frontend/`. No TypeScript errors means the build is clean.
Run `pytest tests/` from the project root. All tests must pass before merging.
```

### Context budget

Every line an agent loads costs context. Apply the same deletion pressure to docs as to code:
- Does this line prevent a specific mistake?
- Would removing it force an agent to guess?
- If neither: delete it.

CLAUDE.md should stay under 150 lines. Every line must earn its place. If Claude consistently ignores a rule, the file is too long — cut elsewhere to restore signal density.

---

## Writing for Humans

A document written well for agents is already readable by humans. Add only what improves human comprehension without adding noise for agents:

- H2/H3 headings for navigation
- Most important content at the top of each section
- One concept per paragraph
- Inline WHY explanations (one sentence, not a separate section)

Do not add padding, transitions, or filler sentences. Agents treat every word as signal.

---

## Document Structure Reference

The project's document hierarchy:

| Layer | Files | Loaded by agents |
|-------|-------|-----------------|
| Entry point | `CLAUDE.md`, `docs/NAVIGATION.md` | Always |
| Architecture | `PHILOSOPHY.md`, `docs/ARCHITECTURE.md`, `docs/KEY_CONCEPTS_AND_DECISIONS.md` | On demand |
| Reference | `docs/DATA_REFERENCE.md`, `docs/REPO_STRUCTURE.md`, `docs/DAPP_KIT_API.md` | When relevant |
| Setup | `docs/SETUP.md`, `docs/TECH_STACK_AND_DEPENDENCIES.md` | When needed |
| Future | `docs/roadmap/*.md` | Rarely |
| Prompts | `prompts/companion.md`, `prompts/tools.yaml`, etc. | Not by agents |

Agents start at `CLAUDE.md` and `NAVIGATION.md`. Everything else is loaded on demand based on the task. This is why CLAUDE.md must be tight — it determines what agents bother to look at.

---

## Audit Checklist

Run before closing any doc-related task:

- [ ] Does every fact in this document match the current codebase?
- [ ] Does `NAVIGATION.md` route to this document for the questions it answers?
- [ ] Does the document contain any past-tense language, historical references, or dates of change?
- [ ] Does the document contain aspirational content outside of `docs/roadmap/`?
- [ ] Are there duplicate facts that also appear in another document?
- [ ] Are all file paths, function names, and module names current?
- [ ] Are there any `[DEPRECATED]`, `TODO`, or zombie sections?
- [ ] Is every imperative instruction explicit rather than implied?
