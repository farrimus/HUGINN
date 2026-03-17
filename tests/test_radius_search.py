"""
Test suite for RadiusSearch class.

Tests verify:
1. System loading from systems.json
2. Structure locations empty on init
3. Case-insensitive system name lookup
4. System ID lookup
"""

import os
import json
import pytest
import sys
import time
from unittest.mock import AsyncMock

# Add project root to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from src.radius_search import RadiusSearch


class TestRadiusSearchInit:
    """Test RadiusSearch initialization."""

    def test_init_default_paths(self):
        """RadiusSearch should initialize with default paths."""
        searcher = RadiusSearch()
        assert searcher is not None
        assert searcher.systems_path is not None
        assert searcher.structure_locations_path is not None
        assert 'systems.json' in searcher.systems_path
        assert 'structure_locations.json' in searcher.structure_locations_path

    def test_init_custom_paths(self):
        """RadiusSearch should accept custom paths."""
        custom_systems = "/custom/path/systems.json"
        custom_structures = "/custom/path/structure_locations.json"
        searcher = RadiusSearch(
            systems_path=custom_systems,
            structure_locations_path=custom_structures
        )
        assert searcher.systems_path == custom_systems
        assert searcher.structure_locations_path == custom_structures

    def test_init_loads_systems(self):
        """RadiusSearch should load systems on init."""
        searcher = RadiusSearch()
        # Systems should be loaded from systems.json
        assert isinstance(searcher.systems, dict)
        assert len(searcher.systems) > 0, "systems dict should be populated from systems.json"

    def test_init_structure_locations_empty(self):
        """RadiusSearch should initialize structure_locations as empty dict."""
        searcher = RadiusSearch()
        assert isinstance(searcher.structure_locations, dict)
        assert len(searcher.structure_locations) == 0, "structure_locations should be empty on init"


class TestGetSystem:
    """Test get_system method."""

    def test_get_system_by_name_case_insensitive(self):
        """get_system should find system by name (case-insensitive)."""
        searcher = RadiusSearch()
        # UR8-K7K is a known system in systems.json
        result = searcher.get_system("UR8-K7K")
        assert result is not None, "Should find UR8-K7K by exact name"
        assert result['name'] == "UR8-K7K"

    def test_get_system_by_name_lowercase(self):
        """get_system should find system by lowercase name."""
        searcher = RadiusSearch()
        result = searcher.get_system("ur8-k7k")
        assert result is not None, "Should find system by lowercase name"
        assert result['name'] == "UR8-K7K"

    def test_get_system_by_name_uppercase(self):
        """get_system should find system by uppercase name."""
        searcher = RadiusSearch()
        result = searcher.get_system("UR8-K7K")
        assert result is not None, "Should find system by any case"

    def test_get_system_by_id(self):
        """get_system should find system by ID."""
        searcher = RadiusSearch()
        # Get a system ID from the loaded systems
        if searcher.systems:
            system_id = next(iter(searcher.systems.keys()))
            result = searcher.get_system(system_id)
            assert result is not None, f"Should find system by ID {system_id}"
            assert result['id'] == int(system_id)

    def test_get_system_not_found(self):
        """get_system should return None for non-existent system."""
        searcher = RadiusSearch()
        result = searcher.get_system("NONEXISTENT-SYSTEM-XYZ")
        assert result is None

    def test_get_system_name_key(self):
        """get_system result should have 'name' key."""
        searcher = RadiusSearch()
        result = searcher.get_system("UR8-K7K")
        if result is not None:
            assert 'name' in result, "System dict should have 'name' key"


class TestSystemsLoading:
    """Test systems loading functionality."""

    def test_systems_dict_populated(self):
        """systems dict should be populated after init."""
        searcher = RadiusSearch()
        assert len(searcher.systems) > 0
        # Check structure of loaded systems
        for system_id, system_data in list(searcher.systems.items())[:1]:
            assert isinstance(system_data, dict)
            assert 'name' in system_data
            assert 'id' in system_data

    def test_systems_contain_ur8_k7k(self):
        """systems should contain UR8-K7K system."""
        searcher = RadiusSearch()
        found = False
        for system_data in searcher.systems.values():
            if isinstance(system_data, dict) and system_data.get('name') == 'UR8-K7K':
                found = True
                break
        assert found, "systems should contain UR8-K7K"


