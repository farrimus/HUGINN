"""Gate assembly transaction builders."""
import logging
from typing import Optional
from src.tx_builders.base import BaseTransactionBuilder
from src.blockchain_queries import nova_client

log = logging.getLogger(__name__)

PACKAGE_ID = "0xf33568afc1a24e7b5de4db95d01b5db1d0ef6a99269251fb9a355dde844255b9"

def build_link_gate_ptb(
    owner_cap_id: str,
    gate_id: str,
    target_system_id: int,
) -> dict:
    """
    Build unsigned PTB for Gate link operation.

    Args:
        owner_cap_id: OwnerCap<Gate> object ID
        gate_id: Gate assembly object ID
        target_system_id: Target system ID (u64)

    Returns:
        PTB inputs/commands dict (ready to wrap in sender/expiration/gasData)
    """
    inputs = [
        {"type": "object", "objectId": owner_cap_id},  # Input 0: OwnerCap<Gate>
        {"type": "object", "objectId": gate_id},       # Input 1: &mut Gate
        {
            "type": "pure",
            "valueType": "u64",
            "value": str(target_system_id)
        }  # Input 2: target_system_id
    ]

    commands = [{
        "kind": "MoveCall",
        "target": f"{PACKAGE_ID}::gate::link_smart_gates",
        "typeArguments": [f"{PACKAGE_ID}::assembly::Gate"],
        "arguments": [0, 1, 2]
    }]

    return {"inputs": inputs, "commands": commands}


def build_unlink_gate_ptb(
    owner_cap_id: str,
    gate_id: str,
) -> dict:
    """
    Build unsigned PTB for Gate unlink operation.

    Args:
        owner_cap_id: OwnerCap<Gate> object ID
        gate_id: Gate assembly object ID

    Returns:
        PTB inputs/commands dict
    """
    inputs = [
        {"type": "object", "objectId": owner_cap_id},  # Input 0: OwnerCap<Gate>
        {"type": "object", "objectId": gate_id},       # Input 1: &mut Gate
    ]

    commands = [{
        "kind": "MoveCall",
        "target": f"{PACKAGE_ID}::gate::unlink_smart_gate",
        "typeArguments": [f"{PACKAGE_ID}::assembly::Gate"],
        "arguments": [0, 1]
    }]

    return {"inputs": inputs, "commands": commands}


class GateTransactionBuilder(BaseTransactionBuilder):
    """Builds unsigned transactions for Gate state changes."""

    async def build_link_ptb(
        self,
        gate_id: str,
        target_system_id: int,
    ) -> dict:
        """
        Build complete unsigned PTB for Gate link.

        Args:
            gate_id: Gate assembly object ID
            target_system_id: Target system to link to

        Returns:
            Full unsigned PTB with sender/expiration/gasData
        """
        # Discover player's OwnerCap<Gate>
        caps = await nova_client.get_owner_caps(self.wallet_address, assembly_type="Gate")
        if not caps:
            raise Exception("You do not own any gates (OwnerCap not found)")

        cap_id = caps[0]

        # Build PTB structure
        ptb_struct = build_link_gate_ptb(cap_id, gate_id, target_system_id)

        # Wrap in full PTB
        ptb = await self.construct_ptb(
            module="gate",
            function="link_smart_gates",
            inputs=ptb_struct["inputs"],
            transactions=ptb_struct["commands"],
            gas_budget=10_000_000,
        )

        return ptb

    async def build_unlink_ptb(
        self,
        gate_id: str,
    ) -> dict:
        """
        Build complete unsigned PTB for Gate unlink.

        Args:
            gate_id: Gate assembly object ID

        Returns:
            Full unsigned PTB
        """
        # Discover player's OwnerCap<Gate>
        caps = await nova_client.get_owner_caps(self.wallet_address, assembly_type="Gate")
        if not caps:
            raise Exception("You do not own any gates (OwnerCap not found)")

        cap_id = caps[0]

        ptb_struct = build_unlink_gate_ptb(cap_id, gate_id)

        ptb = await self.construct_ptb(
            module="gate",
            function="unlink_smart_gate",
            inputs=ptb_struct["inputs"],
            transactions=ptb_struct["commands"],
            gas_budget=10_000_000,
        )

        return ptb
