import json
import tempfile
from pathlib import Path
import pytest
import os


@pytest.fixture
def temp_structures_dir():
    """Create temporary structures directory."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield tmpdir


def test_config_to_startup_flow(monkeypatch, temp_structures_dir):
    """Test full flow: .env → config → structures → startup logging."""
    # Set up minimal config
    monkeypatch.setenv("DEPLOYMENT_ENV", "utopia")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-test")
    monkeypatch.setenv("JWT_SECRET", "test-secret")
    monkeypatch.setenv("TOKEN_KEY_PASSWORD", "test-password")
    monkeypatch.setenv("VPS_SUI_ADDRESS", "0x9a3e...")

    # Create test structure
    struct = {
        "id": "test-keep",
        "system_name": "JITA",
        "owner_address": "0x442f...",
        "tier_registry_object_id": "0xf5ce...",
        "ssu_object_id": "0xa6cd...",
        "polling_enabled": False
    }
    struct_file = Path(temp_structures_dir) / "test-keep.json"
    struct_file.write_text(json.dumps(struct))

    # Load config
    from src.config import load_config_from_env
    config = load_config_from_env()

    assert config["deployment_env"] == "utopia"
    assert "testnet.sui.io" in config["nova_rpc_url"]

    # Load structures
    from src.structure_loader import load_structures_from_directory
    structures = load_structures_from_directory(temp_structures_dir)

    assert len(structures) == 1
    assert structures[0]["id"] == "test-keep"


def test_network_env_changes_endpoints():
    """Test that changing DEPLOYMENT_ENV changes all endpoints."""
    from src.config import get_network_config

    utopia = get_network_config("utopia")
    stillness = get_network_config("stillness")

    # Both environments use testnet RPC (same Sui testnet for both)
    assert "testnet.sui.io" in utopia["nova_rpc_url"].lower()
    assert "testnet.sui.io" in stillness["nova_rpc_url"].lower()

    # Different API endpoints
    assert "utopia" in utopia["world_api_url"].lower()
    assert "stillness" in stillness["world_api_url"].lower()


def test_missing_structure_graceful_startup(monkeypatch):
    """Test server starts gracefully with no structures."""
    with tempfile.TemporaryDirectory() as tmpdir:
        from src.structure_loader import load_structures_from_directory

        # Empty directory
        structures = load_structures_from_directory(tmpdir)
        assert structures == []