class TestStructureLocationsFile:
    """Test structure_locations.json file integrity."""

    def test_structure_locations_file_exists(self):
        """structure_locations.json should exist."""
        data_dir = os.path.join(os.path.dirname(__file__), '..', 'data')
        file_path = os.path.join(data_dir, 'structure_locations.json')
        assert os.path.exists(file_path), f"File not found: {file_path}"

    def test_structure_locations_valid_json(self):
        """structure_locations.json should contain valid JSON."""
        data_dir = os.path.join(os.path.dirname(__file__), '..', 'data')
        file_path = os.path.join(data_dir, 'structure_locations.json')
        with open(file_path, 'r') as f:
            data = json.load(f)
        assert isinstance(data, dict)

    def test_structure_locations_has_required_keys(self):
        """structure_locations.json should have structure_locations and built_at keys."""
        data_dir = os.path.join(os.path.dirname(__file__), '..', 'data')
        file_path = os.path.join(data_dir, 'structure_locations.json')
        with open(file_path, 'r') as f:
            data = json.load(f)
        assert 'structure_locations' in data, "Missing 'structure_locations' key"
        assert 'built_at' in data, "Missing 'built_at' key"
        assert isinstance(data['structure_locations'], dict), "'structure_locations' should be a dict"

    def test_structure_locations_key_correct(self):
        """structure_locations.json key should be 'structure_locations' not 'structures'."""
        data_dir = os.path.join(os.path.dirname(__file__), '..', 'data')
        file_path = os.path.join(data_dir, 'structure_locations.json')
        with open(file_path, 'r') as f:
            data = json.load(f)
        # Should have 'structure_locations' key
        assert 'structure_locations' in data
        # Should NOT have 'structures' key (old name)
        assert 'structures' not in data, "Should use 'structure_locations' key, not 'structures'"

    def test_structure_locations_initial_empty(self):
        """structure_locations.json structure_locations should be initially empty."""
        data_dir = os.path.join(os.path.dirname(__file__), '..', 'data')
        file_path = os.path.join(data_dir, 'structure_locations.json')
        with open(file_path, 'r') as f:
            data = json.load(f)
        assert len(data['structure_locations']) == 0


class TestDistanceCalculation:
    """Test _distance_ly method for spatial distance calculation."""

    def test_distance_ly_same_point(self):
        """Distance between same point should be 0."""
        searcher = RadiusSearch()
        sys_a = {"x": 0, "y": 0, "z": 0}
        sys_b = {"x": 0, "y": 0, "z": 0}
        distance = searcher._distance_ly(sys_a, sys_b)
        assert distance == 0.0

    def test_distance_ly_simple_cartesian(self):
        """Test distance with simple 3-4-5 Pythagorean triple (should give ~5 LY)."""
        searcher = RadiusSearch()
        # In meters: (3*9.461e15)^2 + (4*9.461e15)^2 + 0^2 = (5*9.461e15)^2
        # So 3-4-5 in LY coordinates should yield 5 LY
        sys_a = {"x": 0, "y": 0, "z": 0}
        sys_b = {"x": 3 * 9.461e15, "y": 4 * 9.461e15, "z": 0}
        distance = searcher._distance_ly(sys_a, sys_b)
        assert abs(distance - 5.0) < 0.001, f"Expected ~5.0 LY, got {distance}"

    def test_distance_ly_missing_coordinates_defaults_to_zero(self):
        """Missing x, y, z should default to 0."""
        searcher = RadiusSearch()
        sys_a = {"name": "System A"}  # No coordinates
        sys_b = {"x": 1e16, "y": 0, "z": 0}
        distance = searcher._distance_ly(sys_a, sys_b)
        # Should treat missing coords as 0
        assert distance > 0

    def test_distance_ly_symmetry(self):
        """Distance from A to B should equal distance from B to A."""
        searcher = RadiusSearch()
        sys_a = {"x": 1e16, "y": 2e16, "z": 3e16}
        sys_b = {"x": 4e16, "y": 5e16, "z": 6e16}
        dist_ab = searcher._distance_ly(sys_a, sys_b)
        dist_ba = searcher._distance_ly(sys_b, sys_a)
        assert abs(dist_ab - dist_ba) < 0.001

    def test_distance_ly_positive(self):
        """Distance should always be non-negative."""
        searcher = RadiusSearch()
        sys_a = {"x": -1e16, "y": -2e16, "z": -3e16}
        sys_b = {"x": 1e16, "y": 2e16, "z": 3e16}
        distance = searcher._distance_ly(sys_a, sys_b)
        assert distance >= 0


