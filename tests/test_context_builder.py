# tests/test_context_builder.py
from src.context_builder import build_context_block

def test_empty_inputs_produce_minimal_block():
    block = build_context_block(system_data=None, log_events=[], current_system=None)
    assert "CURRENT SYSTEM" in block
    assert "unknown" in block.lower()

def test_system_data_included():
    system_data = {"name": "Jita", "security": 0.9}
    block = build_context_block(system_data=system_data, log_events=[], current_system="Jita")
    assert "Jita" in block
    assert "0.9" in block

def test_log_events_included():
    events = [
        {"type": "jump", "system": "Jita", "timestamp": "12:00"},
        {"type": "combat", "target": "Rogue Drone", "damage": 450},
    ]
    block = build_context_block(system_data=None, log_events=events, current_system=None)
    assert "jump" in block
    assert "combat" in block

def test_context_block_under_2000_chars():
    # 2000 char hard cap
    system_data = {"name": "Jita", "security": 0.9, "kills": list(range(100))}
    events = [{"type": "event", "data": "x" * 100} for _ in range(20)]
    block = build_context_block(system_data=system_data, log_events=events, current_system="Jita")
    assert len(block) <= 2000

def test_killmails_summarised_not_dumped():
    system_data = {"name": "Jita", "kills": [{"victim": f"Player{i}"} for i in range(50)]}
    block = build_context_block(system_data=system_data, log_events=[], current_system="Jita")
    assert "Player49" not in block  # not dumping raw list
    assert "kill" in block.lower()
    assert "50" in block  # actual count shown


def test_system_change_event_formatted():
    events = [{"type": "system_change", "system": "Amarr"}]
    block = build_context_block(system_data=None, log_events=events, current_system=None)
    assert "Amarr" in block


def test_docking_event_formatted():
    events = [{"type": "docking", "location": "Jita IV - Moon 4"}]
    block = build_context_block(system_data=None, log_events=events, current_system=None)
    assert "Jita IV" in block
