"""Transaction building and submission endpoints."""
from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel, Field
from typing import Optional
import json
import logging
from src.utils import require_token

log = logging.getLogger(__name__)

tx_router = APIRouter(prefix="/tx", tags=["transactions"])

class TransactionRequest(BaseModel):
    """Request to build an unsigned transaction."""
    assembly_type: str = Field(min_length=1, max_length=50, description="Assembly type: gate, ssu, turret, etc.")
    assembly_id: str = Field(min_length=2, max_length=66, description="Sui object ID (0x...)")
    action: str = Field(min_length=1, max_length=50, description="Action: link, unlink, activate, etc.")
    params: dict = Field(default_factory=dict, description="Action-specific parameters")

class TransactionResponse(BaseModel):
    """Response with unsigned transaction."""
    success: bool
    tx_json: Optional[str] = None
    digest: Optional[str] = None
    requires_signature: bool = True
    error: Optional[str] = None

class SimulationResponse(BaseModel):
    """Response from dry-run simulation."""
    success: bool
    gas_estimate: Optional[int] = None
    state_changes: Optional[dict] = None
    error: Optional[str] = None

@tx_router.post("/build", response_model=TransactionResponse)
async def build_transaction(
    req: TransactionRequest,
    token_payload=Depends(require_token),
) -> TransactionResponse:
    """
    Build an unsigned transaction block.

    Returns a PTB ready for signing. Does NOT execute anything.

    MVP supports: assembly_type="gate", action="link" or "unlink"
    """
    try:
        from src.tx_builders.gate_builder import GateTransactionBuilder
        import os

        wallet_address = token_payload.get("address")
        world_package_id = os.getenv("WORLD_PACKAGE_ID")

        if req.assembly_type == "gate":
            builder = GateTransactionBuilder(
                assembly_type="gate",
                wallet_address=wallet_address,
                world_package_id=world_package_id,
            )

            if req.action == "link":
                if "target_system_id" not in req.params:
                    return TransactionResponse(
                        success=False,
                        error="link action requires target_system_id in params"
                    )
                target_system_id = int(req.params["target_system_id"])
                ptb = await builder.build_link_ptb(req.assembly_id, target_system_id)

            elif req.action == "unlink":
                ptb = await builder.build_unlink_ptb(req.assembly_id)

            else:
                return TransactionResponse(
                    success=False,
                    error=f"Unknown action for gate: {req.action}"
                )

            digest = builder.tx_digest(ptb)
            return TransactionResponse(
                success=True,
                tx_json=json.dumps(ptb),
                digest=digest,
            )

        else:
            return TransactionResponse(
                success=False,
                error=f"MVP supports only assembly_type='gate'; got '{req.assembly_type}'"
            )

    except Exception as e:
        log.exception("Build failed: %s", e)
        return TransactionResponse(
            success=False,
            error=str(e)
        )

@tx_router.post("/simulate", response_model=SimulationResponse)
async def simulate_transaction(
    req: TransactionRequest,
    token_payload=Depends(require_token),
) -> SimulationResponse:
    """
    Dry-run a transaction without executing.

    Validates that the transaction would succeed (catches Move errors early).
    """
    try:
        from src.tx_builders.gate_builder import GateTransactionBuilder
        import os

        wallet_address = token_payload.get("address")
        world_package_id = os.getenv("WORLD_PACKAGE_ID")

        if req.assembly_type != "gate":
            return SimulationResponse(
                success=False,
                error=f"Simulation not yet supported for {req.assembly_type}"
            )

        builder = GateTransactionBuilder(
            assembly_type="gate",
            wallet_address=wallet_address,
            world_package_id=world_package_id,
        )

        if req.action == "link":
            target_system_id = int(req.params.get("target_system_id", 0))
            ptb = await builder.build_link_ptb(req.assembly_id, target_system_id)
        elif req.action == "unlink":
            ptb = await builder.build_unlink_ptb(req.assembly_id)
        else:
            return SimulationResponse(
                success=False,
                error=f"Unknown action: {req.action}"
            )

        dry_run_result = await builder.dry_run(ptb)
        return SimulationResponse(
            success=dry_run_result["success"],
            gas_estimate=dry_run_result["gas_estimate"],
            state_changes=dry_run_result["state_changes"],
            error=dry_run_result["error"],
        )

    except Exception as e:
        log.exception("Simulate failed: %s", e)
        return SimulationResponse(
            success=False,
            error=str(e)
        )
