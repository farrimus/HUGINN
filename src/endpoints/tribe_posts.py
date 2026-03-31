"""
src/endpoints/tribe_posts.py

Tribe post board endpoints.

GET    /tribe-posts/{tribe_id}           — last 30 posts (no auth)
POST   /tribe-posts/{tribe_id}           — create post (X-Wallet-Address required)
DELETE /tribe-posts/{tribe_id}/{post_id} — delete own post (X-Wallet-Address required)
GET    /tribe-posts/{tribe_id}/stream    — SSE stream of post events (no auth)
"""

import asyncio
import json
import logging
from dataclasses import asdict
from typing import Optional

from fastapi import APIRouter, Header, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from src.session_store import load_session, _WALLET_RE
from src.tribe_posts import (
    DISPLAY_POSTS,
    MAX_MESSAGE_LEN,
    create_post,
    delete_post,
    load_posts,
    subscribe,
    unsubscribe,
)

log = logging.getLogger(__name__)
tribe_posts_router = APIRouter()


def _require_wallet(x_wallet_address: Optional[str]) -> str:
    if not x_wallet_address or not _WALLET_RE.match(x_wallet_address):
        raise HTTPException(status_code=400, detail="X-Wallet-Address header required")
    return x_wallet_address


# ---------------------------------------------------------------------------
# GET /tribe-posts/{tribe_id}
# ---------------------------------------------------------------------------

@tribe_posts_router.get("/tribe-posts/{tribe_id}")
async def get_tribe_posts(tribe_id: int):
    if tribe_id <= 0:
        raise HTTPException(status_code=400, detail="tribe_id must be a positive integer")
    posts = load_posts(tribe_id)
    return {"tribe_id": tribe_id, "posts": [asdict(p) for p in posts[-DISPLAY_POSTS:]]}


# ---------------------------------------------------------------------------
# POST /tribe-posts/{tribe_id}
# ---------------------------------------------------------------------------

class CreatePostRequest(BaseModel):
    message: str


@tribe_posts_router.post("/tribe-posts/{tribe_id}")
async def post_to_board(
    tribe_id: int,
    req: CreatePostRequest,
    x_wallet_address: Optional[str] = Header(default=None),
):
    wallet = _require_wallet(x_wallet_address)

    if tribe_id <= 0:
        raise HTTPException(status_code=400, detail="tribe_id must be a positive integer")

    session = load_session(wallet)
    if session is None:
        raise HTTPException(status_code=404, detail="Session not found — register first")

    message = req.message.strip()
    if not message:
        raise HTTPException(status_code=400, detail="message is required")
    if len(message) > MAX_MESSAGE_LEN:
        raise HTTPException(status_code=400, detail=f"message exceeds {MAX_MESSAGE_LEN} characters")

    post = create_post(
        tribe_id=tribe_id,
        poster_wallet=wallet,
        poster_name=session.character_name,
        message=message,
    )
    log.info("tribe_posts: post created tribe=%s wallet=%s id=%s", tribe_id, wallet[:12], post.id[:8])
    return {"post": asdict(post)}


# ---------------------------------------------------------------------------
# DELETE /tribe-posts/{tribe_id}/{post_id}
# ---------------------------------------------------------------------------

@tribe_posts_router.delete("/tribe-posts/{tribe_id}/{post_id}")
async def delete_tribe_post(
    tribe_id: int,
    post_id: str,
    x_wallet_address: Optional[str] = Header(default=None),
):
    wallet = _require_wallet(x_wallet_address)

    try:
        deleted_id = delete_post(tribe_id, post_id, wallet)
    except PermissionError as e:
        raise HTTPException(status_code=403, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))

    log.info("tribe_posts: post deleted tribe=%s id=%s by %s", tribe_id, post_id[:8], wallet[:12])
    return {"deleted": deleted_id}


# ---------------------------------------------------------------------------
# GET /tribe-posts/{tribe_id}/stream
# ---------------------------------------------------------------------------

@tribe_posts_router.get("/tribe-posts/{tribe_id}/stream")
async def tribe_posts_stream(tribe_id: int):
    if tribe_id <= 0:
        raise HTTPException(status_code=400, detail="tribe_id must be a positive integer")

    q = subscribe(tribe_id)

    async def generate():
        posts = load_posts(tribe_id)
        snapshot = {
            "type": "snapshot",
            "posts": [asdict(p) for p in posts[-DISPLAY_POSTS:]],
        }
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
