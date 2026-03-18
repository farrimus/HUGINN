# Log Pipeline — Design Document

Last updated: 2026-03-13 (gate graph builder, route_planned event, context_builder route injection, index.html SSE update)

---

## Purpose

The log pipeline turns raw EVE Frontier client log files into a compact, lore-grounded
situational context block that the companion receives before every response.

The companion never sees raw log lines. It sees a dense summary of what the pilot
is doing, where they are, and what has recently happened — enough to respond as a
character who actually knows the situation.

---

## Pipeline Overview

```
Raw log files (Gamelogs/, Chatlogs/)
  → log_agent.py          — watches files, reads new lines, calls parsers
    → parsers.py          — emits clean structured events (or None)
      → session_tracker.py  — aggregates events into sessions, emits summaries
        → POST /log/ingest  — sends summaries + pass-through events to server
          → log_buffer.py   — ring buffer (closed events) + live store (in-progress)
            → context_builder.py  — formats the context block
              → Claude (companion)

HeartbeatEmitter (daemon thread, every 30s):
  → session_tracker.flush_stale()  — close timed-out sessions, send final summaries
  → session_tracker.snapshot()     — snapshot open sessions with in_progress: True
    → POST /log/ingest             — routed to log_buffer.set_live() on server
```

**Key files:**

| File | Location | Role |
|---|---|---|
| `log_agent.py` | `log-agent/` | Watchdog file watcher, owns the observer loop, runs HeartbeatEmitter |
| `parsers.py` | `log-agent/` | Line-level parsing, tag stripping, event shaping |
| `session_tracker.py` | `log-agent/` | Stateful aggregation, session lifetime management, snapshot support |
| `log_buffer.py` | `src/` | Server-side ring buffer + live session store + current_route |
| `context_builder.py` | `src/` | Formats context block from buffer + live sessions + planned route |
| `world_api.py` | `src/` | System index + gate graph builder |
| `route_engine.py` | `src/` | Server-side A* hybrid router (dev/debug only — too CPU-heavy for VPS production use) |
| `ship_profile.py` | `src/` | ShipProfile model + fuel formulas + persistence |
| `RouteCalculator` | `log-agent/` or `client/` (**planned**) | Client-side A* router — downloads `systems.json` once, runs on gaming PC, POSTs `route_planned` |

---

## Log File Formats

### Gamelog
Location: `Gamelogs/`
Line format:
```
[ YYYY.MM.DD HH:MM:SS ] (type) <color/font tags...>message text
```
Types seen in production: `combat`, `mining`, `notify`, `hint`, `info`, `question`, `warning`

Some lines have no `(type)` prefix — these are untagged system messages (e.g. undocking notices).

HTML-style tags (`<color=0x...>`, `<font size=N>`, `<b>`, `<br>`) must be stripped before
any pattern matching. Tags carry no useful information.

### Chatlog
Location: `Chatlogs/`
Line format:
```
[ YYYY.MM.DD HH:MM:SS ] SENDER > message text
```
One file per chat channel. The local channel is the primary source — it contains
system change notifications and player conversations. No `(type)` prefix. No color tags.

---

## Gamelog Events (emitted by parsers.py)

### undock
Source: untagged gamelog lines
Trigger: `Undocking from STATION to SYSTEM solar system.`
Signals the pilot has left a station and is now in space.
Not the primary system location signal — use `system_change` from chatlog for that.

```json
{"type": "undock", "station": "Ersetu II - Keep #37", "system": "Ersetu"}
```

### combat_out
Trigger: `(combat) N to TARGET - WEAPON - HIT_QUALITY`

```json
{"type": "combat_out", "damage": 136, "target": "Bihepopths",
 "weapon": "Tier 3 Coilgun (S)", "hit": "Grazes"}
```

Hit quality values seen in production: `Grazes`, `Hits`, `Glances Off`, `Smashes`, `Penetrates`

### combat_in
Trigger: `(combat) N from SOURCE - HIT_QUALITY`
No weapon name in this format.

```json
{"type": "combat_in", "damage": 22, "source": "Bihepopths", "hit": "Penetrates"}
```

### combat_miss
Trigger (outgoing): `(combat) Your WEAPON misses TARGET completely`
Trigger (incoming): `(combat) TARGET misses you completely`

```json
{"type": "combat_miss", "direction": "outgoing", "weapon": "Base Autocannon (S)", "target": "Faulty Scout Drone"}
{"type": "combat_miss", "direction": "incoming", "source": "Faulty Scout Drone"}
```

### sightline_blocked
Trigger: `(combat) Sightline of TARGET to you is obscured`

```json
{"type": "sightline_blocked", "source": "Faulty Scout Drone"}
```

