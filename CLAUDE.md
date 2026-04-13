# CLAUDE.md -- HUGINN

This file governs Claude Code behavior for this project only.

**Owner:** Markus Thor
**Project:** EVE Frontier AI Companion (post-hackathon)
**Status:** MVP shipped. Active development.

---

## What We're Building

An AI-powered in-lore companion chat agent for EVE Frontier players. The agent speaks, reasons, and responds as an entity native to the EVE Frontier universe -- not as a help bot.

**Core capabilities:**
- Lore-accurate responses
- Situation awareness (location, threats, resources)
- Game client log tracking
- Live game data (World API)

---

## MANDATORY: Data Layer Boundary

**This project has a documented failure mode: reimplementing things dapp-kit already provides.**
**It has happened 9 times. Do not add a 10th.**

Before writing any fetch, query, GraphQL call, parser, formatter, or data transform -- answer this question first:

**Is this game data access?** -> dapp-kit owns it.
**Is this AI, galaxy geography, social boards, or derived metrics?** -> Backend owns it.

### dapp-kit owns -- do not reimplement these

| If you need... | Use this |
|----------------|----------|
| Assembly data (any type) | `useSmartObject()` / `getAssemblyWithOwner()` |
| Character + owned assemblies | `getWalletCharacters()` / `getCharacterAndOwnedObjects()` |
| Type name, category, icon, volume | `getDatahubGameInfo(typeId)` |
| Assembly status -> State enum | `parseStatus(statusVariant)` |
| Move type repr -> assembly kind | `getAssemblyType(moveTypeRepr)` |
| Energy or fuel efficiency constants | `getEnergyConfig()` / `getFuelEfficiencyConfig()` |
| Format duration / volume / address | `formatDuration()` / `formatM3()` / `abbreviateAddress()` |
| Any Sui GraphQL query | `executeGraphQLQuery()` + named queries in `graphql/queries.ts` |

### Backend legitimately owns -- dapp-kit cannot do these

- AI companion chat (Claude API, prompt construction, lore context)
- Galaxy DB / solar system geography
- Derived fuel metrics: `hours_remaining`, `burn_rate_units_per_hr` (dapp-kit returns raw fuel, not computed state)
- Batch network topology (20 assemblies in parallel -- no dapp-kit primitive exists)
- Courier board, Tribe board, session management

---

## Directory Index

Each directory has its own CLAUDE.md with local context. Start there. Load `docs/` files only when a directory CLAUDE.md points you to one.

| Directory | What's there |
|-----------|-------------|
| `src/` | Python backend -- FastAPI, AI, stores, game logic |
| `src/endpoints/` | FastAPI route handlers (one per feature) |
| `frontend/` | React dApp -- components, hooks, dapp-kit |
| `frontend/src/` | React components, hooks, styles, types |
| `prompts/` | AI system prompts and tool definitions |
| `tests/` | pytest suite |
| `data/` | Runtime data -- sessions, memory, galaxy DB |
| `docs/` | Deep reference docs (load on demand) |
| `move/` | Sui Move smart contracts (AccessRegistry) |

## Tech Stack

- **Runtime:** Python 3.12
- **Backend:** FastAPI + uvicorn (port 8745)
- **AI:** Claude API (claude-sonnet-4-6)
- **Game data:** EVE Frontier World API
- **Interface:** React frontend (`/frontend/`) served by FastAPI

## Context Budget

CLAUDE.md files should stay under 150 lines. Every line costs tokens. If a line does not prevent a specific mistake, delete it.

---

## Standing Preferences

- Plan first, implement after confirmation
- Be concise -- short direct answers, no filler
- No emojis
- Ask before any destructive or irreversible action
- Never restart the server -- user handles restarts
- Only run `npm run build` for frontend deploys
