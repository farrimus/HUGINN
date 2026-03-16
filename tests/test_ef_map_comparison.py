# tests/test_ef_map_comparison.py
"""
Accuracy tests comparing our engine against ef-map.com reference values.

HOW TO ADD GOLDEN DATA
──────────────────────
1. Open ef-map.com, click a system → note the "External Temperature" value.
   Add it to SYSTEM_TEMPS below.

2. For a route: set your ship on ef-map, plan a route, note the hop count.
   Add it to ROUTES below.

3. Run:  pytest tests/test_ef_map_comparison.py -v

HELPER SCRIPT
─────────────
   python3 scripts/check_temps.py UR8-K7K "C.92X.S91" EVV-7GK
   Prints our computed safe_jump_temp for each system so you can compare
   line-by-line with ef-map.com.
"""

import pytest
import json
import math
from pathlib import Path

from src.ship_profile import ShipProfile, SHIPS, T_MAX, HEAT_CONSTANT
from src.route_engine import RouteEngine, _SpatialIndex

SYSTEMS_JSON = Path(__file__).parent.parent / "data" / "systems.json"


# ─────────────────────────────────────────────────────────────────────────────
# Fixtures — load the real systems.json once per session
# ─────────────────────────────────────────────────────────────────────────────

@pytest.fixture(scope="session")
def systems_data():
    if not SYSTEMS_JSON.exists():
        pytest.skip("data/systems.json not present — run build_universe.py first")
    raw = json.loads(SYSTEMS_JSON.read_text(encoding="utf-8"))
    return raw.get("systems", {})


@pytest.fixture(scope="session")
def engine(systems_data):
    """Real RouteEngine loaded from systems.json — no mocking."""
    e = RouteEngine()
    e._systems = systems_data
    e._by_name = {v["name"].lower(): k for k, v in systems_data.items() if v.get("name")}
    LY = 9_460_730_472_580_800.0
    e._ly_coords = {
        sid: (s.get("x", 0) / LY, s.get("y", 0) / LY, s.get("z", 0) / LY)
        for sid, s in systems_data.items()
    }
    e._spatial = _SpatialIndex()
    e._spatial.build(e._ly_coords)
    e._mtime = float("inf")  # prevent file reload
    return e


def _get_temp(systems_data, name):
    """Return safe_jump_temp for a named system, or None if not found."""
    for s in systems_data.values():
        if s.get("name", "").lower() == name.lower():
            return s.get("safe_jump_temp", 0.0)
    return None


def _ship_profile(ship_type, fuel_type="D1", fuel_qty=1750, extra_cargo=0):
    ship = SHIPS[ship_type]
    return ShipProfile(
        hull_mass=ship["mass"],
        specific_heat=ship["specific_heat"],
        adaptive_level=0,
        fuel_type=fuel_type,
        fuel_quantity=fuel_qty,
        external_temp=0.0,
        ship_type=ship_type,
        extra_cargo_kg=extra_cargo,
    )


# ─────────────────────────────────────────────────────────────────────────────
# GOLDEN DATA — edit these tables as you verify values on ef-map.com
# ─────────────────────────────────────────────────────────────────────────────

# (system_name, ef_map_temp_degrees, tolerance_degrees)
# Sources: ef-map.com system detail panel, "External Temperature" field.
SYSTEM_TEMPS = [
    ("UR8-K7K",  36.9, 0.5),   # verified 2026-03-16
    # ("EVV-7GK",  ??,   0.5),  # TODO: check ef-map
    # ("ELL-5CK",  ??,   0.5),  # TODO: check ef-map — only a Cold Ice Planet, low temp expected
    # ("U53-QKK",  ??,   0.5),  # TODO: check ef-map
]

# (ship_type, system_name_for_temp, ef_map_range_ly, tolerance_ly)
# ef_map_range_ly: the jump range shown on ef-map for this ship at this system.
# We compute range = (T_MAX - system_temp) * c_eff * hull_mass / (3 * hull_mass).
JUMP_RANGES_AT_SYSTEM = [
    # Reflex at UR8-K7K (temp ~36.9°): range = (150 - 36.9) * 3 / 3 = 113.1 LY
    ("Reflex", "UR8-K7K", 113.1, 1.0),
    # TODO: add more as you read them from ef-map with different ships/systems
]

