# src/blockchain_client.py
"""
Thin HTTP wrapper around the EVE Frontier Blockchain Gateway REST API.
Same pattern as world_api.py — singleton, TTL cache, all errors swallowed.
"""
import os
import time
import logging
import httpx
from typing import Optional

log = logging.getLogger(__name__)

BLOCKCHAIN_GW_URL = os.environ.get(
    "BLOCKCHAIN_GW_URL",
    "https://blockchain-gateway-stillness.live.tech.evefrontier.com",
)

_CACHE_TTL = 120.0   # seconds
_TIMEOUT   = 10.0    # seconds


class BlockchainClient:
    def __init__(self, base_url: str = None, cache_ttl: float = _CACHE_TTL):
        self.base_url = (base_url or BLOCKCHAIN_GW_URL).rstrip("/")
        self.cache_ttl = cache_ttl
        self._cache: dict = {}   # url -> (data, timestamp)
        self._http: Optional[httpx.AsyncClient] = None
        self._logged_fields: set = set()  # assembly IDs whose top-level keys we have logged

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _get_cached(self, url: str):
        entry = self._cache.get(url)
        if entry and (time.time() - entry[1]) < self.cache_ttl:
            return entry[0]
        return None

    def _set_cached(self, url: str, data):
        self._cache[url] = (data, time.time())

    async def _client(self) -> httpx.AsyncClient:
        if self._http is None or self._http.is_closed:
            self._http = httpx.AsyncClient(timeout=_TIMEOUT)
        return self._http

    async def _get(self, url: str):
        """GET url, return parsed JSON or None on any error."""
        cached = self._get_cached(url)
        if cached is not None:
            return cached
        try:
            client = await self._client()
            resp = await client.get(url)
            resp.raise_for_status()
            data = resp.json()
            self._set_cached(url, data)
            return data
        except httpx.ConnectError as e:
            log.warning("BlockchainClient: DNS/connect error for %s: %s", url, e)
            return None
        except httpx.HTTPStatusError as e:
            log.warning("BlockchainClient: HTTP %s for %s", e.response.status_code, url)
            return None
        except Exception as e:
            log.warning("BlockchainClient: error fetching %s: %s", url, e)
            return None

    # ------------------------------------------------------------------
    # Public methods
    # ------------------------------------------------------------------

    async def get_assembly(self, assembly_id: str) -> Optional[dict]:
        """GET /smartassemblies/{assembly_id} — returns full assembly dict or None."""
        url = f"{self.base_url}/smartassemblies/{assembly_id}"
        data = await self._get(url)
        if data and assembly_id not in self._logged_fields:
            log.debug("BlockchainClient: assembly %s top-level keys: %s",
                      assembly_id[:12], list(data.keys()))
            self._logged_fields.add(assembly_id)
        return data

    async def get_assemblies_in_system(self, system_id: int) -> list:
        """GET /api/assemblies?systemId={system_id} — returns list or [] on error."""
        url = f"{self.base_url}/api/assemblies?systemId={system_id}"
        data = await self._get(url)
        if data is None:
            return []
        if isinstance(data, list):
            return data
        # Some endpoints wrap in {"assemblies": [...]}
        if isinstance(data, dict):
            for key in ("assemblies", "data", "items"):
                if isinstance(data.get(key), list):
                    return data[key]
        return []

    def _parse_inventory(self, assembly_data: dict) -> list:
        """Extract inventory items from assembly data.

        Probes candidate paths since field name is not yet confirmed.
        Returns [{type_name, quantity}] or [].
        """
        if not assembly_data:
            return []
        # Candidate top-level keys to probe
        for key in ("inventory", "items", "storageItems", "storage_items"):
            val = assembly_data.get(key)
            if isinstance(val, list):
                return self._normalise_items(val)
            if isinstance(val, dict):
                # Might be {"items": [...]}
                inner = val.get("items") or val.get("storageItems") or []
                if isinstance(inner, list):
                    return self._normalise_items(inner)
        return []

    def _normalise_items(self, items: list) -> list:
        result = []
        for item in items:
            if not isinstance(item, dict):
                continue
            type_name = (
                item.get("typeName") or item.get("type_name") or
                item.get("name") or item.get("itemType") or "Unknown"
            )
            quantity = item.get("quantity") or item.get("qty") or item.get("amount") or 0
            try:
                quantity = int(quantity)
            except (TypeError, ValueError):
                quantity = 0
            result.append({"type_name": type_name, "quantity": quantity})
        return result


# Module-level singleton
blockchain_client = BlockchainClient()
