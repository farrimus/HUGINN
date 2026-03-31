"""
Threat assessment tool — pure function for evaluating threat level from killmails.

Pure function: takes context dict, returns formatted threat string.
No RPC calls, no I/O, deterministic.
"""

from datetime import datetime, timedelta, timezone
from typing import Dict, Any


def assess_threat_level(context: Dict[str, Any], hours_lookback: int = 24) -> str:
    """
    Assess threat level based on recent killmails in a time window.

    Args:
        context: Dict with keys {structure, killmails, memory_events}
        hours_lookback: How many hours to look back (default 24)

    Returns:
        Formatted threat string: "THREAT: {LEVEL} | {kill_count} kills | {recommendation}"
        Levels: LOW (0 kills), MEDIUM (2-5 kills), HIGH (6-10 kills), CRITICAL (11+)
    """
    killmails = context.get("killmails", [])

    if not killmails:
        return "THREAT: LOW | 0 kills | No recent activity"

    # Filter kills within time window
    now = datetime.now(timezone.utc)
    cutoff = now - timedelta(hours=hours_lookback)

    recent_kills = []
    for km in killmails:
        try:
            ts_str = km.get("time") or km.get("timestamp") or ""
            if not ts_str:
                continue
            # Handle ISO format with or without Z
            ts = datetime.fromisoformat(ts_str.replace("Z", "+00:00"))
            if ts >= cutoff:
                recent_kills.append(km)
        except (ValueError, AttributeError):
            # Skip kills with unparseable timestamps
            continue

    kill_count = len(recent_kills)

    # Determine threat level
    if kill_count == 0:
        level = "LOW"
        recommendation = "No recent activity"
    elif kill_count <= 1:
        level = "LOW"
        recommendation = "Minimal threat, stay alert"
    elif kill_count <= 5:
        level = "MEDIUM"
        recommendation = "Activity detected, assess situation"
    elif kill_count <= 10:
        level = "HIGH"
        recommendation = "Significant threat, consider evasion"
    else:
        level = "CRITICAL"
        recommendation = "Active combat zone, immediate evasion advised"

    return f"THREAT: {level} | {kill_count} kills | {recommendation}"
