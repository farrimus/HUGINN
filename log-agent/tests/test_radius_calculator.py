"""
Tests for client-side radius_calculator module.
"""

import pytest
import sys
import os
import json
import tempfile

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from radius_calculator import ClientRadiusCalculator, init_radius_calculator, search


# Test data: minimal systems with coordinates and planets
# 1 LY = 9.461e15 meters, so 1e17 meters ≈ 10.57 LY
_MINIMAL_DATA = {
    "built_at": "2026-03-15T00:00:00Z",
    "systems": {
        "1": {
            "id": 1,
            "name": "Alpha",
            "x": 0,
            "y": 0,
            "z": 0,
            "planet_ids": [101, 102, 103],
            "safe_jump_temp": 30.0
        },
        "2": {
            "id": 2,
            "name": "Beta",
            "x": 1e17,  # ~10.57 LY away
            "y": 0,
            "z": 0,
            "planet_ids": [201, 202],
            "safe_jump_temp": 50.0
        },
        "3": {
            "id": 3,
            "name": "Gamma",
            "x": 2e17,  # ~21.14 LY away
            "y": 0,
            "z": 0,
            "planet_ids": [301, 302, 303, 304, 305, 306, 307, 308],
            "safe_jump_temp": 75.0  # warm
        },
        "4": {
            "id": 4,
            "name": "Delta",
            "x": 3e17,  # ~31.71 LY away
            "y": 0,
            "z": 0,
            "planet_ids": [],
            "safe_jump_temp": 95.0  # hot
        }
    }
}


@pytest.fixture
def temp_systems_file():
    """Create a temporary systems.json file for testing."""
    with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
        json.dump(_MINIMAL_DATA, f)
        temp_path = f.name
    yield temp_path
    os.unlink(temp_path)


