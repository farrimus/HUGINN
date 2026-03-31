"""
src/endpoints/courier.py

Courier contract board endpoints.

GET    /courier              — list active contracts (no auth)
POST   /courier              — post new contract (X-Wallet-Address required)
PATCH  /courier/{id}/claim   — claim a contract (X-Wallet-Address required)
PATCH  /courier/{id}/status  — update status: in_transit, delivered (claimer only)
DELETE /courier/{id}         — cancel contract (poster only)
"""

import logging
from dataclasses import asdict
from typing import Optional

from fastapi import APIRouter, Header, HTTPException
from pydantic import BaseModel

from src.courier_store import (
    cancel_contract,
    claim_contract,
    create_contract,
    load_contracts,
    update_status,
)
from src.session_store import load_session, _WALLET_RE

log = logging.getLogger(__name__)
courier_router = APIRouter()

_ACTIVE_STATUSES = {"open", "claimed", "in_transit"}


def _validate_wallet(wallet: str) -> None:
    if not _WALLET_RE.match(wallet):
        raise HTTPException(status_code=400, detail="Invalid wallet address")


def _require_wallet(x_wallet_address: Optional[str]) -> str:
    if not x_wallet_address or not _WALLET_RE.match(x_wallet_address):
        raise HTTPException(status_code=400, detail="X-Wallet-Address header required")
    return x_wallet_address


# ---------------------------------------------------------------------------
# GET /courier
# ---------------------------------------------------------------------------

@courier_router.get("/courier")
async def list_contracts():
    contracts = load_contracts()
    active = [asdict(c) for c in contracts if c.status in _ACTIVE_STATUSES]
    return {"contracts": active}


# ---------------------------------------------------------------------------
# POST /courier
# ---------------------------------------------------------------------------

class PostContractRequest(BaseModel):
    item_description: str
    from_location: str
    to_location: str
    reward_description: str
    expires_at: Optional[str] = None


@courier_router.post("/courier")
async def post_contract(
    req: PostContractRequest,
    x_wallet_address: Optional[str] = Header(default=None),
):
    wallet = _require_wallet(x_wallet_address)

    session = load_session(wallet)
    if session is None:
        raise HTTPException(status_code=404, detail="Session not found — register with /session/register first")

    if not req.item_description.strip():
        raise HTTPException(status_code=400, detail="item_description is required")
    if not req.from_location.strip():
        raise HTTPException(status_code=400, detail="from_location is required")
    if not req.to_location.strip():
        raise HTTPException(status_code=400, detail="to_location is required")
    if not req.reward_description.strip():
        raise HTTPException(status_code=400, detail="reward_description is required")

    contract = create_contract(
        poster_wallet=wallet,
        poster_name=session.character_name,
        item_description=req.item_description.strip(),
        from_location=req.from_location.strip(),
        to_location=req.to_location.strip(),
        reward_description=req.reward_description.strip(),
        expires_at=req.expires_at,
    )
    log.info("courier: contract posted by %s — %s", wallet[:12], contract.id[:8])
    return {"contract": asdict(contract)}


# ---------------------------------------------------------------------------
# PATCH /courier/{id}/claim
# ---------------------------------------------------------------------------

@courier_router.patch("/courier/{contract_id}/claim")
async def claim(
    contract_id: str,
    x_wallet_address: Optional[str] = Header(default=None),
):
    wallet = _require_wallet(x_wallet_address)

    session = load_session(wallet)
    if session is None:
        raise HTTPException(status_code=404, detail="Session not found")

    try:
        contract = claim_contract(contract_id, wallet, session.character_name)
    except ValueError as e:
        msg = str(e)
        status_code = 404 if "not found" in msg else 409
        raise HTTPException(status_code=status_code, detail=msg)

    log.info("courier: contract %s claimed by %s", contract_id[:8], wallet[:12])
    return {"contract": asdict(contract)}


# ---------------------------------------------------------------------------
# PATCH /courier/{id}/status
# ---------------------------------------------------------------------------

class UpdateStatusRequest(BaseModel):
    status: str  # "in_transit" | "delivered"


@courier_router.patch("/courier/{contract_id}/status")
async def update_contract_status(
    contract_id: str,
    req: UpdateStatusRequest,
    x_wallet_address: Optional[str] = Header(default=None),
):
    wallet = _require_wallet(x_wallet_address)

    try:
        contract = update_status(contract_id, req.status, wallet)
    except PermissionError as e:
        raise HTTPException(status_code=403, detail=str(e))
    except ValueError as e:
        msg = str(e)
        status_code = 404 if "not found" in msg else 400
        raise HTTPException(status_code=status_code, detail=msg)

    log.info("courier: contract %s status → %s by %s", contract_id[:8], req.status, wallet[:12])
    return {"contract": asdict(contract)}


# ---------------------------------------------------------------------------
# DELETE /courier/{id}
# ---------------------------------------------------------------------------

@courier_router.delete("/courier/{contract_id}")
async def delete_contract(
    contract_id: str,
    x_wallet_address: Optional[str] = Header(default=None),
):
    wallet = _require_wallet(x_wallet_address)

    try:
        contract = cancel_contract(contract_id, wallet)
    except PermissionError as e:
        raise HTTPException(status_code=403, detail=str(e))
    except ValueError as e:
        msg = str(e)
        status_code = 404 if "not found" in msg else 400
        raise HTTPException(status_code=status_code, detail=msg)

    log.info("courier: contract %s cancelled by %s", contract_id[:8], wallet[:12])
    return {"cancelled": contract_id}
