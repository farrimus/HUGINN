"""
Killmail analysis tool — pure function for analyzing killmail patterns.

Pure function: takes context dict, returns formatted pattern string.
No RPC calls, no I/O, deterministic.
"""

from typing import Dict, Any
from collections import Counter


def analyze_killmail_patterns(context: Dict[str, Any]) -> str:
    """
    Analyze patterns in recent killmails.

    Args:
        context: Dict with key {killmails} containing killmail data

    Returns:
        Pattern analysis string: "PATTERNS: N kills | Primary threat: ... | Escalation: ..."
    """
    killmails = context.get("killmails", [])

    if not killmails:
        return "PATTERNS: No recent kills"

    kill_count = len(killmails)

    # Find primary threat (most frequent killer)
    killers = []
    for km in killmails:
        km_killers = km.get("killers", [])
        if km_killers:
            for killer in km_killers:
                char = killer.get("character", {})
                killer_name = char.get("name") or f"Killer {char.get('id', '?')}"
                killers.append(killer_name)

    primary_threat = "Unknown"
    if killers:
        killer_counter = Counter(killers)
        primary_threat = killer_counter.most_common(1)[0][0]

    # Detect escalation (rapidly increasing kill rate)
    escalation = "None"
    if kill_count >= 3:
        # Simple heuristic: if kills are recent and frequent
        from datetime import datetime, timedelta, timezone
        now = datetime.now(timezone.utc)
        recent_count = 0
        for km in killmails[:3]:
            try:
                ts_str = km.get("time") or km.get("timestamp") or ""
                if ts_str:
                    ts = datetime.fromisoformat(ts_str.replace("Z", "+00:00"))
                    if ts >= now - timedelta(minutes=30):
                        recent_count += 1
            except (ValueError, AttributeError):
                pass
        if recent_count >= 2:
            escalation = "Rapid (3+ kills in 30 min)"

    return f"PATTERNS: {kill_count} kills | Primary threat: {primary_threat} | Escalation: {escalation}"