### mining
Trigger: `(mining) You mined N units of MATERIAL`
Tags stripped before matching.

```json
{"type": "mining", "quantity": 24, "material": "Feldspar Crystals"}
```

### autopilot
Trigger: `(notify) Autopilot engaged` / `Autopilot disabled`

```json
{"type": "autopilot", "state": "engaged"}
{"type": "autopilot", "state": "disabled"}
```

### docking
Trigger: `(notify) Requested to dock at STATION station`
Trigger: `(notify) Your docking request has been accepted`

```json
{"type": "docking", "state": "requested", "location": "Ersetu II - Keep #37"}
{"type": "docking", "state": "accepted"}
```

### cargo_full
Trigger: `(notify) MODULE has completed operations. Ship's cargo hold is full.`
Also feeds the open mining session (if any) before being forwarded.

```json
{"type": "cargo_full", "module": "Small Cutting Laser"}
```

### ship_stopping
Trigger: `(notify) Ship stopping`

```json
{"type": "ship_stopping"}
```

### gamelog_raw
Any line matching the outer format whose content is not matched by a specific pattern.
Nothing is silently dropped — unrecognised lines are preserved for visibility.

```json
{"type": "gamelog_raw", "msg_type": "notify", "text": "You're halfway onboard already. Please wait."}
```

Applies to unmatched lines of type: `notify`, `combat`, `mining`, and any future unknown types.

---

## Chatlog Events (emitted by parsers.py)

### system_change
Trigger: message matches `Channel changed to Local : SYSTEM`
Primary system location signal — fires on every gate jump.
`sender` is stored for future-proofing: if the sender name changes from "Keeper",
the event still emits and the anomaly is visible in the data.

```json
{"type": "system_change", "system": "UTR-SN4", "sender": "Keeper"}
```

### chat
All other chatlog lines. Captures player conversations, NPC messages, anything else
in the channel. Session tracker and context builder decide what to surface.

```json
{"type": "chat", "sender": "zaroot", "message": "o7"}
```

---

## Dropped (parsers.py returns None)

Deliberately discarded — no situational or lore value for the companion:

- `(info)` — server status, connection errors, cluster messages
- `(question)` — confirmation dialogs ("Are you sure...")
- `(warning)` — jettison confirmations, external link notices
- `(notify)` speed changes — `Speed changed to N m/s`
- `(notify)` proximity spam — `X is too far away...`, `automatic approach`
- Blank lines, log file headers

---

## Session Tracker (implemented — log-agent/session_tracker.py)

Sits between parsers and the server. Absorbs raw combat/mining events, accumulates
them into sessions, and emits summary events when sessions close.

Pass-through events (system_change, docking, autopilot, chat, etc.) are returned
immediately so the server always has real-time state.

### Combat session

Absorbs: `combat_out`, `combat_in`, `combat_miss`, `sightline_blocked`

Tracks:
- Enemies engaged (name → hit count)
- Total damage dealt and received
- Hit quality distribution (in and out)
- Weapons used
- Miss counts (in and out)

Closes on: `system_change`, `docking`, 60-second inactivity timeout, or `flush()`.

Emits `combat_summary`:
```json
{
  "type":         "combat_summary",
  "system":       "Ersetu",
  "duration_s":   90,
  "enemies":      {"Faulty Scout Drone": 3, "Faulty Repair Drone": 1},
  "damage_out":   1240,
  "damage_in":    280,
  "hits_out":     {"Penetrates": 5, "Grazes": 2},
  "hits_in":      {"Penetrates": 4},
  "weapons_used": ["Tier 3 Coilgun (S)"],
  "misses_out":   1,
  "misses_in":    0
}
```

### Mining session

Absorbs: `mining`
Also receives: `cargo_full` (counted but also forwarded)

Tracks:
- Units per material (running total)
- Cargo full count
- Session duration

Closes on: `system_change`, `docking`, 120-second inactivity timeout, or `flush()`.

Emits `mining_summary`:
```json
{
  "type":        "mining_summary",
  "system":      "UTR-SN4",
  "duration_s":  2040,
  "materials":   {"Carbonaceous Ore": 847, "Hermetite": 312},
  "total_units": 1159,
  "cargo_fulls": 2
}
```

### Timeout detection

Timeouts are checked in two places:

1. **Lazily** — on each incoming event via `_flush_stale()` inside `_process()`
2. **Periodically** — `HeartbeatEmitter` calls `tracker.flush_stale()` every 30
   seconds, so sessions that time out with no subsequent game events are still
   closed and sent promptly rather than hanging until the next event arrives.

### Shutdown flush

`tracker.flush()` is called on `KeyboardInterrupt` in `log_agent.py`, which force-closes
all open sessions and sends their summaries before the process exits.

---

## Context Block Format (as built)