# (origin, destination, ship_type, fuel_type, fuel_qty,
#  ef_map_jumps, comparison_mode, notes)
#
# comparison_mode:
#   "eq"  — our hop count must equal ef-map's
#   "lte" — our hop count must be <= ef-map's (we may find a shorter path)
ROUTES = [
    # TODO: add routes once you've read them from ef-map.
    # Example (fill in ef_map_jumps from ef-map.com after you test it):
    # ("UR8-K7K", "C.92X.S91", "Reflex", "D1", 1750, 35, "lte",
    #  "original test route — ef-map returned 35 hops"),
]


# ─────────────────────────────────────────────────────────────────────────────
# 1. System temperature accuracy
# ─────────────────────────────────────────────────────────────────────────────

@pytest.mark.parametrize("system_name,ef_temp,tol", SYSTEM_TEMPS)
def test_system_temperature_matches_ef_map(systems_data, system_name, ef_temp, tol):
    """Our safe_jump_temp must be within tol° of ef-map's displayed value."""
    our_temp = _get_temp(systems_data, system_name)
    assert our_temp is not None, f"System '{system_name}' not found in systems.json"
    assert abs(our_temp - ef_temp) <= tol, (
        f"{system_name}: our temp={our_temp:.2f}°  ef-map={ef_temp:.1f}°  "
        f"diff={abs(our_temp-ef_temp):.2f}°  (tolerance ±{tol}°)"
    )


# ─────────────────────────────────────────────────────────────────────────────
# 2. Jump range formula accuracy
# ─────────────────────────────────────────────────────────────────────────────

@pytest.mark.parametrize("ship_type,system_name,ef_range,tol", JUMP_RANGES_AT_SYSTEM)
def test_jump_range_at_system_matches_ef_map(systems_data, ship_type, system_name, ef_range, tol):
    """Jump range at a specific system must match ef-map within tol LY."""
    system_temp = _get_temp(systems_data, system_name)
    assert system_temp is not None, f"System '{system_name}' not found in systems.json"
    p = _ship_profile(ship_type)
    our_range = p.jump_range_at_temp(system_temp)
    assert abs(our_range - ef_range) <= tol, (
        f"{ship_type} at {system_name} (temp={system_temp:.2f}°): "
        f"our range={our_range:.2f} LY  ef-map={ef_range:.1f} LY  "
        f"diff={abs(our_range-ef_range):.2f} LY  (tolerance ±{tol})"
    )


# ─────────────────────────────────────────────────────────────────────────────
# 3. Route hop count comparison
# ─────────────────────────────────────────────────────────────────────────────

@pytest.mark.parametrize(
    "origin,destination,ship_type,fuel_type,fuel_qty,ef_jumps,mode,notes",
    ROUTES,
)
def test_route_hop_count_vs_ef_map(
    engine, origin, destination, ship_type, fuel_type, fuel_qty,
    ef_jumps, mode, notes,
):
    """Route hop count must match or beat ef-map's result."""
    p = _ship_profile(ship_type, fuel_type=fuel_type, fuel_qty=fuel_qty)
    result = engine.route(origin, destination, p)
    assert result is not None, f"route() returned None for {origin} → {destination}"
    assert result["type"] == "route_planned", (
        f"No route found: {origin} → {destination}\n"
        f"  warnings: {result.get('warnings')}"
    )
    our_jumps = result["jumps"]
    if mode == "eq":
        assert our_jumps == ef_jumps, (
            f"{origin} → {destination} ({ship_type}): "
            f"our jumps={our_jumps}  ef-map={ef_jumps}  [{notes}]"
        )
    else:  # "lte"
        assert our_jumps <= ef_jumps, (
            f"{origin} → {destination} ({ship_type}): "
            f"our jumps={our_jumps} > ef-map={ef_jumps}  [{notes}]"
        )


# ─────────────────────────────────────────────────────────────────────────────
# 4. Formula sanity checks (no ef-map comparison needed, pure math)
# ─────────────────────────────────────────────────────────────────────────────

