"""
Tests for RadiusSearch cache functionality.

Tests the cache building, loading, saving, and refresh methods.
"""

import pytest
import json
import tempfile
import asyncio
from pathlib import Path
from datetime import datetime, timezone

from src.radius_search import RadiusSearch
from src.config import get_data_path


class TestRadiusSearchCache:
    """Test suite for RadiusSearch cache methods."""

    @pytest.fixture
    def temp_data_dir(self, tmp_path, monkeypatch):
        """Fixture: temporary data directory for testing."""
        data_dir = tmp_path / "data"
        data_dir.mkdir()
        monkeypatch.setenv("DATA_PATH", str(data_dir))
        return data_dir

    @pytest.fixture
    def radius_search_instance(self, tmp_path):
        """Fixture: RadiusSearch instance with temp systems and structures."""
        systems_path = tmp_path / "systems.json"
        struct_path = tmp_path / "structure_locations.json"

        # Minimal systems data with test systems
        systems_data = {
            "systems": {
                "30000142": {
                    "id": 30000142,
                    "name": "Jita",
                    "x": 0.0,
                    "y": 0.0,
                    "z": 0.0,
                    "safe_jump_temp": 50,
                    "planet_ids": [1, 2, 3],
                    "gates": True
                },
                "30002544": {
                    "id": 30002544,
                    "name": "UR8-K7K",
                    "x": 1e16,
                    "y": 1e16,
                    "z": 0.0,
                    "safe_jump_temp": 45,
                    "planet_ids": [1],
                    "gates": True
                },
                "30002543": {
                    "id": 30002543,
                    "name": "TEST-NEARBY",
                    "x": 1.1e16,
                    "y": 1.1e16,
                    "z": 0.0,
                    "safe_jump_temp": 60,
                    "planet_ids": [1, 2],
                    "gates": False
                }
            }
        }

        with open(systems_path, 'w') as f:
            json.dump(systems_data, f)

        with open(struct_path, 'w') as f:
            json.dump({"structure_locations": {}}, f)

        return RadiusSearch(
            systems_path=str(systems_path),
            structure_locations_path=str(struct_path)
        )

    def test_cache_path_creation(self, radius_search_instance):
        """Test: cache path is correctly constructed."""
        assembly_id = "test-structure-1"
        cache_path = radius_search_instance.get_cache_path(assembly_id)

        # Path should contain assembly_id and filename
        assert "test-structure-1" in str(cache_path)
        assert "radius_search.json" in str(cache_path)
        assert str(cache_path).endswith("radius_search.json")

    def test_save_and_load_cache(self, radius_search_instance):
        """Test: save cache to disk, then load it back."""
        assembly_id = "test-structure-1"
        cache_data = {
            "assembly_id": assembly_id,
            "center_system": "UR8-K7K",
            "radius_ly": 50.0,
            "static_data_loaded_at": datetime.now(timezone.utc).isoformat() + "Z",
            "kills_last_updated": datetime.now(timezone.utc).isoformat() + "Z",
            "systems": [
                {
                    "name": "UR8-K7K",
                    "distance_ly": 0.0,
                    "planets": 1,
                    "safe_jump_temp": 45,
                    "kills_24h": 5,
                    "gates": True,
                }
            ]
        }

        # Save cache
        radius_search_instance.save_cache(assembly_id, cache_data)

        # Verify file exists
        cache_path = radius_search_instance.get_cache_path(assembly_id)
        assert cache_path.exists(), "Cache file should exist after save"

        # Load cache
        loaded = radius_search_instance.load_cache(assembly_id)
        assert loaded is not None, "Cache should load successfully"
        assert loaded["assembly_id"] == assembly_id
        assert loaded["center_system"] == "UR8-K7K"
        assert len(loaded["systems"]) == 1
        assert loaded["systems"][0]["name"] == "UR8-K7K"

    def test_load_cache_returns_none_when_missing(self, radius_search_instance):
        """Test: load_cache returns None for non-existent cache."""
        assembly_id = "nonexistent-structure"
        loaded = radius_search_instance.load_cache(assembly_id)
        assert loaded is None, "Should return None for missing cache"

    def test_load_cache_handles_corrupted_json(self, radius_search_instance, tmp_path):
        """Test: load_cache gracefully handles corrupted JSON."""
        assembly_id = "corrupted-structure"
        cache_path = radius_search_instance.get_cache_path(assembly_id)

        # Write invalid JSON
        cache_path.write_text("{ invalid json }")

        loaded = radius_search_instance.load_cache(assembly_id)
        assert loaded is None, "Should return None for corrupted JSON"

    @pytest.mark.asyncio
    async def test_build_cache(self, radius_search_instance):
        """Test: build_cache creates correct structure and persists to disk."""
        assembly_id = "test-structure-1"
        center_system = "UR8-K7K"
        radius_ly = 50.0

        # Mock world_api client's get_killmails_for_system to avoid real API calls
        async def mock_get_killmails(system_id, hours=24):
            # Return empty list for all systems to keep test deterministic
            return []

        radius_search_instance.get_killmails_for_system = mock_get_killmails

        # Build cache
        cache = await radius_search_instance.build_cache(
            assembly_id=assembly_id,
            center_system=center_system,
            radius_ly=radius_ly
        )

        # Verify structure
        assert cache["assembly_id"] == assembly_id
        assert cache["center_system"] == center_system
        assert cache["radius_ly"] == radius_ly
        assert "static_data_loaded_at" in cache
        assert "kills_last_updated" in cache
        assert "systems" in cache
        assert isinstance(cache["systems"], list)

        # Verify systems have required fields
        for system in cache["systems"]:
            assert "name" in system
            assert "distance_ly" in system
            assert "planets" in system
            assert "safe_jump_temp" in system
            assert "kills_24h" in system
            assert "gates" in system

        # Verify cache was saved to disk
        cache_path = radius_search_instance.get_cache_path(assembly_id)
        assert cache_path.exists(), "Cache file should be created on disk"

        # Verify we can reload it
        loaded = radius_search_instance.load_cache(assembly_id)
        assert loaded is not None
        assert loaded["assembly_id"] == assembly_id

    @pytest.mark.asyncio
    async def test_refresh_cache_kills(self, radius_search_instance):
        """Test: refresh_cache_kills updates kills data without rebuilding static."""
        assembly_id = "test-structure-1"

        # First, create an initial cache
        initial_cache = {
            "assembly_id": assembly_id,
            "center_system": "UR8-K7K",
            "radius_ly": 50.0,
            "static_data_loaded_at": datetime.now(timezone.utc).isoformat() + "Z",
            "kills_last_updated": datetime.now(timezone.utc).isoformat() + "Z",
            "systems": [
                {
                    "name": "UR8-K7K",
                    "distance_ly": 0.0,
                    "planets": 1,
                    "safe_jump_temp": 45,
                    "kills_24h": 5,
                    "gates": True,
                },
                {
                    "name": "TEST-NEARBY",
                    "distance_ly": 1.5,
                    "planets": 2,
                    "safe_jump_temp": 60,
                    "kills_24h": 3,
                    "gates": False,
                    "killmail_count_24h": 3
                }
            ]
        }

        radius_search_instance.save_cache(assembly_id, initial_cache)
        original_static_time = initial_cache["static_data_loaded_at"]

        # Mock get_killmails to return new kill counts
        async def mock_get_killmails(system_id, hours=24):
            # Return different counts
            return [{"id": i} for i in range(10)]  # 10 kills

        radius_search_instance.get_killmails_for_system = mock_get_killmails

        # Refresh kills
        updated_cache = await radius_search_instance.refresh_cache_kills(assembly_id)

        # Verify static data unchanged
        assert updated_cache["static_data_loaded_at"] == original_static_time
        assert len(updated_cache["systems"]) == 2

        # Verify kills updated (mocked to return 10)
        for system in updated_cache["systems"]:
            assert system["kills_24h"] == 10

        # Verify kills_last_updated changed
        assert updated_cache["kills_last_updated"] != initial_cache["kills_last_updated"]

        # Verify cache was persisted
        reloaded = radius_search_instance.load_cache(assembly_id)
        assert reloaded["systems"][0]["kills_24h"] == 10

    @pytest.mark.asyncio
    async def test_refresh_cache_kills_nonexistent(self, radius_search_instance):
        """Test: refresh_cache_kills raises ValueError for missing cache."""
        assembly_id = "nonexistent-structure"

        with pytest.raises(ValueError, match="No cache found"):
            await radius_search_instance.refresh_cache_kills(assembly_id)

    def test_cache_directory_creation(self, radius_search_instance):
        """Test: cache_dir property creates directory if needed."""
        cache_dir = radius_search_instance.cache_dir
        assert cache_dir.exists() or cache_dir.parent.exists()

    @pytest.mark.asyncio
    async def test_build_cache_with_empty_systems(self, radius_search_instance):
        """Test: build_cache handles center system with no nearby systems."""
        assembly_id = "test-structure-2"
        center_system = "Jita"  # Far from TEST-NEARBY
        radius_ly = 1.0  # Very small radius

        async def mock_get_killmails(system_id, hours=24):
            return []

        radius_search_instance.get_killmails_for_system = mock_get_killmails

        # Build cache with small radius
        cache = await radius_search_instance.build_cache(
            assembly_id=assembly_id,
            center_system=center_system,
            radius_ly=radius_ly
        )

        # Should still have valid structure, but minimal systems
        assert cache["assembly_id"] == assembly_id
        assert cache["center_system"] == center_system
        assert "systems" in cache
        # 1 LY radius is too small, no systems found (center system is excluded)
        assert len(cache["systems"]) == 0