What Claude receives before every response. Built by `context_builder.py` from
`log_buffer.get_recent(N)` plus `log_buffer.get_live()` plus `log_buffer.current_route`.

Live snapshots override buffered summaries of the same type — the most recent
picture of a session always wins.

```
LOCATION: UTR-SN4 | security: 0.3 | 2 recent kill(s) in system
ROUTE PLANNED: UTR-SN4 → I.59R.8J2 → Morioka (2 jumps, est 14 min) | WARNINGS: high temp at I.59R.8J2
MINING (ongoing): Carbonaceous Ore ×847, Hermetite ×312 over 34 min | cargo full ×2
COMBAT (ongoing): 3 × Faulty Scout Drone, 1 × Faulty Repair Drone | dmg 1240 out / 280 in (Penetrates) | Tier 3 Coilgun (S)
JUMPED TO: UTR-SN4
LOCAL CHAT: zaroot, ikeee active
```

**Line order:** LOCATION → ROUTE PLANNED (if set) → MINING/COMBAT → transitions → LOCAL CHAT.

`(ongoing)` is appended when the session data came from a live heartbeat snapshot
rather than a closed summary. It disappears once the session closes and the final
summary lands in the ring buffer.

`ROUTE PLANNED` persists across all chat turns until a new `route_planned` event
replaces it. It is never evicted by TTL.

Hard cap: 2000 characters.

### `context_builder.py` function signature (current)

```python
def build_context_block(
    system_data: Optional[dict],
    log_events: list,
    current_system: Optional[str],
    live_sessions: Optional[list] = None,
    current_route: Optional[dict] = None,
    structure_alerts: Optional[list] = None,
    ship_profile=None,
    nearby_structures: Optional[list] = None,
) -> str
```

**Parameters:**
- `current_route` — passed from `log_buffer.current_route` in the chat endpoint
- `structure_alerts` — critical structures (low fuel, etc.) from Structure AI
- `ship_profile` — Ship heat, range, jump distance from route_engine
- `nearby_structures` — structures within radius_search (e.g., player-owned stations)

---

## Bootstrap & Startup Behaviour

### Initial system detection

On startup, `log_agent.py` calls `bootstrap_system()` which scans the tail of the
most recent `Local_*` chatlog file (last 500 lines) for the most recent `system_change`
event. If found, the system is injected into the `SessionTracker` before the file
watcher starts.

### PeriodicBootstrap — retry when agent starts before game

If no `Local_*` files exist yet (agent started before the game client), bootstrap
finds nothing and the system stays unknown. `PeriodicBootstrap` is a daemon thread
that retries `bootstrap_system()` every 30 seconds until the system becomes known,
then exits cleanly. Log line on exit:

```
[agent] PeriodicBootstrap: system known (UTR-SN4), stopping
```

The thread also runs when bootstrap succeeds immediately, but exits on its first
check (the `current_system is not None` guard).

`PeriodicBootstrap.stop()` is called on `KeyboardInterrupt` alongside the observer.

### Mtime-based new-file detection (race fix)

On Windows, watchdog sometimes fires `on_modified` before `on_created` (or coalesces
them), so the first-sight logic seeking to end-of-file can miss the opening lines of
a new session file (including the first `system_change`).

Fix: `LogFileHandler` records the agent start time (`agent_start: float`). On first
`on_modified` for an unseen file:

- `mtime > agent_start` → file was created after the agent started → read from
  position 0 (new session file)
- `mtime ≤ agent_start` → file existed before the agent started → seek to end
  (old file, no replay)

The `on_created` handler is kept as-is (belt-and-suspenders).

### `SessionTracker.current_system` property

A thread-safe read-only property on `SessionTracker` exposes the current known
system without accessing private `_system` directly. Used by `PeriodicBootstrap`
to decide whether to keep retrying.

---

## Session Heartbeat (implemented — 2026-03-12)

### HeartbeatEmitter

A daemon thread in `log_agent.py`, modelled on `PeriodicBootstrap`. Fires every 30
seconds. On each tick:

1. Calls `tracker.flush_stale()` — closes any sessions that have passed their
   inactivity threshold and sends their final summaries to the server. This drives
   timeout detection even when no game events arrive (e.g. player stops mining and
   idles).
2. Calls `tracker.snapshot()` — returns copies of still-open sessions with
   `in_progress: True` set, without closing them. POSTs each snapshot to `/log/ingest`.

Started in `__main__` alongside `PeriodicBootstrap`. Stopped on `KeyboardInterrupt`.

### snapshot()

New method on `SessionTracker`. Acquires the lock, calls `to_summary()` on any open
combat or mining session, stamps each result with `in_progress: True`, and returns
the list. Does not mutate session state.

