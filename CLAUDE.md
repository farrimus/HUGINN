# CLAUDE.md — Eve Frontier Hackathon Project

This file governs Claude Code behavior for this project only.
Parent CLAUDE.md files (e.g. /root/CLAUDE.md) are NOT authoritative here —
this project has its own rules.

Last updated: 2026-03-18

---

## Project

**Name:** Eve Frontier — In-Lore Chat Companion (working title)
**Owner:** Markús Þór
**Hackathon:** EVE Frontier × Sui Hackathon 2026 — "A Toolkit for Civilization"
**Track:** B — External Application (World API, no blockchain required)
**Deadline:** March 31, 2026
**Status:** MVP complete and running — log agent deployed, DX12 overlay injected, companion chat confirmed end-to-end. Route engine architecture decided; client-side implementation pending.

### What We Are Building

An AI-powered in-lore companion chat agent for EVE Frontier players. The agent lives inside the game's fiction — it speaks, reasons, and responds as an entity native to the EVE Frontier universe, not as a help bot.

Core capabilities:
- **Lore-accurate responses** — answers questions about the game world using accurate EVE Frontier lore and context
- **Situation awareness** — explains the player's current situation (location, nearby threats, resources, etc.)
- **Game client log tracking** — parses EVE Frontier client logs to generate contextual, reactive responses
- **Live game data** — connects to the EVE Frontier World API for real-time universe state

Route calculation is client-side (Python, Windows). Architecture decided 2026-03-13: server builds and serves `data/gate_graph.json` via `GET /data/gate-graph`; client runs BFS and POSTs `route_planned` events back to `/log/ingest`; context_builder injects the route into every Claude prompt. Blocked on: ship temperature mechanics and ship params source. See `docs/CODEBASE.md` routing section for full decision log.

### Tech Stack

- **Runtime:** Python 3.12
- **Backend:** FastAPI + uvicorn, port 8745
- **AI layer:** Claude API (Anthropic, `claude-sonnet-4-6`) — streaming via SSE
- **Game data:** EVE Frontier World API (public endpoints, no auth required)
- **Log parsing:** watchdog file watcher on gaming PC → POSTs structured events to server
- **Interface:** Single-file HTML/JS served by FastAPI (`static/index.html`)

### Prize Category Targets

Primary: **Live Frontier Integration** (real player interaction during judging)
Secondary: **Creative** (novel companion concept, immersive lore voice)
Stretch: **Utility** (route calc + situational awareness = practical value)

---

## Superpowers Skills

Superpowers skills are installed at `/opt/eve-frontier/.superpowers/skills/`.

**This is a structured development project. Use the Superpowers workflow.**

Rules:
- Before starting any non-trivial task, check if a skill applies
- Use `brainstorming` before designing anything new
- Use `writing-plans` before writing code — produce a task plan first
- Use `executing-plans` to implement task by task
- Use `test-driven-development` for all feature code
- Use `systematic-debugging` when something is broken
- Use `verification-before-completion` before declaring any task done

Available skills (invoke with the Skill tool):
- brainstorming
- writing-plans
- executing-plans
- test-driven-development
- systematic-debugging
- requesting-code-review
- receiving-code-review
- subagent-driven-development
- dispatching-parallel-agents
- using-git-worktrees
- finishing-a-development-branch
- verification-before-completion
- writing-skills

---

## Intent & Values

`intent.md` — Read this before making any decision about what the companion says, what it knows, or what it refuses to do. The values there override convenience.

---

## Standing Preferences

- Plan first, implement after Markús confirms
- Be concise — short direct answers, no filler
- No emojis
- Ask before any destructive or irreversible action

---

## Documentation

**Start here:** Read [.claude/docs/nav.md](.claude/docs/nav.md) for navigation paths based on what you need.

Three complementary systems — each with its own curator:

### 1. Agent-Facing (Auto-Generated)
**Managed by:** `/doc-doctor` skill
**Location:** `.claude/docs/modules/` + `.claude/doc-map.md` + `.claude/docs/REGISTRY.md`

Lightweight module documentation (≤150 lines each). Each doc answers: *"When should an agent use this module?"* Includes public API, behavior, integration points, constants. Uses progressive disclosure — heavy details deferred to references or assets.

