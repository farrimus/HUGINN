# src/log_buffer.py
from collections import deque
from typing import Optional
import time

LIVE_TTL_S = 120  # evict live snapshots if no heartbeat received for this long

class LogBuffer:
    def __init__(self, max_size: int = 50):
        self.events: deque = deque(maxlen=max_size)
        self.current_system: Optional[str] = None
        self.current_route: Optional[dict] = None
        self._live: list = []
        self.pending_structure_alerts: list = []

    def add(self, event: dict):
        self.events.append(event)
        if event.get("type") == "system_change":
            self.current_system = event.get("system")
        elif event.get("type") == "route_planned":
            self.current_route = event

    def get_recent(self, n: int = 10) -> list:
        events = list(self.events)
        return events[-n:]

    def set_live(self, snapshots: list):
        now = time.time()
        self._live = [{**e, "_ts": now} for e in snapshots]

    def get_live(self) -> list:
        cutoff = time.time() - LIVE_TTL_S
        return [e for e in self._live if e.get("_ts", 0) > cutoff]

    def clear_live(self, session_type: str):
        """Evict live entry once the real summary arrives."""
        self._live = [e for e in self._live if e.get("type") != session_type]

    def add_structure_alert(self, event: dict):
        """Queue an urgent structure alert for Ship AI delivery. Never evicted."""
        self.pending_structure_alerts.append(event)

    def pop_structure_alerts(self) -> list:
        """Return and clear all pending structure alerts."""
        alerts = self.pending_structure_alerts[:]
        self.pending_structure_alerts = []
        return alerts

# Global singleton used by the FastAPI app
log_buffer = LogBuffer(max_size=50)
