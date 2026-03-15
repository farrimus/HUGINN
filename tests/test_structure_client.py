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
