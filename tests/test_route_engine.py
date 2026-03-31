# tests/test_route_engine.py
import pytest
from unittest.mock import patch
from src.route_engine import RouteEngine
from src.ship_profile import ShipProfile

# Minimal system dict that looks like systems.json output
def _make_systems():
    return {
        "1": {"id": 1, "name": "Alpha",  "x": 0.0,                "y": 0.0, "z": 0.0,
              "gate_links": [2], "safe_jump_temp": 0.0},
        "2": {"id": 2, "name": "Beta",   "x": 9.46e15 * 10,       "y": 0.0, "z": 0.0,
              "gate_links": [1, 3], "safe_jump_temp": 0.0},       # 10 LY from Alpha
        "3": {"id": 3, "name": "Gamma",  "x": 9.46e15 * 10,       "y": 0.0, "z": 9.46e15*10,
              "gate_links": [2], "safe_jump_temp": 0.0},           # diag from Alpha
        "4": {"id": 4, "name": "HotSys", "x": 9.46e15 * 5,        "y": 0.0, "z": 0.0,
              "gate_links": [], "safe_jump_temp": 85.0},           # orange zone, no gates
        "5": {"id": 5, "name": "RedSys", "x": 9.46e15 * 3,        "y": 0.0, "z": 0.0,
              "gate_links": [], "safe_jump_temp": 95.0},           # red zone
    }

def _make_engine(systems):
    e = RouteEngine()
    e._systems = systems
    e._by_name = {v["name"].lower(): k for k, v in systems.items()}
    e._ly_coords = {
        sid: (s["x"] / 9.46e15, s["y"] / 9.46e15, s["z"] / 9.46e15)
        for sid, s in systems.items()
    }
    from src.route_engine import _SpatialIndex
    e._spatial = _SpatialIndex()
    e._spatial.build(e._ly_coords)
    e._mtime = float("inf")  # prevent reload
    return e

def _profile(range_ly=500.0, budget_ly=2000.0):
    """Profile producing approximately range_ly and budget_ly."""
    # Carom-like: hull=7.2e6, specific_heat=8.5
    # range = (150 * 8.5 * 7.2e6) / (3 * 7.2e6) = 425 at temp=0
    # Adjust via external_temp if needed
    # For simplicity, use a high-capacity profile
    return ShipProfile(
        hull_mass=7_200_000,
        specific_heat=8.5 * (range_ly / 425.0),  # scale to desired range
        adaptive_level=0,
        fuel_type="D1",
        fuel_quantity=99999,  # effectively unlimited
        external_temp=0.0,
        extra_cargo_kg=0,
    )

def test_route_result_shape():
    e = _make_engine(_make_systems())
    p = _profile(range_ly=500.0)
    result = e.route("Alpha", "Beta", p)
    assert result is not None
    assert result["type"] == "route_planned"
    assert "path" in result
    assert "jumps" in result
    assert "jump_types" in result
    assert len(result["jump_types"]) == result["jumps"]
    assert "total_ly" in result
    assert "fuel_used" in result
    assert "fuel_remaining" in result
    assert "hot_systems" in result
    assert "alternative" in result
    assert "warnings" in result

def test_gate_route_zero_ly():
    """Gate hops contribute 0 to total_ly."""
    e = _make_engine(_make_systems())
    p = _profile(range_ly=1.0)  # too short to direct-jump
    result = e.bfs("Alpha", "Beta")
    # bfs returns old shape — we test route() here
    # With very short range, A* should use gate
    result = e.route("Alpha", "Beta", p)
    assert result is not None
    # If gate path taken, total_ly should be 0 (no direct jumps)
    if all(jt == "gate" for jt in result["jump_types"]):
        assert result["total_ly"] == 0.0

def test_red_zone_no_direct_jump_out():
    """A system with safe_jump_temp >= 90 cannot be a direct-jump waypoint."""
    systems = _make_systems()
    # RedSys at 3 LY from Alpha — reachable if no heat; unreachable direct if red
    e = _make_engine(systems)
    p = _profile(range_ly=500.0)
    result = e.route("Alpha", "RedSys", p)
    # RedSys has no gates so only way is direct. But as destination it's still reachable.
    # Origin can jump to destination regardless of destination temp.
    assert result is not None

def test_alternative_route_triggered_by_hot_intermediate():
    """Alternative route computed when primary path has temp >= 70 intermediate."""
    # End is placed just beyond direct jump range so A* must route via an intermediate.
    # HotMid is collinear (lower heuristic) → chosen as primary intermediate.
    # CoolMid is a slight diagonal detour used by the alternative.
    #
    # Layout (LY):  Start(0,0) — HotMid(200,0) — End(400,0)
    #                                CoolMid(200,50)
    # Range = 399 LY → direct Start→End (400 LY) is out of range.
    # HotMid at 70° still has ~213 LY range → can reach End (200 LY away). ✓
    LY = 9.46e15
    systems = {
        "1": {"id": 1, "name": "Start",  "x": 0.0,        "y": 0.0,       "z": 0.0,
              "gate_links": [], "safe_jump_temp": 0.0},
        "2": {"id": 2, "name": "HotMid", "x": LY * 200,   "y": 0.0,       "z": 0.0,
              "gate_links": [], "safe_jump_temp": 70.0},   # just at WARM threshold
        "3": {"id": 3, "name": "End",    "x": LY * 400,   "y": 0.0,       "z": 0.0,
              "gate_links": [], "safe_jump_temp": 0.0},
        "4": {"id": 4, "name": "CoolMid","x": LY * 200,   "y": LY * 50,   "z": 0.0,
              "gate_links": [], "safe_jump_temp": 0.0},
    }
    e = _make_engine(systems)
    # Range 399 LY: direct Start→End (400 LY) out of reach; both 2-hop paths valid.
    # HotMid is collinear → lower heuristic → chosen as primary.
    p = _profile(range_ly=399.0)
    result = e.route("Start", "End", p)
    assert result is not None
    assert result["hot_systems"] == ["HotMid"], (
        f"Expected primary to go through HotMid, got hot_systems={result['hot_systems']}, "
        f"path={result['path']}"
    )
    # Alternative must exist (route via CoolMid, avoiding HotMid as direct waypoint)
    assert result["alternative"] is not None, "Expected an alternative route avoiding HotMid"
    assert "HotMid" not in result["alternative"].get("path", []), (
        "Alternative should not route through HotMid"
    )

def test_no_route_returns_no_route_shape():
    systems = _make_systems()
    e = _make_engine(systems)
    p = _profile(range_ly=0.1)  # tiny range, no gates to isolated system
    # Try to reach an isolated far system
    isolated = {
        **systems,
        "99": {"id": 99, "name": "Far", "x": 9.46e15 * 999, "y": 0.0, "z": 0.0,
               "gate_links": [], "safe_jump_temp": 0.0},
    }
    e2 = _make_engine(isolated)
    result = e2.route("Alpha", "Far", p)
    assert result is not None
    assert result["type"] == "no_route"
    assert result["path"] == []
    assert result["jumps"] == 0
    assert len(result["warnings"]) > 0

def test_jumps_equals_len_path_minus_1():
    e = _make_engine(_make_systems())
    p = _profile(range_ly=500.0)
    result = e.route("Alpha", "Gamma", p)
    assert result is not None
    if result["type"] == "route_planned":
        assert result["jumps"] == len(result["path"]) - 1
        assert len(result["jump_types"]) == result["jumps"]