class TestRadiusFiltering:
    """Test find_systems_within_radius method."""

    def test_find_systems_within_radius_nonexistent_center(self):
        """Should return empty list for non-existent center system."""
        searcher = RadiusSearch()
        results = searcher.find_systems_within_radius("NONEXISTENT-SYSTEM-XYZ", 100.0)
        assert results == []

    def test_find_systems_within_radius_actual_system(self):
        """Should find systems within radius of UR8-K7K."""
        searcher = RadiusSearch()
        # Find systems within 100 LY of UR8-K7K
        results = searcher.find_systems_within_radius("UR8-K7K", 100.0)
        assert isinstance(results, list)
        # Should find at least the center system itself (or nearby systems)
        # Check all results have distance_ly field and are within radius
        for system in results:
            assert "distance_ly" in system, "Results should have distance_ly field"
            assert system["distance_ly"] <= 100.0, f"System distance {system['distance_ly']} exceeds radius 100.0"

    def test_find_systems_within_radius_sorted_by_distance(self):
        """Results should be sorted by distance (closest first)."""
        searcher = RadiusSearch()
        results = searcher.find_systems_within_radius("UR8-K7K", 500.0)
        if len(results) > 1:
            # Check that distances are in ascending order
            distances = [s["distance_ly"] for s in results]
            assert distances == sorted(distances), "Results should be sorted by distance"

    def test_find_systems_within_radius_includes_center(self):
        """Results should include center system (with distance 0)."""
        searcher = RadiusSearch()
        results = searcher.find_systems_within_radius("UR8-K7K", 100.0)
        # Center system should be first with distance 0
        if results:
            assert results[0]["distance_ly"] == 0.0 or results[0]["name"] == "UR8-K7K"

    def test_find_systems_within_radius_excludes_systems_without_coordinates(self):
        """Should filter out systems without x, y, z coordinates."""
        searcher = RadiusSearch()
        # This test verifies the filtering logic
        results = searcher.find_systems_within_radius("UR8-K7K", 1000.0)
        for system in results:
            # All returned systems should have valid coordinates
            assert "x" in system and "y" in system and "z" in system, \
                f"System {system.get('name')} missing coordinates"

    def test_find_systems_within_radius_zero_radius(self):
        """With radius 0, should only return center system (if it exists)."""
        searcher = RadiusSearch()
        results = searcher.find_systems_within_radius("UR8-K7K", 0.0)
        # With radius 0, should get 0 or 1 result (just center system if it has coords)
        assert len(results) <= 1
        if len(results) == 1:
            assert results[0]["name"] == "UR8-K7K"
            assert results[0]["distance_ly"] == 0.0

    def test_find_systems_within_radius_large_radius(self):
        """Should find multiple systems within large radius."""
        searcher = RadiusSearch()
        results = searcher.find_systems_within_radius("UR8-K7K", 10000.0)
        # With a large radius, should find multiple systems
        assert len(results) > 1, "Should find multiple systems within large radius"

    def test_find_systems_within_radius_result_contains_all_fields(self):
        """Results should include all original system fields plus distance_ly."""
        searcher = RadiusSearch()
        results = searcher.find_systems_within_radius("UR8-K7K", 100.0)
        if results:
            # Each result should have distance_ly plus original fields
            result = results[0]
            assert "distance_ly" in result
            assert "name" in result or "id" in result
            # distance_ly should be a float
            assert isinstance(result["distance_ly"], float)


