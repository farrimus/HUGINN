# Nav Computer — Implementation Spec

**Date:** 2026-03-15
**Status:** Approved for implementation

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
- Systems with planets or Lagrange points: use the outermost object's orbit radius
- Systems with star only: use `star_radius` — will produce temp near 100, effectively no-jump

**Temperature zones:**

| Zone | Range | Effect |
|------|-------|--------|
| Safe | < 70 | Normal jump range |
| Yellow | 70–79 | Moderately reduced range |
| Orange | 80–89 | Significantly reduced range |
| Red | ≥ 90 | No fuel jumps possible. Gates unaffected. |

### Single-Jump Range Formula

```
range_ly = ((150 - safe_jump_temp) × C_eff × M_hull) / (3 × M_current)
```

- `C_eff = specific_heat × (1 + adaptive_level × 0.02)`
- `M_hull` — ship base mass (kg)
- `M_current` — total loaded mass: hull + extra cargo (kg). Fuel treated as massless pending confirmation of per-unit fuel mass from game data.
- Returns light-years. If `safe_jump_temp ≥ 90`, range = 0.

### Fuel Budget Formula

```
budget_ly = (fuel_quantity × fuel_quality) / (1e-7 × M_current)
```

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

For each system, add three new fields by querying the DB:

```python
# star_luminosity — from SolarSystems table
star_luminosity = row["star_luminosity"]  # watts

# max_orbit_m — outermost planet orbit radius, or star_radius fallback
max_orbit_m = max(planet orbit radii) or lagrange point distances
if none found: max_orbit_m = star_radius  # star-only system, will be very hot

# safe_jump_temp — official formula
import math
L_SUN = 3.828e26
K = 100
D = max_orbit_m / 299_792_458  # light-seconds
safe_jump_temp = 100 * (2/math.pi) * math.atan(K * 2 * math.pi * math.sqrt(star_luminosity / L_SUN) / D)
```

Systems with `safe_jump_temp ≥ 90` are not used as intermediate direct-jump nodes by the router (gates through them still work).

`systems.json` size impact: ~11 MB → ~12 MB. ETag cache means clients only re-download on rebuild.

---

## Section 2: Ship Profile

### ship_profile.py changes

Replace the placeholder defaults with the official ship table. Add:

```python
SHIPS = {
    "Carom":   {"mass": 7_200_000,       "specific_heat": 8.5, "fuel_type": "basic"},
    "Stride":  {"mass": 7_900_000,       "specific_heat": 8.0, "fuel_type": "basic"},
    "Reflex":  {"mass": 9_750_000,       "specific_heat": 3.0, "fuel_type": "basic"},
    "Recurve": {"mass": 10_200_000,      "specific_heat": 1.0, "fuel_type": "basic"},
    "Reiver":  {"mass": 10_400_000,      "specific_heat": 1.0, "fuel_type": "basic"},
    "Lai":     {"mass": 18_929_160,      "specific_heat": 2.5, "fuel_type": "advanced"},
    "USV":     {"mass": 30_266_600,      "specific_heat": 1.8, "fuel_type": "advanced"},
    "Lorha":   {"mass": 42_691_330,      "specific_heat": 2.5, "fuel_type": "advanced"},
    "MCF":     {"mass": 52_313_760,      "specific_heat": 2.5, "fuel_type": "advanced"},
    "Tades":   {"mass": 74_655_480,      "specific_heat": 2.5, "fuel_type": "advanced"},
    "HAF":     {"mass": 81_883_000,      "specific_heat": 2.5, "fuel_type": "advanced"},
    "Maul":    {"mass": 548_435_920,     "specific_heat": 2.5, "fuel_type": "advanced"},
    "Chumaq":  {"mass": 1_487_392_000,   "specific_heat": 3.0, "fuel_type": "advanced"},
}
```

Add `ship_type: Optional[str]` and `extra_cargo_kg: float = 0.0` to `ShipProfile`.

Update `jump_range()` to return light-years (not meters). Update `fuel_budget()` to return light-years.

Update `current_mass` computation: `hull_mass + extra_cargo_kg` (fuel treated as massless pending confirmation of fuel unit mass).

---

## Section 3: Route Engine

### route_engine.py changes

**Per-node jump range.** At each A* node expansion, compute outbound range from that node's `safe_jump_temp` rather than using a fixed ship range:

```python
node_temp = self._systems[node_id].get("safe_jump_temp", 0.0)
if node_temp >= 90:
    node_range_ly = 0.0  # no direct jumps out
else:
    node_range_ly = ((150 - node_temp) * c_eff * hull_mass) / (3 * current_mass)
```

Gate edges are always available regardless of heat.

