# tests/test_log_buffer.py
import pytest
from src.log_buffer import LogBuffer, log_buffer

@pytest.fixture(autouse=True)
def reset_global_buffer():
    log_buffer.events.clear()
    log_buffer.current_system = None
    yield

def test_add_event_stores_in_buffer():
    buf = LogBuffer(max_size=50)
    buf.add({"type": "jump", "system": "Jita"})
    assert len(buf.events) == 1

def test_buffer_caps_at_max_size():
    buf = LogBuffer(max_size=3)
    for i in range(5):
        buf.add({"type": "jump", "system": f"System{i}"})
    assert len(buf.events) == 3

def test_buffer_drops_oldest_when_full():
    buf = LogBuffer(max_size=3)
    for i in range(5):
        buf.add({"type": "jump", "system": f"System{i}"})
    assert buf.events[0]["system"] == "System2"

def test_get_recent_returns_last_n():
    buf = LogBuffer(max_size=50)
    for i in range(20):
        buf.add({"type": "event", "index": i})
    recent = buf.get_recent(10)
    assert len(recent) == 10
    assert recent[-1]["index"] == 19

def test_get_recent_returns_all_if_fewer_than_n():
    buf = LogBuffer(max_size=50)
    buf.add({"type": "event", "index": 0})
    assert len(buf.get_recent(10)) == 1

def test_system_change_events_tracked():
    buf = LogBuffer(max_size=50)
    buf.add({"type": "system_change", "system": "Amarr"})
    assert buf.current_system == "Amarr"

def test_current_system_defaults_to_none():
    buf = LogBuffer(max_size=50)
    assert buf.current_system is None

def test_non_system_change_does_not_update_current_system():
    buf = LogBuffer(max_size=50)
    buf.add({"type": "combat_summary", "system": "Ersetu"})
    assert buf.current_system is None

def test_current_system_updates_on_subsequent_jumps():
    buf = LogBuffer(max_size=50)
    buf.add({"type": "system_change", "system": "Ersetu"})
    buf.add({"type": "system_change", "system": "UTR-SN4"})
    assert buf.current_system == "UTR-SN4"

def test_add_structure_alert_stores_event():
    buf = LogBuffer(max_size=50)
    alert = {"type": "structure_alert", "structure_id": "keep-7a", "severity": "urgent", "message": "Shield below 20%."}
    buf.add_structure_alert(alert)
    alerts = buf.pop_structure_alerts()
    assert len(alerts) == 1
    assert alerts[0]["message"] == "Shield below 20%."

def test_pop_structure_alerts_clears_list():
    buf = LogBuffer(max_size=50)
    buf.add_structure_alert({"type": "structure_alert", "structure_id": "keep-7a", "severity": "urgent", "message": "Test"})
    buf.pop_structure_alerts()
    assert buf.pop_structure_alerts() == []

def test_multiple_structure_alerts_accumulate():
    buf = LogBuffer(max_size=50)
    buf.add_structure_alert({"type": "structure_alert", "structure_id": "keep-7a", "severity": "urgent", "message": "A"})
    buf.add_structure_alert({"type": "structure_alert", "structure_id": "forge-1", "severity": "urgent", "message": "B"})
    alerts = buf.pop_structure_alerts()
    assert len(alerts) == 2

def test_structure_alerts_do_not_go_in_ring_buffer():
    buf = LogBuffer(max_size=50)
    buf.add_structure_alert({"type": "structure_alert", "structure_id": "keep-7a", "severity": "urgent", "message": "A"})
    assert all(e.get("type") != "structure_alert" for e in buf.get_recent(50))
