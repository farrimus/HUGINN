# tests/test_memory_store.py
import os, json, pytest, time
from datetime import datetime, timezone, timedelta
from unittest.mock import AsyncMock, patch
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
    store.append_event("docking", 1, {"pilot_address": "0xabc", "character_name": "Other"})
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
    store.upsert_pilot("0xabc", character_name="Alice", character_id=123, tier="OWNER")
    profile = store.get_pilot("0xabc")
    assert profile["character_name"] == "Alice"
    assert profile["visit_count"] == 1
    assert profile["first_seen"] == profile["last_seen"]

def test_upsert_pilot_updates_existing(store):
    store.bootstrap()
    store.upsert_pilot("0xabc", character_name="Alice", character_id=123, tier="OWNER")
    store.upsert_pilot("0xabc", character_name="Alice", character_id=123, tier="OWNER")
    profile = store.get_pilot("0xabc")
    assert profile["visit_count"] == 2

def test_get_pilot_returns_none_if_missing(store):
    store.bootstrap()
    assert store.get_pilot("0xnotexist") is None

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

# ------------------------------------------------------------------
# Killmail methods tests
# ------------------------------------------------------------------

def test_filter_killmails_by_recency_with_recent_timestamps(store):
    """Test filtering keeps killmails within the time window."""
    now = time.time()
    recent_ts = now - 3600  # 1 hour ago
    old_ts = now - (48 * 3600)  # 48 hours ago

    killmails = [
        {"kill_id": 1, "timestamp": recent_ts},
        {"kill_id": 2, "timestamp": old_ts},
    ]

    filtered = store.filter_killmails_by_recency(killmails, hours=24)
    assert len(filtered) == 1
    assert filtered[0]["kill_id"] == 1


def test_filter_killmails_by_recency_returns_most_recent_first(store):
    """Test that filtered killmails are sorted by recency (newest first)."""
    now = time.time()
    ts1 = now - 1000
    ts2 = now - 500
    ts3 = now - 100

    killmails = [
        {"kill_id": 1, "timestamp": ts1},
        {"kill_id": 3, "timestamp": ts3},
        {"kill_id": 2, "timestamp": ts2},
    ]

    filtered = store.filter_killmails_by_recency(killmails, hours=24)
    assert len(filtered) == 3
    assert filtered[0]["kill_id"] == 3  # Most recent first
    assert filtered[1]["kill_id"] == 2
    assert filtered[2]["kill_id"] == 1


def test_filter_killmails_by_recency_handles_missing_timestamp(store):
    """Test that killmails without timestamps are skipped."""
    now = time.time()
    killmails = [
        {"kill_id": 1, "timestamp": now - 1000},
        {"kill_id": 2},  # Missing timestamp
        {"kill_id": 3, "timestamp": now - 500},
    ]

    filtered = store.filter_killmails_by_recency(killmails, hours=24)
    assert len(filtered) == 2
    kill_ids = [km["kill_id"] for km in filtered]
    assert 2 not in kill_ids


def test_filter_killmails_by_recency_handles_millisecond_timestamps(store):
    """Test that timestamps in milliseconds are converted to seconds."""
    now = time.time()
    now_ms = now * 1000
    recent_ms = now_ms - 3600000  # 1 hour ago in ms
    old_ms = now_ms - (48 * 3600000)  # 48 hours ago in ms

    killmails = [
        {"kill_id": 1, "timestamp": recent_ms},
        {"kill_id": 2, "timestamp": old_ms},
    ]

    filtered = store.filter_killmails_by_recency(killmails, hours=24)
    assert len(filtered) == 1
    assert filtered[0]["kill_id"] == 1


def test_filter_killmails_by_recency_empty_list(store):
    """Test that empty list returns empty list."""
    filtered = store.filter_killmails_by_recency([], hours=24)
    assert filtered == []


def test_filter_killmails_by_recency_different_hour_windows(store):
    """Test filtering with various hour windows."""
    now = time.time()
    killmails = [
        {"kill_id": 1, "timestamp": now - 1800},  # 30 min ago
        {"kill_id": 2, "timestamp": now - 7200},  # 2 hours ago
        {"kill_id": 3, "timestamp": now - 14400},  # 4 hours ago
    ]

    # 1 hour window
    filtered = store.filter_killmails_by_recency(killmails, hours=1)
    assert len(filtered) == 1
    assert filtered[0]["kill_id"] == 1

    # 3 hour window
    filtered = store.filter_killmails_by_recency(killmails, hours=3)
    assert len(filtered) == 2

    # 5 hour window
    filtered = store.filter_killmails_by_recency(killmails, hours=5)
    assert len(filtered) == 3


def test_get_most_recent_killmail_timestamp_with_list(store):
    """Test finding most recent timestamp from a list."""
    now = time.time()
    killmails = [
        {"kill_id": 1, "timestamp": now - 3600},
        {"kill_id": 2, "timestamp": now - 100},
        {"kill_id": 3, "timestamp": now - 7200},
    ]

    ts = store.get_most_recent_killmail_timestamp(killmails)
    assert ts == now - 100


