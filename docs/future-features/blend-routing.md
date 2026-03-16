# Future Feature: Compare + Blend Routing

**Status:** Deferred — design documented, not implemented
**Discussion date:** 2026-03-16
**Depends on:** Confirmed ship jump cooldown formula from ef-map.com

---

## Problem

The nav computer currently offers two routing modes:
- **Fewest jumps** (`cost_mode=jumps`) — minimizes hop count, may fly long direct jumps
- **Least fuel** (`cost_mode=fuel`) — minimizes total LY flown, may use many gate hops

Neither accounts for **time**. A long fuel-optimal route with 9 gate hops may take longer than a 2-hop direct route if the pilot has to wait for cooldown between each hop. The pilot needs a way to see all three and pick based on their actual situation.

---

## Design: Compare+Blend UI

### Side-by-side display

Show three columns in the route result panel (debug.html and eventually overlay):

```
                     JUMPS-OPT    FUEL-OPT    TIME-OPT
Hops                       2           9           4
Total LY                200.4       154.1       178.2
Fuel used (u)            2161        1662        1921
Est. time (min)           8.2        34.5        12.1
```

The pilot can click any column to activate that route.

### Time cost model

Each hop incurs time from two sources:

1. **Jump cooldown** — after a direct jump, the ship enters a heat-based cooldown period. Proportional to origin system `safe_jump_temp`. Higher temp = ship arrives hotter = longer cooldown before next jump.
   - Approximate formula (unconfirmed): `cooldown_sec ∝ origin_temp` — needs measurement from ef-map.com or in-game testing
   - Gate jumps add minimal heat (model as constant low cooldown, e.g. 30s)

2. **Warp time** — warping to a jump point within the destination system. Not yet modeled; treat as constant per hop until data is available.

### Blend parameter: `gate_penalty_ly`

A single float parameter that represents "how many LY of direct jump is a gate hop worth in time terms". This converts the multi-dimensional cost into a single comparable scalar.

- `gate_penalty_ly = 0`: gates are free (equivalent to `cost_mode=fuel`)
- `gate_penalty_ly = 30`: each gate hop costs as much as 30 LY of direct flight

Sliding this value shifts the optimal route between pure-fuel and pure-jumps. The blend mode picks the `gate_penalty_ly` value that minimizes expected real-world travel time given the ship's heat profile.

---

## Open Questions Before Implementation

1. **Ship jump cooldown formula** — what is the exact cooldown time as a function of origin system `safe_jump_temp`? Check ef-map.com/ai-facts or measure in-game.
2. **Gate transit time** — how long does a gate jump take (undock animation + transit)? Rough constant is sufficient for v1.
3. **Warp speed** — does the game expose warp speed per ship? Or is a constant good enough?
4. **UI placement** — three columns may be cramped in the overlay panel (440px width). Debug.html can show it easily; overlay would need a redesign or a compact summary.

---

## Heat mechanics (player-side)

When a pilot makes a direct jump, their ship accumulates heat. The pilot then lands near the outermost orbital of the destination system. To make the next jump, they either:
- **Wait** for the ship to cool (passive cooldown — duration unclear, likely proportional to heat gained)
- **Warp to a cooler location** (inner system, station, belt) — reduces ambient temp, speeds passive cooling

This means the effective time per hop depends on:
- Origin system temp (heat added on departure)
- Destination system ambient temp (affects cooling rate after arrival)
- Whether the pilot actively warps to a cooler spot between jumps

For a time model, the simplest approximation is: `hop_time = base_jump_sec + cooldown_coeff × origin_temp`. Refine once cooldown formula is confirmed.

---

## Implementation Sketch (when ready)

1. Add `cost_mode="blend"` to `route_engine.py`:
   - Cost per gate hop: `gate_penalty_ly` (new parameter, default ~30.0)
   - Cost per direct hop: `distance_ly`
   - Heuristic: Euclidean distance / effective_range
   - This naturally degrades to `fuel` at `gate_penalty_ly=0` and to `jumps` at `gate_penalty_ly=∞`

2. `POST /route` accepts optional `gate_penalty_ly: float = 30.0` when `cost_mode=blend`

3. Debug.html: add "Compare all" button that fires three parallel `POST /route` calls with `jumps`, `fuel`, and `blend`, then displays results side by side

4. Add `time_estimate_min` field to route result (optional, null if cooldown formula unconfirmed)

---

## Related Files

- `src/route_engine.py` — where `cost_mode` is implemented
- `docs/superpowers/specs/2026-03-15-nav-computer-design.md` — nav computer spec (see Deferred Features section)
- `static/debug.html` — current debug UI; blend routing would be added here first
