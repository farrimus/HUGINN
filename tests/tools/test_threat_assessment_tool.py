"""Tests for threat_assessment_tool pure function."""
import pytest
from datetime import datetime, timedelta, timezone
from src.tools.threat_assessment_tool import assess_threat_level


class TestAssessThreatLevel:
    """Test threat assessment pure function."""

    def test_no_kills_recent(self):
        """With no recent kills, threat should be LOW."""
        context = {
            "structure": {},
            "killmails": [],
            "memory_events": []
        }
        result = assess_threat_level(context, hours_lookback=24)
        assert "LOW" in result
        assert "0 kills" in result

    def test_few_kills_medium_threat(self):
        """2-5 kills in 24h should be MEDIUM."""
        now = datetime.now(timezone.utc)
        killmails = [
            {
                "time": (now - timedelta(hours=1)).isoformat(),
                "ship": {"type_id": 1},
                "victim": {"character": {"id": 100}},
                "killers": [{"character": {"id": 101}}]
            },
            {
                "time": (now - timedelta(hours=2)).isoformat(),
                "ship": {"type_id": 2},
                "victim": {"character": {"id": 102}},
                "killers": [{"character": {"id": 103}}]
            },
        ]
        context = {
            "structure": {},
            "killmails": killmails,
            "memory_events": []
        }
        result = assess_threat_level(context, hours_lookback=24)
        assert "MEDIUM" in result or "2 kills" in result

    def test_many_kills_high_threat(self):
        """6-10 kills in 24h should be HIGH."""
        now = datetime.now(timezone.utc)
        killmails = [
            {
                "time": (now - timedelta(hours=i)).isoformat(),
                "ship": {"type_id": 1},
                "victim": {"character": {"id": 100 + i}},
                "killers": [{"character": {"id": 200 + i}}]
            }
            for i in range(7)
        ]
        context = {
            "structure": {},
            "killmails": killmails,
            "memory_events": []
        }
        result = assess_threat_level(context, hours_lookback=24)
        assert "HIGH" in result or "7 kills" in result

    def test_critical_threat(self):
        """11+ kills in 24h should be CRITICAL."""
        now = datetime.now(timezone.utc)
        killmails = [
            {
                "time": (now - timedelta(hours=i)).isoformat(),
                "ship": {"type_id": 1},
                "victim": {"character": {"id": 100 + i}},
                "killers": [{"character": {"id": 200 + i}}]
            }
            for i in range(12)
        ]
        context = {
            "structure": {},
            "killmails": killmails,
            "memory_events": []
        }
        result = assess_threat_level(context, hours_lookback=24)
        assert "CRITICAL" in result or "12 kills" in result

    def test_hours_lookback_window(self):
        """Only kills within hours_lookback window should count."""
        now = datetime.now(timezone.utc)
        killmails = [
            {
                "time": (now - timedelta(hours=1)).isoformat(),
                "ship": {"type_id": 1},
                "victim": {"character": {"id": 100}},
                "killers": [{"character": {"id": 101}}]
            },
            {
                "time": (now - timedelta(hours=10)).isoformat(),
                "ship": {"type_id": 2},
                "victim": {"character": {"id": 102}},
                "killers": [{"character": {"id": 103}}]
            },
        ]
        context = {
            "structure": {},
            "killmails": killmails,
            "memory_events": []
        }
        # Only 1 kill in 6 hour window
        result = assess_threat_level(context, hours_lookback=6)
        assert "1 kill" in result

    def test_returns_formatted_string(self):
        """Result should be formatted threat string."""
        context = {
            "structure": {},
            "killmails": [],
            "memory_events": []
        }
        result = assess_threat_level(context, hours_lookback=24)
        assert isinstance(result, str)
        assert "THREAT:" in result
        assert "|" in result
        assert "kills" in result

    def test_handles_missing_timestamp(self):
        """Should gracefully handle killmails with missing timestamps."""
        killmails = [
            {
                "ship": {"type_id": 1},
                "victim": {"character": {"id": 100}},
                "killers": [{"character": {"id": 101}}]
                # No 'time' field
            }
        ]
        context = {
            "structure": {},
            "killmails": killmails,
            "memory_events": []
        }
        result = assess_threat_level(context, hours_lookback=24)
        assert isinstance(result, str)
        assert "THREAT:" in result
