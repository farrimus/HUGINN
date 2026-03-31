"""
src/endpoints/tribe.py

Tribe presence board endpoints.

POST /tribe/presence              — heartbeat (X-Wallet-Address, body: tribe_id, location, status)
GET  /tribe/{tribe_id}            — current presence snapshot (no auth)
GET  /tribe/{tribe_id}/stream     — SSE stream of presence updates (no auth)
"""

import asyncio
import json
import logging
from typing import Optional

from fastapi import APIRouter, Header, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from src.session_store import load_session, _WALLET_RE
from src.tribe_board import update_presence, get_presence, subscribe, unsubscribe

log = logging.getLogger(__name__)
tribe_router = APIRouter()


def _require_wallet(x_wallet_address: Optional[str]) -> str:
    if not x_wallet_address or not _WALLET_RE.match(x_wallet_address):
        raise HTTPException(status_code=400, detail="X-Wallet-Address header required")
    return x_wallet_address


# ---------------------------------------------------------------------------
# POST /tribe/presence
# ---------------------------------------------------------------------------

class HeartbeatRequest(BaseModel):
    tribe_id: int
    location: str = "unknown"
    status: str = "active"


@tribe_router.post("/tribe/presence")
async def tribe_heartbeat(
    req: HeartbeatRequest,
    x_wallet_address: Optional[str] = Header(default=None),
):
    wallet = _require_wallet(x_wallet_address)

    if req.tribe_id <= 0:
        raise HTTPException(status_code=400, detail="tribe_id must be a positive integer")

    # Resolve character name from session (optional — falls back to abbreviated wallet)
    session = load_session(wallet)
    character_name = session.character_name if session else wallet[:12] + "..."

    location = req.location.strip() or "unknown"
    status = req.status.strip() or "active"

    entry = update_presence(
        tribe_id=req.tribe_id,
        wallet_address=wallet,
        character_name=character_name,
        location=location,
        status=status,
    )
    return {"member": entry}


# ---------------------------------------------------------------------------
# GET /tribe/{tribe_id}
# ---------------------------------------------------------------------------

@tribe_router.get("/tribe/{tribe_id}")
async def get_tribe_presence(tribe_id: int):
    if tribe_id <= 0:
        raise HTTPException(status_code=400, detail="tribe_id must be a positive integer")

    members = get_presence(tribe_id)
    return {
        "tribe_id": tribe_id,
        "online": len(members),
        "members": members,
    }


# ---------------------------------------------------------------------------
# GET /tribe/{tribe_id}/stream
# ---------------------------------------------------------------------------

@tribe_router.get("/tribe/{tribe_id}/stream")
async def tribe_presence_stream(tribe_id: int):
    if tribe_id <= 0:
        raise HTTPException(status_code=400, detail="tribe_id must be a positive integer")

    q = subscribe(tribe_id)

    async def generate():
        # Send current snapshot immediately on connect
        members = get_presence(tribe_id)
        snapshot = {"type": "snapshot", "tribe_id": tribe_id, "members": members}
        yield f"data: {json.dumps(snapshot)}\n\n"

        try:
            while True:
                event = await q.get()
                yield f"data: {json.dumps(event)}\n\n"
        except asyncio.CancelledError:
            pass
        finally:
            unsubscribe(tribe_id, q)

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
