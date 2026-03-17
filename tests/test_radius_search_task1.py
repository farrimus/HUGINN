"""
Test suite for Task 1: Structure Locations Cache and RadiusSearch Scaffold.

Tests:
1. structure_locations.json file exists with correct structure
2. RadiusSearch class can be imported
3. RadiusSearch initialization works
4. Module-level constant for cache path is defined
"""

import os
import json
import pytest
import sys

# Add project root to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from src.radius_search import RadiusSearch, structure_locations_path


class TestStructureLocationsFile:
    """Test structure_locations.json file integrity."""

    def test_structure_locations_file_exists(self):
        """structure_locations.json should exist in data/ directory."""
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
        """structure_locations.json should have 'built_at' and 'structures' keys."""
        data_dir = os.path.join(os.path.dirname(__file__), '..', 'data')
        file_path = os.path.join(data_dir, 'structure_locations.json')
        with open(file_path, 'r') as f:
            data = json.load(f)
        assert 'built_at' in data, "Missing 'built_at' key"
        assert 'structures' in data, "Missing 'structures' key"
        assert isinstance(data['structures'], dict), "'structures' should be a dict"

    def test_structure_locations_initial_empty(self):
        """structure_locations.json structures should be initially empty."""
        data_dir = os.path.join(os.path.dirname(__file__), '..', 'data')
        file_path = os.path.join(data_dir, 'structure_locations.json')
        with open(file_path, 'r') as f:
            data = json.load(f)
        assert len(data['structures']) == 0


class TestRadiusSearchScaffold:
    """Test RadiusSearch class scaffold."""

    def test_radius_search_importable(self):
        """RadiusSearch class should be importable."""
        from src.radius_search import RadiusSearch
        assert RadiusSearch is not None

    def test_radius_search_instantiation(self):
        """RadiusSearch should instantiate without errors."""
        searcher = RadiusSearch()
        assert searcher is not None

    def test_radius_search_has_required_attributes(self):
        """RadiusSearch should have required attributes."""
        searcher = RadiusSearch()
        assert hasattr(searcher, 'structures'), "Missing 'structures' attribute"
        assert hasattr(searcher, 'system_index'), "Missing 'system_index' attribute"
        assert isinstance(searcher.structures, dict)
        assert isinstance(searcher.system_index, dict)

    def test_radius_search_has_required_methods(self):
        """RadiusSearch should have required methods."""
        searcher = RadiusSearch()
        assert hasattr(searcher, 'load_structures'), "Missing 'load_structures' method"
        assert hasattr(searcher, 'search'), "Missing 'search' method"
        assert callable(searcher.load_structures)
        assert callable(searcher.search)


class TestStructureLocationsPath:
    """Test module-level structure_locations_path constant."""

    def test_structure_locations_path_defined(self):
        """structure_locations_path should be defined at module level."""
        assert structure_locations_path is not None

    def test_structure_locations_path_is_string(self):
        """structure_locations_path should be a string."""
        assert isinstance(structure_locations_path, str)

    def test_structure_locations_path_points_to_data_directory(self):
        """structure_locations_path should point to data/structure_locations.json."""
        assert 'data' in structure_locations_path
        assert 'structure_locations.json' in structure_locations_path

    def test_structure_locations_path_is_absolute(self):
        """structure_locations_path should be resolvable (relative to module location)."""
        # It's constructed relative to __file__, so it should be valid
        assert os.path.sep in structure_locations_path or '/' in structure_locations_path


class TestImports:
    """Test that required imports are available."""

    def test_world_api_import(self):
        """world_api should be importable from src.world_api."""
        from src.world_api import world_api
        assert world_api is not None

    def test_radius_search_imports_world_api(self):
        """RadiusSearch module should successfully import world_api."""
        from src import radius_search
        assert hasattr(radius_search, 'world_api')
