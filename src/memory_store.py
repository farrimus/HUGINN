# src/memory_store.py
import os
import time
import json
import logging
from datetime import datetime, timezone, timedelta
from typing import Optional

log = logging.getLogger(__name__)

_DEFAULT_BASE_DIR = os.path.normpath(
    os.path.join(os.path.dirname(__file__), "..", "data", "memory")
)

SUMMARY_CAP = 300


class MemoryStore:
    def __init__(self, base_dir: str = _DEFAULT_BASE_DIR, structure_id: str = "", world_api_client=None):
        self._base = base_dir
        self._sid = structure_id
        self.world_api = world_api_client

    # ------------------------------------------------------------------
    # Paths
    # ------------------------------------------------------------------

    def _root(self) -> str:
        return os.path.join(self._base, self._sid)

    def _events_path(self) -> str:
        return os.path.join(self._root(), "events.jsonl")

    def _summary_path(self) -> str:
        return os.path.join(self._root(), "summary.json")

    def _pilots_dir(self) -> str:
        return os.path.join(self._root(), "pilots")

    def _pilot_path(self, address: str) -> str:
        """Validate Sui address format and return safe file path.

        Validates that address is exactly 0x + 64 hex chars.
        Rejects path traversal attempts and dangerous characters.
        """
        # Validate format: 0x + exactly 64 hex characters
        if not address or not address.startswith('0x') or len(address) != 66:
            raise ValueError('address must be 0x followed by 64 hexadecimal characters')

        # Validate hex content
        hex_part = address[2:]
        try:
            int(hex_part, 16)
        except ValueError:
            raise ValueError('address contains non-hexadecimal characters')

        # Reject dangerous characters that could enable path traversal
        dangerous_chars = ['\\', '/', '..', ':', '.', '\x00', '\t', '\n', '\r']
        for char_seq in dangerous_chars:
            if char_seq in address:
                raise ValueError(f'address contains forbidden character sequence: {repr(char_seq)}')

        # Use lowercase normalized address
        safe = address.lower()
        return os.path.join(self._pilots_dir(), f"{safe}.json")

    # ------------------------------------------------------------------
    # Bootstrap
    # ------------------------------------------------------------------

    def bootstrap(self):
        """Create directory structure if missing."""
        os.makedirs(self._root(), exist_ok=True)
        if not os.path.exists(self._events_path()):
            open(self._events_path(), "w").close()
        if not os.path.exists(self._summary_path()):
            with open(self._summary_path(), "w") as f:
                json.dump({"last_updated": None, "text": ""}, f)

    # ------------------------------------------------------------------
    # Events
    # ------------------------------------------------------------------

    def append_event(self, event_type: str, system_id: int, data: dict):
        ts = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        record = {"ts": ts, "type": event_type, "system_id": system_id, "data": data}
        try:
            with open(self._events_path(), "a") as f:
                f.write(json.dumps(record) + "\n")
        except Exception as e:
            log.warning("memory_store.append_event failed: %s", e)

    def search_events(self, keyword: str, days: int = 7) -> list[dict]:
        """Case-insensitive substring search over raw JSON lines. Returns up to 20 matches, newest first."""
        cutoff = datetime.now(timezone.utc) - timedelta(days=days)
        keyword_lower = keyword.lower()
        results = []
        try:
            with open(self._events_path()) as f:
                lines = f.readlines()
            for line in reversed(lines):
                line = line.strip()
                if not line:
                    continue
                try:
                    event = json.loads(line)
                except json.JSONDecodeError:
                    continue
                ts_str = event.get("ts", "")
                try:
                    ts = datetime.fromisoformat(ts_str.replace("Z", "+00:00"))
                except ValueError:
                    continue
                if ts < cutoff:
                    continue
                if keyword_lower in line.lower():
                    results.append(event)
                if len(results) >= 20:
                    break
        except Exception as e:
            log.warning("memory_store.search_events failed: %s", e)
        return results

    # ------------------------------------------------------------------
    # Summary
    # ------------------------------------------------------------------

    def rebuild_summary(self):
        """Rebuild summary.json from the last 7 days of events."""
        cutoff = datetime.now(timezone.utc) - timedelta(days=7)
        counts = {"docking": 0, "killmail": 0, "ssu_state": 0, "access_change": 0}
        try:
            with open(self._events_path()) as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        event = json.loads(line)
                    except json.JSONDecodeError:
                        continue
                    ts_str = event.get("ts", "")
                    try:
                        ts = datetime.fromisoformat(ts_str.replace("Z", "+00:00"))
                    except ValueError:
                        continue
                    if ts < cutoff:
                        continue
                    etype = event.get("type", "")
                    if etype in counts:
                        counts[etype] += 1
        except Exception as e:
            log.warning("memory_store.rebuild_summary read failed: %s", e)

        text = (
            f"Last 7 days: {counts['docking']} dockings | "
            f"{counts['killmail']} kills | "
            f"{counts['ssu_state']} SSU updates | "
            f"{counts['access_change']} access changes"
        )
        if len(text) > SUMMARY_CAP:
            text = text[:SUMMARY_CAP]

        now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        try:
            with open(self._summary_path(), "w") as f:
                json.dump({"last_updated": now, "text": text}, f)
        except Exception as e:
            log.warning("memory_store.rebuild_summary write failed: %s", e)

    def get_summary(self) -> dict:
        try:
            with open(self._summary_path()) as f:
                return json.load(f)
        except Exception:
            return {"last_updated": None, "text": ""}

    # ------------------------------------------------------------------
    # Pilot profiles
    # ------------------------------------------------------------------

    def upsert_pilot(self, address: str, character_name: str, character_id: int, tier: str):
        os.makedirs(self._pilots_dir(), exist_ok=True)
        path = self._pilot_path(address)
        now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        try:
            if os.path.exists(path):
                with open(path) as f:
                    profile = json.load(f)
                profile["last_seen"] = now
                profile["visit_count"] = profile.get("visit_count", 0) + 1
                profile["tier"] = tier
                profile["character_name"] = character_name
                profile["character_id"] = character_id
            else:
                profile = {
                    "address": address,
                    "character_name": character_name,
                    "character_id": character_id,
                    "tier": tier,
                    "first_seen": now,
                    "last_seen": now,
                    "visit_count": 1,
                }
            with open(path, "w") as f:
                json.dump(profile, f, indent=2)
        except Exception as e:
            log.warning("memory_store.upsert_pilot(%s) failed: %s", address, e)

    def get_pilot(self, address: str) -> Optional[dict]:
        path = self._pilot_path(address)
        if not os.path.exists(path):
            return None
        try:
            with open(path) as f:
                return json.load(f)
        except Exception as e:
            log.warning("memory_store.get_pilot(%s) failed: %s", address, e)
            return None

    # ------------------------------------------------------------------
    # Killmail methods
    # ------------------------------------------------------------------

    async def get_killmails_for_system(self, system_id: int, hours: int = 24) -> list:
        """Fetch killmails for a system and filter by recency.

        Args:
            system_id: Solar system ID to fetch killmails for
            hours: Window in hours to filter by (default 24)

        Returns:
            List of top 10 killmails sorted by most recent first,
            or empty list on API errors
        """
        if not self.world_api:
            log.warning("world_api_client not initialized")
            return []

        try:
            killmails = await self.world_api.get_killmails(system_id)
            if not killmails:
                return []

            filtered = self.filter_killmails_by_recency(killmails, hours)
            return filtered[:10]
        except Exception as e:
            log.warning("get_killmails_for_system(%d) failed: %s", system_id, e)
            return []

    def filter_killmails_by_recency(self, killmails: list, hours: int) -> list:
        """Filter killmails by timestamp within a hours window.

        Args:
            killmails: List of killmail dicts with 'timestamp' field
            hours: Number of hours to include (from now backwards)

        Returns:
            List of killmails within window, sorted by recency (newest first)
        """
        if not killmails:
            return []

        now = time.time()
        cutoff = now - (hours * 3600)

        filtered = []
        for km in killmails:
            if not isinstance(km, dict):
                continue
            ts = km.get("timestamp")
            if ts is None:
                continue
            # Handle both Unix timestamps (seconds) and milliseconds
            ts_seconds = ts / 1000 if ts > 100000000000 else ts
            if ts_seconds >= cutoff:
                filtered.append(km)

        # Sort by timestamp descending (newest first)
        filtered.sort(key=lambda km: km.get("timestamp", 0), reverse=True)
        return filtered

    def get_most_recent_killmail_timestamp(self, killmails: list) -> Optional[float]:
        """Get the most recent killmail timestamp from a list.

        Args:
            killmails: List of killmail dicts with 'timestamp' field

        Returns:
            Most recent timestamp as float, or None if list is empty
        """
        if not killmails:
            return None

        timestamps = []
        for km in killmails:
            if isinstance(km, dict):
                ts = km.get("timestamp")
                if ts is not None:
                    timestamps.append(ts)

        return max(timestamps) if timestamps else None


# Module-level factory — structure_id set at runtime
def get_memory_store(structure_id: str) -> MemoryStore:
    store = MemoryStore(structure_id=structure_id)
    store.bootstrap()
    return store
