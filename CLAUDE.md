# CLAUDE.md — Eve Frontier Hackathon Project

This file governs Claude Code behavior for this project only.

**Owner:** Markús Þór
**Hackathon:** EVE Frontier × Sui Hackathon 2026
**Deadline:** March 31, 2026
**Status:** MVP complete and running — companion chat end-to-end, route architecture decided.

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
**It has happened 9 times. Do not add a 10th. The full boundary is at `docs/DAPP_KIT_BOUNDARY.md`.**

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

## Scope: Backend Only

**This CLAUDE.md governs the Python backend and documentation.**

**Frontend work:** See `/frontend/CLAUDE.md` for React dApp guidance.

## Tech Stack

- **Runtime:** Python 3.12
- **Backend:** FastAPI + uvicorn (port 8745)
- **AI:** Claude API (claude-sonnet-4-6)
- **Game data:** EVE Frontier World API
- **Interface:** React frontend (`/frontend/`) served by FastAPI

---

## Documentation

**Start here:** `/docs/START_HERE.md`

The docs are organized hierarchically. START_HERE.md explains the structure and guides you to what you need.

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
