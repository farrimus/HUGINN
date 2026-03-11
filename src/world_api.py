# src/world_api.py
import os
import time
import httpx
from typing import Optional

class WorldAPIClient:
    def __init__(self, base_url: str = None, api_key: str = None, cache_ttl: float = 30.0):
        self.base_url = base_url or os.getenv("WORLD_API_BASE_URL", "https://api.evefrontier.com")
        self.api_key = api_key if api_key is not None else os.getenv("WORLD_API_KEY", "")
        self.cache_ttl = cache_ttl
        self._cache: dict = {}  # key -> (data, timestamp)
        self._http_client = httpx.AsyncClient(timeout=10.0)

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
        headers = {"Authorization": f"Bearer {self.api_key}"} if self.api_key else {}
        response = await self._http_client.get(
            f"{self.base_url}{endpoint}",
            params=params or {},
            headers=headers,
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
            import logging
            logging.getLogger(__name__).warning("World API fetch failed: %s", e)
            return None

    async def get_system(self, system_name: str) -> Optional[dict]:
        return await self._cached_fetch("/v1/system", {"name": system_name})

    async def get_killmails(self, system_name: str) -> list:
        result = await self._cached_fetch("/v1/killmails", {"system": system_name})
        if result is None:
            return []
        return result if isinstance(result, list) else []

# Global singleton
world_api = WorldAPIClient()
