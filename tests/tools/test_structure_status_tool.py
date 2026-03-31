"""Tests for structure_status_tool pure function."""
import pytest
from src.tools.structure_status_tool import get_structure_status


class TestGetStructureStatus:
    """Test structure status pure function."""

    def test_basic_structure_status(self):
        """Should format structure status block."""
        context = {
            "structure": {
                "assembly_id": "abc123",
                "structure_name": "Test Station",
                "system_name": "UR8-K7K",
                "shield_pct": 85.0,
                "fuel_pct": 72.0,
                "services_online": 3,
                "services_total": 5,
                "docked_ships": [],
            }
        }
        result = get_structure_status(context)
        assert isinstance(result, str)
        assert "assembly_id" in result.lower() or "abc123" in result
        assert "shield" in result.lower()
        assert "fuel" in result.lower()
        assert "85" in result
        assert "72" in result

    def test_with_docked_ships(self):
        """Should list docked ships."""
        context = {
            "structure": {
                "assembly_id": "xyz789",
                "structure_name": "Docking Station",
                "system_name": "UR8-K7K",
                "shield_pct": 90.0,
                "fuel_pct": 80.0,
                "services_online": 5,
                "services_total": 5,
                "docked_ships": [
                    {"type_name": "Corvette"},
                    {"type_name": "Frigate"},
                ],
            }
        }
        result = get_structure_status(context)
        assert "Corvette" in result or "docked" in result.lower()

    def test_critical_shield(self):
        """Should highlight critical shield levels."""
        context = {
            "structure": {
                "assembly_id": "danger123",
                "structure_name": "Vulnerable Station",
                "system_name": "UR8-K7K",
                "shield_pct": 5.0,
                "fuel_pct": 50.0,
                "services_online": 2,
                "services_total": 5,
                "docked_ships": [],
            }
        }
        result = get_structure_status(context)
        assert "5" in result

    def test_returns_formatted_status(self):
        """Result should be formatted status string."""
        context = {
            "structure": {
                "assembly_id": "test",
                "structure_name": "Test",
                "system_name": "UR8-K7K",
                "shield_pct": 50.0,
                "fuel_pct": 50.0,
                "services_online": 3,
                "services_total": 5,
                "docked_ships": [],
            }
        }
        result = get_structure_status(context)
        assert isinstance(result, str)
        assert len(result) > 0

    def test_handles_missing_services(self):
        """Should handle structures with no services field."""
        context = {
            "structure": {
                "assembly_id": "minimal",
                "structure_name": "Minimal Station",
                "system_name": "UR8-K7K",
                "shield_pct": 100.0,
                "fuel_pct": 100.0,
            }
        }
        result = get_structure_status(context)
        assert isinstance(result, str)
