# tests/test_context_builder.py
from src.context_builder import build_context_block


def test_empty_inputs_produce_minimal_block():
    block = build_context_block(system_data=None, log_events=[], current_system=None)
    assert "LOCATION" in block
    assert "unknown" in block.lower()


def test_system_name_and_security_shown():
    system_data = {"name": "Jita", "security": 0.9}
    block = build_context_block(system_data=system_data, log_events=[], current_system="Jita")
    assert "Jita" in block
    assert "0.9" in block


def test_context_block_under_2000_chars():
    system_data = {"name": "Jita", "security": 0.9, "kills": list(range(100))}
    events = [{"type": "gamelog_raw", "msg_type": "notify", "text": "x" * 100} for _ in range(20)]
    block = build_context_block(system_data=system_data, log_events=events, current_system="Jita")
    assert len(block) <= 2000


def test_kill_count_shown():
    system_data = {"name": "Jita", "kills": [{"victim": f"Player{i}"} for i in range(50)]}
    block = build_context_block(system_data=system_data, log_events=[], current_system="Jita")
    assert "50" in block
    assert "kill" in block.lower()


def test_mining_summary_formatted():
    events = [{
        "type":        "mining_summary",
        "system":      "UTR-SN4",
        "duration_s":  2040,
        "materials":   {"Carbonaceous Ore": 847, "Hermetite": 312},
        "total_units": 1159,
        "cargo_fulls": 2,
    }]
    block = build_context_block(system_data=None, log_events=events, current_system="UTR-SN4")
    assert "MINING" in block
    assert "Carbonaceous Ore" in block
    assert "847" in block
    assert "Hermetite" in block
    assert "312" in block
    assert "cargo full" in block.lower()


def test_combat_summary_formatted():
    events = [{
        "type":         "combat_summary",
        "system":       "Ersetu",
        "duration_s":   90,
        "enemies":      {"Faulty Scout Drone": 3, "Faulty Repair Drone": 1},
        "damage_out":   1240,
        "damage_in":    280,
        "hits_out":     {"Penetrates": 5, "Grazes": 2},
        "hits_in":      {"Penetrates": 4},
        "weapons_used": ["Tier 3 Coilgun (S)"],
        "misses_out":   1,
        "misses_in":    0,
    }]
    block = build_context_block(system_data=None, log_events=events, current_system="Ersetu")
    assert "COMBAT" in block
    assert "Faulty Scout Drone" in block
    assert "1240" in block
    assert "280" in block
    assert "Tier 3 Coilgun (S)" in block
    assert "Penetrates" in block


def test_system_change_shown():
    events = [{"type": "system_change", "system": "UTR-SN4", "sender": "Keeper"}]
    block = build_context_block(system_data=None, log_events=events, current_system=None)
    assert "UTR-SN4" in block


def test_docking_accepted_shown():
    events = [{"type": "docking", "state": "accepted"}]
    block = build_context_block(system_data=None, log_events=events, current_system=None)
    assert "DOCKED" in block


def test_docking_requested_shows_location():
    events = [{"type": "docking", "state": "requested", "location": "Jita IV - Moon 4"}]
    block = build_context_block(system_data=None, log_events=events, current_system=None)
    assert "Jita IV" in block


def test_chat_pilots_shown():
    events = [
        {"type": "chat", "sender": "zaroot",  "message": "o7"},
        {"type": "chat", "sender": "ikeee",   "message": "gf"},
        {"type": "chat", "sender": "zaroot",  "message": "fly safe"},
    ]
    block = build_context_block(system_data=None, log_events=events, current_system=None)
    assert "LOCAL CHAT" in block
    assert "zaroot" in block


def test_autopilot_shown():
    events = [{"type": "autopilot", "state": "engaged"}]
    block = build_context_block(system_data=None, log_events=events, current_system=None)
    assert "AUTOPILOT" in block
    assert "engaged" in block


