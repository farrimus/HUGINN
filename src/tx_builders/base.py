"""Base transaction builder for Sui assemblies."""
import json
import hashlib
import logging
from typing import List, Optional
from src.blockchain_queries import nova_client

log = logging.getLogger(__name__)

# Move error code → readable message mapping
MOVE_ERROR_MAP = {
    "ENotOwner": "You do not own this assembly",
    "EAlreadyLinked": "Gate is already linked to a target",
    "EInvalidTargetSystem": "Target system does not exist or is invalid",
    "EAssemblyNotFound": "Assembly object not found",
    # Legacy codes (fallback)
    "0x1": "Not authorized",
    "0x2": "Already in list",
    "0x3": "Not found in list",
}

def map_move_error(error_str: str) -> str:
    """Map Sui Move abort code to readable message."""
    for code, msg in MOVE_ERROR_MAP.items():
        if code in error_str:
            return msg
    return f"Move error: {error_str}"

class BaseTransactionBuilder:
    """
    Base class for all assembly transaction builders.

    Knows how to:
    - Construct Sui PTBs from package/module/function info
    - Dry-run transactions
    - Map Move errors to readable messages
    """

    def __init__(
        self,
        assembly_type: str,
        wallet_address: str,
        world_package_id: str,
    ):
        """
        Args:
            assembly_type: "ssu", "gate", "turret", etc.
            wallet_address: Player's Sui address ("0x...")
            world_package_id: Network-specific package ID (from .env)
        """
        self.assembly_type = assembly_type
        self.wallet_address = wallet_address
        self.world_package_id = world_package_id
        self.nova_client = nova_client

    async def construct_ptb(
        self,
        module: str,
        function: str,
        inputs: List[dict],
        transactions: List[dict],
        gas_budget: int = 10_000_000,
    ) -> dict:
        """
        Construct a Sui Programmable Transaction Block.

        Args:
            module: Move module name (e.g., "gate", "ssu")
            function: Entry function name (e.g., "link", "activate")
            inputs: List of input objects/values
            transactions: List of Move calls
            gas_budget: Gas budget in MIST (default 10M for simple ops; 20M+ for complex)

        Returns:
            Unsigned PTB dict (Sui PTB JSON format)

        Note: Caller fills gasData.payment with coin objects (client-side responsibility).
        """
        current_epoch = await self.nova_client.get_current_epoch()

        return {
            "version": 1,
            "sender": self.wallet_address,
            "expiration": {"Epoch": current_epoch},
            "gasData": {
                "payment": [],  # Client fills with coin objects
                "owner": self.wallet_address,
                "price": 1000,
                "budget": gas_budget,
            },
            "inputs": inputs,
            "transactions": transactions,
        }

    async def dry_run(self, ptb: dict) -> dict:
        """
        Simulate transaction without executing.

        Returns:
            {"success": bool, "gas_estimate": int, "state_changes": dict, "error": str}
        """
        try:
            result = await self.nova_client.dry_run_transaction_block(ptb)

            if result.get("error"):
                error_msg = map_move_error(str(result["error"]))
                return {
                    "success": False,
                    "gas_estimate": None,
                    "state_changes": None,
                    "error": error_msg,
                }

            effects = result.get("result", {}).get("effects", {})
            gas_used = effects.get("gasUsed", {})
            computation_cost = int(gas_used.get("computationCost", 0))

            return {
                "success": True,
                "gas_estimate": computation_cost,
                "state_changes": effects.get("modifiedAt"),
                "error": None,
            }
        except Exception as e:
            log.exception("Dry-run failed: %s", e)
            return {
                "success": False,
                "gas_estimate": None,
                "state_changes": None,
                "error": str(e),
            }

    def tx_digest(self, ptb: dict) -> str:
        """Compute transaction digest hash (first 16 hex chars of SHA256)."""
        ptb_json = json.dumps(ptb, sort_keys=True)
        return hashlib.sha256(ptb_json.encode()).hexdigest()[:16]
