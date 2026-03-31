"""
Alert detection tool — pure function for detecting structure alerts.

Pure function: takes context dict, returns formatted alert string.
No RPC calls, no I/O, deterministic.
"""

from typing import Dict, Any


def detect_alerts(context: Dict[str, Any]) -> str:
    """
    Evaluate structure state and detect alerts.

    Args:
        context: Dict with key {structure} containing structure data

    Returns:
        Alert string: "ALERTS: None" or "ALERTS: URGENT\n  - {alert}"
    """
    structure = context.get("structure", {})

    if not structure:
        return "ALERTS: No structure data available"

    alerts = []
    shield_pct = structure.get("shield_pct", 100)
    fuel_pct = structure.get("fuel_pct", 100)

    # Check for urgent conditions
    if shield_pct < 20.0:
        alerts.append(f"URGENT: Shield critical at {shield_pct:.0f}%")

    if fuel_pct < 10.0:
        alerts.append(f"URGENT: Fuel critical at {fuel_pct:.0f}%")
    elif fuel_pct < 25.0:
        alerts.append(f"WARNING: Fuel low at {fuel_pct:.0f}%")

    if not alerts:
        return "ALERTS: None"

    # Format alert string
    alert_text = "ALERTS: URGENT\n"
    for alert in alerts:
        alert_text += f"  - {alert}\n"

    return alert_text.rstrip()