class TestClassifyHeat:
    """Test classify_heat() method on RadiusSearch."""

    def test_cool_system_below_70(self):
        """System with safe_jump_temp < 70 should be classified as cool."""
        searcher = RadiusSearch()
        system = {"safe_jump_temp": 65.0}
        result = searcher.classify_heat(system)
        assert result == "cool"

    def test_cool_system_at_boundary(self):
        """System with safe_jump_temp just below 70 should be cool."""
        searcher = RadiusSearch()
        system = {"safe_jump_temp": 69.9}
        result = searcher.classify_heat(system)
        assert result == "cool"

    def test_warm_system_at_70(self):
        """System with safe_jump_temp at exactly 70 should be classified as warm."""
        searcher = RadiusSearch()
        system = {"safe_jump_temp": 70.0}
        result = searcher.classify_heat(system)
        assert result == "warm"

    def test_warm_system_mid_range(self):
        """System with safe_jump_temp between 70-89 should be warm."""
        searcher = RadiusSearch()
        system = {"safe_jump_temp": 75.5}
        result = searcher.classify_heat(system)
        assert result == "warm"

    def test_warm_system_at_89(self):
        """System with safe_jump_temp at 89 should be warm."""
        searcher = RadiusSearch()
        system = {"safe_jump_temp": 89.0}
        result = searcher.classify_heat(system)
        assert result == "warm"

    def test_warm_system_just_below_90(self):
        """System with safe_jump_temp just below 90 should be warm."""
        searcher = RadiusSearch()
        system = {"safe_jump_temp": 89.9}
        result = searcher.classify_heat(system)
        assert result == "warm"

    def test_hot_system_at_90(self):
        """System with safe_jump_temp at exactly 90 should be classified as hot."""
        searcher = RadiusSearch()
        system = {"safe_jump_temp": 90.0}
        result = searcher.classify_heat(system)
        assert result == "hot"

    def test_hot_system_above_90(self):
        """System with safe_jump_temp > 90 should be hot."""
        searcher = RadiusSearch()
        system = {"safe_jump_temp": 95.5}
        result = searcher.classify_heat(system)
        assert result == "hot"

    def test_missing_safe_jump_temp(self):
        """System without safe_jump_temp should default to 0 and be cool."""
        searcher = RadiusSearch()
        system = {}
        result = searcher.classify_heat(system)
        assert result == "cool"

    def test_none_safe_jump_temp(self):
        """System with safe_jump_temp as None should default to 0 and be cool."""
        searcher = RadiusSearch()
        system = {"safe_jump_temp": None}
        result = searcher.classify_heat(system)
        assert result == "cool"

    def test_zero_safe_jump_temp(self):
        """System with safe_jump_temp of 0 should be cool."""
        searcher = RadiusSearch()
        system = {"safe_jump_temp": 0.0}
        result = searcher.classify_heat(system)
        assert result == "cool"

    def test_negative_safe_jump_temp(self):
        """System with negative safe_jump_temp should be cool."""
        searcher = RadiusSearch()
        system = {"safe_jump_temp": -10.0}
        result = searcher.classify_heat(system)
        assert result == "cool"

    def test_very_high_safe_jump_temp(self):
        """System with very high safe_jump_temp should be hot."""
        searcher = RadiusSearch()
        system = {"safe_jump_temp": 150.0}
        result = searcher.classify_heat(system)
        assert result == "hot"


class TestCountPlanets:
    """Test count_planets() method on RadiusSearch."""

    def test_system_with_planets(self):
        """System with planet_ids should return correct count."""
        searcher = RadiusSearch()
        system = {"planet_ids": [1, 2, 3, 4, 5]}
        result = searcher.count_planets(system)
        assert result == 5

    def test_system_with_single_planet(self):
        """System with one planet should return 1."""
        searcher = RadiusSearch()
        system = {"planet_ids": [42]}
        result = searcher.count_planets(system)
        assert result == 1

    def test_system_with_no_planets(self):
        """System with empty planet_ids should return 0."""
        searcher = RadiusSearch()
        system = {"planet_ids": []}
        result = searcher.count_planets(system)
        assert result == 0

    def test_system_missing_planet_ids(self):
        """System without planet_ids key should return 0."""
        searcher = RadiusSearch()
        system = {}
        result = searcher.count_planets(system)
        assert result == 0

    def test_system_with_none_planet_ids(self):
        """System with planet_ids as None should return 0."""
        searcher = RadiusSearch()
        system = {"planet_ids": None}
        result = searcher.count_planets(system)
        assert result == 0

    def test_system_with_many_planets(self):
        """System with many planets should return correct count."""
        searcher = RadiusSearch()
        planet_ids = list(range(1, 51))  # 50 planets
        system = {"planet_ids": planet_ids}
        result = searcher.count_planets(system)
        assert result == 50

    def test_system_with_string_ids_in_list(self):
        """System with string planet IDs should count them correctly."""
        searcher = RadiusSearch()
        system = {"planet_ids": ["p1", "p2", "p3"]}
        result = searcher.count_planets(system)
        assert result == 3

    def test_system_with_mixed_id_types(self):
        """System with mixed int/string planet IDs should count correctly."""
        searcher = RadiusSearch()
        system = {"planet_ids": [1, "p2", 3, "p4"]}
        result = searcher.count_planets(system)
        assert result == 4


