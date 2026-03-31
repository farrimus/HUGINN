# src/location_index.py
"""
Indexes LocationRevealedEvent from the EVE Frontier package.
Each event pairs an assembly_id with real-world coordinates.
Persisted to data/location_index.json; rebuilt on demand via admin endpoint.
"""
import os
import json
import logging
from typing import Optional

log = logging.getLogger(__name__)


def _get_eve_frontier_package() -> str:
    """Get EVE Frontier package ID from config."""
    from src.config import load_config_from_env
    config = load_config_from_env()
    return config["eve_frontier_package"]


def _get_location_event_type() -> str:
    """Get location event type string for Sui events."""
    package = _get_eve_frontier_package()
    return f"{package}::location::LocationRevealedEvent"


try:
    from src.blockchain_queries import nova_client
except Exception:  # pragma: no cover
    nova_client = None  # type: ignore[assignment]


class LocationIndex:
    def __init__(self, path: str = None):
        from src.config import get_data_path

        if path is None:
            path = get_data_path("location_index.json", env_specific=True)
        self._path = path
        self._data: dict = {}  # {assembly_id: {solarsystem, x, y, z, location_hash}}

    def load(self) -> None:
        """Load index from disk if it exists. No network calls."""
        if not os.path.exists(self._path):
            return
        try:
            with open(self._path) as f:
                self._data = json.load(f)
            log.info("LocationIndex: loaded %d entries", len(self._data))
        except Exception as e:
            log.warning("LocationIndex.load failed: %s", e)

    def _save(self) -> None:
        try:
            os.makedirs(os.path.dirname(self._path), exist_ok=True)
            with open(self._path, "w") as f:
                json.dump(self._data, f, indent=2)
        except Exception as e:
            log.warning("LocationIndex._save failed: %s", e)

    async def rebuild(self) -> int:
        """
        Fetch all LocationRevealedEvent pages from chain, rebuild index.
        Returns number of entries indexed. All errors are logged, not raised.
        """
        new_data: dict = {}
        cursor = None

        try:
            while True:
                result = await nova_client._rpc("suix_queryEvents", [
                    {"MoveEventType": _get_location_event_type()},
                    cursor,
                    50,
                    False,  # ascending — process oldest first
                ])
                page = result.get("result", {})
                events = page.get("data") or []
                for event in events:
                    parsed = event.get("parsedJson") or {}
                    assembly_id = parsed.get("assembly_id")
                    if not assembly_id:
                        continue
                    new_data[assembly_id] = {
                        "solarsystem": parsed.get("solarsystem", ""),
                        "x": parsed.get("x"),
                        "y": parsed.get("y"),
                        "z": parsed.get("z"),
                        "location_hash": parsed.get("location_hash", ""),
                    }
                if not page.get("hasNextPage"):
                    break
                cursor = page.get("nextCursor")
        except Exception as e:
            log.warning("LocationIndex.rebuild failed: %s", e)
            return 0

        self._data = new_data
        self._save()
        log.info("LocationIndex: rebuilt with %d entries", len(self._data))
        return len(self._data)

    def get(self, assembly_id: str) -> Optional[dict]:
        return self._data.get(assembly_id)

    def get_all(self) -> list:
        return [{"assembly_id": k, **v} for k, v in self._data.items()]


# Module-level singleton.
# load() only reads data/location_index.json from disk — no network call.
# rebuild() is the network call; it is only invoked by the admin endpoint.
location_index = LocationIndex()
location_index.load()
