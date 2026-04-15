"""
src/endpoints/watcher.py

SSU Watcher endpoints.

GET    /watcher/{wallet}              — list watch rules for wallet
POST   /watcher/{wallet}             — add watch rule
DELETE /watcher/{wallet}/{rule_id}   — remove rule
GET    /watcher/alerts/stream        — SSE stream of alerts (X-Wallet-Address header)
"""

import asyncio
import datetime
import json
import logging
import uuid
from typing import Optional

from fastapi import APIRouter, Header, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from src.session_store import load_session, save_session, _WALLET_RE

log = logging.getLogger(__name__)
watcher_router = APIRouter()

# Per-wallet SSE queues: wallet_address -> list[Queue]
_alert_clients: dict[str, list[asyncio.Queue]] = {}


def _validate_wallet(wallet: str) -> None:
    if not _WALLET_RE.match(wallet):
        raise HTTPException(status_code=400, detail="Invalid wallet address")


def _require_owner(wallet: str, x_wallet_address: Optional[str]) -> None:
    if x_wallet_address != wallet:
        raise HTTPException(status_code=403, detail="Forbidden")


def push_alert(wallet_address: str, alert: dict) -> None:
    """Called by watcher task to push an alert to connected SSE clients."""
    for q in list(_alert_clients.get(wallet_address, [])):
        try:
            q.put_nowait(alert)
        except asyncio.QueueFull:
            pass


# ---------------------------------------------------------------------------
# GET /watcher/{wallet}
# ---------------------------------------------------------------------------

@watcher_router.get("/watcher/{wallet}")
async def list_watch_rules(
    wallet: str,
    x_wallet_address: Optional[str] = Header(default=None),
):
    _validate_wallet(wallet)
    _require_owner(wallet, x_wallet_address)
    session = load_session(wallet)
    if session is None:
        raise HTTPException(status_code=404, detail="Session not found")
    return {"rules": session.watch_list}


# ---------------------------------------------------------------------------
# POST /watcher/{wallet}
# ---------------------------------------------------------------------------

class AddWatchRequest(BaseModel):
    ssu_id: str
    ssu_name: Optional[str] = None
    item_filter: Optional[str] = None
    threshold: int = 0
    scope: str = "personal"


@watcher_router.post("/watcher/{wallet}")
async def add_watch_rule(
    wallet: str,
    req: AddWatchRequest,
    x_wallet_address: Optional[str] = Header(default=None),
):
    _validate_wallet(wallet)
    _require_owner(wallet, x_wallet_address)

    if not _WALLET_RE.match(req.ssu_id):
        raise HTTPException(status_code=400, detail="Invalid SSU ID (must be 0x...)")
    if req.scope not in ("personal", "tribe", "all"):
        raise HTTPException(status_code=400, detail="scope must be personal, tribe, or all")

    session = load_session(wallet)
    if session is None:
        raise HTTPException(status_code=404, detail="Session not found")

    rule = {
        "id": str(uuid.uuid4()),
        "wallet_address": wallet,
        "ssu_id": req.ssu_id,
        "ssu_name": req.ssu_name,
        "item_filter": req.item_filter,
        "threshold": req.threshold,
        "scope": req.scope,
        "last_checked": None,
        "last_alert": None,
        "active": True,
    }
    existing = next(
        (r for r in session.watch_list
         if r.get("ssu_id") == req.ssu_id and r.get("scope") == req.scope),
        None,
    )
    if existing:
        return {"rule": existing}
    session.watch_list.append(rule)
    save_session(session)
    log.info("watcher: rule added for %s — SSU %s", wallet[:12], req.ssu_id[:12])
    return {"rule": rule}


# ---------------------------------------------------------------------------
# DELETE /watcher/{wallet}/{rule_id}
# ---------------------------------------------------------------------------

@watcher_router.delete("/watcher/{wallet}/{rule_id}")
async def delete_watch_rule(
    wallet: str,
    rule_id: str,
    x_wallet_address: Optional[str] = Header(default=None),
):
    _validate_wallet(wallet)
    _require_owner(wallet, x_wallet_address)

    session = load_session(wallet)
    if session is None:
        raise HTTPException(status_code=404, detail="Session not found")

    before = len(session.watch_list)
    session.watch_list = [r for r in session.watch_list if r.get("id") != rule_id]
    if len(session.watch_list) == before:
        raise HTTPException(status_code=404, detail="Rule not found")

    save_session(session)
    log.info("watcher: rule %s deleted for %s", rule_id[:8], wallet[:12])
    return {"deleted": rule_id}


# ---------------------------------------------------------------------------
# GET /watcher/alerts/stream
# ---------------------------------------------------------------------------

@watcher_router.get("/watcher/alerts/stream")
async def alerts_stream(
    x_wallet_address: Optional[str] = Header(default=None),
):
    if not x_wallet_address or not _WALLET_RE.match(x_wallet_address):
        raise HTTPException(status_code=400, detail="X-Wallet-Address header required")

    wallet = x_wallet_address
    q: asyncio.Queue = asyncio.Queue(maxsize=50)
    _alert_clients.setdefault(wallet, []).append(q)

    async def generate():
        yield ": keep-alive\n\n"
        try:
            while True:
                alert = await q.get()
                yield f"data: {json.dumps(alert)}\n\n"
        except asyncio.CancelledError:
            pass
        finally:
            try:
                _alert_clients[wallet].remove(q)
            except (KeyError, ValueError):
                pass

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
