# Nav Computer — Implementation Spec

**Date:** 2026-03-15
**Status:** Implemented (2026-03-16 — see amendment notes below)

---

## Goal

Replace the current gate-only route calculator with a full navigation computer that finds the best path between any two systems using a mix of direct jumps and gate jumps, accounts for per-system heat conditions, presents up to two route options, and lets the pilot input their ship profile through the overlay panel, slash commands, or natural language with Claude.

---

## Background: Jump Mechanics

### External Temperature Formula

```
H(D) = 100 × (2/π) × arctan(K × 2π × √(L / L_sun) / D)
```

- `L` — star luminosity in watts (from DB `SolarSystems.star_luminosity`)
- `L_sun` — 3.828 × 10²⁶ W (IAU nominal solar luminosity)
- `K` — 100 (distance scaling constant)
- `D` — distance from star in light-seconds (`orbit_radius_meters / 299_792_458`)
- Output: 0–100 game units (asymptotic, never exceeds 100)

**Safe jump point distance:**
- `D` uses the **outermost non-Cold-Ice-Giant planet's orbitRadius only**. Cold Ice Giants have extreme orbital radii that cause severe underestimation of heat (confirmed via ef-map.com comparison). **Lagrange points are not used** — ef-map.com uses planet orbits only, not Lagrange points.
- Systems with star only (no planets): use `star_radius` as fallback — will produce temp near 100, effectively no-jump.

> **Amendment 2026-03-16:** Original spec said "use outermost object's orbit radius" (including Lagrange points). This was corrected after calibration against ef-map.com: UR8-K7K target 36.9° — planets-only formula gives 37.0° ✓; with Lagrange points included the result was 10.8° ✗. Cold Ice Giants also excluded from the planet set for the same reason.

**Temperature zones:**

| Zone | Range | Effect |
|------|-------|--------|
| Safe | < 70 | Normal jump range |
| Yellow | 70–79 | Moderately reduced range |
| Orange | 80–89 | Significantly reduced range |
| Red | ≥ 90 | No fuel jumps possible. Gates unaffected. |

### Single-Jump Range Formula

```
range_ly = ((T_max - safe_jump_temp) × C_eff × M_hull) / (3 × M_current)
```

- `T_max = 150` (game constant)
- `C_eff = specific_heat × (1 + adaptive_level × 0.02)`
- `M_hull` — ship base mass (kg)
- `M_current` — total loaded mass: hull + extra cargo (kg). Fuel is treated as massless (not added to M_current) pending confirmation of per-unit fuel mass from game data.
- Returns light-years. If `safe_jump_temp ≥ 90`, range = 0.

### Fuel Budget Formula

```
budget_ly = (fuel_quantity × fuel_quality) / (1e-7 × M_current)
```

- `fuel_quality` — the Quality value from the Fuel Types table below (e.g., D1 → 0.10, EU-90 → 0.90).
- `1e-7` — game-canonical constant (dimensionless scale factor from official formula; not derived).
- `M_current` — same definition as jump range: `hull_mass + extra_cargo_kg` (fuel massless).
- `adaptive_level` does **not** appear in the fuel budget formula. It only scales `C_eff` in the jump range formula.

### Ship Reference Table

| Ship | Mass (kg) | Specific Heat | Max Fuel | Fuel Type |
|------|-----------|---------------|----------|-----------|
| Carom | 7,200,000 | 8.5 | 3,000 | Basic |
| Stride | 7,900,000 | 8.0 | 3,200 | Basic |
| Reflex | 9,750,000 | 3.0 | 1,750 | Basic |
| Recurve | 10,200,000 | 1.0 | 970 | Basic |
| Reiver | 10,400,000 | 1.0 | 1,416 | Basic |
| Lai | 18,929,160 | 2.5 | 2,400 | Advanced |
| USV | 30,266,600 | 1.8 | 2,420 | Advanced |
| Lorha | 42,691,330 | 2.5 | 2,508 | Advanced |
| MCF | 52,313,760 | 2.5 | 6,548 | Advanced |
| Tades | 74,655,480 | 2.5 | 5,972 | Advanced |
| HAF | 81,883,000 | 2.5 | 4,184 | Advanced |
| Maul | 548,435,920 | 2.5 | 24,160 | Advanced |
| Chumaq | 1,487,392,000 | 3.0 | 270,585 | Advanced |

