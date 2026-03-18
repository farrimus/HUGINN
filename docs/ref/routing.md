# Routing Architecture

**Last updated:** 2026-03-16
**Related:** `src/route_engine.py`, `src/ship_profile.py`, `data/systems.json`, `data/gates.json`

---

## Design

Routing must run **client-side on the Windows gaming PC**.

**Why not server-side:**
- The VPS is a Hetzner 2 vCPU / 4 GB instance — shared, low-spec, running multiple services
- A* over 24,426 systems with spatial range queries is CPU-intensive and will block FastAPI's event loop
- The gaming PC has orders of magnitude more CPU headroom and sits next to the game process
- Ship parameters (mass, temp, fuel) change constantly — the client has them, the server doesn't

**Current state:** `src/route_engine.py` and `src/ship_profile.py` exist on the server as a **reference implementation and dev/test tool**. `POST /route` and `GET/POST /ship-profile` are functional but should not be used in production routing — they are useful for debugging and for Claude to verbally describe a hypothetical route when asked.

**Target architecture:** A Python `RouteCalculator` process on Windows loads `systems.json` once, runs A* locally, and POSTs the result as a `route_planned` event to `/log/ingest`. The server only stores and relays the result — zero compute on the VPS.

---

## Data flow (target)

```
[Windows — RouteCalculator process]
  1. On startup: GET /data/systems (downloads systems.json, ~7 MB, cached with ETag)
  2. Builds in-memory graph + spatial index
  3. On route request (pilot input or chat trigger):
     - Reads ship params from local profile / user input
     - Runs A* locally (gaming CPU — fast)
     - POST /log/ingest {"type": "route_planned", "path": [...], "jumps": N, ...}

[Server]
  4. log_buffer stores result in current_route
  5. Next Claude prompt includes "ROUTE PLANNED: ..." line automatically
  6. Claude responds verbally, aware of the computed route
```

## Data flow (current — dev/debug only)

```
POST /route {"destination": "X"}  → server-side A* (avoid in production, CPU cost on VPS)
POST /chat "fly to X"             → regex match → server-side route → Claude responds
```

The chat intent detection (`_extract_route_destination`) and server `/route` endpoint remain useful for demos and for Claude to handle simple verbal route queries — but heavy production routing belongs on the client.

---

## Jump mechanics (from ef-map.com/ai-facts)

**Single-jump range (meters):**
```
range = ((150 - ext_temp) × specific_heat × hull_mass) / (3 × current_mass)
```

**Total fuel budget (meters):**
```
budget = (fuel_quantity × fuel_quality) / (1e-7 × current_mass)
```

**External temp from star (blocks jumping if ≥ 90):**
```
H(D) = 100 × (2/π) × arctan(100 × 2π × √(L / L_sun) / D)
```

**Fuel quality table:** D1=10%, D2=15%, SOF-40/EU-40=40%, SOF-80=80%, EU-90=90%

---

## Router algorithm

`route_engine.py` provides three modes via the `cost_mode` parameter:

1. **`bfs(origin, dest)`** — gate-only, free, no ship params. Finds shortest gate-hop path within a connected cluster. Fast (< 5ms). Used as fallback when A* returns no result (also surfaced via `gate_only=true` in the API).

2. **`route(origin, dest, profile, cost_mode="jumps")`** — heat-aware A* hybrid.
   - **`cost_mode="jumps"`** (default): minimizes hop count. Gate hops cost 1; direct jumps cost 1. Heuristic = dist_to_dest / max_range. Finds fewest-hop paths even when the route refuels en route at cool systems.
   - **`cost_mode="fuel"`**: minimizes total LY flown. Gate hops cost 0 LY; direct jumps cost distance in LY. Heuristic = 0 (Dijkstra). Finds routes that string gate hops together to save fuel even at the cost of many more hops.
   - **`gate_only=true`**: calls BFS, gate hops only. When true, only use gate jumps (0 cost). When false, calculate heat-based route cost.

   Per-node jump range is computed from the system's `safe_jump_temp` (not the player's `external_temp`). Red-zone systems (≥90°) block outbound direct jumps (range=0). `_SpatialIndex` narrows candidates via sorted X-axis binary search + dy/dz AABB guards.

   **Alternative route:** After the primary A* pass, if any system in `path[1:-1]` has `safe_jump_temp ≥ WARM_SYSTEM_TEMP (70.0)`, a second A* pass runs with those hot systems excluded as direct-jump waypoints (gates through them are still allowed). The alternative is stored in `log_buffer.pending_alternative`. Calling `POST /route/activate` swaps `current_route ↔ pending_alternative`.

---

## Universe data structure

`data/systems.json` — built from EVE Frontier ResFiles via `build_universe.py`:
```json
{
  "built_at": "...",
  "systems": {
    "30000001": {
      "id": 30000001, "name": "SYSTEM-NAME",
      "x": -5.1e18, "y": -4.4e17, "z": 1.3e18,
      "region_id": 10000001, "constellation_id": 20000001,
      "sun_type_id": 45031, "sun_type": "Sun K7 (Orange)", "spectral_class": "K7",
      "star_luminosity": 6.3e26,
      "star_radius": 4.8e8,
      "max_orbit_m": 1.4e11,
      "safe_jump_temp": 54.3,
      "planet_ids": [...],
      "gate_links": [30000004, 30000005]
    }
  }
}
```

