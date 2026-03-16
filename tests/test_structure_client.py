import pytest
from src.structure_profile import StructureProfile
from src.structure_client import build_structure_context, detect_alerts, LobbyClient, LOBBY_SYSTEM_PROMPT

def make_profile(**kwargs):
    base = dict(structure_id="keep-7a", owner_address="0xabc",
                structure_name="Keep-7A", structure_type="Smart Storage Unit",
                system_name="UTR-SN4", shield_pct=97.0, fuel_pct=84.0,
                services_online=3, services_total=3, docked_count=2)
    base.update(kwargs)
    return StructureProfile(**base)

def test_context_includes_structure_name():
    ctx = build_structure_context(make_profile(), "OWNER")
    assert "Keep-7A" in ctx

def test_context_includes_system_name():
    ctx = build_structure_context(make_profile(), "OWNER")
    assert "UTR-SN4" in ctx

def test_context_includes_shield_and_fuel_for_owner():
    ctx = build_structure_context(make_profile(shield_pct=97.0, fuel_pct=84.0), "OWNER")
    assert "97" in ctx
    assert "84" in ctx

def test_context_hides_shield_fuel_for_vetted():
    ctx = build_structure_context(make_profile(shield_pct=97.0, fuel_pct=84.0), "VETTED")
    # Assert on the STATUS line label, not bare numbers that could appear elsewhere
    assert "shield:" not in ctx.lower()
    assert "fuel:" not in ctx.lower()
    assert "STATUS" not in ctx

def test_detect_no_alerts_when_healthy():
    alerts = detect_alerts(make_profile(shield_pct=97.0, fuel_pct=84.0))
    assert alerts == []

def test_detect_urgent_alert_low_shield():
    alerts = detect_alerts(make_profile(shield_pct=18.0, fuel_pct=50.0))
    urgent = [a for a in alerts if a["severity"] == "urgent"]
    assert any("shield" in a["message"].lower() for a in urgent)

def test_detect_urgent_alert_critical_fuel():
    alerts = detect_alerts(make_profile(shield_pct=97.0, fuel_pct=8.0))
    urgent = [a for a in alerts if a["severity"] == "urgent"]
    assert any("fuel" in a["message"].lower() for a in urgent)

def test_detect_routine_alert_low_fuel():
    alerts = detect_alerts(make_profile(shield_pct=97.0, fuel_pct=22.0))
    routine = [a for a in alerts if a["severity"] == "routine"]
    assert any("fuel" in a["message"].lower() for a in routine)

def test_detect_no_duplicate_alerts():
    # fuel at 8% triggers urgent only, not both urgent and routine
    alerts = detect_alerts(make_profile(shield_pct=97.0, fuel_pct=8.0))
    fuel_alerts = [a for a in alerts if "fuel" in a["message"].lower()]
    severities = [a["severity"] for a in fuel_alerts]
    assert severities.count("urgent") <= 1
    assert severities.count("routine") == 0  # urgent takes priority


def test_lobby_prompt_has_no_internal_data():
    prompt = LOBBY_SYSTEM_PROMPT.format(
        structure_name="Keep-7A",
        structure_type="Smart Storage Unit",
        system_name="JITA",
    )
    assert "Keep-7A" in prompt
    assert "fuel" not in prompt.lower()
    assert "shield" not in prompt.lower()
    # Restricted language must be present
    assert "restricted" in prompt.lower()

def test_lobby_client_instantiates():
    client = LobbyClient()
    assert client is not None

import json, os

def make_profile_with_system(**kwargs):
    base = dict(structure_id="keep-7a", owner_address="0xabc",
                structure_name="Keep-7A", structure_type="Smart Storage Unit",
                system_name="UTR-SN4", region_name="Deep Space", system_id=30000001,
                shield_pct=97.0, fuel_pct=84.0,
                services_online=3, services_total=3, docked_count=2)
    base.update(kwargs)
    return StructureProfile(**base)

def test_context_includes_region_name():
    ctx = build_structure_context(make_profile_with_system(), "OWNER")
    assert "Deep Space" in ctx

def test_context_cap_is_2000():
    from src.structure_client import CONTEXT_CAP
    assert CONTEXT_CAP == 2000

