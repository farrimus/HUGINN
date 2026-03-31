"""Tests for alert_detection_tool pure function."""
import pytest
from src.tools.alert_detection_tool import detect_alerts


class TestDetectAlerts:
    """Test alert detection pure function."""

    def test_no_alerts(self):
        """Healthy structure should have no alerts."""
        context = {
            "structure": {
                "assembly_id": "safe123",
                "structure_name": "Safe Station",
                "shield_pct": 95.0,
                "fuel_pct": 80.0,
            }
        }
        result = detect_alerts(context)
        assert isinstance(result, str)
        assert "ALERTS:" in result
        assert "None" in result

    def test_shield_alert(self):
        """Shield < 20% should trigger alert."""
        context = {
            "structure": {
                "assembly_id": "danger123",
                "structure_name": "Damaged Station",
                "shield_pct": 15.0,
                "fuel_pct": 80.0,
            }
        }
        result = detect_alerts(context)
        assert "ALERTS:" in result
        assert ("shield" in result.lower() or "15" in result)

    def test_fuel_alert(self):
        """Fuel < 10% should trigger urgent alert."""
        context = {
            "structure": {
                "assembly_id": "empty123",
                "structure_name": "Empty Station",
                "shield_pct": 95.0,
                "fuel_pct": 5.0,
            }
        }
        result = detect_alerts(context)
        assert "ALERTS:" in result
        assert ("fuel" in result.lower() or "5" in result)

    def test_multiple_alerts(self):
        """Multiple conditions should list multiple alerts."""
        context = {
            "structure": {
                "assembly_id": "critical123",
                "structure_name": "Critical Station",
                "shield_pct": 10.0,
                "fuel_pct": 5.0,
            }
        }
        result = detect_alerts(context)
        assert "ALERTS:" in result
        # Should mention both critical conditions

    def test_returns_formatted_alert_string(self):
        """Result should be formatted alert string."""
        context = {
            "structure": {
                "assembly_id": "test",
                "structure_name": "Test",
                "shield_pct": 50.0,
                "fuel_pct": 50.0,
            }
        }
        result = detect_alerts(context)
        assert isinstance(result, str)
        assert "ALERTS:" in result