### Fuel Types

| Type | Quality | Ships |
|------|---------|-------|
| D1 | 0.10 | Basic |
| D2 | 0.15 | Basic |
| SOF-40 | 0.40 | Advanced |
| EU-40 | 0.40 | Advanced |
| SOF-80 | 0.80 | Advanced |
| EU-90 | 0.90 | Advanced |

---

## Architecture

### Files Modified or Created

| File | Change |
|------|--------|
| `build_universe.py` | Add `star_luminosity`, `max_orbit_m`, `safe_jump_temp` per system |
| `src/ship_profile.py` | Add ship table constants, update defaults, add `extra_cargo_kg` field |
| `src/route_engine.py` | Per-node heat-adjusted range, return primary + optional alternative |
| `main.py` | `/route` returns both variants; new `POST /route/activate`; `GET /current-route` returns all variants; `/chat` `/route` handler updated; `/profile` slash command |
| `src/context_builder.py` | Add one-line ship profile summary to context block |
| `overlay/overlay_ui/ship_profile_panel.h/.cpp` | New F7 panel |
| `overlay/overlay_ui/route_panel.cpp` | Show two options with SELECT, jump type per hop |
| `overlay/overlay_ui/http_client.h/.cpp` | Any new GET/POST helpers needed |
| `overlay/overlay_ui/render.cpp/.h` | Wire up ship_profile_panel init/draw/shutdown |
| `overlay/overlay_ui/CMakeLists.txt` | Add ship_profile_panel.cpp |

---

## Section 1: Data Layer

### build_universe.py additions

For each system, add new fields by querying the DB:

```python
# star_luminosity — from SolarSystems table
star_luminosity = row["star_luminosity"]  # watts

# max_orbit_m — outermost non-Cold-Ice-Giant planet orbit radius, or star_radius fallback
# Lagrange points are NOT used (ef-map.com confirmed planets-only)
# Cold Ice Giants excluded (extreme orbits produce severe heat underestimation)
max_orbit_m = MAX(orbitRadius) WHERE typeDescription != 'Cold Ice Giant'
if none found: max_orbit_m = star_radius  # star-only system, will be very hot

# safe_jump_temp — official formula
import math
L_SUN = 3.828e26
K = 100
D = max_orbit_m / 299_792_458  # light-seconds
safe_jump_temp = 100 * (2/math.pi) * math.atan(K * 2 * math.pi * math.sqrt(star_luminosity / L_SUN) / D)
```

Systems with `safe_jump_temp ≥ 90` (Red zone) produce `node_range_ly = 0` in the A* expansion — no direct jump out is possible, but gate edges through them remain available. The primary route may freely use Yellow (70–79) and Orange (80–89) systems as direct-jump waypoints. The alternative route is the one that additionally avoids all systems with `safe_jump_temp ≥ 70` as direct-jump waypoints.

- **Red zone (≥90°):** 655 systems (revised from original estimate of 159)
- **Warm zone (70–89°):** 1,254 systems (revised from ~905)

`systems.json` size impact: ~11 MB → ~12 MB. ETag cache means clients only re-download on rebuild.

---

## Section 2: Ship Profile

### ship_profile.py changes

Replace the placeholder defaults with the official ship table. Add:

```python
SHIPS = {
    "Carom":   {"mass": 7_200_000,       "specific_heat": 8.5, "fuel_category": "basic"},
    "Stride":  {"mass": 7_900_000,       "specific_heat": 8.0, "fuel_category": "basic"},
    "Reflex":  {"mass": 9_750_000,       "specific_heat": 3.0, "fuel_category": "basic"},
    "Recurve": {"mass": 10_200_000,      "specific_heat": 1.0, "fuel_category": "basic"},
    "Reiver":  {"mass": 10_400_000,      "specific_heat": 1.0, "fuel_category": "basic"},
    "Lai":     {"mass": 18_929_160,      "specific_heat": 2.5, "fuel_category": "advanced"},
    "USV":     {"mass": 30_266_600,      "specific_heat": 1.8, "fuel_category": "advanced"},
    "Lorha":   {"mass": 42_691_330,      "specific_heat": 2.5, "fuel_category": "advanced"},
    "MCF":     {"mass": 52_313_760,      "specific_heat": 2.5, "fuel_category": "advanced"},
    "Tades":   {"mass": 74_655_480,      "specific_heat": 2.5, "fuel_category": "advanced"},
    "HAF":     {"mass": 81_883_000,      "specific_heat": 2.5, "fuel_category": "advanced"},
    "Maul":    {"mass": 548_435_920,     "specific_heat": 2.5, "fuel_category": "advanced"},
    "Chumaq":  {"mass": 1_487_392_000,   "specific_heat": 3.0, "fuel_category": "advanced"},
}
```