class TestIsHeatTrap:
    """Test is_heat_trap() method on RadiusSearch."""

    def test_cool_system_not_heat_trap(self):
        """Cool system (< 70°) should not be a heat trap."""
        searcher = RadiusSearch()
        system = {"safe_jump_temp": 65.0}
        result = searcher.is_heat_trap(system)
        assert result is False

    def test_warm_system_is_heat_trap(self):
        """Warm system (70-89°) should be a heat trap."""
        searcher = RadiusSearch()
        system = {"safe_jump_temp": 75.0}
        result = searcher.is_heat_trap(system)
        assert result is True

    def test_hot_system_is_heat_trap(self):
        """Hot system (>= 90°) should be a heat trap."""
        searcher = RadiusSearch()
        system = {"safe_jump_temp": 95.0}
        result = searcher.is_heat_trap(system)
        assert result is True

    def test_system_at_exactly_70_is_heat_trap(self):
        """System at exactly 70° should be a heat trap."""
        searcher = RadiusSearch()
        system = {"safe_jump_temp": 70.0}
        result = searcher.is_heat_trap(system)
        assert result is True

    def test_system_just_below_70_not_heat_trap(self):
        """System just below 70° should not be a heat trap."""
        searcher = RadiusSearch()
        system = {"safe_jump_temp": 69.9}
        result = searcher.is_heat_trap(system)
        assert result is False

    def test_system_at_exactly_90_is_heat_trap(self):
        """System at exactly 90° should be a heat trap."""
        searcher = RadiusSearch()
        system = {"safe_jump_temp": 90.0}
        result = searcher.is_heat_trap(system)
        assert result is True

    def test_missing_safe_jump_temp_not_heat_trap(self):
        """System without safe_jump_temp should not be a heat trap (defaults to 0)."""
        searcher = RadiusSearch()
        system = {}
        result = searcher.is_heat_trap(system)
        assert result is False

    def test_none_safe_jump_temp_not_heat_trap(self):
        """System with safe_jump_temp as None should not be a heat trap."""
        searcher = RadiusSearch()
        system = {"safe_jump_temp": None}
        result = searcher.is_heat_trap(system)
        assert result is False

    def test_zero_safe_jump_temp_not_heat_trap(self):
        """System with safe_jump_temp of 0 should not be a heat trap."""
        searcher = RadiusSearch()
        system = {"safe_jump_temp": 0.0}
        result = searcher.is_heat_trap(system)
        assert result is False

    def test_negative_safe_jump_temp_not_heat_trap(self):
        """System with negative safe_jump_temp should not be a heat trap."""
        searcher = RadiusSearch()
        system = {"safe_jump_temp": -10.0}
        result = searcher.is_heat_trap(system)
        assert result is False