**Registry:** [.claude/docs/REGISTRY.md](.claude/docs/REGISTRY.md) maps each module to its reference docs and design/plan artifacts. Use this to find cross-references without loading full context.

Auto-maintained: Run `/doc-doctor` whenever you add or modify a module. It detects changes by checksum, regenerates docs, audits quality, and updates the registry.

### 2. Development Artifacts (Skill-Managed)
**Managed by:** `superpowers` skill
**Location:** `/docs/superpowers/specs/` (design docs) and `/docs/superpowers/plans/` (task plans)

Superpowers design sessions write to this directory. Structure is tool-maintained — plans and specs from brainstorming and writing-plans skills live here. Never modify these directory structure; doc-doctor indexes them.

### 3. Reference Documentation (Manual)
**Managed by:** You
**Location:** `/docs/` (root and `ref/` subdirectory)

User/architect-facing stable documentation:
- `CODEBASE.md` — architecture overview, directory tree, quick reference
- `log-pipeline.md` — canonical log pipeline design (keep current)
- `ref/ship-ai.md` — Ship AI modules, event flow, test coverage
- `ref/structure-ai.md` — Structure AI, Sui deployment, auth endpoints
- `ref/routing.md` — routing algorithm, heat formula, ship profile
- `ref/overlay.md` — DX12 overlay C++ architecture
- `ref/ui.md` — index.html, debug.html, in-game environment
- `ref/ops.md` — config, ops commands, known gaps

### Doc Workflow — Progressive Disclosure

**Pattern:** When you need context on something, start with doc-doctor's lightweight curated docs, then step down to heavier references only if needed.

1. **First:** Check [.claude/docs/nav.md](.claude/docs/nav.md) for the reading path matching your task
2. **Then:** Read [.claude/docs/modules/index.md](.claude/docs/modules/index.md) for overview, use [.claude/docs/REGISTRY.md](.claude/docs/REGISTRY.md) to find cross-references and related modules
3. **Next:** Read the specific lightweight module docs from `.claude/docs/modules/` — these give you API, behavior, integration points
4. **If needed:** Step down to `/docs/ref/` (algorithm details, full design), then `/docs/superpowers/specs/` (design rationale)
5. **Special cases:**
   - Before implementation: also check `/intent.md` (voice/values) first
   - After design sprint: Superpowers skill writes specs to `/docs/superpowers/specs/`
   - After implementation: Run `/doc-doctor` to regenerate module docs and update registry
   - When docs drift: Update `/docs/ref/` to match code, run `/doc-doctor` to update registry and module links

---

## Key Paths

```
/opt/eve-frontier/                           — project root
/opt/eve-frontier/main.py                    — FastAPI server entry point (port 8745)
/opt/eve-frontier/src/                       — server modules
/opt/eve-frontier/static/index.html          — chat UI (single file)
/opt/eve-frontier/log-agent/                 — Windows client: file watcher, parsers
/opt/eve-frontier/tests/                     — server-side pytest suite
/opt/eve-frontier/log-agent/tests/           — log agent pytest suite
/opt/eve-frontier/data/system_index.json     — cached World API system index (24,501 systems)
/opt/eve-frontier/data/gate_graph.json       — gate adjacency + system metadata
/opt/eve-frontier/.env                       — server config (ANTHROPIC_API_KEY, SERVER_TOKEN, PORT)
/opt/eve-frontier/log-agent/.env.example     — Windows agent config template
/opt/eve-frontier/.superpowers/              — Superpowers skills (custom, installed)

DOCUMENTATION:
/opt/eve-frontier/intent.md                  — lore, voice, values (foundational)
/opt/eve-frontier/docs/CODEBASE.md           — architecture, directory tree, quick reference
/opt/eve-frontier/docs/log-pipeline.md       — canonical log pipeline design doc
/opt/eve-frontier/docs/ref/                  — detailed reference docs (routing, ship AI, structure AI, UI, ops)
/opt/eve-frontier/docs/superpowers/          — skill-managed: design specs and task plans
/opt/eve-frontier/.claude/docs/modules/      — auto-generated agent module docs (doc-doctor maintained)
/opt/eve-frontier/.claude/doc-map.md         — doc-doctor audit trail (never delete)
/opt/eve-frontier/CLAUDE.md                  — this file
```
