"""
Utility functions shared across the backend.
"""

import os
import logging
from fastapi import Header, HTTPException

log = logging.getLogger(__name__)


def parse_status(raw, _depth: int = 0) -> str:
    """Extract a human-readable status string from a nested Sui Move variant dict.

    Handles strings, None, and nested {"@variant": "ONLINE"} / {"status": {...}} structures.
    """
    if raw is None:
        return "UNKNOWN"
    if isinstance(raw, str):
        return raw
    if isinstance(raw, dict) and _depth < 3:
        for key in ("@variant", "variant", "name"):
            v = raw.get(key)
            if isinstance(v, str):
                return v
        v = raw.get("status")
        if v is not None:
            return parse_status(v, _depth + 1)
    return str(raw)


def classify_assembly_type(move_type_repr: str) -> str:
    """Map a Move type repr string to a canonical assembly type name.

    E.g. '0x...::storage_unit::StorageUnit<...>' → 'SmartStorageUnit'.
    """
    if "::storage_unit::StorageUnit" in move_type_repr:
        return "SmartStorageUnit"
    if "::turret::Turret" in move_type_repr:
        return "SmartTurret"
    if "::gate::Gate" in move_type_repr:
        return "SmartGate"
    if "::network_node::NetworkNode" in move_type_repr:
        return "NetworkNode"
    if "::manufacturing::Manufacturing" in move_type_repr:
        return "Manufacturing"
    if "::refinery::Refinery" in move_type_repr:
        return "Refinery"
    if "::assembly::Assembly" in move_type_repr:
        return "Assembly"
    return "Unknown"


def require_token(x_server_token: str = Header(default="")):
    """Simple server token validation for internal endpoints.

    Used by admin, debug, and internal endpoints that don't use DApp Kit auth.
    Allows no auth if SERVER_TOKEN env var is not set (local dev mode).
    """
    expected = os.getenv("SERVER_TOKEN", "")
    if not expected:
        return  # No token configured — open access (local-only mode)
    if x_server_token != expected:
        raise HTTPException(status_code=403, detail="Invalid token")


def require_session_owner(x_wallet_address: str = Header(default="")) -> str:
    """Verify the caller has a stored session with tier == OWNER.

    Returns the caller's wallet address. Raises 403 otherwise.
    Used by PATCH /admin/config and POST /session/{wallet}/vouch.
    """
    import re
    _WALLET_RE = re.compile(r"^0x[0-9a-fA-F]{1,64}$")
    if not x_wallet_address or not _WALLET_RE.match(x_wallet_address):
        raise HTTPException(status_code=403, detail="Forbidden")
    from src.session_store import load_session
    session = load_session(x_wallet_address)
    if session is None or session.tier != "OWNER":
        raise HTTPException(status_code=403, detail="Forbidden")
    return x_wallet_address


async def lookup_character(address: str) -> dict:
    """
    Look up a character by wallet address via the World API.
    Returns the full character dict, or empty dict on failure.

    Used by discovery endpoints and blockchain queries to resolve character info.
    Falls back gracefully if World API is unavailable.
    """
    try:
        from src.world_api import world_api
        result = await world_api.get_character_by_address(address)
        return result or {}
    except Exception as e:
        log.warning("World API character lookup failed for %s: %s", address, e)
    return {}
