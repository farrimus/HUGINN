# context_builder

## Overview
Assembles the `[SHIP SENSORS]` context block that Claude sees in every prompt. Synthesizes game state (location, route, combat, mining, ships, structures) into a human-readable format. The only function is `build_context_block()`.

## When Should an Agent Use This Module?
- Building the live context for Ship AI prompts
- Formatting game events into readable summaries
- Injecting route planning data into Claude prompts

## Key API
| Symbol | Type | Purpose | Agent Instruction |
|--------|------|---------|------------------|
| `build_context_block(...)` | function | Assembles context from system data, events, and game state | Always call before each Claude prompt to get current state |

### Function Parameters
- `system_data` (dict, optional): Current system metadata (name, security, kills, safe_jump_temp)
- `log_events` (list): Game events from log buffer (combat, mining, transitions, chat)
- `current_system` (str, optional): Current system name; overrides system_data if provided
- `live_sessions` (list, optional): Real-time session snapshots (combat/mining in progress)
- `current_route` (dict, optional): Active route plan from client (path, warnings, highlights)
- `structure_alerts` (list, optional): Urgent structure AI alerts (prepended for visibility)
- `ship_profile` (ShipProfile, optional): Ship stats (fuel, range, temperature constraints)
- `nearby_structures` (list, optional): Player-owned structures in current system

### Return Value
- `str`: ≤2000 chars. Plain text block with labeled sections (LOCATION, SHIP, MINING, ROUTE, etc.)

## Critical Gotchas & Pitfalls for Agents
• **Order matters:** Structure alerts are prepended first for visibility — they override other sections.
• **Truncation at 2000 chars:** Long paths or verbose events are silently truncated. Output is always safe to embed.
• **Stale events:** Only the last 5 transition events are shown; older events are dropped by design.
• **Missing keys:** All optional fields default gracefully — passing `None` is safe.

## Architecture
```
Input: system_data, log_events, ship_profile, route
  ↓
Parse events by type (combat, mining, transitions, chat)
  ↓
Build labeled sections: LOCATION, SHIP, ALERTS, MINING, COMBAT, ROUTE
  ↓
Truncate to 2000 chars max
  ↓
Output: plain text block ready for Claude
```

## Agent Guidance
**Primary Workflow**
1. Collect current state: system, ship profile, recent log events, live sessions
2. Call `build_context_block()` with all available data
3. Inject result as-is into every Claude prompt under `[SHIP SENSORS]` section
4. Re-call before each new prompt to capture live updates

**Best Practices & Anti-Patterns**
- Always / Call once per prompt, not multiple times per prompt
- Always / Pass `ship_profile` if available (enables range/fuel calculations)
- Never / Filter or edit the output — let Claude see raw formatted state
- Never / Pass `live_sessions` without checking they're still in-progress (stale sessions pollute context)

**Cross-Module Dependencies**
- Depends on: `log_buffer` (events), `ship_profile` (stats), `world_api` (system metadata)
- Used by: `claude_client` (Ship AI prompt assembly)

## Progressive Disclosure
**Read this main file by default.**

**Load deeper files ONLY when:**
- You need event format spec: read `/docs/log-pipeline.md` section on log event types
- You need context block schema: read `/docs/ref/ship-ai.md` section on prompt structure
