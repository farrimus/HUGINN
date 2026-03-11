# CLAUDE.md — Eve Frontier Hackathon Project

This file governs Claude Code behavior for this project only.
Parent CLAUDE.md files (e.g. /root/CLAUDE.md) are NOT authoritative here —
this project has its own rules.

Last updated: 2026-03-11

---

## Project

**Name:** Eve Frontier — In-Lore Chat Companion (working title)
**Owner:** Markús Þór
**Hackathon:** EVE Frontier × Sui Hackathon 2026 — "A Toolkit for Civilization"
**Track:** B — External Application (World API, no blockchain required)
**Deadline:** March 31, 2026
**Status:** Day 1 — planning phase

### What We Are Building

An AI-powered in-lore companion chat agent for EVE Frontier players. The agent lives inside the game's fiction — it speaks, reasons, and responds as an entity native to the EVE Frontier universe, not as a help bot.

Core capabilities:
- **Lore-accurate responses** — answers questions about the game world using accurate EVE Frontier lore and context
- **Route calculation** — calculates travel routes between systems using live or cached map data
- **Situation awareness** — explains the player's current situation (location, nearby threats, resources, etc.)
- **Game client log tracking** — parses EVE Frontier client logs to generate contextual, reactive responses
- **Live game data** — connects to the EVE Frontier World API for real-time universe state

### Tech Stack (initial thinking — subject to brainstorming)

- **Runtime:** Node.js or Python (TBD)
- **AI layer:** Claude API (Anthropic) — for lore-grounded, character-voice responses
- **Game data:** EVE Frontier World API (public + private endpoints)
- **Log parsing:** EVE Frontier game client log files
- **Interface:** TBD — could be web UI, desktop overlay, or CLI

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

## Standing Preferences

- Plan first, implement after Markús confirms
- Be concise — short direct answers, no filler
- No emojis
- Ask before any destructive or irreversible action

---

## Key Paths

```
/opt/eve-frontier/              — project root
/opt/eve-frontier/.superpowers/ — Superpowers skills
/opt/eve-frontier/CLAUDE.md     — this file
```
