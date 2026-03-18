# route_engine

## Overview
Hybrid A*/Dijkstra pathfinding engine with temperature-aware constraints. Finds gate-hop and direct-jump routes respecting ship fuel/heat budgets. Includes spatial indexing for fast radius queries and hot-system detection.

## When Should an Agent Use This Module?
- Computing routes for the Ship AI (primary use)
- Checking if a destination is reachable
- Analyzing route fuel cost and jump counts
- Detecting hot systems (temperature warnings)

## Key API
| Symbol | Type | Purpose | Agent Instruction |
|--------|------|---------|------------------|
| `route_engine.route(origin, dest, profile, cost_mode)` | method | Compute full route with warnings and alternatives | **Always use this** for player route requests |
| `route_engine.bfs(origin, dest)` | method | Gate-only shortest path (ignores ship stats) | Use only when ship profile unavailable |
| `route_engine.ready()` | method | Check if systems.json is loaded | Call once at startup; returns bool |
| `route_engine.resolve(name)` | method | Resolve system name to ID | Use for name validation before route calls |
| `route_engine.system_info(name)` | method | Get system metadata (security, temp, planets) | Use to check system safety before jumping |

## Critical Gotchas & Pitfalls for Agents
• **File watcher required:** engine auto-loads from `systems.json` on first call. Missing file = silent failure (returns `no_route`). Check logs.
• **Temperature affects range:** Same ship, different systems = different jump ranges. `node_range_ly()` uses `safe_jump_temp` from target system, not current ship temp.
• **Hot system avoidance:** Engine calculates a primary route, then if hot systems exist, generates an alternative route avoiding those nodes as direct-jump waypoints. **Always show both if alternative exists.**
• **Fuel warnings:** If route costs more fuel than ship carries, a warning is included but the route is still returned. **Never assume fuel_remaining > 0.**

## Architecture
```
Input: origin, destination, ShipProfile
  ↓
Load systems.json (lazy load, cached)
  ↓
Resolve names to system IDs
  ↓
Run A* with two cost modes:
  - "jumps": minimize hop count (heuristic: straight-line dist / max range)
  - "fuel": minimize direct-jump distance (gates free, Dijkstra)
  ↓
Detect hot intermediates (temp >= 70°C)
  ↓
Generate alternative if hot systems exist
  ↓
Format result with per-hop breakdown, warnings, fuel calc
  ↓
Output: route dict with path, jumps, fuel, warnings, alternative
```

## Agent Guidance
**Primary Workflow**
1. Validate origin/dest with `resolve()`
2. Call `route()` with ship profile and cost_mode="jumps" (default)
3. Check for `warnings` — fuel, security, unreachable
4. If `alternative` exists, inform player of hot-system avoidance
5. Inject full route dict into context for Claude

**Best Practices & Anti-Patterns**
- Always / Call `route()` with full ship profile — gates-only routes are incomplete
- Always / Check `fuel_remaining` and show warnings prominently
- Never / Assume a route exists without checking for `"type": "no_route"`
- Never / Use `bfs()` for real gameplay — it ignores fuel constraints

**Cross-Module Dependencies**
- Depends on: `ship_profile` (fuel/heat calcs), `world_api` (system metadata), `galaxy_db` (gate graph)
- Used by: client RouteCalculator (Python), `context_builder` (route injection), `claude_client` (situation awareness)

## Progressive Disclosure
**Read this main file by default.**

**Load deeper files ONLY when:**
- You need algorithm details: read `/docs/ref/routing.md` (A* pseudocode, heat formula, ship physics)
- You need hot-system logic: read `/docs/ref/routing.md` section on temperature constraints
- You need performance tuning: read `/docs/ref/routing.md` section on spatial indexing
