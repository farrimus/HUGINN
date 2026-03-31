"""
src/endpoints/news.py

GET /news/latest — Huginn's Signal article.
Access gated to OWNER and TRIBE via on-chain AccessRegistry.
"""
import logging
from typing import Optional

from fastapi import APIRouter, Header, HTTPException, Query

log = logging.getLogger(__name__)
news_router = APIRouter()


@news_router.get("/news/latest")
async def get_latest_news(
    assembly_id: str = Query(...),
    x_wallet_address: Optional[str] = Header(None),
):
    """Return latest Huginn Signal article. OWNER and TRIBE only."""
    if not x_wallet_address:
        raise HTTPException(status_code=401, detail="X-Wallet-Address required")

    from src.structure_persistence import load_profile
    profile = load_profile(assembly_id)
    if not profile:
        raise HTTPException(status_code=404, detail="Assembly not found")

    tier = "NONE"
    if profile.tier_registry_object_id:
        try:
            from src.blockchain_queries import sui_rpc_client
            registry = await sui_rpc_client.get_access_registry(profile.tier_registry_object_id)
            if registry:
                tier = sui_rpc_client.resolve_tier(x_wallet_address, registry)
        except Exception as e:
            log.warning("news: tier resolution failed: %s", e)

    if tier not in ("OWNER", "TRIBE"):
        raise HTTPException(status_code=403, detail="Signal access restricted to OWNER and TRIBE")

    from src.huginn_news import load_article
    article = load_article()
    if not article:
        raise HTTPException(status_code=404, detail="No Signal on file")

    return article
