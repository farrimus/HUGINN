"""
src/endpoints/session.py

Character session endpoints.

POST   /session/register           — create or update session (upsert on wallet+name)
GET    /session/{wallet}           — fetch session
PATCH  /session/{wallet}           — update tribe_id / character_id (owner auth)
GET    /session/{wallet}/memory    — fetch interaction_memory[] (owner auth)
POST   /session/{wallet}/memory    — append memory entry (owner auth)
"""

import datetime
import logging
from typing import Optional

from fastapi import APIRouter, HTTPException, Header, Query, Request
from pydantic import BaseModel

from src.session_store import (
    CharacterSession,
    load_session,
    save_session,
    _WALLET_RE,
)
from src.vouch_store import set_override, remove_override, apply_override, GRANTABLE_TIERS

log = logging.getLogger(__name__)
session_router = APIRouter()

_MAX_MEMORY = 200


def _require_owner(wallet: str, x_wallet_address: Optional[str]) -> None:
    if x_wallet_address != wallet:
        raise HTTPException(status_code=403, detail="Forbidden")


def _require_session_owner(x_wallet_address: Optional[str]) -> str:
    """Return caller's wallet if their stored session tier == OWNER. Raises 403 otherwise."""
    from src.utils import require_session_owner
    return require_session_owner(x_wallet_address or "")


def _validate_wallet(wallet: str) -> None:
    if not _WALLET_RE.match(wallet):
        raise HTTPException(status_code=400, detail="Invalid wallet address")


# ---------------------------------------------------------------------------
# POST /session/register
# ---------------------------------------------------------------------------

class RegisterRequest(BaseModel):
    wallet_address: str
    character_name: str
    assembly_id: Optional[str] = None
    tenant: str = ""
    character_id: Optional[int] = None
    tribe_id: Optional[int] = None


@session_router.post("/session/register")
async def register_session(req: RegisterRequest):
    """Create or update a session. Upserts character_name if it changed.
    If assembly_id is provided, resolves the caller's access tier from the
    on-chain AccessRegistry and returns it in the response."""
    _validate_wallet(req.wallet_address)
    if not req.character_name.strip():
        raise HTTPException(status_code=400, detail="character_name required")

    import os
    _tenant = req.tenant.strip() or os.getenv("DEPLOYMENT_ENV", "utopia")

    session = load_session(req.wallet_address, tenant=_tenant)
    if session is None:
        session = CharacterSession(
            wallet_address=req.wallet_address,
            character_name=req.character_name.strip(),
            tenant=_tenant,
        )
        log.info("session: new session for %s (%s) tenant=%s", req.wallet_address[:12], req.character_name, _tenant)
    else:
        if session.character_name != req.character_name.strip():
            log.info("session: name update %s: %r -> %r",
                     req.wallet_address[:12], session.character_name, req.character_name.strip())
            session.character_name = req.character_name.strip()
        session.tenant = _tenant

    if req.character_id is not None:
        session.character_id = req.character_id
    if req.tribe_id is not None:
        session.tribe_id = req.tribe_id

    tier = "NONE"
    if req.assembly_id:
        try:
            from src.structure_persistence import load_profile
            from src.blockchain_queries import sui_rpc_client
            profile = load_profile(req.assembly_id)
            registry_id = (profile.tier_registry_object_id if profile else None) \
                or os.environ.get("TIER_REGISTRY_OBJECT_ID", "")
            if registry_id:
                registry = await sui_rpc_client.get_access_registry(registry_id)
                if registry:
                    tier = sui_rpc_client.resolve_tier(req.wallet_address, registry)
                    log.info("session/register: %s tier=%s", req.wallet_address[:12], tier)
        except Exception as e:
            log.warning("session/register: tier resolution failed: %s", e)

    # Apply any server-side vouch override (elevation only)
    tier = apply_override(tier, req.wallet_address)

    session.tier = tier
    save_session(session, tenant=_tenant)

    from dataclasses import asdict
    return {"tier": tier, **asdict(session)}


# ---------------------------------------------------------------------------
# GET /session/{wallet}
# ---------------------------------------------------------------------------

@session_router.get("/session/{wallet}")
async def get_session(wallet: str):
    _validate_wallet(wallet)
    session = load_session(wallet)
    if session is None:
        raise HTTPException(status_code=404, detail="Session not found")
    from dataclasses import asdict
    return asdict(session)


# ---------------------------------------------------------------------------
# PATCH /session/{wallet}
# ---------------------------------------------------------------------------

class PatchSessionRequest(BaseModel):
    character_id: Optional[int] = None
    tribe_id: Optional[int] = None
    ship_profile: Optional[dict] = None