class TestHeatClassificationIntegration:
    """Integration tests combining heat classification with count_planets."""

    def test_warm_system_with_planets(self):
        """Warm system with planets should be flagged as heat trap."""
        searcher = RadiusSearch()
        system = {
            "safe_jump_temp": 75.5,
            "planet_ids": [1, 2, 3],
            "name": "Test System"
        }
        assert searcher.is_heat_trap(system) is True
        assert searcher.classify_heat(system) == "warm"
        assert searcher.count_planets(system) == 3

    def test_cool_system_with_many_planets(self):
        """Cool system with planets should not be flagged as heat trap."""
        searcher = RadiusSearch()
        system = {
            "safe_jump_temp": 50.0,
            "planet_ids": list(range(1, 21)),  # 20 planets
            "name": "Temperate System"
        }
        assert searcher.is_heat_trap(system) is False
        assert searcher.classify_heat(system) == "cool"
        assert searcher.count_planets(system) == 20

    def test_hot_system_no_planets(self):
        """Hot system without planets should be flagged as heat trap."""
        searcher = RadiusSearch()
        system = {
            "safe_jump_temp": 100.0,
            "planet_ids": [],
            "name": "Barren Hot System"
        }
        assert searcher.is_heat_trap(system) is True
        assert searcher.classify_heat(system) == "hot"
        assert searcher.count_planets(system) == 0

    def test_system_missing_all_fields(self):
        """System with all missing fields should default safely."""
        searcher = RadiusSearch()
        system = {"name": "Unknown System"}
        assert searcher.is_heat_trap(system) is False
        assert searcher.classify_heat(system) == "cool"
        assert searcher.count_planets(system) == 0

    def test_boundary_systems(self):
        """Test boundary conditions for all three methods together."""
        searcher = RadiusSearch()

        # At the warm/hot boundary (90°)
        system_90 = {"safe_jump_temp": 90.0, "planet_ids": [1]}
        assert searcher.classify_heat(system_90) == "hot"
        assert searcher.is_heat_trap(system_90) is True
        assert searcher.count_planets(system_90) == 1

        # Just below boundary (89.9°)
        system_89_9 = {"safe_jump_temp": 89.9, "planet_ids": [2, 3]}
        assert searcher.classify_heat(system_89_9) == "warm"
        assert searcher.is_heat_trap(system_89_9) is True
        assert searcher.count_planets(system_89_9) == 2

        # At the cool/warm boundary (70°)
        system_70 = {"safe_jump_temp": 70.0, "planet_ids": [4, 5, 6]}
        assert searcher.classify_heat(system_70) == "warm"
        assert searcher.is_heat_trap(system_70) is True
        assert searcher.count_planets(system_70) == 3

        # Just below boundary (69.9°)
        system_69_9 = {"safe_jump_temp": 69.9, "planet_ids": [7]}
        assert searcher.classify_heat(system_69_9) == "cool"
        assert searcher.is_heat_trap(system_69_9) is False
        assert searcher.count_planets(system_69_9) == 1


