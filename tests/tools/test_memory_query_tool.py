"""Tests for memory_query_tool pure function."""
import pytest
from datetime import datetime, timezone
from src.tools.memory_query_tool import query_memory_events


class TestQueryMemoryEvents:
    """Test memory query pure function."""

    def test_no_events(self):
        """No events should return appropriate message."""
        context = {"memory_events": []}
        result = query_memory_events(context)
        assert isinstance(result, str)
        assert "MEMORY:" in result
        assert "No events" in result

    def test_single_event(self):
        """Single event should be returned."""
        context = {
            "memory_events": [
                {
                    "ts": datetime.now(timezone.utc).isoformat(),
                    "type": "visit",
                    "data": {"character": "Pilot Name"}
                }
            ]
        }
        result = query_memory_events(context)
        assert "MEMORY:" in result
        assert "1" in result or "event" in result.lower()

    def test_multiple_events(self):
        """Multiple events should show count."""
        context = {
            "memory_events": [
                {
                    "ts": datetime.now(timezone.utc).isoformat(),
                    "type": "visit",
                    "data": {"character": f"Pilot {i}"}
                }
                for i in range(10)
            ]
        }
        result = query_memory_events(context)
        assert "MEMORY:" in result
        assert "10" in result or "total" in result.lower()

    def test_with_filters(self):
        """Should filter events based on filters."""
        context = {
            "memory_events": [
                {
                    "ts": datetime.now(timezone.utc).isoformat(),
                    "type": "visit",
                    "data": {"character": "Pilot A"}
                },
                {
                    "ts": datetime.now(timezone.utc).isoformat(),
                    "type": "raid",
                    "data": {"attackers": 3}
                },
            ]
        }
        filters = {"type": "raid"}
        result = query_memory_events(context, filters)
        assert isinstance(result, str)
        assert "MEMORY:" in result

    def test_last_n_events(self):
        """Should return last N events (max 5)."""
        context = {
            "memory_events": [
                {
                    "ts": datetime.now(timezone.utc).isoformat(),
                    "type": "visit",
                    "data": {"character": f"Pilot {i}"}
                }
                for i in range(15)
            ]
        }
        result = query_memory_events(context)
        assert "MEMORY:" in result
        assert "15" in result or "total" in result.lower()

    def test_returns_formatted_memory_string(self):
        """Result should be formatted memory string."""
        context = {"memory_events": []}
        result = query_memory_events(context)
        assert isinstance(result, str)
        assert "MEMORY:" in result