@session_router.patch("/session/{wallet}")
async def patch_session(
    wallet: str,
    req: PatchSessionRequest,
    x_wallet_address: Optional[str] = Header(default=None),
):
    _validate_wallet(wallet)
    _require_owner(wallet, x_wallet_address)
    session = load_session(wallet)
    if session is None:
        raise HTTPException(status_code=404, detail="Session not found")

    changed = False
    if req.character_id is not None:
        session.character_id = req.character_id
        changed = True
    if req.tribe_id is not None:
        session.tribe_id = req.tribe_id
        changed = True
    if req.ship_profile is not None:
        session.ship_profile = req.ship_profile
        changed = True

    if changed:
        save_session(session)

    from dataclasses import asdict
    return asdict(session)


# ---------------------------------------------------------------------------
# GET /session/{wallet}/memory
# ---------------------------------------------------------------------------

@session_router.get("/session/{wallet}/memory")
async def get_memory(
    wallet: str,
    x_wallet_address: Optional[str] = Header(default=None),
):
    _validate_wallet(wallet)
    _require_owner(wallet, x_wallet_address)
    session = load_session(wallet)
    if session is None:
        raise HTTPException(status_code=404, detail="Session not found")
    return {"memory": session.interaction_memory}


# ---------------------------------------------------------------------------
# POST /session/{wallet}/memory
# ---------------------------------------------------------------------------

class MemoryEntryRequest(BaseModel):
    type: str
    summary: str
    data: dict = {}


@session_router.post("/session/{wallet}/memory")
async def append_memory(
    wallet: str,
    req: MemoryEntryRequest,
    x_wallet_address: Optional[str] = Header(default=None),
):
    _validate_wallet(wallet)
    _require_owner(wallet, x_wallet_address)
    session = load_session(wallet)
    if session is None:
        raise HTTPException(status_code=404, detail="Session not found")

    entry = {
        "timestamp": datetime.datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ"),
        "type": req.type,
        "summary": req.summary[:500],
        "data": req.data,
    }
    session.interaction_memory.append(entry)

    # Cap at _MAX_MEMORY, keep newest
    if len(session.interaction_memory) > _MAX_MEMORY:
        session.interaction_memory = session.interaction_memory[-_MAX_MEMORY:]

    save_session(session)
    return {"entry": entry, "total": len(session.interaction_memory)}


# ---------------------------------------------------------------------------
# POST /session/{wallet}/vouch
# ---------------------------------------------------------------------------

class VouchRequest(BaseModel):
    tier: str = "VETTED"
    env: Optional[str] = None


@session_router.post("/session/{wallet}/vouch")
async def vouch_wallet(
    wallet: str,
    req: VouchRequest,
    x_wallet_address: Optional[str] = Header(default=None),
):
    """Grant a tier override to wallet. Caller must have an OWNER-tier session."""
    _validate_wallet(wallet)
    voucher_wallet = _require_session_owner(x_wallet_address)

    tier = req.tier.upper()
    if tier not in GRANTABLE_TIERS:
        raise HTTPException(status_code=400,
                            detail=f"Invalid tier. Allowed: {sorted(GRANTABLE_TIERS)}")
    if wallet.lower() == voucher_wallet.lower():
        raise HTTPException(status_code=400, detail="Cannot vouch for yourself")

    set_override(wallet, tier, env=req.env)
    log.info("vouch: %s granted %s -> %s (env=%s)", voucher_wallet[:12], wallet[:12], tier, req.env or "current")

    # Immediately update existing session — only if vouching into the current env
    import os as _os
    current_env = _os.getenv("DEPLOYMENT_ENV", "utopia")
    updated_session = False
    if not req.env or req.env == current_env:
        target = load_session(wallet)
        if target is not None:
            new_tier = apply_override(target.tier, wallet)
            if new_tier != target.tier:
                target.tier = new_tier
                save_session(target)
                updated_session = True

    return {"wallet": wallet, "tier": tier, "updated_session": updated_session}


# ---------------------------------------------------------------------------
# DELETE /session/{wallet}/vouch
# ---------------------------------------------------------------------------

@session_router.delete("/session/{wallet}/vouch")
async def revoke_vouch(
    wallet: str,
    env: Optional[str] = Query(default=None),
    x_wallet_address: Optional[str] = Header(default=None),
):
    """Remove tier override for wallet. Resets session tier to NONE."""
    _validate_wallet(wallet)
    _require_session_owner(x_wallet_address)

    revoked = remove_override(wallet, env=env)

    # Reset session only if revoking from the current env
    import os as _os
    current_env = _os.getenv("DEPLOYMENT_ENV", "utopia")
    if not env or env == current_env:
        target = load_session(wallet)
        if target is not None:
            target.tier = "NONE"
            save_session(target)
            log.info("vouch: revoked override for %s, session reset to NONE", wallet[:12])

    return {"wallet": wallet, "revoked": revoked}