class TestFilterKillmailsByRecency:
    """Test filter_killmails_by_recency method on RadiusSearch."""

    def test_filter_killmails_by_recency_with_recent_timestamps(self):
        """Test filtering keeps killmails within the time window."""
        searcher = RadiusSearch()
        now = time.time()
        recent_ts = now - 3600  # 1 hour ago
        old_ts = now - (48 * 3600)  # 48 hours ago

        killmails = [
            {"kill_id": 1, "timestamp": recent_ts},
            {"kill_id": 2, "timestamp": old_ts},
        ]

        filtered = searcher.filter_killmails_by_recency(killmails, hours=24)
        assert len(filtered) == 1
        assert filtered[0]["kill_id"] == 1

    def test_filter_killmails_by_recency_returns_most_recent_first(self):
        """Test that filtered killmails are sorted by recency (newest first)."""
        searcher = RadiusSearch()
        now = time.time()
        ts1 = now - 1000
        ts2 = now - 500
        ts3 = now - 100

        killmails = [
            {"kill_id": 1, "timestamp": ts1},
            {"kill_id": 3, "timestamp": ts3},
            {"kill_id": 2, "timestamp": ts2},
        ]

        filtered = searcher.filter_killmails_by_recency(killmails, hours=24)
        assert len(filtered) == 3
        assert filtered[0]["kill_id"] == 3  # Most recent first
        assert filtered[1]["kill_id"] == 2
        assert filtered[2]["kill_id"] == 1

    def test_filter_killmails_by_recency_handles_missing_timestamp(self):
        """Test that killmails without timestamps are skipped."""
        searcher = RadiusSearch()
        now = time.time()
        killmails = [
            {"kill_id": 1, "timestamp": now - 1000},
            {"kill_id": 2},  # Missing timestamp
            {"kill_id": 3, "timestamp": now - 500},
        ]

        filtered = searcher.filter_killmails_by_recency(killmails, hours=24)
        assert len(filtered) == 2
        kill_ids = [km["kill_id"] for km in filtered]
        assert 2 not in kill_ids

    def test_filter_killmails_by_recency_handles_millisecond_timestamps(self):
        """Test that timestamps in milliseconds are converted to seconds."""
        searcher = RadiusSearch()
        now = time.time()
        now_ms = now * 1000
        recent_ms = now_ms - 3600000  # 1 hour ago in ms
        old_ms = now_ms - (48 * 3600000)  # 48 hours ago in ms

        killmails = [
            {"kill_id": 1, "timestamp": recent_ms},
            {"kill_id": 2, "timestamp": old_ms},
        ]

        filtered = searcher.filter_killmails_by_recency(killmails, hours=24)
        assert len(filtered) == 1
        assert filtered[0]["kill_id"] == 1

    def test_filter_killmails_by_recency_empty_list(self):
        """Test that empty list returns empty list."""
        searcher = RadiusSearch()
        filtered = searcher.filter_killmails_by_recency([], hours=24)
        assert filtered == []

    def test_filter_killmails_by_recency_different_hour_windows(self):
        """Test filtering with various hour windows."""
        searcher = RadiusSearch()
        now = time.time()
        killmails = [
            {"kill_id": 1, "timestamp": now - 1800},  # 30 min ago
            {"kill_id": 2, "timestamp": now - 7200},  # 2 hours ago
            {"kill_id": 3, "timestamp": now - 14400},  # 4 hours ago
        ]

        # 1 hour window
        filtered = searcher.filter_killmails_by_recency(killmails, hours=1)
        assert len(filtered) == 1
        assert filtered[0]["kill_id"] == 1

        # 3 hour window
        filtered = searcher.filter_killmails_by_recency(killmails, hours=3)
        assert len(filtered) == 2

        # 5 hour window
        filtered = searcher.filter_killmails_by_recency(killmails, hours=5)
        assert len(filtered) == 3


class TestGetMostRecentKillmailTimestamp:
    """Test get_most_recent_killmail_timestamp method on RadiusSearch."""

    def test_get_most_recent_killmail_timestamp_with_list(self):
        """Test finding most recent timestamp from a list."""
        searcher = RadiusSearch()
        now = time.time()
        killmails = [
            {"kill_id": 1, "timestamp": now - 3600},
            {"kill_id": 2, "timestamp": now - 100},
            {"kill_id": 3, "timestamp": now - 7200},
        ]

        ts = searcher.get_most_recent_killmail_timestamp(killmails)
        assert ts == now - 100

    def test_get_most_recent_killmail_timestamp_empty_list(self):
        """Test that empty list returns None."""
        searcher = RadiusSearch()
        ts = searcher.get_most_recent_killmail_timestamp([])
        assert ts is None

    def test_get_most_recent_killmail_timestamp_missing_timestamp_field(self):
        """Test that killmails without timestamp are skipped."""
        searcher = RadiusSearch()
        now = time.time()
        killmails = [
            {"kill_id": 1, "timestamp": now - 3600},
            {"kill_id": 2},  # No timestamp
            {"kill_id": 3, "timestamp": now - 7200},
        ]

        ts = searcher.get_most_recent_killmail_timestamp(killmails)
        assert ts == now - 3600

    def test_get_most_recent_killmail_timestamp_all_missing(self):
        """Test that list with no valid timestamps returns None."""
        searcher = RadiusSearch()
        killmails = [
            {"kill_id": 1},
            {"kill_id": 2},
        ]

        ts = searcher.get_most_recent_killmail_timestamp(killmails)
        assert ts is None


