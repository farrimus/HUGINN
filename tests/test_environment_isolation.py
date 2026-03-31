"""
Integration tests for environment-aware data paths.
Verifies that switching DEPLOYMENT_ENV correctly routes data files.
"""
import pytest
import os
import tempfile
from src.config import get_data_path, load_config_from_env
from src.ship_profile import _profile_path
from src.route_engine import RouteEngine
from src.world_api import WorldAPIClient
from src.structure_persistence import _get_default_base_dir as get_structures_dir
from src.deal_store import DealStore
from src.memory_store import MemoryStore
from src.location_index import LocationIndex
from src.type_names import get_type_name
from src.galaxy_db import GalaxyDB


class TestEnvironmentIsolation:
    """Test suite for environment isolation between Utopia and Stillness."""

    def test_config_respects_deployment_env_utopia(self, monkeypatch):
        """Verify config loads correct URLs for Utopia."""
        monkeypatch.setenv("DEPLOYMENT_ENV", "utopia")
        config = load_config_from_env()

        assert config["deployment_env"] == "utopia"
        assert "utopia" in config["world_api_url"]
        assert "testnet" in config["nova_rpc_url"]

    def test_config_respects_deployment_env_stillness(self, monkeypatch):
        """Verify config loads correct URLs for Stillness."""
        monkeypatch.setenv("DEPLOYMENT_ENV", "stillness")
        config = load_config_from_env()

        assert config["deployment_env"] == "stillness"
        assert "stillness" in config["world_api_url"]

    def test_shared_data_path_independent_of_env(self, monkeypatch):
        """Verify shared data paths don't include environment."""
        monkeypatch.setenv("DEPLOYMENT_ENV", "utopia")
        path_utopia = get_data_path("systems.json", env_specific=False)

        monkeypatch.setenv("DEPLOYMENT_ENV", "stillness")
        path_stillness = get_data_path("systems.json", env_specific=False)

        # Both should be identical and at root level
        assert path_utopia == path_stillness
        assert "systems.json" in path_utopia
        assert "data/" in path_utopia
        assert "utopia" not in path_utopia
        assert "stillness" not in path_utopia

    def test_env_specific_paths_differ(self, monkeypatch):
        """Verify environment-specific paths are truly separate."""
        monkeypatch.setenv("DEPLOYMENT_ENV", "utopia")
        path_utopia = get_data_path("system_index.json", env_specific=True)

        monkeypatch.setenv("DEPLOYMENT_ENV", "stillness")
        path_stillness = get_data_path("system_index.json", env_specific=True)

        # Paths should differ and contain environment name
        assert path_utopia != path_stillness
        assert "utopia" in path_utopia
        assert "stillness" in path_stillness

    def test_ship_profile_is_shared(self, monkeypatch):
        """Verify ship profile is shared across environments."""
        monkeypatch.setenv("DEPLOYMENT_ENV", "utopia")
        path_utopia = _profile_path()

        monkeypatch.setenv("DEPLOYMENT_ENV", "stillness")
        path_stillness = _profile_path()

        # Same path for both environments
        assert path_utopia == path_stillness

    def test_world_api_respects_deployment_env(self, monkeypatch):
        """Verify WorldAPIClient uses correct API endpoint."""
        monkeypatch.setenv("DEPLOYMENT_ENV", "utopia")
        monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")
        monkeypatch.setenv("JWT_SECRET", "test-secret")

        api_utopia = WorldAPIClient()
        assert "utopia" in api_utopia.base_url

        monkeypatch.setenv("DEPLOYMENT_ENV", "stillness")
        api_stillness = WorldAPIClient()
        assert "stillness" in api_stillness.base_url

    def test_world_api_index_paths_separate(self, monkeypatch):
        """Verify WorldAPIClient uses separate index files per env."""
        monkeypatch.setenv("DEPLOYMENT_ENV", "utopia")
        monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")
        monkeypatch.setenv("JWT_SECRET", "test-secret")

        api_utopia = WorldAPIClient()
        index_utopia = api_utopia._index_file()

        monkeypatch.setenv("DEPLOYMENT_ENV", "stillness")
        api_stillness = WorldAPIClient()
        index_stillness = api_stillness._index_file()

        # Paths should differ
        assert index_utopia != index_stillness
        assert "utopia" in index_utopia
        assert "stillness" in index_stillness

    def test_route_engine_systems_path_is_shared(self, monkeypatch):
        """Verify route engine uses shared systems.json."""
        monkeypatch.setenv("DEPLOYMENT_ENV", "utopia")
        engine_utopia = RouteEngine()
        path_utopia = engine_utopia._systems_path()

        monkeypatch.setenv("DEPLOYMENT_ENV", "stillness")
        engine_stillness = RouteEngine()
        path_stillness = engine_stillness._systems_path()

        # Same systems.json for both
        assert path_utopia == path_stillness
        assert "systems.json" in path_utopia

    def test_structures_directory_per_env(self, monkeypatch):
        """Verify structures directory is per-environment."""
        monkeypatch.setenv("DEPLOYMENT_ENV", "utopia")
        dir_utopia = get_structures_dir()

        monkeypatch.setenv("DEPLOYMENT_ENV", "stillness")
        dir_stillness = get_structures_dir()

        # Different directories per environment
        assert dir_utopia != dir_stillness
        assert "utopia" in dir_utopia
        assert "stillness" in dir_stillness

    def test_deal_store_per_env(self, monkeypatch):
        """Verify DealStore uses per-environment deals directory."""
        monkeypatch.setenv("DEPLOYMENT_ENV", "utopia")
        store_utopia = DealStore()

        monkeypatch.setenv("DEPLOYMENT_ENV", "stillness")
        store_stillness = DealStore()

        # Different base directories per environment
        assert store_utopia._base != store_stillness._base
        assert "utopia" in store_utopia._base
        assert "stillness" in store_stillness._base

    def test_memory_store_per_env(self, monkeypatch):
        """Verify MemoryStore uses per-environment memory directory."""
        monkeypatch.setenv("DEPLOYMENT_ENV", "utopia")
        store_utopia = MemoryStore(structure_id="test-1")

        monkeypatch.setenv("DEPLOYMENT_ENV", "stillness")
        store_stillness = MemoryStore(structure_id="test-1")

        # Different base directories per environment
        assert store_utopia._base != store_stillness._base
        assert "utopia" in store_utopia._base
        assert "stillness" in store_stillness._base

    def test_location_index_per_env(self, monkeypatch):
        """Verify LocationIndex uses per-environment location file."""
        monkeypatch.setenv("DEPLOYMENT_ENV", "utopia")
        index_utopia = LocationIndex()

        monkeypatch.setenv("DEPLOYMENT_ENV", "stillness")
        index_stillness = LocationIndex()

        # Different paths per environment
        assert index_utopia._path != index_stillness._path
        assert "utopia" in index_utopia._path
        assert "stillness" in index_stillness._path

    def test_type_names_shared(self, monkeypatch):
        """Verify type_names uses shared data file."""
        # Just verify the function still works after refactoring
        result = get_type_name(1)
        assert isinstance(result, str)

    def test_galaxy_db_shared(self, monkeypatch):
        """Verify GalaxyDB uses shared database file."""
        monkeypatch.setenv("DEPLOYMENT_ENV", "utopia")
        db_utopia = GalaxyDB()
        path_utopia = db_utopia._path

        monkeypatch.setenv("DEPLOYMENT_ENV", "stillness")
        db_stillness = GalaxyDB()
        path_stillness = db_stillness._path

        # Same database for both environments
        assert path_utopia == path_stillness
        assert "eve_universe.db" in path_utopia


