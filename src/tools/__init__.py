"""
Pure tools for AI agent — 6 deterministic functions for context analysis.

Each tool is a pure function (no RPC calls, no I/O, deterministic):
- assess_threat_level(context, hours_lookback) — threat assessment from killmails
- get_structure_status(context) — formatted structure status block
- detect_alerts(context) — alert detection from structure state
- analyze_killmail_patterns(context) — pattern analysis from killmails
- query_memory_events(context, filters) — memory event queries with filtering
- plan_evasion_route(context, destination) — route planning

All tools take pre-fetched context dict (no RPC calls).
Returns are formatted strings for Claude consumption.
"""

from src.tools.threat_assessment_tool import assess_threat_level
from src.tools.structure_status_tool import get_structure_status
from src.tools.alert_detection_tool import detect_alerts
from src.tools.killmail_analysis_tool import analyze_killmail_patterns
from src.tools.memory_query_tool import query_memory_events
from src.tools.route_planning_tool import plan_evasion_route

__all__ = [
    "assess_threat_level",
    "get_structure_status",
    "detect_alerts",
    "analyze_killmail_patterns",
    "query_memory_events",
    "plan_evasion_route",
]
