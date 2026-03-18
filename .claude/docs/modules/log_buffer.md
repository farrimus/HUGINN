# log_buffer

## When Should an Agent Use This Module?

Use **log_buffer** when you need to maintain an in-memory ring buffer of player events from the game client. The buffer:
- Accepts structured events (combat, mining, navigation, chat)
- Tracks current player location and active route
- Manages live (streaming) snapshots with TTL
- Queues urgent structure alerts for immediate delivery

This is the primary state store for everything the Ship AI knows about the current play session.

## Public API

```python
class LogBuffer:
    def __init__(self, max_size: int = 50):
        """Initialize ring buffer (default 50 events)."""

    # Key fields
    current_route: Optional[dict]  # Last route_planned event
    pending_alternative: Optional[dict]  # Alternative route (swappable)

    def add(self, event: dict):
        """Append event; auto-extract system_change and route_planned."""

    def get_recent(self, n: int = 10) -> list:
        """Return last n events (default 10)."""

    def set_live(self, snapshots: list):
        """Accept live snapshots (combat/mining in progress); auto-timestamp."""

    def get_live(self) -> list:
        """Return live snapshots still within TTL (120s)."""

    def clear_live(self, session_type: str):
        """Evict live snapshots of type 'combat_summary' or 'mining_summary'."""

    def add_structure_alert(self, event: dict):
        """Queue an urgent alert (never evicted)."""

    def pop_structure_alerts(self) -> list:
        """Return and clear all pending structure alerts."""

# Global singleton used by FastAPI
log_buffer = LogBuffer(max_size=50)
```

## Behavior

| Operation | Behavior |
|-----------|----------|
| `add(event)` | Appends to ring buffer; auto-extracts `system` from `system_change` events; auto-stores `route_planned` events |
| `get_recent(10)` | Returns last 10 events (or fewer if buffer not full) |
| `set_live([snapshots])` | Stamps each snapshot with `_ts = time.time()`, replaces prior live list |
| `get_live()` | Filters `_live` to only those with `_ts > now - 120`, returns only non-stale entries |
| `clear_live('combat_summary')` | Removes all live entries where `type == 'combat_summary'` — called when real summary arrives |
| `add_structure_alert()` | Appends to `pending_structure_alerts` (never expires) |
| `pop_structure_alerts()` | Returns copy of alerts, clears list |

## Key Fields

- `events` — Ring buffer (deque) of recent events
- `current_system` — Last player location (auto-updated on system_change)
- `current_route` — Last route_planned event (for context_builder injection)
- `pending_alternative` — Alternative route (set by route_engine when warm intermediates found; swappable with current_route via `/route/activate`)
- `_live` — List of snapshots (combat/mining in progress) with TTL
- `pending_structure_alerts` — Urgent alerts from Structure AI (never evicted)

## Constants

- `LIVE_TTL_S = 120` — Live snapshots evicted if no heartbeat in 2 minutes

## Integration Points

- **Input:** `/log/ingest` POST endpoint appends events
- **Input:** `/live` POST endpoint refreshes live snapshots
- **Input:** Structure AI adds structure alerts via `add_structure_alert()`
- **Output:** `/chat` endpoint calls `get_recent()` and `get_live()` for context building
