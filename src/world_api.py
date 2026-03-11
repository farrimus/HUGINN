# src/world_api.py
import os
import time
import logging
import httpx
from typing import Optional

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
    # System index — built once at startup
    # ------------------------------------------------------------------

    async def build_system_index(self) -> int:
        """Fetch all solar systems and build a name→id lookup index.
        Returns the number of systems indexed."""
        index: dict = {}
        limit = 1000
        offset = 0

        log.info("Building solar system index...")
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
        return len(index)

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