def test_gamelog_raw_not_shown():
    # Raw passthrough events should be silently skipped in the context block
    events = [{"type": "gamelog_raw", "msg_type": "notify", "text": "some ui noise"}]
    block = build_context_block(system_data=None, log_events=events, current_system=None)
    assert "some ui noise" not in block


def test_undock_shown():
    events = [{"type": "undock", "station": "Ersetu II - Keep #37", "system": "Ersetu"}]
    block = build_context_block(system_data=None, log_events=events, current_system=None)
    assert "UNDOCKED" in block
    assert "Ersetu II - Keep #37" in block
    assert "Ersetu" in block


def test_ship_stopping_shown():
    events = [{"type": "ship_stopping"}]
    block = build_context_block(system_data=None, log_events=events, current_system=None)
    assert "SHIP STOPPED" in block


def test_cargo_full_shown():
    events = [{"type": "cargo_full", "module": "Small Cutting Laser"}]
    block = build_context_block(system_data=None, log_events=events, current_system=None)
    assert "CARGO FULL" in block
    assert "Small Cutting Laser" in block


def test_transitions_capped_at_five():
    # 6 jumps — only the last 5 should appear; the first should be dropped
    events = [{"type": "system_change", "system": f"SYS{i}", "sender": "Keeper"} for i in range(6)]
    block = build_context_block(system_data=None, log_events=events, current_system=None)
    assert "SYS0" not in block
    for i in range(1, 6):
        assert f"SYS{i}" in block


def test_chat_single_sender():
    events = [
        {"type": "chat", "sender": "zaroot", "message": "o7"},
        {"type": "chat", "sender": "zaroot", "message": "fly safe"},
    ]
    block = build_context_block(system_data=None, log_events=events, current_system=None)
    assert "zaroot active" in block
    # Must NOT show a count when there's only one unique sender
    assert "pilots active" not in block


def test_chat_multiple_senders():
    events = [
        {"type": "chat", "sender": "zaroot", "message": "o7"},
        {"type": "chat", "sender": "ikeee",  "message": "gf"},
        {"type": "chat", "sender": "pvpgod",  "message": "die"},
    ]
    block = build_context_block(system_data=None, log_events=events, current_system=None)
    assert "pilots active" in block
    assert "zaroot" in block


def test_mining_no_cargo_fulls_omits_suffix():
    events = [{
        "type":        "mining_summary",
        "system":      "UTR-SN4",
        "duration_s":  600,
        "materials":   {"Carbonaceous Ore": 200},
        "total_units": 200,
        "cargo_fulls": 0,
    }]
    block = build_context_block(system_data=None, log_events=events, current_system="UTR-SN4")
    assert "MINING" in block
    assert "cargo full" not in block.lower()


def test_combat_no_hits_in_omits_hit_quality():
    events = [{
        "type":         "combat_summary",
        "system":       "Ersetu",
        "duration_s":   30,
        "enemies":      {"Faulty Scout Drone": 2},
        "damage_out":   500,
        "damage_in":    0,
        "hits_out":     {"Penetrates": 2},
        "hits_in":      {},
        "weapons_used": ["Base Autocannon (S)"],
        "misses_out":   0,
        "misses_in":    0,
    }]
    block = build_context_block(system_data=None, log_events=events, current_system="Ersetu")
    assert "COMBAT" in block
    # No incoming hits — no hit quality in parentheses in the damage segment
    combat_line = block.split("COMBAT")[1].split("\n")[0]
    dmg_part = combat_line.split("| dmg ")[1].split(" | ")[0]
    assert "(" not in dmg_part


def test_current_system_takes_priority_over_system_data_name():
    system_data = {"name": "DataName", "security": 0.5}
    block = build_context_block(system_data=system_data, log_events=[], current_system="LiveName")
    assert "LiveName" in block
    assert "DataName" not in block


