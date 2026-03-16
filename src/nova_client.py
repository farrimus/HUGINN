# src/nova_client.py
"""
Sui JSON-RPC client for Nova chain (EVE Frontier builder sandbox).
Reads AccessRegistry shared objects for structure access tier resolution.

RPC endpoint configured via NOVA_RPC_URL env var.
Switching to Stillness: set NOVA_RPC_URL to the Stillness full-node endpoint.
"""
import os
import logging
import httpx
from dataclasses import dataclass, field
from typing import Optional

log = logging.getLogger(__name__)

NOVA_RPC_URL = os.environ.get(
    "NOVA_RPC_URL",
    "https://fullnode.testnet.sui.io"
)


@dataclass
class AccessRegistry:
    owner: str
    tribe: list = field(default_factory=list)
    vetted: list = field(default_factory=list)


class NovaClient:
    def __init__(self, rpc_url: str = NOVA_RPC_URL):
        self._rpc_url = rpc_url

    async def get_access_registry(self, object_id: str) -> Optional[AccessRegistry]:
        """
        Fetch an AccessRegistry shared object by its Sui object ID.
        Returns None on any RPC error (caller should fall back to server-side tier logic).

        Sui JSON-RPC method: sui_getObject
        https://docs.sui.io/sui-api-ref#sui_getobject
        """
        log.info("get_access_registry called: len=%d repr=%r", len(object_id), object_id)
        payload = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "sui_getObject",
            "params": [
                object_id,
                {"showContent": True}
            ]
        }
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.post(self._rpc_url, json=payload)
                resp.raise_for_status()
                data = resp.json()
            fields = (data.get("result", {})
                         .get("data", {})
                         .get("content", {})
                         .get("fields", {}))
            if not fields:
                log.warning("AccessRegistry object %s: no fields in response", object_id)
                return None
            return AccessRegistry(
                owner=fields.get("owner", ""),
                tribe=fields.get("tribe", []),
                vetted=fields.get("vetted", []),
            )
        except Exception as e:
            log.warning("Nova RPC error fetching AccessRegistry %s: %s", object_id, e)
            return None

    async def _rpc(self, method: str, params: list) -> dict:
        """Generic Sui JSON-RPC call. Returns the full response dict."""
        payload = {"jsonrpc": "2.0", "id": 1, "method": method, "params": params}
        async with httpx.AsyncClient(timeout=10.0) as client:
            r = await client.post(self._rpc_url, json=payload)
            r.raise_for_status()
            return r.json()

    def resolve_tier(self, address: str, registry: AccessRegistry) -> str:
        """Resolve access tier for a wallet address against an AccessRegistry."""
        addr = address.lower()
        if addr == registry.owner.lower():
            return "OWNER"
        if any(addr == t.lower() for t in registry.tribe):
            return "TRIBE"
        if any(addr == v.lower() for v in registry.vetted):
            return "VETTED"
        return "NONE"


# Global singleton
nova_client = NovaClient()
