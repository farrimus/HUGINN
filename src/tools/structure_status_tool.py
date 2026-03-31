"""
Structure status tool — pure function for formatting structure status.

Pure function: takes context dict, returns formatted status string.
No RPC calls, no I/O, deterministic.
"""

from typing import Dict, Any


def get_structure_status(context: Dict[str, Any]) -> str:
    """
    Format structure status information from context.

    Args:
        context: Dict with key {structure} containing structure data

    Returns:
        Formatted status block with assembly_id, location, shield%, fuel%, docked ships, services
    """
    structure = context.get("structure", {})

    if not structure:
        return "STATUS: No structure data available"

    assembly_id = structure.get("assembly_id", "Unknown")
    structure_name = structure.get("structure_name", "Unknown")
    system_name = structure.get("system_name", "Unknown")
    shield_pct = structure.get("shield_pct", 0)
    fuel_pct = structure.get("fuel_pct", 0)
    services_online = structure.get("services_online", 0)
    services_total = structure.get("services_total", 0)
    docked_ships = structure.get("docked_ships", [])

    # Build status string
    lines = []
    lines.append(f"STATUS: {assembly_id}")
    lines.append(f"  Location: {system_name} | Shield: {shield_pct:.0f}% | Fuel: {fuel_pct:.0f}%")
    lines.append(f"  Services: {services_online}/{services_total}")

    if docked_ships:
        ship_types = ", ".join(
            ship.get("type_name", "Unknown") for ship in docked_ships[:5]
        )
        lines.append(f"  Docked: {ship_types}")

    return "\n".join(lines)