class TestPathStructure:
    """Test the structure and organization of data paths."""

    def test_data_directory_structure(self, monkeypatch):
        """Verify data directory structure is correctly organized."""
        # Test shared data
        systems_path = get_data_path("systems.json", env_specific=False)
        assert systems_path.endswith("data/systems.json")

        # Test environment-specific data
        monkeypatch.setenv("DEPLOYMENT_ENV", "utopia")
        utopia_index = get_data_path("system_index.json", env_specific=True)
        assert utopia_index.endswith("data/utopia/system_index.json")

        monkeypatch.setenv("DEPLOYMENT_ENV", "stillness")
        stillness_index = get_data_path("system_index.json", env_specific=True)
        assert stillness_index.endswith("data/stillness/system_index.json")

    def test_nested_env_specific_paths(self, monkeypatch):
        """Verify nested paths work correctly with env separation."""
        monkeypatch.setenv("DEPLOYMENT_ENV", "utopia")
        path = get_data_path("structures/keep-7a.json", env_specific=True)
        assert "data/utopia/structures/keep-7a.json" in path

        monkeypatch.setenv("DEPLOYMENT_ENV", "stillness")
        path = get_data_path("structures/keep-7a.json", env_specific=True)
        assert "data/stillness/structures/keep-7a.json" in path


class TestDefaultEnvironment:
    """Test behavior when DEPLOYMENT_ENV is not explicitly set."""

    def test_default_to_utopia(self, monkeypatch):
        """Verify default environment is Utopia."""
        monkeypatch.delenv("DEPLOYMENT_ENV", raising=False)
        path = get_data_path("system_index.json", env_specific=True)
        assert "utopia" in path

    def test_config_default_to_utopia(self, monkeypatch):
        """Verify config defaults to Utopia."""
        monkeypatch.delenv("DEPLOYMENT_ENV", raising=False)
        monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")
        monkeypatch.setenv("JWT_SECRET", "test-secret")

        config = load_config_from_env()
        assert config["deployment_env"] == "utopia"
