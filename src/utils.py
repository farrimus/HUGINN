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
    Returns dict with 'id' and 'name' keys, or empty dict on failure.

    Used by discovery endpoints and blockchain queries to resolve character info.
    Falls back gracefully if World API is unavailable.
    """
    import httpx
    from src.config import load_config_from_env

    config = load_config_from_env()
    world_api_base = os.environ.get("WORLD_API_BASE_URL") or config["world_api_url"]
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            resp = await client.get(f"{world_api_base}/v2/smartcharacters", params={"address": address})
            if resp.status_code == 200:
                data = resp.json()
                items = data if isinstance(data, list) else data.get("items", [])
                if items:
                    return {"id": items[0].get("id", 0), "name": items[0].get("name", "")}
    except Exception as e:
        log.warning("World API character lookup failed for %s: %s", address, e)
    return {}
