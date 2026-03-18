# ShipProfile

## Overview
Ship profile manages vessel configuration (mass, heat capacity, fuel) and computes jump range and fuel budget using EVE Frontier's canonical jump mechanics. Provides query methods for route planning and operational readiness checks. Persistent JSON storage via `data/ship_profile.json`.

## When Should an Agent Use This Module?
- **Route context:** Call `jump_range()` or `jump_range_at_temp(safe_jump_temp)` to report current maximum single-jump distance
- **Fuel tracking:** Call `fuel_budget()` to show how far the current fuel load stretches in light-years
- **Jump validation:** Call `can_jump()` to check if external temperature blocks jumping
- **Load/save:** Use `load_profile()` to read persistent ship state; `save_profile(profile)` to persist changes
- **Ship selection:** Set `ship_type` (e.g., "Carom", "Lai") to auto-populate `hull_mass` and `specific_heat` from SHIPS table
- **Route engine internal:** Jump range formula uses `jump_range_at_temp(safe_jump_temp)` per system during A* traversal

## Key API

| Symbol | Type | Purpose | Agent Instruction | Gotchas |
|--------|------|---------|-------------------|---------|
| **ShipProfile** | dataclass | Main config: hull_mass, specific_heat, adaptive_level, fuel_type, fuel_quantity, external_temp, extra_cargo_kg, ship_type | Read `load_profile()` to get current; modify fields; call `save_profile(profile)` to persist | `current_mass` field is legacy; actual mass used is `hull_mass + extra_cargo_kg` |
| **ShipProfile.can_jump()** | method → bool | Checks if `external_temp < 90.0` (red zone threshold) | Use to validate jump readiness. Red zone (≥90°) blocks all outbound direct jumps | Returns false if in red zone, true otherwise |
| **ShipProfile.jump_range()** | method → float | Single-jump distance (LY) at current `external_temp` using full formula | Report to pilot after each temp reading. Call after docking/undocking to reflect new ambient. | Returns 0.0 if `can_jump()` is false; uses actual effective mass (hull + cargo) |
| **ShipProfile.jump_range_at_temp(safe_jump_temp)** | method → float | Single-jump distance at hypothetical temperature (used by route engine for planning) | Pass system's `safe_jump_temp` to see range at that location without changing profile | Used internally by `route_engine.py` A* per-node; not for chat reporting |
| **ShipProfile.fuel_budget()** | method → float | Total distance (LY) the ship can travel with current fuel load | Report as "budget: N LY" in context. Depends on `fuel_type` quality, not quantity alone | Returns 0.0 if `fuel_type` not in FUEL_QUALITY table (unknown fuel) |
| **ShipProfile.fuel_for_distance(ly)** | method → float | Fuel units consumed to jump a given distance (LY) | Used to compute fuel cost of a specific route leg. Inverse of fuel_budget. | Depends on fuel type quality; returns 0.0 if fuel_type unknown |
| **ShipProfile._current_mass** | property → float | Effective mass (hull + extra cargo). Used in all calculations. | Internal; accessed by range/budget formulas. Never expose directly in chat. | Fuel is massless; only cargo adds mass |
| **ShipProfile.with_overrides(**kwargs)** | method → ShipProfile | Return a copy with selected fields updated | Use to test hypothetical configs: `profile.with_overrides(extra_cargo_kg=5_000_000)` | Only non-None values override; None values are skipped |
| **load_profile()** | module fn → ShipProfile | Load stored profile from `data/ship_profile.json`; return default if missing/corrupted | Call at startup or when profile changes on disk. Cached in module global `_stored`. | Filters unknown keys to handle legacy JSON. Warns on load failure; returns default ShipProfile. |
| **save_profile(profile)** | module fn → None | Persist profile to `data/ship_profile.json` and module global `_stored` | Call after any profile update. Creates `data/` directory if missing. | Logs warnings on failure; does not raise exceptions. |
| **SHIPS** | dict[str, dict] | 13 ship types → {mass, specific_heat, fuel_category} | Use to validate ship names or auto-fill hull_mass. Always present: Carom, Stride, Reflex, Recurve, Reiver (basic); Lai, USV, Lorha, MCF, Tades, HAF, Maul, Chumaq (advanced) | Each ship has canonical mass and heat capacity. Do not modify. |
| **SHIP_MAX_FUEL** | dict[str, int] | 13 ship types → max fuel units (tank capacity) | Reference for "cargo full" scenarios. Map each ship to max fuel. | Value is units, not liters. Different ships have different tank sizes. |
| **FUEL_QUALITY** | dict[str, float] | Fuel type → quality multiplier (0.0–0.90). D1=0.10, D2=0.15, SOF-40/EU-40=0.40, SOF-80=0.80, EU-90=0.90 | Used in fuel_budget/fuel_for_distance formulas. Higher quality = more range per unit. | Unknown fuel type returns 0.0 quality (invalid fuel). |
| **FUEL_CATEGORY** | dict[str, str] | Fuel type → category: "basic" (D1, D2) or "advanced" (SOF-40, EU-40, SOF-80, EU-90) | Reference only. "basic" fuels for frigates; "advanced" for larger ships. | Ship's fuel_category must match available fuel types. |
| **FUEL_CONSTANT** | float (1e-7) | Denominator in fuel budget formula | Do not use directly. Internal to fuel formulas. | Game-canonical constant. |
| **T_MAX** | float (150.0) | Max reference temperature in jump range formula | Do not use directly. Used in: `jump_range = ((T_MAX - temp) * c_eff * hull_mass) / (3 * current_mass)` | Game constant from ef-map.com. |
| **HEAT_CONSTANT** | float (3.0) | Divisor in jump range formula | Do not use directly. Internal constant. | Appears as denominator in jump_range calculation. |
| **NO_JUMP_TEMP** | float (90.0) | Red zone threshold. ≥90° blocks outbound direct jumps. | Used by `can_jump()`. Systems with `safe_jump_temp ≥ 90` require gate hops only. | Hard game rule; no exceptions. |

