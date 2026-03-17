"""
Test suite for heat classification and planet counting methods.

This module validates:
1. classify_heat() categorizes systems as cool, warm, or hot
2. count_planets() counts planets from planet_ids list
3. is_heat_trap() flags warm/hot systems correctly
4. Edge cases: missing/invalid data, None values, empty lists
"""

import pytest
from src.route_engine import RouteEngine


class TestClassifyHeat:
    """Test classify_heat() method."""

    def test_cool_system_below_70(self):
        """System with safe_jump_temp < 70 should be classified as cool."""
        engine = RouteEngine()
        system = {"safe_jump_temp": 65.0}
        result = engine.classify_heat(system)
        assert result == "cool"

    def test_cool_system_at_boundary(self):
        """System with safe_jump_temp just below 70 should be cool."""
        engine = RouteEngine()
        system = {"safe_jump_temp": 69.9}
        result = engine.classify_heat(system)
        assert result == "cool"

    def test_warm_system_at_70(self):
        """System with safe_jump_temp at exactly 70 should be classified as warm."""
        engine = RouteEngine()
        system = {"safe_jump_temp": 70.0}
        result = engine.classify_heat(system)
        assert result == "warm"

    def test_warm_system_mid_range(self):
        """System with safe_jump_temp between 70-89 should be warm."""
        engine = RouteEngine()
        system = {"safe_jump_temp": 75.5}
        result = engine.classify_heat(system)
        assert result == "warm"

    def test_warm_system_at_89(self):
        """System with safe_jump_temp at 89 should be warm."""
        engine = RouteEngine()
        system = {"safe_jump_temp": 89.0}
        result = engine.classify_heat(system)
        assert result == "warm"

    def test_warm_system_just_below_90(self):
        """System with safe_jump_temp just below 90 should be warm."""
        engine = RouteEngine()
        system = {"safe_jump_temp": 89.9}
        result = engine.classify_heat(system)
        assert result == "warm"

    def test_hot_system_at_90(self):
        """System with safe_jump_temp at exactly 90 should be classified as hot."""
        engine = RouteEngine()
        system = {"safe_jump_temp": 90.0}
        result = engine.classify_heat(system)
        assert result == "hot"

    def test_hot_system_above_90(self):
        """System with safe_jump_temp > 90 should be hot."""
        engine = RouteEngine()
        system = {"safe_jump_temp": 95.5}
        result = engine.classify_heat(system)
        assert result == "hot"

    def test_missing_safe_jump_temp(self):
        """System without safe_jump_temp should default to 0 and be cool."""
        engine = RouteEngine()
        system = {}
        result = engine.classify_heat(system)
        assert result == "cool"

    def test_none_safe_jump_temp(self):
        """System with safe_jump_temp as None should default to 0 and be cool."""
        engine = RouteEngine()
        system = {"safe_jump_temp": None}
        result = engine.classify_heat(system)
        assert result == "cool"

    def test_zero_safe_jump_temp(self):
        """System with safe_jump_temp of 0 should be cool."""
        engine = RouteEngine()
        system = {"safe_jump_temp": 0.0}
        result = engine.classify_heat(system)
        assert result == "cool"

    def test_negative_safe_jump_temp(self):
        """System with negative safe_jump_temp should be cool."""
        engine = RouteEngine()
        system = {"safe_jump_temp": -10.0}
        result = engine.classify_heat(system)
        assert result == "cool"

    def test_very_high_safe_jump_temp(self):
        """System with very high safe_jump_temp should be hot."""
        engine = RouteEngine()
        system = {"safe_jump_temp": 150.0}
        result = engine.classify_heat(system)
        assert result == "hot"


class TestCountPlanets:
    """Test count_planets() method."""

    def test_system_with_planets(self):
        """System with planet_ids should return correct count."""
        engine = RouteEngine()
        system = {"planet_ids": [1, 2, 3, 4, 5]}
        result = engine.count_planets(system)
        assert result == 5

    def test_system_with_single_planet(self):
        """System with one planet should return 1."""
        engine = RouteEngine()
        system = {"planet_ids": [42]}
        result = engine.count_planets(system)
        assert result == 1

    def test_system_with_no_planets(self):
        """System with empty planet_ids should return 0."""
        engine = RouteEngine()
        system = {"planet_ids": []}
        result = engine.count_planets(system)
        assert result == 0

    def test_system_missing_planet_ids(self):
        """System without planet_ids key should return 0."""
        engine = RouteEngine()
        system = {}
        result = engine.count_planets(system)
        assert result == 0

    def test_system_with_none_planet_ids(self):
        """System with planet_ids as None should return 0."""
        engine = RouteEngine()
        system = {"planet_ids": None}
        result = engine.count_planets(system)
        assert result == 0

    def test_system_with_many_planets(self):
        """System with many planets should return correct count."""
        engine = RouteEngine()
        planet_ids = list(range(1, 51))  # 50 planets
        system = {"planet_ids": planet_ids}
        result = engine.count_planets(system)
        assert result == 50

    def test_system_with_string_ids_in_list(self):
        """System with string planet IDs should count them correctly."""
        engine = RouteEngine()
        system = {"planet_ids": ["p1", "p2", "p3"]}
        result = engine.count_planets(system)
        assert result == 3

    def test_system_with_mixed_id_types(self):
        """System with mixed int/string planet IDs should count correctly."""
        engine = RouteEngine()
        system = {"planet_ids": [1, "p2", 3, "p4"]}
        result = engine.count_planets(system)
        assert result == 4


