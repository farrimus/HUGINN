# Ship AI Companion — Design Spec

**Project:** EVE Frontier Hackathon 2026 — "A Toolkit for Civilization"
**Track:** B — External Application
**Date:** 2026-03-11
**Status:** Approved

---

## Overview

An AI-powered in-lore companion chat agent for EVE Frontier. The agent presents as the player's ship AI — dry, functional, with emergent personality quirks. It is aware of the live game state, reacts to client log events, calculates routes, and answers questions grounded in EVE Frontier lore.

Two entry points, one UI:
- **Overlay** — player opens the web app in a browser alongside the game
- **In-game browser** — player interacts with a Smart Assembly that has the app URL configured; EVE Frontier opens it in an internal browser window (max 787×1198px at 1440p, fluid/responsive layout)

---

## Architecture

```
[EVE Frontier game client]
        |
        | in-game browser opens URL  /  player opens overlay in browser
        v
[HTML/JS chat window]  <-- streaming responses (SSE) --  [FastAPI server on VPS]
        |                                                        |
        | POST /chat {message, context}                         |
        v                                                        |
[FastAPI server]                                                 |
    |           |              |               |                 |
    v           v              v               v                 |
[Claude API] [World API]  [Log parser]  [Route engine]          |
```

**Stack:**
- Backend: Python, FastAPI
- Frontend: Plain HTML/CSS/JS (no framework, no build step)
- AI: Claude API (Anthropic) with streaming via Server-Sent Events
- Game data: EVE Frontier World API
- Hosting: this VPS (`/opt/eve-frontier/`)

---

## Frontend

Single `index.html` served by FastAPI.

- Dark background, monospace font — ship terminal aesthetic
- AI messages: dim green, left-aligned
- Player messages: distinct colour, right-aligned
- Responses stream token by token (SSE) — feels alive
- Input bar fixed at bottom
- Responsive/fluid layout — fills whatever size the in-game browser provides
- Overlay mode: includes a minimize button (collapses to corner tab)
- In-game browser mode: no minimize, fills window
- URL params on open: `?object_id=<id>&system=<name>` pre-load context when opened from a Smart Assembly

---

## Backend Modules

### 1. Claude API — Ship AI Voice

Persistent system prompt defines the character: name, personality, in-universe knowledge boundaries, tone (dry, functional, slight quirks).

Context assembled per request:
```
[system prompt: ship AI character]
[context block: current system, recent log events, relevant game state]
[conversation history: last 20 exchanges]
[user message]
```

Responses streamed via SSE. Conversation history capped at 20 exchanges to manage token limits.

### 2. World API Client

Thin wrapper around EVE Frontier's public World API. Called on demand. Responses cached for 30 seconds to avoid hammering the API.

Fetches:
- Current system data
- Nearby systems
- Recent killmails
- Smart Assembly data (when opened from an object)

Results summarised before injection into context (not dumped raw).

### 3. Log Parser

Watches the EVE Frontier client log file via a file-watcher. Parses new lines as they arrive. Extracts structured events: jumps, combat, docking, interactions.

Maintains a rolling buffer of the last 50 events. Injects the last 10 into context per message automatically — the AI knows what just happened without the player explaining it.

Log file location and transport method (Syncthing vs local agent vs other) is deferred to implementation. The module accepts either a local path or a streamed input.

### 4. Route Engine

Input: origin system name + destination system name.
Output: ordered list of jumps, jump count, threat annotations from recent killmail data.

Map graph sourced from the World API or a static dataset (determined during implementation based on what the API exposes).

---

## Graceful Degradation

Each module fails independently — no single failure crashes the companion.

| Module fails | Behaviour |
|---|---|
| World API down | AI reports sensor unavailability, proceeds without live data |
| Log file not found / not synced | AI operates without log context, no crash |
| Route engine has no map data | AI reports navigation charts unavailable |
| Claude API error | Inline error shown in chat window, input remains enabled |

---

## Security / Auth

Personal use only. App runs on VPS, not exposed publicly. Optional: a simple secret token in the URL (`?token=<secret>`) for basic protection if the port is exposed.

---

## Hackathon Prize Category Targets

| Category | Rationale |
|---|---|
| Live Frontier Integration (primary) | Runs against live game data during judging period |
| Creative (secondary) | In-lore ship AI character with personality is novel |
| Utility (stretch) | Route calculation + situational awareness = practical player tool |

---

## Deferred Decisions

- Log file transport method (Syncthing / local agent / local run)
- Exact ship AI name and personality details
- Whether map graph comes from World API or static dataset
- Whether to expose the app publicly vs. localhost only