class TestGetKillmailsForSystem:
    """Test get_killmails_for_system method on RadiusSearch."""

    @pytest.mark.asyncio
    async def test_get_killmails_for_system_returns_list(self):
        """Test that get_killmails_for_system returns a list."""
        searcher = RadiusSearch()
        mock_api = AsyncMock()
        now = time.time()
        mock_api.get_killmails.return_value = [
            {"kill_id": 1, "timestamp": now - 1000},
            {"kill_id": 2, "timestamp": now - 500},
        ]

        searcher.world_api_client = mock_api
        result = await searcher.get_killmails_for_system(30000142)

        assert isinstance(result, list)
        assert len(result) == 2
        mock_api.get_killmails.assert_called_once_with(30000142)

    @pytest.mark.asyncio
    async def test_get_killmails_for_system_applies_recency_filter(self):
        """Test that get_killmails_for_system filters by recency."""
        searcher = RadiusSearch()
        mock_api = AsyncMock()
        now = time.time()
        mock_api.get_killmails.return_value = [
            {"kill_id": 1, "timestamp": now - 1000},  # recent
            {"kill_id": 2, "timestamp": now - (48 * 3600)},  # old (>24 hours)
        ]

        searcher.world_api_client = mock_api
        result = await searcher.get_killmails_for_system(30000142, hours=24)

        assert len(result) == 1
        assert result[0]["kill_id"] == 1

    @pytest.mark.asyncio
    async def test_get_killmails_for_system_limits_to_10(self):
        """Test that get_killmails_for_system returns at most 10 killmails."""
        searcher = RadiusSearch()
        mock_api = AsyncMock()
        now = time.time()
        killmails = [
            {"kill_id": i, "timestamp": now - i}
            for i in range(20)
        ]
        mock_api.get_killmails.return_value = killmails

        searcher.world_api_client = mock_api
        result = await searcher.get_killmails_for_system(30000142)

        assert len(result) == 10

    @pytest.mark.asyncio
    async def test_get_killmails_for_system_returns_most_recent_first(self):
        """Test that results are sorted by most recent first."""
        searcher = RadiusSearch()
        mock_api = AsyncMock()
        now = time.time()
        mock_api.get_killmails.return_value = [
            {"kill_id": 1, "timestamp": now - 3600},
            {"kill_id": 2, "timestamp": now - 100},
            {"kill_id": 3, "timestamp": now - 7200},
        ]

        searcher.world_api_client = mock_api
        result = await searcher.get_killmails_for_system(30000142)

        assert result[0]["kill_id"] == 2  # Most recent first
        assert result[1]["kill_id"] == 1
        assert result[2]["kill_id"] == 3

    @pytest.mark.asyncio
    async def test_get_killmails_for_system_handles_api_error(self):
        """Test that API errors return empty list."""
        searcher = RadiusSearch()
        mock_api = AsyncMock()
        mock_api.get_killmails.side_effect = Exception("API error")

        searcher.world_api_client = mock_api
        result = await searcher.get_killmails_for_system(30000142)

        assert result == []

    @pytest.mark.asyncio
    async def test_get_killmails_for_system_returns_empty_when_no_api(self):
        """Test that None world_api_client returns empty list."""
        searcher = RadiusSearch()
        searcher.world_api_client = None
        result = await searcher.get_killmails_for_system(30000142)

        assert result == []

    @pytest.mark.asyncio
    async def test_get_killmails_for_system_handles_empty_api_response(self):
        """Test that empty API response returns empty list."""
        searcher = RadiusSearch()
        mock_api = AsyncMock()
        mock_api.get_killmails.return_value = []

        searcher.world_api_client = mock_api
        result = await searcher.get_killmails_for_system(30000142)

        assert result == []

    @pytest.mark.asyncio
    async def test_get_killmails_for_system_custom_hours_window(self):
        """Test that custom hours window is applied correctly."""
        searcher = RadiusSearch()
        mock_api = AsyncMock()
        now = time.time()
        mock_api.get_killmails.return_value = [
            {"kill_id": 1, "timestamp": now - 3600},  # 1 hour ago
            {"kill_id": 2, "timestamp": now - (5 * 3600)},  # 5 hours ago
            {"kill_id": 3, "timestamp": now - (25 * 3600)},  # 25 hours ago
        ]

        searcher.world_api_client = mock_api

        # 6-hour window should include first two
        result = await searcher.get_killmails_for_system(30000142, hours=6)
        assert len(result) == 2

        # 30-hour window should include all
        result = await searcher.get_killmails_for_system(30000142, hours=30)
        assert len(result) == 3
