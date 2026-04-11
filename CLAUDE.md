# CLAUDE.md — Eve Frontier Hackathon Project

This file governs Claude Code behavior for this project only.

**Owner:** Markús Þór
**Project:** EVE Frontier AI Companion (post-hackathon)
**Status:** MVP shipped. Actively developing: SystemKnowledgeStore, Signal Broadcast refinement, session/admin fixes.

---

## What We're Building

An AI-powered in-lore companion chat agent for EVE Frontier players. The agent speaks, reasons, and responds as an entity native to the EVE Frontier universe—not as a help bot.

**Core capabilities:**
- Lore-accurate responses
- Situation awareness (location, threats, resources)
- Game client log tracking
- Live game data (World API)

---

## MANDATORY: Data Layer Boundary

**This project has a documented failure mode: reimplementing things dapp-kit already provides.**
**It has happened 9 times. Do not add a 10th.**

Before writing any fetch, query, GraphQL call, parser, formatter, or data transform — answer this question first:

**Is this game data access?** → dapp-kit owns it.
**Is this AI, galaxy geography, social boards, or derived metrics?** → Backend owns it.

### dapp-kit owns — do not reimplement these

| If you need... | Use this |
|----------------|----------|
| Assembly data (any type) | `useSmartObject()` / `getAssemblyWithOwner()` |
| Character + owned assemblies | `getWalletCharacters()` / `getCharacterAndOwnedObjects()` |
| Type name, category, icon, volume | `getDatahubGameInfo(typeId)` |
| Assembly status → State enum | `parseStatus(statusVariant)` |
| Move type repr → assembly kind | `getAssemblyType(moveTypeRepr)` |
| Energy or fuel efficiency constants | `getEnergyConfig()` / `getFuelEfficiencyConfig()` |
| Format duration / volume / address | `formatDuration()` / `formatM3()` / `abbreviateAddress()` |
| Any Sui GraphQL query | `executeGraphQLQuery()` + named queries in `graphql/queries.ts` |

### Backend legitimately owns — dapp-kit cannot do these

- AI companion chat (Claude API, prompt construction, lore context)
- Galaxy DB / solar system geography
- Derived fuel metrics: `hours_remaining`, `burn_rate_units_per_hr` (dapp-kit returns raw fuel, not computed state)
- Batch network topology (20 assemblies in parallel — no dapp-kit primitive exists)
- Courier board, Tribe board, session management

---

## Scope

This CLAUDE.md governs the full stack: Python backend, React frontend, and documentation.

**Backend:** `src/` + `main.py` — FastAPI, AI companion, game data endpoints.
**Frontend:** `frontend/src/` — React dApp. Components in `components/`, hooks in `hooks/`. Architecture in `/docs/ARCHITECTURE.md`.

## Tech Stack

- **Runtime:** Python 3.12
- **Backend:** FastAPI + uvicorn (port 8745)
- **AI:** Claude API (claude-sonnet-4-6)
- **Game data:** EVE Frontier World API
- **Interface:** React frontend (`/frontend/`) served by FastAPI

---

## Current Priorities

**Active work and known bugs:** `memory/MEMORY.md` — read this first for current state, open bugs, and next tasks.

## Documentation

**Start here:** `/docs/NAVIGATION.md` — maps every question to the right document.

For architecture: `/docs/ARCHITECTURE.md`. For data schemas: `/docs/DATA_REFERENCE.md`. For engineering philosophy: `/PHILOSOPHY.md`. For how to write and maintain docs: `/docs/DOC_STANDARDS.md`.

---

## Superpowers Workflow

This project uses structured development skills. Use them:
- `brainstorming` — before designing anything new
- `writing-plans` — before writing code
- `executing-plans` — implement task by task
- `test-driven-development` — for all feature code
- `systematic-debugging` — when something breaks
- `verification-before-completion` — before declaring tasks done

(Other skills available: requesting-code-review, receiving-code-review, subagent-driven-development, dispatching-parallel-agents, using-git-worktrees, finishing-a-development-branch, writing-skills)

---

## Standing Preferences

- Plan first, implement after confirmation
- Be concise — short direct answers, no filler
- No emojis
- Ask before any destructive or irreversible action