`fuel_category` (`"basic"` or `"advanced"`) drives the fuel type dropdown filter. `ShipProfile.fuel_type` stores the specific fuel code the pilot has loaded (e.g., `"D1"`, `"EU-90"`). These are distinct fields.

Add `ship_type: Optional[str]` and `extra_cargo_kg: float = 0.0` to `ShipProfile`. `extra_cargo_kg` must be ≥ 0; backend rejects negative values. No upper bound is enforced (no hard ship cargo limit in game data). If `ship_type` is provided but does not match a key in `SHIPS`, backend returns 422. If `fuel_type` is provided but does not belong to the `fuel_category` of the selected `ship_type` (e.g., D1 on an Advanced ship), backend returns 422.

Update `jump_range()` to return light-years (not meters). Update `fuel_budget()` to return light-years.

Update `current_mass` computation: `hull_mass + extra_cargo_kg`. Fuel quantity does not contribute to mass and is excluded from all mass calculations — both the jump range formula and the fuel budget formula use this same `current_mass` value.

---

## Section 3: Route Engine

### route_engine.py changes

**Routing modes (`cost_mode` parameter):**

> **Amendment 2026-03-16:** The route engine now supports three modes, exposed as `cost_mode` in `POST /route` and echoed back in the result.

| `cost_mode` | Algorithm | Gate cost | Direct cost | Heuristic | Goal |
|-------------|-----------|-----------|-------------|-----------|------|
| `"jumps"` (default) | A* | 1 hop | 1 hop | dist/max_range | Fewest hops |
| `"fuel"` | Dijkstra (A* h=0) | 0 LY | distance_ly | 0 | Minimum LY flown |
| `"gate"` | BFS | — | not used | — | Gates only |

Fuel-optimized mode often routes through many gate hops to avoid long direct jumps, reducing total LY significantly at the cost of more hops. Example: UR8-K7K → EVV-7GK: jumps-opt = 2 hops / 200.4 LY; fuel-opt = 9 hops / 154.1 LY.

**Per-node jump range.** At each A* node expansion, compute outbound range from that node's `safe_jump_temp` rather than using a fixed ship range:

```python
T_MAX = 150  # game constant
node_temp = self._systems[node_id].get("safe_jump_temp", 0.0)
if node_temp >= 90:
    node_range_ly = 0.0  # Red zone — no direct jumps out; gates still available
else:
    node_range_ly = ((T_MAX - node_temp) * c_eff * hull_mass) / (3 * current_mass)
```

Gate edges are always available regardless of heat.

**Spatial index** switches from meters to light-years to match the updated range formula. System coordinates in systems.json are in meters. `route_engine.py` converts all three axes (x, y, z) to LY at load time using the IAU light-year: `x_ly = x_m / 9_460_730_472_580_800` (exact IAU value; approximation `9_460_000_000_000_000` is acceptable for game precision). The conversion is not done in `build_universe.py` — systems.json retains meter coordinates. All subsequent A* distance calculations and range comparisons are performed entirely in LY. LY-converted coordinates are internal to `route_engine.py` and never exposed to API callers; all route responses use system names.

**Alternative route.** After finding the primary route, check if any **intermediate** system (all path nodes except origin and destination) has `safe_jump_temp ≥ 70` (Yellow zone or hotter). The intent is to offer the pilot a cooler-path option when their primary route passes through thermally restricted space. If any such intermediate exists, run a second A* pass. In this pass, build an exclusion set from the path nodes at indices `1` through `len(path) - 2` (i.e., all nodes except index 0 = origin and index -1 = destination) where `safe_jump_temp ≥ 70`. Never add origin or destination to the exclusion set. The destination is always a valid direct-jump target regardless of its temperature — only intermediate waypoints are excluded. Systems in the exclusion set cannot be used as direct-jump waypoints but can still be gate-transited. If the alternative path exists and differs from the primary, include it. If unreachable or identical, return `None` for alternative.

