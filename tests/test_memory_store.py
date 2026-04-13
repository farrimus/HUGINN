# tests/test_memory_store.py
import os, json, pytest
from datetime import datetime, timezone, timedelta
from src.memory_store import MemoryStore

@pytest.fixture
def store(tmp_path):
    return MemoryStore(base_dir=str(tmp_path), structure_id="test-ssu")

def test_bootstrap_creates_directory(tmp_path):
    store = MemoryStore(base_dir=str(tmp_path), structure_id="new-ssu")
    store.bootstrap()
    assert os.path.isdir(os.path.join(str(tmp_path), "new-ssu"))
    assert os.path.exists(os.path.join(str(tmp_path), "new-ssu", "events.jsonl"))
    assert os.path.exists(os.path.join(str(tmp_path), "new-ssu", "summary.json"))

def test_bootstrap_idempotent(store):
    store.bootstrap()
    store.bootstrap()  # should not raise

def test_append_event(store):
    store.bootstrap()
    store.append_event("killmail", 30000142, {"kill_id": 1, "victim_name": "Bob"})
    lines = open(store._events_path()).readlines()
    assert len(lines) == 1
    event = json.loads(lines[0])
    assert event["type"] == "killmail"
    assert event["system_id"] == 30000142
    assert event["data"]["kill_id"] == 1
    assert "ts" in event

def test_append_multiple_events(store):
    store.bootstrap()
    store.append_event("killmail", 1, {"kill_id": 1})
    store.append_event("ssu_state", 1, {"fuel_pct": 80.0})
    lines = open(store._events_path()).readlines()
    assert len(lines) == 2

def test_search_events_finds_keyword(store):
    store.bootstrap()
    store.append_event("killmail", 1, {"kill_id": 42, "victim_name": "EVE_PILOT_X"})
    store.append_event("docking", 1, {"pilot_address": "0xaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa", "character_name": "Other"})
    results = store.search_events("EVE_PILOT_X", days=7)
    assert len(results) == 1
    assert results[0]["type"] == "killmail"

def test_search_events_respects_days(store):
    store.bootstrap()
    # Write an old event manually
    old_ts = (datetime.now(timezone.utc) - timedelta(days=10)).strftime("%Y-%m-%dT%H:%M:%SZ")
    with open(store._events_path(), "a") as f:
        f.write(json.dumps({"ts": old_ts, "type": "docking", "system_id": 1,
                            "data": {"pilot_address": "0xold"}}) + "\n")
    results = store.search_events("0xold", days=7)
    assert len(results) == 0

def test_search_events_returns_most_recent_first(store):
    store.bootstrap()
    store.append_event("killmail", 1, {"kill_id": 1, "victim_name": "alpha"})
    store.append_event("killmail", 1, {"kill_id": 2, "victim_name": "alpha"})
    results = store.search_events("alpha", days=7)
    assert results[0]["data"]["kill_id"] == 2  # most recent first

def test_upsert_pilot_creates_new(store):
    store.bootstrap()
    store.upsert_pilot("0xaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa", character_name="Alice", character_id=123, tier="OWNER")
    profile = store.get_pilot("0xaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa")
    assert profile["character_name"] == "Alice"
    assert profile["visit_count"] == 1
    assert profile["first_seen"] == profile["last_seen"]

def test_upsert_pilot_updates_existing(store):
    store.bootstrap()
    store.upsert_pilot("0xaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa", character_name="Alice", character_id=123, tier="OWNER")
    store.upsert_pilot("0xaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa", character_name="Alice", character_id=123, tier="OWNER")
    profile = store.get_pilot("0xaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa")
    assert profile["visit_count"] == 2

def test_get_pilot_returns_none_if_missing(store):
    store.bootstrap()
    assert store.get_pilot("0xbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb") is None

def test_rebuild_summary(store):
    store.bootstrap()
    store.append_event("docking", 1, {"pilot_address": "0xa", "character_name": "Alice"})
    store.append_event("killmail", 1, {"kill_id": 1, "victim_name": "Bob"})
    store.rebuild_summary()
    summary = store.get_summary()
    assert summary["text"] != ""
    assert "docking" in summary["text"].lower() or "1" in summary["text"]

def test_rebuild_summary_truncates_to_300(store):
    store.bootstrap()
    for i in range(100):
        store.append_event("killmail", 1, {"kill_id": i, "victim_name": f"Pilot{i}"})
    store.rebuild_summary()
    summary = store.get_summary()
    assert len(summary["text"]) <= 300
