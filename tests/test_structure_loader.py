import pytest
import json
import tempfile
from pathlib import Path
from src.structure_loader import load_structures_from_directory, validate_structure, get_structure_by_id


def test_load_structures_empty_directory():
    """Test loading from empty directory returns empty list."""
    with tempfile.TemporaryDirectory() as tmpdir:
        structures = load_structures_from_directory(tmpdir)
        assert structures == []


def test_load_structures_single_valid():
    """Test loading single valid structure JSON."""
    with tempfile.TemporaryDirectory() as tmpdir:
        struct = {
            "id": "keep-7a",
            "system_name": "JITA",
            "owner_address": "0x442f3e5fa2c28d0c7e8f3c1b9a2e4d6f5c8b1a3e",
            "tier_registry_object_id": "0xf5ceffdbe44bb38e4796d7b885d0d95c5047fd2fe2e2a4e62eb5865512f64708",
            "ssu_object_id": "0xa6cdad6b62d093dff11ea1b7ca665c561eb9ee4214f9e8a26d83a34fc0f1bc81",
            "services": ["repair"],
            "polling_enabled": True
        }
        Path(tmpdir, "keep-7a.json").write_text(json.dumps(struct))

        structures = load_structures_from_directory(tmpdir)
        assert len(structures) == 1
        assert structures[0]["id"] == "keep-7a"


def test_load_structures_missing_required_field():
    """Test that missing required field raises ValueError."""
    with tempfile.TemporaryDirectory() as tmpdir:
        struct = {
            "id": "test",
            "system_name": "JITA",
            # Missing: owner_address, tier_registry_object_id, ssu_object_id
        }
        Path(tmpdir, "test.json").write_text(json.dumps(struct))

        with pytest.raises(ValueError, match="Missing required fields"):
            load_structures_from_directory(tmpdir)


def test_load_structures_filename_mismatch():
    """Test that filename must match id."""
    with tempfile.TemporaryDirectory() as tmpdir:
        struct = {
            "id": "keep-7a",
            "system_name": "JITA",
            "owner_address": "0x442f...",
            "tier_registry_object_id": "0xf5ce...",
            "ssu_object_id": "0xa6cd...",
        }
        # File is keep-07a.json but id is keep-7a
        Path(tmpdir, "keep-07a.json").write_text(json.dumps(struct))

        with pytest.raises(ValueError, match="doesn't match ID"):
            load_structures_from_directory(tmpdir)


def test_load_structures_invalid_json():
    """Test that invalid JSON raises ValueError."""
    with tempfile.TemporaryDirectory() as tmpdir:
        Path(tmpdir, "invalid.json").write_text("{ bad json }")

        with pytest.raises(ValueError, match="Invalid JSON"):
            load_structures_from_directory(tmpdir)


def test_load_structures_multiple_sorted():
    """Test that multiple structures are loaded and sorted by ID."""
    with tempfile.TemporaryDirectory() as tmpdir:
        for struct_id in ["zebra-01", "alpha-01", "middle-01"]:
            struct = {
                "id": struct_id,
                "system_name": "TEST",
                "owner_address": "0x...",
                "tier_registry_object_id": "0x...",
                "ssu_object_id": "0x...",
            }
            Path(tmpdir, f"{struct_id}.json").write_text(json.dumps(struct))

        structures = load_structures_from_directory(tmpdir)
        assert len(structures) == 3
        ids = [s["id"] for s in structures]
        assert ids == ["alpha-01", "middle-01", "zebra-01"]


def test_validate_structure_required_fields():
    """Test structure validation."""
    valid = {
        "id": "test",
        "system_name": "JITA",
        "owner_address": "0x...",
        "tier_registry_object_id": "0x...",
        "ssu_object_id": "0x...",
    }
    # Should not raise
    validate_structure(valid)


def test_validate_structure_optional_fields():
    """Test that optional fields have sensible defaults."""
    struct = {
        "id": "test",
        "system_name": "JITA",
        "owner_address": "0x...",
        "tier_registry_object_id": "0x...",
        "ssu_object_id": "0x...",
        "services": ["repair", "reprocess"],
        "polling_enabled": False
    }
    validate_structure(struct)
    assert struct["services"] == ["repair", "reprocess"]
    assert struct["polling_enabled"] is False


def test_validate_structure_defaults_optional_fields():
    """Test that optional fields get defaults."""
    struct = {
        "id": "test",
        "system_name": "JITA",
        "owner_address": "0x...",
        "tier_registry_object_id": "0x...",
        "ssu_object_id": "0x...",
    }
    validate_structure(struct)
    # After validation, optional fields should have sensible defaults
    assert struct["services"] == []
    assert struct["polling_enabled"] is True


def test_get_structure_by_id_found():
    """Test that get_structure_by_id finds structure by ID."""
    structures = [
        {"id": "keep-7a", "system_name": "JITA"},
        {"id": "forge-03", "system_name": "HIGHSEC"}
    ]
    result = get_structure_by_id(structures, "keep-7a")
    assert result is not None
    assert result["id"] == "keep-7a"


def test_get_structure_by_id_not_found():
    """Test that get_structure_by_id returns None when not found."""
    structures = [{"id": "keep-7a", "system_name": "JITA"}]
    result = get_structure_by_id(structures, "missing-id")
    assert result is None


def test_get_structure_by_id_empty_list():
    """Test that get_structure_by_id handles empty list."""
    result = get_structure_by_id([], "anything")
    assert result is None


def test_load_structures_creates_missing_directory():
    """Test that load_structures_from_directory creates directory if missing."""
    with tempfile.TemporaryDirectory() as tmpdir:
        nonexistent = Path(tmpdir) / "missing" / "structures"
        structures = load_structures_from_directory(str(nonexistent))
        assert structures == []
        assert nonexistent.exists()


def test_load_structures_ignores_non_json_files():
    """Test that non-JSON files in directory are ignored."""
    with tempfile.TemporaryDirectory() as tmpdir:
        # Create a non-JSON file that should be ignored
        Path(tmpdir, "readme.txt").write_text("This should be ignored")
        Path(tmpdir, "config.bak").write_text("Also ignored")

        structures = load_structures_from_directory(tmpdir)
        assert structures == []