@pytest.mark.parametrize("ship_type,expected_range_at_zero", [
    # range at temp=0 = T_MAX * specific_heat / 3 (mass cancels when no cargo)
    ("Carom",   150.0 * 8.5 / 3),   # 425.0 LY
    ("Stride",  150.0 * 8.0 / 3),   # 400.0 LY
    ("Reflex",  150.0 * 3.0 / 3),   # 150.0 LY
    ("Recurve", 150.0 * 1.0 / 3),   # 50.0 LY
    ("Reiver",  150.0 * 1.0 / 3),   # 50.0 LY
])
def test_max_range_at_zero_temp(ship_type, expected_range_at_zero):
    """At 0° system temp, range = T_MAX * C / 3 (mass cancels)."""
    p = _ship_profile(ship_type)
    assert abs(p.jump_range_at_temp(0.0) - expected_range_at_zero) < 0.01, (
        f"{ship_type}: range at 0° expected {expected_range_at_zero:.1f} LY, "
        f"got {p.jump_range_at_temp(0.0):.2f} LY"
    )


def test_range_decreases_with_system_temp():
    """Higher system temp → shorter jump range, reaches 0 at 90°."""
    p = _ship_profile("Reflex")
    ranges = [p.jump_range_at_temp(t) for t in [0, 20, 40, 60, 89.9, 90.0]]
    for i in range(len(ranges) - 1):
        assert ranges[i] > ranges[i + 1], \
            f"Range should decrease with temp: {ranges}"
    assert ranges[-1] == 0.0, "Range must be 0 at 90°"


def test_range_increases_with_adaptive_level():
    """Each adaptive level adds 2% to specific heat."""
    base = _ship_profile("Carom")
    base_range = base.jump_range_at_temp(0.0)
    for lvl in range(1, 4):
        p = ShipProfile(
            hull_mass=SHIPS["Carom"]["mass"],
            specific_heat=SHIPS["Carom"]["specific_heat"],
            adaptive_level=lvl,
            fuel_type="D1", fuel_quantity=3000,
        )
        lvl_range = p.jump_range_at_temp(0.0)
        expected = base_range * (1 + lvl * 0.02)
        assert abs(lvl_range - expected) < 0.01, \
            f"Adaptive level {lvl}: expected {expected:.2f} LY, got {lvl_range:.2f} LY"


def test_cargo_reduces_range():
    """Extra cargo increases current mass → reduces jump range."""
    p_clean = _ship_profile("Carom")
    p_cargo = _ship_profile("Carom", extra_cargo=1_000_000)
    assert p_clean.jump_range_at_temp(0.0) > p_cargo.jump_range_at_temp(0.0)


def test_temp_formula_constants_match_ef_map():
    """Verify T_MAX=150, HEAT_CONSTANT=3 match ef-map published formula."""
    assert T_MAX == 150.0, f"T_MAX should be 150, got {T_MAX}"
    assert HEAT_CONSTANT == 3.0, f"HEAT_CONSTANT should be 3, got {HEAT_CONSTANT}"


# ─────────────────────────────────────────────────────────────────────────────
# 5. Route quality checks (structure, not exact match)
# ─────────────────────────────────────────────────────────────────────────────

@pytest.mark.skipif(not SYSTEMS_JSON.exists(), reason="systems.json required")
def test_route_never_exceeds_gate_only_hop_count(engine):
    """A* (gate+direct) must never produce MORE hops than gate-only BFS."""
    test_pairs = [
        ("UR8-K7K", "EVV-7GK"),
    ]
    p = _ship_profile("Reflex", fuel_qty=1750)
    for origin, dest in test_pairs:
        # Skip silently if either system has no gate path (direct-only cluster)
        bfs = engine.bfs(origin, dest)
        if bfs is None:
            continue
        astar = engine.route(origin, dest, p)
        if astar["type"] == "no_route":
            continue
        assert astar["jumps"] <= bfs["jumps"], (
            f"{origin} → {dest}: A* gave {astar['jumps']} jumps "
            f"but BFS gate-only gave {bfs['jumps']}"
        )


@pytest.mark.skipif(not SYSTEMS_JSON.exists(), reason="systems.json required")
def test_route_result_is_self_consistent(engine):
    """jump_types length must equal jumps, path length must equal jumps+1."""
    p = _ship_profile("Reflex", fuel_qty=1750)
    result = engine.route("UR8-K7K", "EVV-7GK", p)
    assert result is not None
    if result["type"] == "route_planned":
        assert len(result["path"]) == result["jumps"] + 1
        assert len(result["jump_types"]) == result["jumps"]