class TestIsHeatTrap:
    """Test is_heat_trap() method."""

    def test_cool_system_not_heat_trap(self):
        """Cool system (< 70°) should not be a heat trap."""
        engine = RouteEngine()
        system = {"safe_jump_temp": 65.0}
        result = engine.is_heat_trap(system)
        assert result is False

    def test_warm_system_is_heat_trap(self):
        """Warm system (70-89°) should be a heat trap."""
        engine = RouteEngine()
        system = {"safe_jump_temp": 75.0}
        result = engine.is_heat_trap(system)
        assert result is True

    def test_hot_system_is_heat_trap(self):
        """Hot system (>= 90°) should be a heat trap."""
        engine = RouteEngine()
        system = {"safe_jump_temp": 95.0}
        result = engine.is_heat_trap(system)
        assert result is True

    def test_system_at_exactly_70_is_heat_trap(self):
        """System at exactly 70° should be a heat trap."""
        engine = RouteEngine()
        system = {"safe_jump_temp": 70.0}
        result = engine.is_heat_trap(system)
        assert result is True

    def test_system_just_below_70_not_heat_trap(self):
        """System just below 70° should not be a heat trap."""
        engine = RouteEngine()
        system = {"safe_jump_temp": 69.9}
        result = engine.is_heat_trap(system)
        assert result is False

    def test_system_at_exactly_90_is_heat_trap(self):
        """System at exactly 90° should be a heat trap."""
        engine = RouteEngine()
        system = {"safe_jump_temp": 90.0}
        result = engine.is_heat_trap(system)
        assert result is True

    def test_missing_safe_jump_temp_not_heat_trap(self):
        """System without safe_jump_temp should not be a heat trap (defaults to 0)."""
        engine = RouteEngine()
        system = {}
        result = engine.is_heat_trap(system)
        assert result is False

    def test_none_safe_jump_temp_not_heat_trap(self):
        """System with safe_jump_temp as None should not be a heat trap."""
        engine = RouteEngine()
        system = {"safe_jump_temp": None}
        result = engine.is_heat_trap(system)
        assert result is False

    def test_zero_safe_jump_temp_not_heat_trap(self):
        """System with safe_jump_temp of 0 should not be a heat trap."""
        engine = RouteEngine()
        system = {"safe_jump_temp": 0.0}
        result = engine.is_heat_trap(system)
        assert result is False

    def test_negative_safe_jump_temp_not_heat_trap(self):
        """System with negative safe_jump_temp should not be a heat trap."""
        engine = RouteEngine()
        system = {"safe_jump_temp": -10.0}
        result = engine.is_heat_trap(system)
        assert result is False


class TestHeatClassificationIntegration:
    """Integration tests combining heat classification with count_planets."""

    def test_warm_system_with_planets(self):
        """Warm system with planets should be flagged as heat trap."""
        engine = RouteEngine()
        system = {
            "safe_jump_temp": 75.5,
            "planet_ids": [1, 2, 3],
            "name": "Test System"
        }
        assert engine.is_heat_trap(system) is True
        assert engine.classify_heat(system) == "warm"
        assert engine.count_planets(system) == 3

    def test_cool_system_with_many_planets(self):
        """Cool system with planets should not be flagged as heat trap."""
        engine = RouteEngine()
        system = {
            "safe_jump_temp": 50.0,
            "planet_ids": list(range(1, 21)),  # 20 planets
            "name": "Temperate System"
        }
        assert engine.is_heat_trap(system) is False
        assert engine.classify_heat(system) == "cool"
        assert engine.count_planets(system) == 20

    def test_hot_system_no_planets(self):
        """Hot system without planets should be flagged as heat trap."""
        engine = RouteEngine()
        system = {
            "safe_jump_temp": 100.0,
            "planet_ids": [],
            "name": "Barren Hot System"
        }
        assert engine.is_heat_trap(system) is True
        assert engine.classify_heat(system) == "hot"
        assert engine.count_planets(system) == 0

    def test_system_missing_all_fields(self):
        """System with all missing fields should default safely."""
        engine = RouteEngine()
        system = {"name": "Unknown System"}
        assert engine.is_heat_trap(system) is False
        assert engine.classify_heat(system) == "cool"
        assert engine.count_planets(system) == 0

    def test_boundary_systems(self):
        """Test boundary conditions for all three methods together."""
        engine = RouteEngine()

        # At the warm/hot boundary (90°)
        system_90 = {"safe_jump_temp": 90.0, "planet_ids": [1]}
        assert engine.classify_heat(system_90) == "hot"
        assert engine.is_heat_trap(system_90) is True
        assert engine.count_planets(system_90) == 1

        # Just below boundary (89.9°)
        system_89_9 = {"safe_jump_temp": 89.9, "planet_ids": [2, 3]}
        assert engine.classify_heat(system_89_9) == "warm"
        assert engine.is_heat_trap(system_89_9) is True
        assert engine.count_planets(system_89_9) == 2

        # At the cool/warm boundary (70°)
        system_70 = {"safe_jump_temp": 70.0, "planet_ids": [4, 5, 6]}
        assert engine.classify_heat(system_70) == "warm"
        assert engine.is_heat_trap(system_70) is True
        assert engine.count_planets(system_70) == 3

        # Just below boundary (69.9°)
        system_69_9 = {"safe_jump_temp": 69.9, "planet_ids": [7]}
        assert engine.classify_heat(system_69_9) == "cool"
        assert engine.is_heat_trap(system_69_9) is False
        assert engine.count_planets(system_69_9) == 1