def test_structure_alert_prepended_before_location():
    alerts = [{"type": "structure_alert", "structure_id": "keep-7a", "structure_name": "Keep-7A", "severity": "urgent", "message": "Shield below 20%."}]
    result = build_context_block(None, [], "UTR-SN4", structure_alerts=alerts)
    lines = result.split("\n")
    assert lines[0].startswith("STRUCTURE ALERT")
    assert "Keep-7A" in lines[0]
    assert "Shield below 20%." in lines[0]
    assert any("LOCATION" in l for l in lines)

def test_no_structure_alert_line_when_none():
    result = build_context_block(None, [], "UTR-SN4")
    assert "STRUCTURE ALERT" not in result

def test_multiple_structure_alerts_all_shown():
    alerts = [
        {"type": "structure_alert", "structure_id": "a", "structure_name": "A", "severity": "urgent", "message": "Msg1"},
        {"type": "structure_alert", "structure_id": "b", "structure_name": "B", "severity": "urgent", "message": "Msg2"},
    ]
    result = build_context_block(None, [], "UTR-SN4", structure_alerts=alerts)
    assert result.count("STRUCTURE ALERT") == 2


# ---------------------------------------------------------------------------
# Route planned
# ---------------------------------------------------------------------------

_SHORT_ROUTE = {
    "type":       "route_planned",
    "origin":     "jita",
    "destination": "utr-sn4",
    "path":       ["jita", "perimeter", "utr-sn4"],
    "jumps":      2,
    "gate_hops":  2,
    "direct_jumps": 0,
    "warnings":   [],
    "highlights": [],
    "est_time_min": None,
}


def test_route_planned_basic():
    block = build_context_block(None, [], "JITA", current_route=_SHORT_ROUTE)
    assert "ROUTE PLANNED" in block
    assert "JITA" in block
    assert "PERIMETER" in block
    assert "UTR-SN4" in block
    assert "2 jumps" in block


def test_route_planned_single_jump_singular():
    route = {**_SHORT_ROUTE, "path": ["jita", "perimeter"], "jumps": 1}
    block = build_context_block(None, [], "JITA", current_route=route)
    assert "1 jump" in block
    assert "1 jumps" not in block


def test_route_planned_est_time_shown():
    route = {**_SHORT_ROUTE, "est_time_min": 14}
    block = build_context_block(None, [], "JITA", current_route=route)
    assert "14 min" in block


def test_route_planned_no_est_time_omitted():
    block = build_context_block(None, [], "JITA", current_route=_SHORT_ROUTE)
    assert "est" not in block


def test_route_planned_warning_shown():
    route = {**_SHORT_ROUTE, "warnings": ["PERIMETER: O0-class star (37000K) — jump disruption risk"]}
    block = build_context_block(None, [], "JITA", current_route=route)
    assert "ROUTE WARN" in block
    assert "PERIMETER" in block
    assert "O0" in block


def test_route_planned_warnings_capped_at_three():
    route = {**_SHORT_ROUTE, "warnings": [f"WARN{i}" for i in range(5)]}
    block = build_context_block(None, [], "JITA", current_route=route)
    assert block.count("ROUTE WARN") == 3


def test_route_planned_highlight_shown():
    route = {**_SHORT_ROUTE, "highlights": ["UTR-SN4: 8 planets (Temperate, Gas) — resource-rich"]}
    block = build_context_block(None, [], "JITA", current_route=route)
    assert "ROUTE STOP" in block
    assert "8 planets" in block


def test_route_planned_highlights_capped_at_two():
    route = {**_SHORT_ROUTE, "highlights": [f"STOP{i}" for i in range(4)]}
    block = build_context_block(None, [], "JITA", current_route=route)
    assert block.count("ROUTE STOP") == 2


def test_route_planned_long_path_truncated():
    long_path = [f"sys{i}" for i in range(10)]
    route = {**_SHORT_ROUTE, "path": long_path, "jumps": 9}
    block = build_context_block(None, [], "SYS0", current_route=route)
    assert "ROUTE PLANNED" in block
    assert "9 jumps" in block
    # Intermediate systems not expanded inline
    assert "sys1" not in block
    assert "sys5" not in block
    # But origin and destination present
    assert "SYS0" in block
    assert "SYS9" in block