**Spatial index** switches from meters to light-years to match the updated range formula. System coordinates in systems.json are in meters; convert to LY on load: `x_ly = x_m / 9_460_000_000_000_000`.

**Alternative route.** After finding the primary route, check if any intermediate system has `safe_jump_temp > 70`. If yes, run a second A* pass that skips systems with `safe_jump_temp > 70` as direct-jump nodes (they can still be gate-transited). If the alternative path exists and differs from the primary, include it. If unreachable or identical, return `None` for alternative.

**Route result shape:**

```python
{
    "type": "route_planned",
    "path": ["sys-a", "sys-b", ...],          # system names
    "jumps": 6,
    "jump_types": ["direct", "gate", ...],     # one per hop
    "total_ly": 142.3,
    "fuel_used": 87.0,
    "fuel_remaining": 213.0,
    "hot_systems": ["sys-c"],                  # intermediate systems with temp > 70
    "alternative": { ...same shape... } | None,
    "warnings": [],
}
```

**`GET /current-route` response shape:**

```json
{
  "route": { ...active route... },
  "alternative": { ...or null... }
}
```

**New endpoint: `POST /route/activate`**

Body: `{"variant": "primary" | "alternative"}`. Swaps `log_buffer.current_route` to the chosen variant. Returns the activated route.

Server stores both variants in `log_buffer` (add `pending_alternative` field alongside `current_route`).

---

## Section 4: Route Panel (Overlay)

Panel size: 440×260. Position: bottom-left (unchanged).

### Display layout

```
NAV COMPUTER                              [F7]
──────────────────────────────────────────────
SYS-A → [4 hops] → SYS-B  6j · 142 LY · 87u  [USE]
SYS-A → [6 hops] → SYS-B  8j · 198 LY · 112u [USE]
──────────────────────────────────────────────
                                         [CLEAR]
```

- First row: primary (optimal) route. Always shown when a route is active.
- Second row: alternative. Only shown when server returns a non-null alternative.
- `[USE]` button calls `POST /route/activate` with the appropriate variant. Active route row is highlighted brighter green. Inactive row is dimmed.
- Jump type detail is not shown inline in the panel (space constraint) but is available in the companion chat response.
- CRT scanline effect retained.

### Jump type annotation in companion chat

When `/route DEST` is processed, the streamed reply lists each hop:

```
ROUTE: SYS-A → [4 hops] → SYS-B (6 jumps · 142 LY · 87u fuel)
  1. SYS-A → NEXT-1   direct  47 LY  28u
  2. NEXT-1 → NEXT-2  gate
  3. NEXT-2 → NEXT-3  direct  51 LY  31u
  ...
```

Jump types: `direct`, `gate`, `player gate` (future).

---

## Section 5: Ship Profile Panel (Overlay)

New panel toggled by **F7**. Position: top-left, 440×280.

### Fields

| Field | Type | Notes |
|-------|------|-------|
| Ship type | Dropdown | 13 ships; auto-fills mass + specific heat |
| Fuel type | Dropdown | Filtered: basic ships show D1/D2 only |
| Fuel units | Integer input | |
| Adaptive level | Integer 0–10 | |
| Extra cargo (kg) | Integer input | Optional; default 0 |

### Computed display (live, read-only)

```
JUMP RANGE:   425.0 LY   (at current system temp)
FUEL BUDGET:  416.7 LY
```

Current system temp is fetched from `/current-route` (already polled). If unknown, shows temp = 0 assumption.

### SAVE button

POSTs to `POST /ship-profile`. Shows "SAVED" for 2 seconds on success, "ERROR" on failure.

---

## Section 6: Input Methods

### Slash commands (companion panel)

All handled server-side in `/chat` before reaching Claude:

```
/profile              → print current profile (one-line summary)
/profile ship Carom   → set ship type, auto-fill mass + specific_heat
/profile fuel 300 D1  → set fuel_quantity=300, fuel_type=D1
/profile level 3      → set adaptive_level=3
/profile cargo 50000  → set extra_cargo_kg=50000
/route DEST           → compute route with current profile
```

### Claude (natural language)

Claude can update the profile via tool use or by recognising intent and calling `POST /ship-profile`. Example triggers:

- "I just refuelled — 2000 units of EU-90" → update fuel
- "I'm in a Lai now" → update ship type
- "What's my jump range from here?" → read profile + current system temp, compute

### Context block addition

`build_context_block` adds a one-line ship summary when a profile exists:

```
SHIP: Lai | EU-90 × 2400u | range 380 LY | budget 1141 LY
```

---

## Out of Scope

- Fuel mass per unit (treat as massless until confirmed from game data)
- Player-owned gate routing (architecture supports it as a future edge type)
- Route time estimates
- Multi-waypoint routing