def test_context_removes_local_pilots_line():
    ctx = build_structure_context(make_profile_with_system(), "OWNER")
    assert "LOCAL:" not in ctx
    assert "pilots in system" not in ctx

def test_context_vetted_hides_status():
    ctx = build_structure_context(make_profile_with_system(), "VETTED")
    assert "STATUS" not in ctx
    assert "shield:" not in ctx.lower()

def test_system_prompt_includes_region_name():
    from src.structure_client import StructureClient
    client = StructureClient()
    prompt = client.build_system_prompt(
        make_profile_with_system(region_name="The Forge"),
        "OWNER", "Alice", 123
    )
    assert "The Forge" in prompt

def test_context_with_memory_block(tmp_path):
    from src.memory_store import MemoryStore
    store = MemoryStore(base_dir=str(tmp_path), structure_id="keep-7a")
    store.bootstrap()
    store.append_event("docking", 1, {"pilot_address": "0xa", "character_name": "Bob"})
    store.rebuild_summary()
    summary = store.get_summary()
    ctx = build_structure_context(make_profile_with_system(), "OWNER", memory_text=summary["text"])
    assert "[STRUCTURE MEMORY]" in ctx  # must be injected as named block


# ---------------------------------------------------------------------------
# Phase 1: ASSEMBLIES line
# ---------------------------------------------------------------------------

def make_profile_with_assemblies(**kwargs):
    base = dict(structure_id="keep-7a", owner_address="0xabc",
                structure_name="Keep-7A", structure_type="Smart Storage Unit",
                system_name="UTR-SN4", region_name="Deep Space", system_id=30000001,
                shield_pct=97.0, fuel_pct=84.0,
                services_online=2, services_total=2, docked_count=0,
                connected_assemblies=[
                    {"object_id": "0xGATE01", "type_name": "Smart Gate", "status": "ONLINE"},
                    {"object_id": "0xTURRET01", "type_name": "Smart Turret", "status": "ONLINE"},
                    {"object_id": "0xTURRET02", "type_name": "Smart Turret", "status": "OFFLINE"},
                ])
    base.update(kwargs)
    return StructureProfile(**base)


def test_assemblies_line_present_for_owner():
    ctx = build_structure_context(make_profile_with_assemblies(), "OWNER")
    assert "ASSEMBLIES:" in ctx
    assert "Smart Gate" in ctx
    assert "Smart Turret" in ctx


def test_assemblies_line_absent_for_vetted():
    ctx = build_structure_context(make_profile_with_assemblies(), "VETTED")
    assert "ASSEMBLIES:" not in ctx


def test_assemblies_line_absent_when_empty():
    profile = make_profile_with_assemblies(connected_assemblies=[])
    ctx = build_structure_context(profile, "OWNER")
    assert "ASSEMBLIES:" not in ctx


def test_assemblies_counts_online_vs_total():
    ctx = build_structure_context(make_profile_with_assemblies(), "OWNER")
    # Smart Turret has 2 total, 1 online
    assert "1 ONLINE" in ctx


# ---------------------------------------------------------------------------
# Phase 2: INVENTORY line
# ---------------------------------------------------------------------------

def make_profile_with_inventory(**kwargs):
    base = dict(structure_id="keep-7a", owner_address="0xabc",
                structure_name="Keep-7A", structure_type="Smart Storage Unit",
                system_name="UTR-SN4", shield_pct=97.0, fuel_pct=84.0,
                services_online=1, services_total=1, docked_count=0,
                ssu_inventory=[
                    {"type_name": "Tritanium", "quantity": 500},
                    {"type_name": "Fuel Block", "quantity": 10},
                ])
    base.update(kwargs)
    return StructureProfile(**base)


def test_inventory_line_present_for_owner():
    ctx = build_structure_context(make_profile_with_inventory(), "OWNER")
    assert "INVENTORY:" in ctx
    assert "Tritanium" in ctx
    assert "500" in ctx


def test_inventory_line_absent_for_vetted():
    ctx = build_structure_context(make_profile_with_inventory(), "VETTED")
    assert "INVENTORY:" not in ctx


def test_inventory_line_absent_when_empty():
    profile = make_profile_with_inventory(ssu_inventory=[])
    ctx = build_structure_context(profile, "OWNER")
    assert "INVENTORY:" not in ctx