**Route result shape:**

> **Amendment 2026-03-16:** Additional fields added: `cost_mode`, `origin_temp`, `origin_planets`, and per-hop metadata `hops`. System names are stored and returned **uppercase**.

```python
{
    "type": "route_planned",
    "path": ["SYS-A", "SYS-B", ...],          # system names (uppercase)
    "jumps": 6,                                # edges traversed = len(path) - 1
    "jump_types": ["direct", "gate", ...],     # len == jumps, one entry per edge
    "total_ly": 142.3,
    "fuel_used": 87.0,
    "fuel_remaining": 213.0,
    "hot_systems": ["SYS-C"],                  # intermediate systems with safe_jump_temp ≥ 70
    "cost_mode": "jumps",                      # echoed from request
    "origin_temp": 36.9,                       # safe_jump_temp of origin system
    "origin_planets": 4,                       # planet_count of origin system
    "hops": [
        {
            "from": "SYS-A",
            "to": "SYS-B",
            "type": "gate",                    # "gate" or "direct"
            "distance_ly": 0.0,
            "dest_temp": 78.2,
            "dest_planets": 3
        },
        ...
    ],
    "alternative": { ...same shape... } | None,
    "warnings": [],
}
```

**Unreachable destination.** If no path exists (disconnected cluster, destination unknown, or fuel insufficient to reach any neighbor), `route()` returns:

```python
{
    "type": "no_route",
    "path": [],
    "jumps": 0,
    "jump_types": [],
    "total_ly": 0.0,
    "fuel_used": 0.0,
    "fuel_remaining": <current fuel budget>,
    "hot_systems": [],
    "alternative": None,
    "warnings": ["No route found to <destination>"],
}
```

`current_route` is set to this result; `pending_alternative` is set to `None`. The overlay displays the warning text in place of route rows.

**`GET /current-route` response shape:**

```json
{
  "route": { ...active route... },
  "alternative": { ...or null... },
  "current_system_temp": 45.2
}
```

`current_system_temp` is the `safe_jump_temp` of `log_buffer.current_system` looked up from the in-memory systems index. `null` if the current system is unknown.

**New endpoint: `POST /route/activate`**

Body: `{"variant": "primary" | "alternative"}`. Swaps `log_buffer.current_route` to the chosen variant. Returns the activated route.

Error cases:
- `variant` is not `"primary"` or `"alternative"` → 422
- `variant` is `"alternative"` but `pending_alternative` is `None` → 404 with `{"detail": "no alternative route available"}`
- No route in `log_buffer` → 404 with `{"detail": "no active route"}`

Server stores both variants in `log_buffer` (add `pending_alternative` field alongside `current_route`). Both fields are set atomically when `POST /route` succeeds: `current_route` = primary result, `pending_alternative` = alternative result (or `None`). A new route request overwrites both fields. `POST /route/activate` only swaps which variant is `current_route`; it does not clear `pending_alternative`.

---

## Section 4: Route Panel (Overlay)

Panel size: 440×260. Position: bottom-left (unchanged). Polls `GET /current-route` every 5 seconds (matches existing route panel polling interval).

### Display layout

```
NAV COMPUTER
──────────────────────────────────────────────
SYS-A → SYS-B   6 jumps · 142 LY · 87u   [USE]
SYS-A → SYS-B   8 jumps · 198 LY · 112u  [USE]
──────────────────────────────────────────────
                                         [CLEAR]
```

Terminology: **jump** = one hop in the path (direct or gate). The display uses "jumps" only — no separate "hops" field.

- First row: primary (optimal) route. Always shown when a route is active.
- Second row: alternative. Only shown when server returns a non-null alternative.
- `[USE]` button calls `POST /route/activate` with the appropriate variant. Active route row: bright green text (matches existing panel palette). Inactive row: gray/dimmed text.
- Jump type detail is not shown inline in the panel (space constraint) but is available in the companion chat response.
- CRT scanline effect retained.