def test_get_most_recent_killmail_timestamp_empty_list(store):
    """Test that empty list returns None."""
    ts = store.get_most_recent_killmail_timestamp([])
    assert ts is None


def test_get_most_recent_killmail_timestamp_missing_timestamp_field(store):
    """Test that killmails without timestamp are skipped."""
    now = time.time()
    killmails = [
        {"kill_id": 1, "timestamp": now - 3600},
        {"kill_id": 2},  # No timestamp
        {"kill_id": 3, "timestamp": now - 7200},
    ]

    ts = store.get_most_recent_killmail_timestamp(killmails)
    assert ts == now - 3600


def test_get_most_recent_killmail_timestamp_all_missing(store):
    """Test that list with no valid timestamps returns None."""
    killmails = [
        {"kill_id": 1},
        {"kill_id": 2},
    ]

    ts = store.get_most_recent_killmail_timestamp(killmails)
    assert ts is None


@pytest.mark.asyncio
async def test_get_killmails_for_system_returns_list(store):
    """Test that get_killmails_for_system returns a list."""
    mock_api = AsyncMock()
    now = time.time()
    mock_api.get_killmails.return_value = [
        {"kill_id": 1, "timestamp": now - 1000},
        {"kill_id": 2, "timestamp": now - 500},
    ]

    store.world_api = mock_api
    result = await store.get_killmails_for_system(30000142)

    assert isinstance(result, list)
    assert len(result) == 2
    mock_api.get_killmails.assert_called_once_with(30000142)


@pytest.mark.asyncio
async def test_get_killmails_for_system_applies_recency_filter(store):
    """Test that get_killmails_for_system filters by recency."""
    mock_api = AsyncMock()
    now = time.time()
    mock_api.get_killmails.return_value = [
        {"kill_id": 1, "timestamp": now - 1000},  # recent
        {"kill_id": 2, "timestamp": now - (48 * 3600)},  # old (>24 hours)
    ]

    store.world_api = mock_api
    result = await store.get_killmails_for_system(30000142, hours=24)

    assert len(result) == 1
    assert result[0]["kill_id"] == 1


@pytest.mark.asyncio
async def test_get_killmails_for_system_limits_to_10(store):
    """Test that get_killmails_for_system returns at most 10 killmails."""
    mock_api = AsyncMock()
    now = time.time()
    killmails = [
        {"kill_id": i, "timestamp": now - i}
        for i in range(20)
    ]
    mock_api.get_killmails.return_value = killmails

    store.world_api = mock_api
    result = await store.get_killmails_for_system(30000142)

    assert len(result) == 10


@pytest.mark.asyncio
async def test_get_killmails_for_system_returns_most_recent_first(store):
    """Test that results are sorted by most recent first."""
    mock_api = AsyncMock()
    now = time.time()
    mock_api.get_killmails.return_value = [
        {"kill_id": 1, "timestamp": now - 3600},
        {"kill_id": 2, "timestamp": now - 100},
        {"kill_id": 3, "timestamp": now - 7200},
    ]

    store.world_api = mock_api
    result = await store.get_killmails_for_system(30000142)

    assert result[0]["kill_id"] == 2  # Most recent first
    assert result[1]["kill_id"] == 1
    assert result[2]["kill_id"] == 3


@pytest.mark.asyncio
async def test_get_killmails_for_system_handles_api_error(store):
    """Test that API errors return empty list."""
    mock_api = AsyncMock()
    mock_api.get_killmails.side_effect = Exception("API error")

    store.world_api = mock_api
    result = await store.get_killmails_for_system(30000142)

    assert result == []


@pytest.mark.asyncio
async def test_get_killmails_for_system_returns_empty_when_no_api(store):
    """Test that None world_api returns empty list."""
    store.world_api = None
    result = await store.get_killmails_for_system(30000142)

    assert result == []


@pytest.mark.asyncio
async def test_get_killmails_for_system_handles_empty_api_response(store):
    """Test that empty API response returns empty list."""
    mock_api = AsyncMock()
    mock_api.get_killmails.return_value = []

    store.world_api = mock_api
    result = await store.get_killmails_for_system(30000142)

    assert result == []


@pytest.mark.asyncio
async def test_get_killmails_for_system_custom_hours_window(store):
    """Test that custom hours window is applied correctly."""
    mock_api = AsyncMock()
    now = time.time()
    mock_api.get_killmails.return_value = [
        {"kill_id": 1, "timestamp": now - 3600},  # 1 hour ago
        {"kill_id": 2, "timestamp": now - (5 * 3600)},  # 5 hours ago
        {"kill_id": 3, "timestamp": now - (25 * 3600)},  # 25 hours ago
    ]

    store.world_api = mock_api

    # 6-hour window should include first two
    result = await store.get_killmails_for_system(30000142, hours=6)
    assert len(result) == 2

    # 30-hour window should include all
    result = await store.get_killmails_for_system(30000142, hours=30)
    assert len(result) == 3
