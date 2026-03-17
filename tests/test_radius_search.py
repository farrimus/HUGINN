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
