# log-agent/tests/test_session_tracker.py
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

import time
import session_tracker as st_module
from session_tracker import SessionTracker

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def make_combat_out(damage=100, target="Faulty Scout Drone", weapon="Base Autocannon (S)", hit="Penetrates"):
    return {"type": "combat_out", "damage": damage, "target": target, "weapon": weapon, "hit": hit}

def make_combat_in(damage=50, source="Faulty Scout Drone", hit="Grazes"):
    return {"type": "combat_in", "damage": damage, "source": source, "hit": hit}

def make_mining(quantity=100, material="Carbonaceous Ore"):
    return {"type": "mining", "quantity": quantity, "material": material}

def make_system_change(system="UTR-SN4"):
    return {"type": "system_change", "system": system, "sender": "Keeper"}

# ---------------------------------------------------------------------------
# Combat session
# ---------------------------------------------------------------------------

def test_combat_events_absorbed():
    tracker = SessionTracker()
    out = tracker.process(make_combat_out(damage=200))
    assert out == []  # absorbed, not forwarded

def test_combat_in_absorbed():
    tracker = SessionTracker()
    out = tracker.process(make_combat_in(damage=50))
    assert out == []

def test_combat_session_summary_on_system_change():
    tracker = SessionTracker()
    tracker.process(make_combat_out(damage=300, target="Faulty Scout Drone", hit="Smashes"))
    tracker.process(make_combat_in(damage=80, source="Faulty Scout Drone", hit="Grazes"))

    out = tracker.process(make_system_change("Ersetu"))

    summaries = [e for e in out if e["type"] == "combat_summary"]
    assert len(summaries) == 1
    s = summaries[0]
    assert s["damage_out"] == 300
    assert s["damage_in"] == 80
    assert "Faulty Scout Drone" in s["enemies"]
    assert s["hits_out"]["Smashes"] == 1
    assert s["hits_in"]["Grazes"] == 1
    assert "Base Autocannon (S)" in s["weapons_used"]

def test_system_change_passed_through():
    tracker = SessionTracker()
    out = tracker.process(make_system_change("Ersetu"))
    assert any(e["type"] == "system_change" for e in out)

def test_system_change_updates_system():
    tracker = SessionTracker()
    tracker.process(make_system_change("Ersetu"))
    tracker.process(make_combat_out())
    out = tracker.process(make_system_change("UTR-SN4"))
    summary = next(e for e in out if e["type"] == "combat_summary")
    assert summary["system"] == "Ersetu"

def test_combat_miss_tracked():
    tracker = SessionTracker()
    tracker.process({"type": "combat_miss", "direction": "outgoing", "weapon": "Coilgun", "target": "Drone"})
    tracker.process({"type": "combat_miss", "direction": "incoming", "source": "Drone"})
    out = tracker.process(make_system_change())
    s = next(e for e in out if e["type"] == "combat_summary")
    assert s["misses_out"] == 1
    assert s["misses_in"] == 1

def test_sightline_adds_enemy():
    tracker = SessionTracker()
    tracker.process({"type": "sightline_blocked", "source": "Faulty Repair Drone"})
    out = tracker.process(make_system_change())
    s = next(e for e in out if e["type"] == "combat_summary")
    assert "Faulty Repair Drone" in s["enemies"]

def test_combat_session_closes_on_docking():
    tracker = SessionTracker()
    tracker.process(make_combat_out())
    out = tracker.process({"type": "docking", "state": "accepted"})
    assert any(e["type"] == "combat_summary" for e in out)

# ---------------------------------------------------------------------------
# Mining session
# ---------------------------------------------------------------------------

def test_mining_events_absorbed():
    tracker = SessionTracker()
    out = tracker.process(make_mining(100, "Carbonaceous Ore"))
    assert out == []

def test_mining_session_accumulates():
    tracker = SessionTracker()
    tracker.process(make_mining(100, "Carbonaceous Ore"))
    tracker.process(make_mining(50,  "Carbonaceous Ore"))
    tracker.process(make_mining(200, "Hermetite"))
    out = tracker.process(make_system_change())
    s = next(e for e in out if e["type"] == "mining_summary")
    assert s["materials"]["Carbonaceous Ore"] == 150
    assert s["materials"]["Hermetite"] == 200
    assert s["total_units"] == 350