**`safe_jump_temp` formula** (stored per system, computed by `build_universe.py`):
```
H(D) = 100 × (2/π) × arctan(K × 2π × √(L / L_sun) / D)
```
where `L_sun = 3.828e26 W`, `K = 100` (game canonical), `D = max_orbit_m / 299_792_458` (light-seconds).

`max_orbit_m` = outermost **planet** orbitRadius, excluding **Cold Ice Giants** (their extreme orbits cause severe underestimation). **Lagrange points are not used** — ef-map.com confirmed planets-only. For star-only systems, `max_orbit_m` falls back to `star_radius`.

- **Red zone** (≥90°): no outbound direct jump possible — 655 systems
- **Warm zone** (70–89°): triggers alternative route computation — 1,254 systems
- Total systems: 24,426

**Gate network facts:**
- 3,438 unique gate pairs, 231 disconnected clusters, largest = 39 systems
- ~2,878 systems have gates; ~21,548 are unreachable by gate alone
- Gate hops are free (fuel cost 0) — zero-cost edges in A*

---

## Ship profile

Stored in `data/ship_profile.json`, managed via `src/ship_profile.py`. The `ship_type` field auto-fills `hull_mass` and `specific_heat` from the SHIPS table.

| Field | Description |
|---|---|
| `ship_type` | Ship name (e.g. "Carom") — auto-fills hull_mass + specific_heat from SHIPS table |
| `hull_mass` | Base hull mass (kg) — set automatically when ship_type is provided |
| `specific_heat` | Ship thermal capacity — set automatically when ship_type is provided |
| `adaptive_level` | Adaptive upgrade level (0–10) |
| `fuel_type` | D1 / D2 / SOF-40 / EU-40 / SOF-80 / EU-90 |
| `fuel_quantity` | Units of fuel loaded |
| `extra_cargo_kg` | Additional cargo mass (kg); added to hull_mass for range/budget calculations |
| `external_temp` | Override for ambient temp (default 0 = deep space) |

**SHIPS table** (13 entries): Carom, Stride, Reflex, Recurve, Reiver (basic — D1/D2 fuel); Lai, USV, Lorha, MCF, Tades, HAF, Maul, Chumaq (advanced — SOF/EU fuel).

**Jump range formula:**
```
range_ly = ((150 - temp) × C_eff × M_hull) / (3 × M_current)
C_eff = specific_heat × (1 + adaptive_level × 0.02)
M_current = hull_mass + extra_cargo_kg
```

**Fuel budget formula:**
```
budget_ly = (fuel_quantity × fuel_quality) / (1e-7 × M_current)
```

---

## Route response format

```json
{
  "type": "route_planned",
  "path": ["SYSTEM-A", "SYSTEM-B", "SYSTEM-C"],
  "jumps": 2,
  "jump_types": ["gate", "direct"],
  "total_ly": 142.5,
  "fuel_used": 87.4,
  "fuel_remaining": 412.6,
  "hot_systems": ["SYSTEM-B"],
  "warnings": ["SYSTEM-B: safe_jump_temp 78.2° — warm zone"],
  "cost_mode": "jumps",
  "origin_temp": 36.9,
  "origin_planets": 4,
  "hops": [
    {
      "from": "SYSTEM-A",
      "to": "SYSTEM-B",
      "type": "gate",
      "distance_ly": 0.0,
      "dest_temp": 78.2,
      "dest_planets": 3
    },
    {
      "from": "SYSTEM-B",
      "to": "SYSTEM-C",
      "type": "direct",
      "distance_ly": 142.5,
      "dest_temp": 22.1,
      "dest_planets": 5
    }
  ],
  "alternative": { "...same shape, or null..." }
}
```

System names are stored and returned **uppercase** (e.g. `UR8-K7K`, not `ur8-k7k`). Input fields in the UI enforce uppercase via `oninput` and `text-transform: uppercase`.

`GET /current-route` returns:
```json
{
  "route": { "...route object or null..." },
  "alternative": { "...route object or null..." },
  "current_system_temp": 54.3
}
```

---

## Future: ship stat auto-extraction

Currently, ship parameters are entered manually via the F7 ship profile panel or `POST /ship-profile`. The SHIPS table covers all 13 known ships so `ship_type` selection auto-fills mass and specific_heat — the main remaining manual input is fuel quantity and adaptive level.

**Potential future improvements:**
- Parse ship stats from game log lines (if EVE Frontier logs undock/loadout events with stats)
- Query the World API for ship type stats by `typeID` (if endpoint exists)
- Read directly from game memory via overlay DLL (technically possible, high complexity)
- Community-maintained ship stat database (similar to EVE Online's pyfa/ESI)

---

## Deferred features

- **Blend/time-optimized routing** — design doc at `docs/future-features/blend-routing.md`. Shows fewest-jump + least-fuel side by side; time model needs ship jump cooldown formula from ef-map.com.
- **ef-map golden tests** — `tests/test_ef_map_comparison.py` has 1 confirmed system (UR8-K7K=36.9°). Use `scripts/check_temps.py` to add more.
- **A* memory usage** — path stored as full list per heap entry (quadratic). Acceptable for dev/debug; optimize before client-side port.
