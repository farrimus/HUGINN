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
        self.package_id = os.environ.get(
            "EVE_FRONTIER_PACKAGE",
            "0xd12a70c74c1e759445d6f209b01d43d860e97fcf2ef72ccbbd00afd828043f75"
        )

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

    async def get_owner_caps(self, address: str, assembly_type: str = "Gate") -> list[str]:
        """
        Discover player's OwnerCap objects for an assembly type.

        Uses suix_getOwnedObjects with StructType filter (confirmed working on Nova testnet).
        Character holds OwnerCaps per world-contracts keychain pattern (transferred during deploy).

        Args:
            address: Player's Sui wallet address ("0x...")
            assembly_type: Assembly type name ("Gate", "StorageUnit", "Turret", etc.)

        Returns:
            List of OwnerCap object IDs, or empty list if none found
        """
        filter_type = f"{self.package_id}::assembly::OwnerCap<{self.package_id}::assembly::{assembly_type}>"
        resp = await self._rpc("suix_getOwnedObjects", [address, {"StructType": filter_type}, None, 50])

        caps = []
        for obj in resp.get("result", {}).get("data", []):
            if "data" in obj and "objectId" in obj["data"]:
                caps.append(obj["data"]["objectId"])

        return caps

    async def dry_run_transaction_block(self, tx: dict) -> dict:
        """
        Simulate a transaction without executing (sui_dryRunTransactionBlock).

        Used to validate PTB structure and catch Move errors before submission.

        Args:
            tx: Transaction block (Sui PTB JSON format)

        Returns:
            RPC response: {"result": {"effects": {...}, "events": [...]}, "error": {...}}
        """
        return await self._rpc("sui_dryRunTransactionBlock", [tx])

    async def execute_transaction_block(self, tx: dict, signatures: list[str]) -> dict:
        """
        Submit a signed transaction block to the network.

        Args:
            tx: Transaction block
            signatures: List of signatures

        Returns:
            RPC response: {"result": {"digest": "0x...", "effects": {...}}, "error": {...}}
        """
        return await self._rpc("sui_executeTransactionBlock", [
            tx,
            signatures,
            None,  # requestedEvents
            "WaitForLocalExecution"  # executionMode
        ])

    async def get_current_epoch(self) -> int:
        """
        Get current Sui epoch for PTB expiration window.

        Returns:
            Current epoch + 7 (7-epoch expiration window per Sui standard)
        """
        result = await self._rpc("sui_getLatestCheckpoint", [])
        sequence_num = int(result.get("result", {}).get("sequenceNumber", 0))
        return (sequence_num // 1000) + 7

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

    async def get_character(self, wallet_address: str) -> dict:
        """
        Resolve wallet address → Character via World API.

        Wrapper around structure_auth.lookup_character() for consistency in nova_client interface.
        Character = keychain holding OwnerCaps (per world-contracts pattern).

        Args:
            wallet_address: Sui wallet ("0x...")

        Returns:
            Character object: {"id": "0x...", "name": "...", ...}
        """
        from src.structure_auth import lookup_character
        return await lookup_character(wallet_address)


# Global singleton
nova_client = NovaClient()
