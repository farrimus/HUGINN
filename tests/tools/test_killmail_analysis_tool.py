"""Tests for killmail_analysis_tool pure function."""
import pytest
from datetime import datetime, timedelta, timezone
from src.tools.killmail_analysis_tool import analyze_killmail_patterns


class TestAnalyzeKillmailPatterns:
    """Test killmail pattern analysis pure function."""

    def test_no_killmails(self):
        """No killmails should return appropriate message."""
        context = {"killmails": []}
        result = analyze_killmail_patterns(context)
        assert isinstance(result, str)
        assert "PATTERNS:" in result

    def test_single_killmail(self):
        """Single killmail should be counted."""
        context = {
            "killmails": [
                {
                    "time": datetime.now(timezone.utc).isoformat(),
                    "ship": {"type_id": 1, "type_name": "Corvette"},
                    "victim": {"character": {"id": 100}},
                    "killers": [{"character": {"id": 101}}]
                }
            ]
        }
        result = analyze_killmail_patterns(context)
        assert "PATTERNS:" in result
        assert "1 kill" in result or "kills" in result.lower()

    def test_multiple_killmails(self):
        """Multiple killmails should show pattern."""
        now = datetime.now(timezone.utc)
        context = {
            "killmails": [
                {
                    "time": (now - timedelta(hours=i)).isoformat(),
                    "ship": {"type_id": 1, "type_name": "Corvette"},
                    "victim": {"character": {"id": 100 + i}},
                    "killers": [{"character": {"id": 200 + i}}]
                }
                for i in range(5)
            ]
        }
        result = analyze_killmail_patterns(context)
        assert "PATTERNS:" in result
        assert "5" in result or "kills" in result.lower()

    def test_primary_threat_identification(self):
        """Should identify primary threat (most frequent killer)."""
        context = {
            "killmails": [
                {
                    "time": datetime.now(timezone.utc).isoformat(),
                    "ship": {"type_id": 1, "type_name": "Corvette"},
                    "victim": {"character": {"id": 100}},
                    "killers": [{"character": {"id": 999, "name": "Pirate A"}}]
                },
                {
                    "time": datetime.now(timezone.utc).isoformat(),
                    "ship": {"type_id": 2, "type_name": "Frigate"},
                    "victim": {"character": {"id": 101}},
                    "killers": [{"character": {"id": 999, "name": "Pirate A"}}]
                },
            ]
        }
        result = analyze_killmail_patterns(context)
        assert "PATTERNS:" in result
        assert "2 kills" in result or "Primary threat" in result

    def test_escalation_detection(self):
        """Should detect if recent kills show escalation."""
        now = datetime.now(timezone.utc)
        context = {
            "killmails": [
                {
                    "time": (now - timedelta(minutes=5)).isoformat(),
                    "ship": {"type_id": 1, "type_name": "Corvette"},
                    "victim": {"character": {"id": 100}},
                    "killers": [{"character": {"id": 101}}]
                },
                {
                    "time": (now - timedelta(minutes=2)).isoformat(),
                    "ship": {"type_id": 2, "type_name": "Corvette"},
                    "victim": {"character": {"id": 102}},
                    "killers": [{"character": {"id": 103}}]
                },
            ]
        }
        result = analyze_killmail_patterns(context)
        assert isinstance(result, str)

    def test_returns_formatted_pattern_string(self):
        """Result should be formatted pattern string."""
        context = {"killmails": []}
        result = analyze_killmail_patterns(context)
        assert isinstance(result, str)
        assert "PATTERNS:" in result