def test_route_planned_short_path_not_truncated():
    route = {**_SHORT_ROUTE}  # 3 systems — below threshold
    block = build_context_block(None, [], "JITA", current_route=route)
    # All 3 systems shown
    assert "JITA" in block
    assert "PERIMETER" in block
    assert "UTR-SN4" in block


def test_route_error_shown():
    route = {
        "type":     "route_planned",
        "error":    "No gate route found to DELTA",
        "path":     [],
        "jumps":    0,
        "warnings": [],
        "highlights": [],
    }
    block = build_context_block(None, [], "JITA", current_route=route)
    assert "ROUTE ERROR" in block
    assert "No gate route" in block
    assert "ROUTE PLANNED" not in block


def test_route_error_suppresses_path_display():
    route = {
        "type":  "route_planned",
        "error": "Unknown system: void",
        "path":  [],
        "jumps": 0,
        "warnings": [],
        "highlights": [],
    }
    block = build_context_block(None, [], "JITA", current_route=route)
    assert "ROUTE PLANNED" not in block


def test_no_route_when_none():
    block = build_context_block(None, [], "JITA", current_route=None)
    assert "ROUTE" not in block


def test_ship_profile_summary_in_context():
    from src.ship_profile import ShipProfile
    profile = ShipProfile(
        hull_mass=18_929_160, specific_heat=2.5, fuel_type="EU-90",
        fuel_quantity=2400, extra_cargo_kg=0, external_temp=0.0,
        adaptive_level=0, ship_type="Lai",
    )
    block = build_context_block(
        system_data=None,
        log_events=[],
        current_system="test",
        ship_profile=profile,
    )
    assert "SHIP:" in block
    assert "EU-90" in block
    assert "2400" in block
    assert "~" in block  # temp unknown → approximate range


def test_no_ship_profile_no_ship_line():
    block = build_context_block(
        system_data=None,
        log_events=[],
        current_system="test",
        ship_profile=None,
    )
    assert "SHIP:" not in block


# ---------------------------------------------------------------------------
# Phase 3: nearby_structures (PLAYER STRUCTURE lines)
# ---------------------------------------------------------------------------

_STRUCT = {"type_name": "SSU", "status": "ONLINE", "fuel_pct": 64.0, "services_online": 2, "system_name": "UTR-SN4"}


def test_player_structure_line_present_when_provided():
    block = build_context_block(None, [], "UTR-SN4", nearby_structures=[_STRUCT])
    assert "PLAYER STRUCTURE" in block
    assert "SSU" in block
    assert "ONLINE" in block


def test_player_structure_absent_when_empty_list():
    block = build_context_block(None, [], "UTR-SN4", nearby_structures=[])
    assert "PLAYER STRUCTURE" not in block


def test_player_structure_absent_when_none():
    block = build_context_block(None, [], "UTR-SN4", nearby_structures=None)
    assert "PLAYER STRUCTURE" not in block


def test_player_structure_capped_at_three():
    structs = [
        {"type_name": f"SSU{i}", "status": "ONLINE", "fuel_pct": 50.0, "services_online": 1, "system_name": "S"}
        for i in range(5)
    ]
    block = build_context_block(None, [], "S", nearby_structures=structs)
    assert block.count("PLAYER STRUCTURE") == 3


def test_player_structure_fuel_and_svc_shown():
    block = build_context_block(None, [], "UTR-SN4", nearby_structures=[_STRUCT])
    assert "fuel:64%" in block
    assert "2 svc" in block


def test_total_block_with_structures_under_2000():
    structs = [_STRUCT] * 3
    block = build_context_block(None, [], "UTR-SN4", nearby_structures=structs)
    assert len(block) <= 2000