def test_mining_cargo_full_counted():
    tracker = SessionTracker()
    tracker.process(make_mining(100, "Ore"))
    tracker.process({"type": "cargo_full", "module": "Asteroid Mining Laser"})
    tracker.process({"type": "cargo_full", "module": "Asteroid Mining Laser"})
    out = tracker.process(make_system_change())
    s = next(e for e in out if e["type"] == "mining_summary")
    assert s["cargo_fulls"] == 2

def test_cargo_full_passes_through_regardless():
    tracker = SessionTracker()
    # No open mining session
    out = tracker.process({"type": "cargo_full", "module": "Mining Laser"})
    assert any(e["type"] == "cargo_full" for e in out)

def test_mining_session_closes_on_docking():
    tracker = SessionTracker()
    tracker.process(make_mining(300, "Ore"))
    out = tracker.process({"type": "docking", "state": "requested", "location": "Ersetu II"})
    assert any(e["type"] == "mining_summary" for e in out)

# ---------------------------------------------------------------------------
# Pass-through events
# ---------------------------------------------------------------------------

def test_autopilot_passes_through():
    tracker = SessionTracker()
    out = tracker.process({"type": "autopilot", "state": "engaged"})
    assert out == [{"type": "autopilot", "state": "engaged"}]

def test_chat_passes_through():
    tracker = SessionTracker()
    out = tracker.process({"type": "chat", "sender": "zaroot", "message": "o7"})
    assert out[0]["sender"] == "zaroot"

def test_ship_stopping_passes_through():
    tracker = SessionTracker()
    out = tracker.process({"type": "ship_stopping"})
    assert out == [{"type": "ship_stopping"}]

def test_gamelog_raw_passes_through():
    tracker = SessionTracker()
    e = {"type": "gamelog_raw", "msg_type": "notify", "text": "some message"}
    assert tracker.process(e) == [e]

# ---------------------------------------------------------------------------
# Flush on shutdown
# ---------------------------------------------------------------------------

def test_flush_emits_open_sessions():
    tracker = SessionTracker()
    tracker.process(make_combat_out(damage=500))
    tracker.process(make_mining(200, "Ore"))
    out = tracker.flush()
    types = {e["type"] for e in out}
    assert "combat_summary" in types
    assert "mining_summary" in types

def test_flush_clears_sessions():
    tracker = SessionTracker()
    tracker.process(make_combat_out())
    tracker.flush()
    out = tracker.flush()
    assert out == []

# ---------------------------------------------------------------------------
# Timeout (fast path — patch monotonic clock)
# ---------------------------------------------------------------------------

def test_combat_timeout_emits_summary(monkeypatch):
    tracker = SessionTracker()
    tracker.process(make_combat_out(damage=100))

    # Wind the clock forward past the timeout
    original = time.monotonic
    monkeypatch.setattr(st_module.time, "monotonic",
                        lambda: original() + st_module.COMBAT_TIMEOUT_S + 1)

    # Next event triggers the stale check
    out = tracker.process({"type": "ship_stopping"})
    assert any(e["type"] == "combat_summary" for e in out)

def test_mining_timeout_emits_summary(monkeypatch):
    tracker = SessionTracker()
    tracker.process(make_mining(100, "Ore"))

    original = time.monotonic
    monkeypatch.setattr(st_module.time, "monotonic",
                        lambda: original() + st_module.MINING_TIMEOUT_S + 1)

    out = tracker.process({"type": "ship_stopping"})
    assert any(e["type"] == "mining_summary" for e in out)

# ---------------------------------------------------------------------------
# current_system property
# ---------------------------------------------------------------------------

def test_current_system_initially_none():
    tracker = SessionTracker()
    assert tracker.current_system is None

def test_current_system_set_by_system_change():
    tracker = SessionTracker()
    tracker.process(make_system_change("Ersetu"))
    assert tracker.current_system == "Ersetu"

def test_current_system_set_by_undock_when_unknown():
    tracker = SessionTracker()
    tracker.process({"type": "undock", "station": "Ersetu II - Keep #37", "system": "Ersetu"})
    assert tracker.current_system == "Ersetu"

def test_undock_does_not_override_known_system():
    tracker = SessionTracker()
    tracker.process(make_system_change("UTR-SN4"))
    tracker.process({"type": "undock", "station": "Ersetu II - Keep #37", "system": "Ersetu"})
    # system_change already set the system; undock must not overwrite it
    assert tracker.current_system == "UTR-SN4"
