# src/world_api.py
import os
import time
import json
import logging
import httpx
from typing import Optional

INDEX_PATH = os.path.join(os.path.dirname(__file__), "..", "data", "system_index.json")

log = logging.getLogger(__name__)

REAL_BASE_URL = "https://world-api-stillness.live.tech.evefrontier.com"

class WorldAPIClient:
    def __init__(self, base_url: str = None, cache_ttl: float = 30.0):
        self.base_url = base_url or os.getenv("WORLD_API_BASE_URL", REAL_BASE_URL)
        self.cache_ttl = cache_ttl
        self._cache: dict = {}          # cache_key -> (data, timestamp)
        self._system_index: dict = {}   # name (lowercase) -> system_id
        self._http_client = httpx.AsyncClient(timeout=10.0)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _cache_key(self, endpoint: str, params: dict) -> str:
        return f"{endpoint}:{sorted(params.items())}"

    def _get_cached(self, key: str) -> Optional[dict]:
        if key not in self._cache:
            return None
        data, ts = self._cache[key]
        if time.time() - ts > self.cache_ttl:
            del self._cache[key]
            return None
        return data

    async def _fetch(self, endpoint: str, params: dict = None) -> dict:
        response = await self._http_client.get(
            f"{self.base_url}{endpoint}",
            params=params or {},
        )
        response.raise_for_status()
        return response.json()

    async def _cached_fetch(self, endpoint: str, params: dict = None) -> Optional[dict]:
        key = self._cache_key(endpoint, params or {})
        cached = self._get_cached(key)
        if cached is not None:
            return cached
        try:
            data = await self._fetch(endpoint, params)
            self._cache[key] = (data, time.time())
            return data
        except Exception as e:
            log.warning("World API fetch failed: %s", e)
            return None

    # ------------------------------------------------------------------
    # System index — persisted to disk, built from API when missing
    # ------------------------------------------------------------------

    def _index_file(self) -> str:
        return os.path.normpath(os.path.join(os.path.dirname(__file__), "..", "data", "system_index.json"))

    def load_index_from_disk(self) -> bool:
        """Load index from disk cache. Returns True if loaded successfully."""
        path = self._index_file()
        if not os.path.exists(path):
            return False
        try:
            with open(path, "r") as f:
                data = json.load(f)
            self._system_index = data.get("index", {})
            built_at = data.get("built_at", "unknown")
            log.info("System index loaded from disk: %d systems (built %s)", len(self._system_index), built_at)
            return True
        except Exception as e:
            log.warning("Failed to load system index from disk: %s", e)
            return False

    def save_index_to_disk(self):
        """Persist the current index to disk."""
        path = self._index_file()
        os.makedirs(os.path.dirname(path), exist_ok=True)
        try:
            with open(path, "w") as f:
                json.dump({
                    "built_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                    "count": len(self._system_index),
                    "index": self._system_index,
                }, f)
            log.info("System index saved to disk: %s", path)
        except Exception as e:
            log.warning("Failed to save system index to disk: %s", e)

    async def load_or_build_index(self) -> int:
        """Load index from disk if available, otherwise fetch from API and save.
        Returns number of systems indexed."""
        if self.load_index_from_disk():
            return len(self._system_index)
        return await self.rebuild_index()

    async def rebuild_index(self) -> int:
        """Force a full rebuild from the API and save to disk.
        Use this when the game adds new systems."""
        index: dict = {}
        limit = 1000
        offset = 0

        log.info("Building solar system index from API...")
        while True:
            try:
                result = await self._fetch("/v2/solarsystems", {"limit": limit, "offset": offset})
            except Exception as e:
                log.warning("Failed to fetch solarsystems page (offset=%d): %s", offset, e)
                break

            systems = result.get("data", [])
            for s in systems:
                name = s.get("name", "")
                sid = s.get("id")
                if name and sid:
                    index[name.lower()] = sid

            total = result.get("metadata", {}).get("total", 0)
            offset += len(systems)
            if offset >= total or not systems:
                break

        self._system_index = index
        log.info("System index built: %d systems", len(index))
        self.save_index_to_disk()
        return len(index)

    # Keep build_system_index as an alias for backward compat with tests
    async def build_system_index(self) -> int:
        return await self.rebuild_index()

    def resolve_system_id(self, name: str) -> Optional[int]:
        """Look up a system ID by name (case-insensitive)."""
        return self._system_index.get(name.lower())

    # ------------------------------------------------------------------
    # Public API methods
    # ------------------------------------------------------------------

    async def get_system(self, system_name: str) -> Optional[dict]:
        """Fetch full system data by name. Returns None if not found or on error."""
        system_id = self.resolve_system_id(system_name)
        if system_id is None:
            log.warning("System '%s' not found in index", system_name)
            return None
        return await self._cached_fetch(f"/v2/solarsystems/{system_id}")

    async def get_system_by_id(self, system_id: int) -> Optional[dict]:
        """Fetch full system data by ID directly."""
        return await self._cached_fetch(f"/v2/solarsystems/{system_id}")

# Global singleton
world_api = WorldAPIClient()
