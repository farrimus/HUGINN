import pytest
import os
import json
import tempfile
from src.structure_profile import StructureProfile, load_profile, save_profile, profile_path

def test_default_profile_fields():
    p = StructureProfile(structure_id="keep-7a", owner_address="0xabc")
    assert p.structure_id == "keep-7a"
    assert p.owner_address == "0xabc"
    assert p.structure_name == "keep-7a"  # defaults to id
    assert p.routine_alerts == []

def test_save_and_load_roundtrip(tmp_path):
    p = StructureProfile(
        structure_id="keep-7a",
        owner_address="0xabc",
        structure_name="Keep-7A",
        structure_type="Smart Storage Unit",
        system_name="UTR-SN4",
        owner_character_id=12345,
        nova_registry_object_id="0xreg123",
    )
    path = tmp_path / "structures" / "keep-7a.json"
    save_profile(p, base_dir=str(tmp_path))
    loaded = load_profile("keep-7a", base_dir=str(tmp_path))
    assert loaded.structure_name == "Keep-7A"
    assert loaded.owner_character_id == 12345

def test_load_nonexistent_returns_none(tmp_path):
    result = load_profile("no-such-structure", base_dir=str(tmp_path))
    assert result is None

def test_add_routine_alert(tmp_path):
    p = StructureProfile(structure_id="keep-7a", owner_address="0xabc")
    p.routine_alerts.append({"message": "Fuel at 24%", "ts": 1000})
    save_profile(p, base_dir=str(tmp_path))
    loaded = load_profile("keep-7a", base_dir=str(tmp_path))
    assert len(loaded.routine_alerts) == 1

def test_as_dict_owner_tier():
    p = StructureProfile(structure_id="keep-7a", owner_address="0xabc",
                         structure_name="Keep-7A", system_name="UTR-SN4",
                         shield_pct=97.0, fuel_pct=84.0, services_online=3, services_total=3,
                         docked_count=2)
    d = p.as_dict_for_tier("OWNER")
    assert d["shield_pct"] == 97.0
    assert d["fuel_pct"] == 84.0
    assert d["docked_count"] == 2

def test_as_dict_vetted_tier_hides_sensitive_fields():
    p = StructureProfile(structure_id="keep-7a", owner_address="0xabc",
                         shield_pct=97.0, fuel_pct=84.0, services_online=3,
                         docked_count=2)
    d = p.as_dict_for_tier("VETTED")
    assert "shield_pct" not in d
    assert "fuel_pct" not in d
    assert "services_online" not in d
    assert "docked_count" not in d
    assert d["structure_id"] == "keep-7a"

def test_invalid_structure_id_raises():
    from src.structure_profile import profile_path
    import pytest
    with pytest.raises(ValueError):
        profile_path("../../../etc/passwd")
    with pytest.raises(ValueError):
        profile_path("valid; rm -rf /")

def test_new_fields_have_defaults():
    p = StructureProfile(structure_id="test-1", owner_address="0xabc")
    assert p.region_name == ""
    assert p.system_id == 0

def test_new_fields_survive_roundtrip(tmp_path):
    p = StructureProfile(
        structure_id="test-2",
        owner_address="0xabc",
        region_name="The Forge",
        system_id=30000142,
    )
    save_profile(p, base_dir=str(tmp_path))
    loaded = load_profile("test-2", base_dir=str(tmp_path))
    assert loaded.region_name == "The Forge"
    assert loaded.system_id == 30000142

def test_old_profile_json_missing_new_fields_gets_defaults(tmp_path):
    """Profiles created before this change load fine — new fields default to empty/0."""
    import json, os
    old_data = {"structure_id": "old-1", "owner_address": "0xdef",
                "structure_name": "Old", "structure_type": "Smart Storage Unit",
                "system_name": "", "owner_character_id": 0,
                "nova_registry_object_id": "", "created_at": "",
                "shield_pct": 100.0, "fuel_pct": 100.0,
                "services_online": 0, "services_total": 0,
                "docked_count": 0, "routine_alerts": []}
    os.makedirs(str(tmp_path), exist_ok=True)
    with open(os.path.join(str(tmp_path), "old-1.json"), "w") as f:
        json.dump(old_data, f)
    loaded = load_profile("old-1", base_dir=str(tmp_path))
    assert loaded is not None
    assert loaded.region_name == ""
    assert loaded.system_id == 0

def test_profile_json_with_extra_unknown_field_loads_without_error(tmp_path):
    """Future profile versions with extra keys must not crash load_profile."""
    import json, os
    data = {"structure_id": "future-1", "owner_address": "0xdef",
            "structure_name": "Future", "structure_type": "Smart Storage Unit",
            "system_name": "", "owner_character_id": 0,
            "nova_registry_object_id": "", "created_at": "",
            "shield_pct": 100.0, "fuel_pct": 100.0,
            "services_online": 0, "services_total": 0,
            "docked_count": 0, "routine_alerts": [],
            "region_name": "Test Region", "system_id": 42,
            "unknown_future_field": "ignored"}
    os.makedirs(str(tmp_path), exist_ok=True)
    with open(os.path.join(str(tmp_path), "future-1.json"), "w") as f:
        json.dump(data, f)
    loaded = load_profile("future-1", base_dir=str(tmp_path))
    assert loaded is not None
    assert loaded.region_name == "Test Region"
    assert not hasattr(loaded, "unknown_future_field")