## Critical Gotchas & Pitfalls

• **`current_mass` field is legacy** — Do not use. Always use the `_current_mass` property, which sums `hull_mass + extra_cargo_kg`. The field is kept for backward compatibility with stored JSON but is ignored by all formulas.

• **Fuel is massless** — Only `extra_cargo_kg` adds to effective mass. Increasing fuel quantity does NOT change jump range (only fuel budget). Cargo does.

• **Red zone blocks outbound jumps only** — If `external_temp ≥ 90`, this ship cannot jump away. It can still dock/gate-hop. Routes must avoid red-zone waypoints (except as gates through them).

• **Fuel type unknown = zero budget** — If `fuel_type` is not in FUEL_QUALITY table, both `fuel_budget()` and `fuel_for_distance()` return 0.0. Validate fuel type before arithmetic.

• **Adaptive level applies 2% per level** — `c_eff = specific_heat * (1 + adaptive_level * 0.02)`. Level 10 = 20% bonus. High levels improve heat handling.

• **Ship type auto-fill only on load** — Setting `ship_type` does not retroactively update `hull_mass` or `specific_heat`. You must reload from SHIPS manually or use `with_overrides()` to apply both.

• **External temp is an override** — `external_temp` in the profile is NOT the current system temp from the World API. It is a manual override for testing. Use it only for debug. In production, the route engine passes `safe_jump_temp` into `jump_range_at_temp()` instead.

## Architecture

### Jump Range Mechanics

Single-jump distance in light-years:
```
range_ly = ((T_MAX - external_temp) × C_eff × hull_mass) / (3 × current_mass)
where:
  T_MAX = 150.0 (game constant)
  external_temp = system's safe_jump_temp (or profile override)
  C_eff = specific_heat × (1 + adaptive_level × 0.02)
  hull_mass = base ship mass (from SHIPS table)
  current_mass = hull_mass + extra_cargo_kg (effective)
  3 = HEAT_CONSTANT (game divisor)
```

