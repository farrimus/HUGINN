"""
Utility functions for auth and world API queries.
Extracted from deleted custom auth modules (using official DApp Kit for production auth).
"""

import os
import logging
from fastapi import Header, HTTPException

log = logging.getLogger(__name__)


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
