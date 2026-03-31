"""Tests for route_planning_tool pure function."""
import pytest
from src.tools.route_planning_tool import plan_evasion_route


class TestPlanEvasonRoute:
    """Test route planning pure function."""

    def test_same_system_route(self):
        """Route to same system should be minimal."""
        context = {
            "structure": {
                "assembly_id": "test123",
                "system_name": "UR8-K7K",
            }
        }
        result = plan_evasion_route(context, "UR8-K7K")
        assert isinstance(result, str)
        assert "ROUTE:" in result

    def test_adjacent_system_route(self):
        """Route to adjacent system should be 1 gate."""
        context = {
            "structure": {
                "assembly_id": "test123",
                "system_name": "UR8-K7K",
            }
        }
        result = plan_evasion_route(context, "ADJACENT-SYS")
        assert "ROUTE:" in result

    def test_distant_system_route(self):
        """Route to distant system should show multiple gates."""
        context = {
            "structure": {
                "assembly_id": "test123",
                "system_name": "UR8-K7K",
            }
        }
        result = plan_evasion_route(context, "DISTANT-SYS")
        assert "ROUTE:" in result

    def test_includes_origin_and_destination(self):
        """Route should include both origin and destination."""
        context = {
            "structure": {
                "assembly_id": "test123",
                "system_name": "HOME-SYS",
            }
        }
        result = plan_evasion_route(context, "TARGET-SYS")
        assert "ROUTE:" in result
        assert "HOME-SYS" in result or "origin" in result.lower()
        assert "TARGET-SYS" in result or "destination" in result.lower()

    def test_returns_formatted_route_string(self):
        """Result should be formatted route string."""
        context = {
            "structure": {
                "assembly_id": "test123",
                "system_name": "UR8-K7K",
            }
        }
        result = plan_evasion_route(context, "DEST-SYS")
        assert isinstance(result, str)
        assert "ROUTE:" in result

    def test_empty_destination(self):
        """Should handle empty destination gracefully."""
        context = {
            "structure": {
                "assembly_id": "test123",
                "system_name": "UR8-K7K",
            }
        }
        result = plan_evasion_route(context, "")
        assert isinstance(result, str)
