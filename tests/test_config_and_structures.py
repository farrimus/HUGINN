"""Unit tests for config system and structure loader (no app import)."""
import pytest
import json
import tempfile
from pathlib import Path


def test_config_loads_and_validates(monkeypatch):
    """Test that config loading and validation works."""
    # Set minimal env vars
    monkeypatch.setenv("DEPLOYMENT_ENV", "utopia")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-test")
    monkeypatch.setenv("JWT_SECRET", "test-secret")

    from src.config import load_config_from_env, validate_startup_config

    config = load_config_from_env()

    # Should have all expected keys
    assert "deployment_env" in config
    assert "anthropic_api_key" in config
    assert "jwt_secret" in config
    assert "world_api_url" in config
    assert "nova_rpc_url" in config
    assert config["deployment_env"] == "utopia"

    # Validate startup config
    errors = validate_startup_config(config)
    # May have errors due to missing VPS_SUI_ADDRESS, but config should load
    assert isinstance(errors, list)


def test_config_validation_catches_missing_keys(monkeypatch):
    """Test that validation catches missing required keys."""
    monkeypatch.setenv("DEPLOYMENT_ENV", "utopia")
    # Missing ANTHROPIC_API_KEY
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)

    from src.config import load_config_from_env, validate_startup_config

    config = load_config_from_env()
    errors = validate_startup_config(config)

    assert len(errors) > 0
    assert any("ANTHROPIC_API_KEY" in error for error in errors)


def test_load_structures_from_directory():
    """Test that structures can be loaded from data/structures directory."""
    from src.structure_loader import load_structures_from_directory

    structures = load_structures_from_directory("data/structures")

    # Should load at least some structures (or empty if directory is empty)
    assert isinstance(structures, list)

    # If there are structures, validate they have required fields
    for struct in structures:
        assert "id" in struct
        assert "system_name" in struct
        assert "owner_address" in struct
        assert "tier_registry_object_id" in struct
        assert "ssu_object_id" in struct


def test_structure_loader_validates_required_fields():
    """Test that structure loader validates required fields."""
    from src.structure_loader import validate_structure

    # Valid structure
    valid = {
        "id": "test",
        "system_name": "JITA",
        "owner_address": "0x442f3e5fa2c28d0c7e8f3c1b9a2e4d6f5c8b1a3e",
        "tier_registry_object_id": "0xf5ce",
        "ssu_object_id": "0xa6cd"
    }

    # Should not raise
    validate_structure(valid)
    assert "services" in valid  # Should add defaults
    assert "polling_enabled" in valid

    # Missing required field
    invalid = {
        "id": "test",
        "system_name": "JITA",
        # Missing owner_address, etc.
    }

    with pytest.raises(ValueError):
        validate_structure(invalid)


def test_structure_loader_creates_directory_if_missing(monkeypatch):
    """Test that structure loader creates directory if it doesn't exist."""
    with tempfile.TemporaryDirectory() as tmpdir:
        struct_dir = Path(tmpdir) / "structures"
        assert not struct_dir.exists()

        from src.structure_loader import load_structures_from_directory

        structures = load_structures_from_directory(str(struct_dir))

        # Directory should be created
        assert struct_dir.exists()
        assert structures == []


def test_structure_loader_multiple_files(monkeypatch):
    """Test that structure loader can load multiple structure files."""
    with tempfile.TemporaryDirectory() as tmpdir:
        struct_dir = Path(tmpdir)

        # Create two test structures
        for i in range(2):
            struct = {
                "id": f"test-keep-{i}",
                "system_name": "JITA",
                "owner_address": "0x442f3e5fa2c28d0c7e8f3c1b9a2e4d6f5c8b1a3e",
                "tier_registry_object_id": "0xf5ce",
                "ssu_object_id": "0xa6cd",
                "polling_enabled": False
            }
            (struct_dir / f"test-keep-{i}.json").write_text(json.dumps(struct))

        from src.structure_loader import load_structures_from_directory

        structures = load_structures_from_directory(str(struct_dir))

        assert len(structures) == 2
        assert structures[0]["id"] == "test-keep-0"
        assert structures[1]["id"] == "test-keep-1"


def test_structure_loader_rejects_mismatched_filename():
    """Test that structure loader rejects files where ID doesn't match filename."""
    with tempfile.TemporaryDirectory() as tmpdir:
        struct_dir = Path(tmpdir)

        # Create structure with ID that doesn't match filename
        struct = {
            "id": "correct-id",
            "system_name": "JITA",
            "owner_address": "0x442f3e5fa2c28d0c7e8f3c1b9a2e4d6f5c8b1a3e",
            "tier_registry_object_id": "0xf5ce",
            "ssu_object_id": "0xa6cd"
        }
        (struct_dir / "wrong-filename.json").write_text(json.dumps(struct))

        from src.structure_loader import load_structures_from_directory

        with pytest.raises(ValueError, match="doesn't match ID"):
            load_structures_from_directory(str(struct_dir))