### Server-side live store (log_buffer.py)

Separate from the ring buffer so heartbeats do not pollute recent-event history.

| Method | Behaviour |
|---|---|
| `set_live(snapshots)` | Replaces `_live` with the new list, stamping each entry with `_ts = time.time()` |
| `get_live()` | Returns entries newer than 120 seconds (TTL = `LIVE_TTL_S`). Stale entries are silently dropped — no explicit eviction needed. |
| `clear_live(session_type)` | Removes live entries matching `session_type`. Called when the real closed summary arrives. |

The 120s TTL matches `MINING_TIMEOUT_S`. If the agent crashes mid-session the ghost
live entry expires on the server within 2 minutes without any manual intervention.

### Ingest routing (main.py)

```
in_progress: True  →  log_buffer.set_live([data])
otherwise          →  log_buffer.add(data)
                       if combat_summary or mining_summary: log_buffer.clear_live(type)
```

### Known Limitations

- Heartbeat granularity is 30s. The companion may lag up to 30s behind the current
  session state (e.g. a burst of mining that happened 25s ago won't appear until the
  next tick).
- Only one live entry per session type is kept. If two mining sessions somehow overlap
  (not possible under current rules, but worth noting), only the latest snapshot is
  retained.

---

## Route Planned Event (2026-03-13)

A new event type posted by the **client-side RouteCalculator** (Python, Windows — planned).
It is sent to `/log/ingest` like any other event.

```json
{
  "type": "route_planned",
  "path": ["utr-sn4", "i.59r.8j2", "morioka"],
  "jumps": 2,
  "est_time_min": 14,
  "warnings": ["high temp at i.59r.8j2"]
}
```

**Server handling:**
- `log_buffer.add(event)` stores it in the ring buffer (history)
- Additionally sets `log_buffer.current_route = event` (persists until replaced)
- `context_builder.py` formats it as the `ROUTE PLANNED:` line

**The server never calculates routes.** It only stores and relays what the client sends.
The `warnings` list is populated by the client's BFS filter based on ship parameters and
system conditions (temperature, security status). Claude reads the warnings and can
comment on route hazards without performing any calculations itself.

---

## Gate Graph (2026-03-13)

`world_api.rebuild_index()` now builds `data/gate_graph.json` in the same paginated
API pass as the system index. No extra API calls.

**What it contains:**

```json
{
  "built_at": "2026-03-13T10:00:00Z",
  "adj": {
    "utr-sn4": ["i.59r.8j2", "neighbor-b"],
    "i.59r.8j2": ["utr-sn4", "morioka"]
  },
  "meta": {
    "utr-sn4": { "id": 30001001, "security": 0.3, "location": {"x": 1.5e14, "y": -2.1e13, "z": 8.7e13} }
  }
}
```

Served at `GET /data/gate-graph` (auth required) with ETag / If-None-Match support.
Client downloads once at startup and caches to disk.

**Known uncertainty:** It is unconfirmed whether the bulk `/v2/solarsystems` paginated
endpoint includes `gateLinks` per system. If `adj` is empty after a rebuild, individual
system fetches (`/v2/solarsystems/{id}`) will be needed — 24,501 calls, feasible but slow.
Test by triggering `POST /admin/rebuild-index` and checking `gate_graph.json`:
```bash
curl -H "X-Server-Token: $TOKEN" http://localhost:8745/data/gate-graph | jq '(.adj | length)'
# Should be ~24000 if gateLinks are in bulk response; 0 if not
```

---

## Known Limitations

- Heartbeat granularity is 30s. The companion may lag up to 30s behind the current
  session state.
- Only one live entry per session type is kept.
- `current_route` is never evicted — stale route persists in Claude's context until
  replaced. A `route_cleared` event type could be added if this becomes noisy.
- Gate graph `adj` population depends on `gateLinks` being present in the bulk
  `/v2/solarsystems` API response. Unconfirmed as of 2026-03-13 — trigger a rebuild
  and check `adj` length to verify.

---

## Lore Notes for Context Building

- System names are alphanumeric coordinates (UTR-SN4, I.59R.8J2) — use verbatim
- "Faulty" drones (Scout, Analyzer, Repair) are corrupted pre-Collapse automation
- Weapon names (Coilgun, Autocannon, Mass Driver, Railgun) are in-universe tech — use verbatim
- Hit quality terms (Penetrates, Grazes, Smashes, Glances Off) are game flavor language — use verbatim
- Material names (Carbonaceous Ore, Hermetite, Aestasium, Feldspar Crystals) are lore terms — use verbatim
- Currency: LUX
- Structures: Keep, Fabricator, Citadel, Stellar Constructions
- "Keeper" — guiding AI entity, lore character, sender of system change notifications in local chat
