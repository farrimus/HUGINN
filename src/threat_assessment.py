"""
Threat assessment module for both Ship AI and Structure AI.

Synthesizes killmail data + memory history + access tier into actionable threat context.
Used by:
- Ship AI: assess regional threats
- Structure AI: assess imminent threats to structure
- Client-side: inform pilot of nearby danger
"""

import logging
from datetime import datetime, timezone, timedelta
from typing import Optional, List

log = logging.getLogger(__name__)


class ThreatAssessment:
    """Analyze killmails + memory to generate threat context."""

    def __init__(self):
        pass

    def assess_structure_threat(
        self,
        killmails: List[dict],
        memory_events: List[dict],
        pilot_tier: str = "OWNER",
        is_first_visit: bool = False,
        hours_lookback: int = 2,
    ) -> Optional[str]:
        """
        Assess immediate threat to a structure based on recent kills.

        Args:
            killmails: List of recent killmail dicts from World API
            memory_events: Historical events from memory_store
            pilot_tier: OWNER, TRIBE, PATRON, VETTED, NONE
            is_first_visit: True if this is pilot's first visit
            hours_lookback: Time window for recent kills (default 2h)

        Returns:
            Threat context string (e.g., "THREAT: 3 kills | frigate-heavy | Pirate X | escalating")
            or None if no threat detected.
        """
        now = datetime.now(timezone.utc)
        cutoff = now - timedelta(hours=hours_lookback)

        # Filter recent kills
        recent_kills = []
        for km in (killmails or []):
            ts_str = km.get("timestamp") or ""
            try:
                ts = datetime.fromisoformat(ts_str.replace("Z", "+00:00"))
                if ts >= cutoff:
                    recent_kills.append(km)
            except ValueError:
                pass

        if not recent_kills:
            return None

        # Extract threat patterns
        victim_classes = self._get_victim_classes(recent_kills)
        primary_aggressor = self._get_primary_aggressor(recent_kills)
        escalation = self._assess_escalation(recent_kills, memory_events)
        risk_level = self._assess_risk_level(
            len(recent_kills), pilot_tier, is_first_visit, escalation
        )

        # Format output
        class_summary = self._format_class_summary(victim_classes)
        return (
            f"THREAT: {len(recent_kills)} kills ({class_summary}) | "
            f"{primary_aggressor} active | {escalation} | RISK: {risk_level}"
        )

    def assess_ship_threat(
        self,
        nearby_killmails: List[dict],
        your_ship_class: str,
        memory_events: List[dict],
        hours_lookback: int = 24,
    ) -> Optional[str]:
        """
        Assess threat to a ship in a region based on victim types.

        Args:
            nearby_killmails: Recent kills in the system/region
            your_ship_class: Your ship's class (from ship_profile)
            memory_events: Historical events to assess trend
            hours_lookback: Time window for recent kills

        Returns:
            Threat context string or None.
        """
        if not nearby_killmails:
            return None

        now = datetime.now(timezone.utc)
        cutoff = now - timedelta(hours=hours_lookback)

        # Filter recent
        recent = [
            km for km in nearby_killmails
            if self._is_recent(km.get("timestamp"), cutoff)
        ]

        if not recent:
            return None

        # Check if your ship type is being targeted
        victim_classes = self._get_victim_classes(recent)
        your_vulnerability = "high" if victim_classes.get(your_ship_class, 0) > 0 else "low"
        escalation = self._assess_escalation(recent, memory_events)

        if your_vulnerability == "high":
            return (
                f"THREAT: {len(recent)} kills in region, "
                f"{your_ship_class}s targeted {victim_classes.get(your_ship_class, 0)}× | "
                f"{escalation}"
            )
        elif len(recent) > 5:
            return f"CAUTION: {len(recent)} kills in region (last {hours_lookback}h) | {escalation}"

        return None

    # ---- Helpers ----

    def _get_victim_classes(self, killmails: List[dict]) -> dict:
        """Count victims by ship class."""
        classes = {}
        for km in killmails:
            ship_class = km.get("victim_ship_class", "unknown")
            classes[ship_class] = classes.get(ship_class, 0) + 1
        return classes

    def _get_primary_aggressor(self, killmails: List[dict]) -> str:
        """Identify most active aggressor corp/entity."""
        aggressors = {}
        for km in killmails:
            corp = km.get("attacker_corp") or km.get("primary_attacker", "Unknown")
            aggressors[corp] = aggressors.get(corp, 0) + 1
        if not aggressors:
            return "Unknown"
        return max(aggressors, key=aggressors.get)

    def _assess_escalation(self, recent_kills: List[dict], memory_events: List[dict]) -> str:
        """Compare recent kill rate to 7-day baseline."""
        if not memory_events:
            return "unknown trend"

        # Count kills in last 7 days from memory
        cutoff_7d = datetime.now(timezone.utc) - timedelta(days=7)
        kills_7d = 0
        for event in memory_events:
            if event.get("type") == "killmail":
                ts_str = event.get("ts", "")
                try:
                    ts = datetime.fromisoformat(ts_str.replace("Z", "+00:00"))
                    if ts >= cutoff_7d:
                        kills_7d += 1
                except ValueError:
                    pass

        if kills_7d == 0:
            return "new activity"

        baseline = kills_7d / 7  # avg per day
        current_rate = len(recent_kills) / (2 / 24) if len(recent_kills) > 0 else 0  # kills per day (2h window)

        if current_rate > baseline * 3:
            return "escalating rapidly"
        elif current_rate > baseline * 1.5:
            return "escalating"
        elif current_rate < baseline * 0.5:
            return "quieting down"
        else:
            return "routine"

    def _assess_risk_level(
        self, kill_count: int, tier: str, is_first_visit: bool, escalation: str
    ) -> str:
        """Assess overall risk based on multiple factors."""
        if escalation in ("escalating rapidly", "escalating") and kill_count > 3:
            return "CRITICAL"
        if is_first_visit and tier in ("VETTED", "NONE"):
            return "HIGH"
        if kill_count >= 5:
            return "HIGH"
        if kill_count >= 2:
            return "MEDIUM"
        return "LOW"

    def _format_class_summary(self, classes: dict) -> str:
        """Format class counts as compact string."""
        if not classes:
            return "unknown"
        parts = [f"{cls}×{count}" for cls, count in sorted(classes.items())]
        return ", ".join(parts[:3])  # Cap at 3 classes

    def _is_recent(self, ts_str: Optional[str], cutoff: datetime) -> bool:
        """Check if timestamp is after cutoff."""
        if not ts_str:
            return False
        try:
            ts = datetime.fromisoformat(ts_str.replace("Z", "+00:00"))
            return ts >= cutoff
        except ValueError:
            return False


# Singleton
threat_assessment = ThreatAssessment()
