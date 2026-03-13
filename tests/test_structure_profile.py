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