### Jump type annotation in companion chat

When `/route DEST` is processed, the streamed reply lists each hop:

```
ROUTE: SYS-A → SYS-B  6 jumps · 142 LY · 87u
  1. SYS-A   → NEXT-1  direct  47 LY  28u
  2. NEXT-1  → NEXT-2  gate
  3. NEXT-2  → NEXT-3  direct  51 LY  31u
  ...
```

Jump types: `direct`, `gate`. Player-owned gates are out of scope and will be a future edge type.

---

## Section 5: Ship Profile Panel (Overlay)

New panel toggled by **F7**. Position: top-left, 440×280.

### Fields

| Field | Type | Notes |
|-------|------|-------|
| Ship type | Dropdown | 13 ships; auto-fills mass + specific heat |
| Fuel type | Dropdown | Filtered: basic ships show D1/D2; advanced ships show SOF-40/EU-40/SOF-80/EU-90. Changing ship type resets fuel type to the lowest-quality default for that category: D1 for basic, SOF-40 for advanced. |
| Fuel units | Integer input | UI clamps to ship's Max Fuel from reference table; backend also validates |
| Adaptive level | Integer 0–10 | UI clamps to 0–10; backend rejects values outside this range |
| Extra cargo (kg) | Integer input | Optional; default 0 |

### Computed display (live, read-only)

```
JUMP RANGE:   425.0 LY   (at current system temp)
FUEL BUDGET:  416.7 LY
```

Current system temp is read from the `current_system_temp` field in the `/current-route` poll response (added to that endpoint for this purpose). If `null` (system unknown or no route computed yet), both computed fields show `—`. The panel does not require an active route — it shows `—` whenever `current_system_temp` is absent from the poll response.

### SAVE button

POSTs to `POST /ship-profile`. Shows "SAVED" for 2 seconds on success, "ERROR" on failure.

---

## Section 6: Input Methods

### Slash commands (companion panel)

All handled server-side in `/chat` before reaching Claude. Each `/profile` mutation immediately calls `POST /ship-profile` — no separate SAVE step required. The server responds with the updated profile summary, which is streamed back as the reply.

```
/profile              → print current profile (one-line summary)
/profile ship Carom   → set ship type, auto-fill mass + specific_heat; auto-save
/profile fuel 300 D1  → set fuel_quantity=300, fuel_type=D1; auto-save
/profile level 3      → set adaptive_level=3; auto-save
/profile cargo 50000  → set extra_cargo_kg=50000; auto-save
/route DEST           → compute route with current profile
```

### Claude (natural language)

Claude can update the profile via tool use or by recognising intent and calling `POST /ship-profile`. Example triggers:

- "I just refuelled — 2000 units of EU-90" → update fuel
- "I'm in a Lai now" → update ship type
- "What's my jump range from here?" → read profile + current system temp, compute

### Context block addition

`build_context_block` adds a one-line ship summary when a profile exists. This is the Claude chat context, not the overlay panel. `range` and `budget` are computed at context-build time using `log_buffer.current_system_temp` (best-effort; updated whenever the log agent sends a system_change event). If the current system is unknown, range is computed with temp = 0 (maximum possible range) and labeled `range ~NNN LY` to signal the estimate. The overlay panel (Section 5) uses a different rule: it shows `—` for unknown temp instead of estimating. `budget` is independent of location in both contexts.

```
SHIP: Lai | EU-90 × 2400u | range 380 LY | budget 1141 LY
```

---

## Out of Scope

- Fuel mass per unit (treat as massless until confirmed from game data)
- Player-owned gate routing (architecture supports it as a future edge type)
- Route time estimates
- Multi-waypoint routing

---

## Deferred Features (post-2026-03-16)

### Compare+Blend Routing

A third routing mode that models **time cost** in addition to fuel cost, enabling a combined score. Design discussion captured in `docs/future-features/blend-routing.md`.

Key open questions before implementation:
1. Ship jump cooldown formula — proportional to origin system `safe_jump_temp`; exact formula not yet confirmed from ef-map.com
2. Gate transit time — need in-game measurement of gate jump duration
3. UI: side-by-side panel showing jumps-opt, fuel-opt, and time-opt routes simultaneously
