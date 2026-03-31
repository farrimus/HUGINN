# src/tribe_board.py
"""
In-memory tribe presence board. Not persisted — ephemeral per process.

Presence entries expire after PRESENCE_TTL_SECONDS (5 minutes) and are
filtered at read time. No background cleanup required.

tribe_id -> wallet_address -> {wallet_address, character_name, location, status, last_ping}
"""
import asyncio
import datetime
import logging
from typing import Optional

log = logging.getLogger(__name__)

PRESENCE_TTL_SECONDS = 300  # 5 minutes

# tribe_id -> { wallet_address -> presence_entry }
TRIBE_PRESENCE: dict[int, dict[str, dict]] = {}

# tribe_id -> list of SSE queues for subscribers
_tribe_sse_clients: dict[int, list[asyncio.Queue]] = {}


def _now() -> str:
    return datetime.datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")


def _is_fresh(entry: dict) -> bool:
    """Return True if the entry's last_ping is within TTL."""
    try:
        last = datetime.datetime.strptime(entry["last_ping"], "%Y-%m-%dT%H:%M:%SZ")
        age = (datetime.datetime.utcnow() - last).total_seconds()
        return age < PRESENCE_TTL_SECONDS
    except (KeyError, ValueError):
        return False


def update_presence(
    tribe_id: int,
    wallet_address: str,
    character_name: str,
    location: str,
    status: str,
) -> dict:
    """Write or update a presence entry. Returns the updated entry."""
    entry = {
        "wallet_address": wallet_address,
        "character_name": character_name,
        "location": location,
        "status": status,
        "last_ping": _now(),
    }
    TRIBE_PRESENCE.setdefault(tribe_id, {})[wallet_address] = entry

    # Broadcast to all SSE subscribers for this tribe
    event = {"type": "presence_update", "tribe_id": tribe_id, "member": entry}
    for q in list(_tribe_sse_clients.get(tribe_id, [])):
        try:
            q.put_nowait(event)
        except asyncio.QueueFull:
            pass

    log.debug("tribe: presence updated tribe=%s wallet=%s", tribe_id, wallet_address[:12])
    return entry


def get_presence(tribe_id: int) -> list[dict]:
    """Return all fresh presence entries for a tribe."""
    members = TRIBE_PRESENCE.get(tribe_id, {})
    return [e for e in members.values() if _is_fresh(e)]


def subscribe(tribe_id: int) -> asyncio.Queue:
    """Add a new SSE subscriber queue for a tribe. Caller must call unsubscribe on disconnect."""
    q: asyncio.Queue = asyncio.Queue(maxsize=100)
    _tribe_sse_clients.setdefault(tribe_id, []).append(q)
    return q


def unsubscribe(tribe_id: int, q: asyncio.Queue) -> None:
    """Remove a subscriber queue."""
    try:
        _tribe_sse_clients[tribe_id].remove(q)
    except (KeyError, ValueError):
        pass