class TestClientRadiusCalculator:
    """Test ClientRadiusCalculator class."""

    def test_init_loads_systems(self, temp_systems_file):
        """Test that initialization loads systems from file."""
        calc = ClientRadiusCalculator(temp_systems_file)
        assert len(calc.systems) == 4
        assert "1" in calc.systems
        assert calc.systems["1"]["name"] == "Alpha"

    def test_get_system_by_id(self, temp_systems_file):
        """Test system lookup by ID."""
        calc = ClientRadiusCalculator(temp_systems_file)
        sys = calc.get_system(1)
        assert sys is not None
        assert sys["name"] == "Alpha"

    def test_get_system_by_name_case_insensitive(self, temp_systems_file):
        """Test system lookup by name (case-insensitive)."""
        calc = ClientRadiusCalculator(temp_systems_file)
        sys = calc.get_system("alpha")
        assert sys is not None
        assert sys["id"] == 1

        sys = calc.get_system("ALPHA")
        assert sys is not None
        assert sys["id"] == 1

    def test_get_system_not_found(self, temp_systems_file):
        """Test that nonexistent system returns None."""
        calc = ClientRadiusCalculator(temp_systems_file)
        sys = calc.get_system("NonExistent")
        assert sys is None

    def test_distance_ly(self, temp_systems_file):
        """Test Euclidean distance calculation."""
        calc = ClientRadiusCalculator(temp_systems_file)
        alpha = calc.get_system("alpha")
        beta = calc.get_system("beta")

        dist = calc._distance_ly(alpha, beta)
        # 1e17 meters / 9.461e15 m/LY ≈ 10.57 LY
        assert 10 < dist < 11

    def test_count_planets(self, temp_systems_file):
        """Test planet counting."""
        calc = ClientRadiusCalculator(temp_systems_file)
        alpha = calc.get_system("alpha")
        gamma = calc.get_system("gamma")
        delta = calc.get_system("delta")

        assert calc.count_planets(alpha) == 3
        assert calc.count_planets(gamma) == 8
        assert calc.count_planets(delta) == 0

    def test_classify_heat(self, temp_systems_file):
        """Test heat classification."""
        calc = ClientRadiusCalculator(temp_systems_file)
        alpha = calc.get_system("alpha")
        gamma = calc.get_system("gamma")
        delta = calc.get_system("delta")

        assert calc.classify_heat(alpha) == "cool"
        assert calc.classify_heat(gamma) == "warm"
        assert calc.classify_heat(delta) == "hot"

    def test_is_heat_trap(self, temp_systems_file):
        """Test heat trap detection."""
        calc = ClientRadiusCalculator(temp_systems_file)
        alpha = calc.get_system("alpha")
        gamma = calc.get_system("gamma")
        delta = calc.get_system("delta")

        assert calc.is_heat_trap(alpha) is False
        assert calc.is_heat_trap(gamma) is True
        assert calc.is_heat_trap(delta) is True

    def test_find_systems_within_radius(self, temp_systems_file):
        """Test finding systems within a radius."""
        calc = ClientRadiusCalculator(temp_systems_file)

        # 30 LY should get Alpha, Beta, Gamma (not Delta which is ~31.71 LY)
        results = calc.find_systems_within_radius("Alpha", 30)
        assert len(results) == 3
        assert results[0]["name"] == "Alpha"  # distance_ly == 0
        assert results[0]["distance_ly"] == 0

        # 5 LY should only get Alpha
        results = calc.find_systems_within_radius("Alpha", 5)
        assert len(results) == 1
        assert results[0]["name"] == "Alpha"

    def test_search_planets_filter(self, temp_systems_file):
        """Test search with planets filter."""
        calc = ClientRadiusCalculator(temp_systems_file)

        result = calc.search("Alpha", 30, filters=["planets"])
        assert result["center"] == "Alpha"
        assert result["radius_ly"] == 30
        assert result["total_systems"] == 3  # Alpha, Beta, Gamma (within 30 LY)
        assert "planets" in result["filters"]

        planets_filter = result["filters"]["planets"]
        assert planets_filter["count"] == 3  # Alpha, Beta, Gamma have planets
        assert planets_filter["systems"][0]["name"] == "Gamma"  # Most planets first
        assert planets_filter["systems"][0]["planets"] == 8

    def test_search_heat_filter(self, temp_systems_file):
        """Test search with heat filter."""
        calc = ClientRadiusCalculator(temp_systems_file)

        result = calc.search("Alpha", 30, filters=["heat"])
        assert "heat" in result["filters"]

        heat_filter = result["filters"]["heat"]
        assert heat_filter["count"] == 1  # Only Gamma is warm/hot within 30 LY
        assert heat_filter["systems"][0]["name"] == "Gamma"
        assert heat_filter["systems"][0]["safe_jump_temp"] == 75.0

    def test_search_multiple_filters(self, temp_systems_file):
        """Test search with multiple filters."""
        calc = ClientRadiusCalculator(temp_systems_file)

        result = calc.search("Alpha", 20, filters=["planets", "heat"])
        assert "planets" in result["filters"]
        assert "heat" in result["filters"]

    def test_search_empty_radius(self, temp_systems_file):
        """Test search with only center system (very small radius)."""
        calc = ClientRadiusCalculator(temp_systems_file)

        # Radius of 0.5 LY includes only Alpha (at distance 0)
        result = calc.search("Alpha", 0.5)
        assert result["total_systems"] == 1
        assert result["filters"] == {}

    def test_search_nonexistent_center(self, temp_systems_file):
        """Test search with nonexistent center system."""
        calc = ClientRadiusCalculator(temp_systems_file)

        result = calc.search("NonExistent", 100)
        assert result["total_systems"] == 0
        assert result["center"] == "NonExistent"

    def test_search_skip_heat_traps(self, temp_systems_file):
        """Test search with skip_heat_traps option."""
        calc = ClientRadiusCalculator(temp_systems_file)

        result = calc.search("Alpha", 30, skip_heat_traps=True)
        assert result["total_systems"] == 2  # Only Alpha and Beta (cool/neutral)

    def test_module_functions_require_init(self):
        """Test that module-level search() requires init_radius_calculator()."""
        # Clear any existing instance
        import radius_calculator
        radius_calculator._radius_calculator = None

        with pytest.raises(RuntimeError):
            search("Alpha", 100)

    def test_module_level_init_and_search(self, temp_systems_file):
        """Test module-level init_radius_calculator() and search()."""
        import radius_calculator

        # Initialize with custom path
        calc = init_radius_calculator(temp_systems_file)
        assert calc is not None
        assert len(calc.systems) == 4

        # Module-level search should work
        result = search("Alpha", 30, filters=["planets"])
        assert result["center"] == "Alpha"
        assert "planets" in result["filters"]


def test_systems_json_real_data():
    """Test that radius calculator can load actual systems.json file."""
    log_agent_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    systems_path = os.path.normpath(
        os.path.join(log_agent_dir, "..", "data", "systems.json")
    )

    if not os.path.exists(systems_path):
        pytest.skip(f"systems.json not found at {systems_path}")

    calc = ClientRadiusCalculator(systems_path)
    assert len(calc.systems) > 0

    # Verify structure
    for system_id, system_data in list(calc.systems.items())[:5]:
        assert isinstance(system_data, dict)
        assert "name" in system_data
        assert "x" in system_data
        assert "y" in system_data
        assert "z" in system_data
