# log-agent/tests/test_route_calculator.py
import pytest
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from route_calculator import RouteCalculator, _parse_command

# ---------------------------------------------------------------------------
# Minimal in-memory systems data (4 systems, 3 gate pairs forming a line)
# A(1) --gate-- B(2) --gate-- C(3)    D(4) isolated (no gates)
# B is hot (O-class), C is planet-rich (8 planets)
# ---------------------------------------------------------------------------
_MINIMAL_DATA = {
    "built_at": "2026-03-15T00:00:00Z",
    "systems": {
        "1": {
            "id": 1, "name": "alpha",
            "x": 0, "y": 0, "z": 0,
            "gate_links": [2],
            "star_temperature": 5000.0, "hot_system": False,
            "spectral_class": "G2",
            "planet_count": 3,
            "planet_types": {"Barren Planet": 2, "Gas Giant": 1},
            "lagrange_count": 12,
        },
        "2": {
            "id": 2, "name": "beta",
            "x": 1e17, "y": 0, "z": 0,
            "gate_links": [1, 3],
            "star_temperature": 35000.0, "hot_system": True,
            "spectral_class": "O0",
            "planet_count": 2,
            "planet_types": {"Lava Planet": 2},
            "lagrange_count": 8,
        },
        "3": {
            "id": 3, "name": "gamma",
            "x": 2e17, "y": 0, "z": 0,
            "gate_links": [2],
            "star_temperature": 4000.0, "hot_system": False,
            "spectral_class": "K7",
            "planet_count": 8,
            "planet_types": {
                "Temperate Planet": 2, "Gas Giant": 2, "Water-Oceanic Planet": 1,
                "Barren Planet": 2, "Lava Planet": 1
            },
            "lagrange_count": 40,
        },
        "4": {
            "id": 4, "name": "delta",
            "x": 9e17, "y": 0, "z": 0,
            "gate_links": [],  # isolated
            "star_temperature": 3000.0, "hot_system": False,
            "spectral_class": "M0",
            "planet_count": 1,
            "planet_types": {"Cold Ice Planet": 1},
            "lagrange_count": 4,
        },
    }
}


def make_calc() -> RouteCalculator:
    calc = RouteCalculator("http://localhost:8745", "token")
    calc._load_from_data(_MINIMAL_DATA)
    return calc


# ---------------------------------------------------------------------------
# _parse_command
# ---------------------------------------------------------------------------

def test_parse_command_basic():
    assert _parse_command("/route JITA") == "JITA"

def test_parse_command_lowercase():
    assert _parse_command("/route jita") == "jita"

def test_parse_command_hyphenated():
    assert _parse_command("/route UTR-SN4") == "UTR-SN4"

def test_parse_command_not_a_route():
    assert _parse_command("/help") is None
    assert _parse_command("hello world") is None
    assert _parse_command("/route") is None  # no destination

def test_parse_command_extra_whitespace():
    assert _parse_command("  /route  JITA  ") == "JITA"


# ---------------------------------------------------------------------------
# _load_from_data / name_index
# ---------------------------------------------------------------------------

def test_load_builds_name_index():
    calc = make_calc()
    assert calc.resolve_name("alpha") == 1
    assert calc.resolve_name("BETA") == 2    # case-insensitive
    assert calc.resolve_name("gamma") == 3
    assert calc.resolve_name("unknown") is None


# ---------------------------------------------------------------------------
# BFS routing
# ---------------------------------------------------------------------------

def test_bfs_direct_neighbor():
    calc = make_calc()
    path = calc.bfs(1, 2)
    assert path == [1, 2]

def test_bfs_two_hops():
    calc = make_calc()
    path = calc.bfs(1, 3)
    assert path == [1, 2, 3]

def test_bfs_same_system():
    calc = make_calc()
    assert calc.bfs(1, 1) == [1]

def test_bfs_no_path_isolated_system():
    calc = make_calc()
    assert calc.bfs(1, 4) is None

def test_bfs_reverse_direction():
    calc = make_calc()
    path = calc.bfs(3, 1)
    assert path == [3, 2, 1]


# ---------------------------------------------------------------------------
# route() — full event output
# ---------------------------------------------------------------------------

def test_route_basic_fields():
    calc = make_calc()
    event = calc.route("alpha", "gamma")
    assert event["type"] == "route_planned"
    assert event["origin"] == "alpha"
    assert event["destination"] == "gamma"
    assert event["path"] == ["alpha", "beta", "gamma"]
    assert event["jumps"] == 2
    assert event["gate_hops"] == 2
    assert event["direct_jumps"] == 0

def test_route_hot_system_warning():
    calc = make_calc()
    event = calc.route("alpha", "gamma")
    assert len(event["warnings"]) == 1
    assert "BETA" in event["warnings"][0]
    assert "O0" in event["warnings"][0]
    assert "35000" in event["warnings"][0]

def test_route_no_warning_for_endpoint_hot_system():
    """Hot system at origin or destination is not flagged as a warning."""
    calc = make_calc()
    event = calc.route("alpha", "beta")
    # beta is the destination, not intermediate — no warning
    assert event["warnings"] == []

def test_route_planet_rich_highlight():
    calc = make_calc()
    event = calc.route("alpha", "gamma")
    assert len(event["highlights"]) >= 1
    assert "GAMMA" in event["highlights"][0]
    assert "8 planets" in event["highlights"][0]

def test_route_unknown_origin():
    calc = make_calc()
    event = calc.route("nowhere", "gamma")
    assert event["type"] == "route_planned"
    assert "error" in event
    assert event["path"] == []

def test_route_unknown_destination():
    calc = make_calc()
    event = calc.route("alpha", "void")
    assert "error" in event
    assert event["path"] == []

def test_route_no_gate_path():
    calc = make_calc()
    event = calc.route("alpha", "delta")
    assert event["path"] == []
    assert event["jumps"] == 0
    assert any("No gate route" in w for w in event["warnings"])


# ---------------------------------------------------------------------------
# handle_command
# ---------------------------------------------------------------------------

def test_handle_command_valid():
    calc = make_calc()
    event = calc.handle_command("/route gamma", current_system="alpha")
    assert event is not None
    assert event["type"] == "route_planned"
    assert event["destination"] == "gamma"

def test_handle_command_not_a_route():
    calc = make_calc()
    assert calc.handle_command("hello", current_system="alpha") is None
    assert calc.handle_command("/help", current_system="alpha") is None

def test_handle_command_unknown_current_system():
    calc = make_calc()
    event = calc.handle_command("/route gamma", current_system=None)
    assert event is not None
    assert "error" in event

def test_handle_command_case_insensitive_dest():
    calc = make_calc()
    event = calc.handle_command("/route GAMMA", current_system="alpha")
    assert event["path"] == ["alpha", "beta", "gamma"]
