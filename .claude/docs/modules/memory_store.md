# memory_store

## Overview

File-backed persistent memory per structure. Stores timestamped game events (docking, kills, SSU updates, access changes) for historical context and AI summary; also tracks every pilot who has authenticated with structured profiles (address, character name, ID, tier, visit stats).

## When Should an Agent Use This Module?

Use **memory_store** when you need to:
- Persist Structure AI state across server restarts
- Search historical game events by keyword (last 7 days by default)
- Track pilot visits and authentication history
- Get or rebuild a human-readable summary of recent structure activity

The store is per-structure: `data/memory/{structure_id}/` with three file types:
- `events.jsonl` — append-only log of game events
- `summary.json` — Claude-condensed summary (max 300 chars)
- `pilots/{safe_address}.json` — individual pilot profile (Sui address-keyed)

## Key API

| Symbol | Type | Purpose | Agent Instruction | Gotchas |
|--------|------|---------|-------------------|---------|
| `MemoryStore` | class | Per-structure event + pilot store | Initialize once per structure via `get_memory_store()` factory | Always call `bootstrap()` before use |
| `append_event(event_type, system_id, data)` | method | Log a game event (docking, kill, alert, etc.) | Call after structure state changes; `data` is arbitrary dict (flattened to JSON) | Silently swallows I/O errors (logged as warnings only) |
| `search_events(keyword, days=7)` | method | Case-insensitive substring search over raw JSON lines | Use to fetch recent events for context injection | Returns max 20 matches, newest first; ignores malformed lines |
| `rebuild_summary()` | method | Read last 7 days of events, tally event type counts, write summary | Call at end of `/structure-chat` response (see structure_auth.py) | No Claude call — just counts and formats a simple line |
| `get_summary()` | method | Load summary.json (timestamp + text) | Use to inject memory context into `/structure-chat` prompt | Returns `{"last_updated": None or ISO8601, "text": ""}` on I/O error |
| `upsert_pilot(address, character_name, character_id, tier)` | method | Create or update pilot profile JSON | Call after successful `/auth/verify` (see auth_verify in main.py) | Validates Sui address format (0x + 64 hex); raises `ValueError` on invalid format |
| `get_pilot(address)` | method | Load pilot profile (name, tier, visit count, first/last seen) | Use to customize greeting or fetch pilot reputation | Returns `None` if not found; silently returns `None` on I/O error |
| `bootstrap()` | method | Create directory structure + files if missing | Call once at server startup or per-structure initialization | Safe to call multiple times (uses `exist_ok=True`) |
| `get_memory_store(structure_id)` | factory function | Create and bootstrap a MemoryStore for a structure | Use instead of `MemoryStore()` directly | Returns ready-to-use store; structure_id required |
| `SUMMARY_CAP` | constant | Max character length for summary text (300) | Truncate summary if rebuild produces text longer than this | — |
| `_DEFAULT_BASE_DIR` | constant | `data/memory/` relative to project root | Overridable via `MemoryStore(base_dir=...)` constructor | — |

## Critical Gotchas & Pitfalls

• **Event search is case-insensitive substring matching.** `search_events("kill", days=7)` will find lines containing "kill", "Kill", "KILL", or as part of "killmail". Not regex, not word-boundary aware.

• **Max 20 results returned.** If searching for a common term, you may not get all matches. Oldest matches are dropped (newest-first order).

• **Address validation is strict.** `upsert_pilot()` expects `0x` + exactly 64 hex characters. Will raise `ValueError` on format mismatch. Use `get_pilot()` to check if a profile exists without validation errors.

• **All I/O errors are swallowed.** `append_event()`, `search_events()`, `rebuild_summary()`, `get_summary()`, `upsert_pilot()`, and `get_pilot()` log warnings but never raise exceptions. Always assume writes may silently fail if disk is full or permissions change.

• **summary.json is NOT rebuilt by the AI.** It is rebuilt only when `rebuild_summary()` is called (at end of `/structure-chat` response). It contains tallies of event types (docking, killmail, ssu_state, turret_state, access_change), not condensed lore.

• **Pilot profiles auto-increment visit_count.** Each call to `upsert_pilot()` increments the `visit_count` field and updates `last_seen` timestamp. Use `get_pilot()` to read current count.

## Architecture

```
MemoryStore
├── _base (base_dir, default: data/memory/)
├── _sid (structure_id, e.g., "keep-7a")
└── _root() = {_base}/{_sid}

Files:
├── events.jsonl ← append_event() writes here (JSONL, one event per line)
├── summary.json ← rebuild_summary() writes here; get_summary() reads it
└── pilots/
    └── {normalized_address}.json ← upsert_pilot() / get_pilot() use this
```

Each event JSON line:
```json
{"ts": "2026-03-18T15:30:45Z", "type": "docking", "system_id": 30000004, "data": {...}}
```

Each pilot profile:
```json
{
  "address": "0x1234...5678",
  "character_name": "Markús Þór",
  "character_id": 2123456,
  "tier": "OWNER",
  "first_seen": "2026-03-18T12:00:00Z",
  "last_seen": "2026-03-18T15:30:45Z",
  "visit_count": 5
}
```

## Agent Guidance

**Primary Workflow**

1. **At server startup:** Call `get_memory_store(structure_id)` once per structure (bootstraps automatically).
2. **On structure event (dock/undock/kill/SSU alert):** Call `append_event(event_type, system_id, event_data)`.
3. **Before `/structure-chat` response:** Call `mem.get_summary()` and inject the `text` field into the prompt.
4. **After `/structure-chat` response finishes:** Call `mem.rebuild_summary()` to update tallies.
5. **On successful `/auth/verify`:** Call `mem.upsert_pilot(address, name, character_id, tier)` to record the visit.
6. **When building chatbot context:** Optionally call `mem.search_events(keyword, days=7)` to fetch recent matching events and inject them.

**Best Practices & Anti-Patterns**

- Always use the `get_memory_store()` factory; never instantiate `MemoryStore()` directly in production.
- Never assume writes succeeded. Log calls to `append_event()` / `upsert_pilot()` are "fire and forget" — they won't throw exceptions even if the disk is full.
- Always validate address format before calling `upsert_pilot()` if the address comes from untrusted input. The method will raise `ValueError` on invalid format.
- Never rely on summary to be fresh. It's only updated when `rebuild_summary()` is called. If the server crashes between a call and the next `/structure-chat`, the summary will be stale.
- Use `search_events()` only for UI-driven searches or debugging. For context injection, always call `get_summary()` instead (faster, per-structure granularity).

**Cross-Module Dependencies**

- **Used by:** `structure_auth.py` (calls `upsert_pilot()` on successful auth verify; calls `get_summary()` in `/structure-chat` event_stream)
- **Used by:** `ssu_poller.py` (calls `append_event("killmail", ...)` and `append_event(event_type, ...)` for on-chain events)
- **Used by:** `main.py` (calls `mem.rebuild_summary()` at end of `/structure-chat` generator)

## Progressive Disclosure

Read this file by default. Load deeper files only when told above.
- Implementation details (address validation, file paths) → `references/memory_store-deep.md` (not yet written; check registry)
- Test coverage → `tests/test_memory_store.py` (12 tests: event append/search, summary rebuild/get, pilot upsert/get)
