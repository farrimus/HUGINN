"""
Memory query tool — pure function for querying memory events.

Pure function: takes context dict and optional filters, returns formatted memory string.
No RPC calls, no I/O, deterministic.
"""

from typing import Dict, Any, Optional


def query_memory_events(context: Dict[str, Any], filters: Optional[Dict[str, Any]] = None) -> str:
    """
    Query memory events from context, optionally filtering.

    Args:
        context: Dict with key {memory_events} containing event list
        filters: Optional dict with filter criteria (e.g., {"type": "raid"})

    Returns:
        Memory string: "MEMORY: No events" or "MEMORY: N total, last 5: ..."
    """
    memory_events = context.get("memory_events", [])

    if not memory_events:
        return "MEMORY: No events recorded"

    # Apply filters if provided
    filtered_events = memory_events
    if filters:
        filtered_events = []
        for event in memory_events:
            match = True
            for key, value in filters.items():
                if event.get(key) != value:
                    match = False
                    break
            if match:
                filtered_events.append(event)

    total_count = len(memory_events)
    filtered_count = len(filtered_events)

    if filtered_count == 0:
        return f"MEMORY: {total_count} total, no matches for filters"

    # Get last 5 events
    last_events = filtered_events[-5:]

    # Format summary
    lines = [f"MEMORY: {total_count} total"]

    if filtered_count < total_count:
        lines[0] += f" ({filtered_count} matching)"

    # Add brief event summaries
    event_summaries = []
    for event in last_events:
        event_type = event.get("type", "unknown")
        ts = event.get("ts", "")[:10]  # Date only
        event_summaries.append(f"{ts} {event_type}")

    if event_summaries:
        lines.append(f"  Recent: {' | '.join(event_summaries)}")

    return "\n".join(lines)
