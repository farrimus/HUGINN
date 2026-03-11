# src/context_builder.py
from typing import Optional

def build_context_block(
    system_data: Optional[dict],
    log_events: list,
    current_system: Optional[str],
) -> str:
    lines = []

    # Current system
    system_name = current_system or (system_data or {}).get("name", "unknown")
    lines.append(f"CURRENT SYSTEM: {system_name}")

    if system_data:
        security = system_data.get("security")
        if security is not None:
            lines.append(f"SECURITY: {security:.1f}")
        kills = system_data.get("kills", [])
        if kills:
            lines.append(f"RECENT KILLS IN SYSTEM: {min(len(kills), 5)} recorded")

    # Recent log events (last 10)
    if log_events:
        lines.append("RECENT EVENTS:")
        for event in log_events[-10:]:
            event_type = event.get("type", "unknown")
            if event_type == "jump":
                lines.append(f"  - jumped to {event.get('system', '?')}")
            elif event_type == "combat":
                lines.append(f"  - combat: {event.get('damage', '?')} dmg vs {event.get('target', '?')}")
            elif event_type == "system_change":
                lines.append(f"  - entered system {event.get('system', '?')}")
            elif event_type == "docking":
                lines.append(f"  - docked at {event.get('location', '?')}")
            else:
                lines.append(f"  - {event_type}")

    block = "\n".join(lines)
    return block[:2000]
