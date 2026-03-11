# src/log_buffer.py
from collections import deque
from typing import Optional

class LogBuffer:
    def __init__(self, max_size: int = 50):
        self.events: deque = deque(maxlen=max_size)
        self.current_system: Optional[str] = None

    def add(self, event: dict):
        self.events.append(event)
        if event.get("type") == "system_change":
            self.current_system = event.get("system")

    def get_recent(self, n: int = 10) -> list:
        events = list(self.events)
        return events[-n:]

# Global singleton used by the FastAPI app
log_buffer = LogBuffer(max_size=50)
