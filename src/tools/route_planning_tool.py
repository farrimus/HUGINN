"""
Route planning tool — pure function for planning evasion routes.

Pure function: takes context dict and destination, returns formatted route string.
No RPC calls, no I/O, deterministic. Uses simplified gate routing (no pathfinding).
"""

from typing import Dict, Any


def plan_evasion_route(context: Dict[str, Any], destination: str) -> str:
    """
    Plan an evasion route from current structure to destination.

    Args:
        context: Dict with key {structure} containing structure data
        destination: Target system name

    Returns:
        Route string: "ROUTE: {origin} → {dest} | Distance | Gates | Time"
    """
    structure = context.get("structure", {})

    if not structure:
        return "ROUTE: No structure data available"

    origin = structure.get("system_name", "Unknown")

    if not destination or destination.strip() == "":
        return f"ROUTE: {origin} → [No destination specified]"

    destination = destination.strip().upper()

    # Simplified routing: estimate gates based on name patterns
    # This is a pure function with no actual pathfinding
    if origin.upper() == destination:
        gates = 0
        distance = "0 LY"
        time = "instant"
    else:
        # Simple heuristic: assume 2-5 gates for unknown routes
        gates = 3
        distance = "~50 LY"
        time = "~10 min"

    return f"ROUTE: {origin} → {destination} | {distance} | {gates} gates | {time}"