**Key insight:** Range decreases with cargo (heavier = shorter jumps). Adaptive upgrades improve heat dissipation, increasing range. Hotter systems reduce range. Red zone (≥90°) forces range to 0.

### Fuel Budget Mechanics

Total distance available with current fuel:
```
budget_ly = (fuel_quantity × fuel_quality) / (1e-7 × current_mass)
where:
  fuel_quantity = units of fuel loaded
  fuel_quality = FUEL_QUALITY[fuel_type] (0.0–0.90)
  1e-7 = FUEL_CONSTANT (game canonical)
  current_mass = hull_mass + extra_cargo_kg
```

**Key insight:** Higher quality fuel stretches further per unit. Heavier ships burn more fuel per LY (inverse relationship with mass). Fuel quantity is independent of distance (can replan within budget).

### Storage

`data/ship_profile.json` (JSON):
```json
{
  "hull_mass": 10000000.0,
  "current_mass": 11000000.0,
  "specific_heat": 1.0,
  "adaptive_level": 0,
  "fuel_type": "SOF-80",
  "fuel_quantity": 500.0,
  "external_temp": 0.0,
  "ship_type": "Lai",
  "extra_cargo_kg": 0.0
}
```

Loaded by `load_profile()` with validation. Persisted by `save_profile(profile)`.

## Agent Guidance

### Primary Workflow

1. **On session start:** `profile = load_profile()` — read persistent state
2. **After docking/undocking:** Call `profile.jump_range()` to report current max jump distance
3. **Fuel tracking:** Call `profile.fuel_budget()` to show remaining range in LY
4. **Route requests:** Route engine internally uses `jump_range_at_temp(safe_jump_temp)` per system; you do not call this directly in chat
5. **Config changes:** Modify profile fields (e.g., `profile.fuel_type = "EU-90"`), then `save_profile(profile)`
6. **Hypothetical planning:** Use `profile.with_overrides(extra_cargo_kg=5_000_000).fuel_budget()` to preview range with more cargo

### Best Practices & Anti-Patterns

- **Always use `_current_mass` property**, never the `current_mass` field (legacy)
- **Never divide or multiply by fuel_quality directly** — use `fuel_budget()` and `fuel_for_distance()` instead
- **Always validate fuel type exists in FUEL_QUALITY** before reporting fuel figures to pilot
- **Red zone check:** Call `can_jump()` after each location change (reported via `system_change` event with `safe_jump_temp`)
- **Cargo impacts range** — remind pilot that loading 5M kg cargo reduces jump distance by ~30% (example for typical ship)
- **Adaptive is a bonus** — upgrading from level 0 to 5 increases range by ~10%; communicate as "improved heat handling"
- **Never modify SHIPS table at runtime** — it is read-only canonical data

### Cross-Module Dependencies

- **`route_engine.py`** — reimplements heat calculation, doesn't call `jump_range_at_temp()`; computes range independently per node
- **`context_builder.py`** — includes `ShipProfile` in context block; formats `range_ly` and `fuel_budget_ly` for Claude prompts
- **`world_api.py`** — provides `safe_jump_temp` per system; route engine combines with ship_profile for per-node planning
- **`main.py`** — `/ship-profile` GET/POST endpoints expose load/save and compute jump range + fuel budget for UI

## Progressive Disclosure

**Read this file by default.** Load deeper files only when told above.

- **Jump formulas + constants** → `/docs/ref/routing.md` § "Ship profile" and "Jump mechanics"
- **Full test coverage** → `/opt/eve-frontier/tests/test_ship_profile.py`
- **Route engine integration** → `/opt/eve-frontier/src/route_engine.py` (uses `jump_range_at_temp()`)
- **API endpoint behavior** → `/opt/eve-frontier/src/endpoints/ship_profile.py` (GET/POST handlers)
