# Project Overview — HUGINN

## Mission

HUGINN is an AI-powered intelligence companion for EVE Frontier players, embedded directly in player-owned Smart Storage Units (SSUs). It gives pilots a persistent, in-lore terminal intelligence — field awareness, route planning, and accumulated knowledge from every other pilot who has passed through — delivered through a natural language interface in the in-game browser.

---

## Problem

EVE Frontier is a hostile sandbox MMO with intentionally sparse information. Players lack context: they don't know what enemies inhabit a system they're about to jump into, what resources exist there, who has recently been killed nearby, or how to chart an efficient route. No in-game tool provides this. HUGINN fills that gap — not as a wiki or walkthrough, but as an always-on, in-lore field intelligence layer that pilots collectively populate with their own observations.

---

## What Was Built

These features were delivered and are running in production. All are functional but none are fully finished — the project is continuing development beyond the hackathon.

| Feature | What it does |
|---------|-------------|
| AI companion chat | Claude-powered streaming chat. HUGINN speaks in-lore: brief, operational, no filler. Accesses live game data via tools mid-conversation. |
| On-chain access control | Per-request tier resolution from the Sui AccessRegistry contract: OWNER, TRIBE, VETTED, NONE. Each tier sees different data. |
| Route planner | Pathfinding across 24,426 solar systems using gate topology. Accounts for jump range and fuel budget. |
| Recon (system intelligence) | Live + historical data for any solar system: security status, kill activity, resources, threats. |
| Kill feed | Killmails synced hourly from Sui blockchain events. Available to the AI and displayed in-app. |
| Log upload + intel | Players upload their EVE Frontier game logs. HUGINN parses them, extracts per-system observations, and stores them for future queries by any pilot. |
| SSU watcher | Alert streams for structure state changes. Pilots can set watch rules and receive SSE notifications. |
| Courier board | Per-structure hauling contract board. Pilots post, claim, and track contracts. |
| Tribe presence board | Real-time tribe member presence and posts. |
| Huginn Signal | AI-generated intelligence broadcast. HUGINN synthesizes recent events into a structured situation report. |
| Ship profile | Pilots register their ship type and fuel load. HUGINN uses this for route and fuel calculations. |
| Multi-tenant | Supports both EVE Frontier environments: utopia (test) and stillness (staging/live). |

### Move smart contract

A Sui Move contract (`move/access_registry/`) is deployed on-chain. It manages per-structure access control: owner, tribe addresses, and vetted addresses. Structure owners interact with it directly via their Sui wallets. The backend reads its state on every request to resolve the pilot's access tier.

---

## Current Status

**All features are work in progress.** The most complete are route planning, recon, and log upload. None are considered fully shipped.

Log parsing is the most actively evolving: as players use the system, unknown entity types (other players, ships, player-owned structures) are encountered, catalogued, and incrementally fed back into the parser to improve coverage.

**Hackathon context:** The project was submitted to the EVE Frontier × Sui Hackathon 2026 (deadline March 31, 2026). The submitted repo is frozen for judge review — a verdict is expected ~10 days from April 5. All new development happens on separate branches and must not modify the submission state.

---

## Player-Facing Value

HUGINN is designed to run continuously and accept connections from any pilot who docks at a participating SSU. Target: many concurrent sessions, always on, no downtime.

A pilot who docks at a HUGINN-equipped SSU gets:

- Immediate context on the system they're in and neighboring systems
- Kill activity, resource types, and hazard notes accumulated from prior pilot reports
- Route planning with jump-range and fuel awareness
- Hauling contracts posted by the structure owner or tribe
- Tribe presence — who's active, where
- AI-generated situation reports synthesized from recent events

The intelligence improves over time: every log upload and every pilot report adds to a shared, permanent knowledge base. The more pilots who use HUGINN, the more useful it becomes.
