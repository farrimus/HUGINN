"""
Admin and debug endpoints — health, rebuilding indexes, debug state, log streaming.

Endpoints:
- GET /health                              — Health check
- POST /admin/rebuild-index                — Rebuild world API index
- POST /admin/rebuild-location-index       — Rebuild location index
- GET /debug                               — Full pipeline debug state
- GET /logs/stream                         — SSE stream of live log lines
"""

import os
import json
import asyncio
import logging
from collections import deque
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse

from src.utils import require_token
from src.world_api import world_api
from src.location_index import location_index
from src.route_engine import route_engine

log = logging.getLogger(__name__)

admin_router = APIRouter()

# ────────────────────────────────────────────────────────────────────────────
# Live log broadcaster — streams server log lines to connected SSE clients
# ────────────────────────────────────────────────────────────────────────────

_log_history: deque = deque(maxlen=200)
_log_clients: list[asyncio.Queue] = []
_log_loop: asyncio.AbstractEventLoop | None = None


class _LogBroadcastHandler(logging.Handler):
    """Custom logging handler that broadcasts log lines to SSE clients."""
    def emit(self, record: logging.LogRecord):
        line = self.format(record)
        _log_history.append(line)
        if _log_loop and not _log_loop.is_closed():
            for q in list(_log_clients):
                _log_loop.call_soon_threadsafe(q.put_nowait, line)


_broadcast_handler = _LogBroadcastHandler()
_broadcast_handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s"))


def init_logging():
    """Initialize logging handler and set up broadcast. Called from main.py lifespan."""
    global _log_loop
    _log_loop = asyncio.get_event_loop()

    root_logger = logging.getLogger()
    root_logger.addHandler(_broadcast_handler)

    # Check for DEBUG env var to enable verbose logging
    if os.getenv("DEBUG", "").lower() in ("1", "true", "yes"):
        root_logger.setLevel(logging.DEBUG)
        log.debug("Debug logging enabled via DEBUG env var")
    else:
        root_logger.setLevel(logging.INFO)


# ────────────────────────────────────────────────────────────────────────────
# Admin and debug routes
# ────────────────────────────────────────────────────────────────────────────

@admin_router.get("/health")
async def health():
    """Health check endpoint."""
    return {"status": "ok", "systems_indexed": len(world_api._system_index)}


@admin_router.post("/admin/rebuild-index", dependencies=[Depends(require_token)])
async def rebuild_index():
    """Rebuild world API systems index."""
    count = await world_api.rebuild_index()
    return {"systems_indexed": count}


@admin_router.post("/admin/rebuild-location-index", dependencies=[Depends(require_token)])
async def rebuild_location_index():
    """Rebuild LocationRevealedEvent index from chain. Requires X-Server-Token."""
    count = await location_index.rebuild()
    return {"entries_indexed": count}


@admin_router.get("/debug", dependencies=[Depends(require_token)])
async def debug():
    """
    Returns the full live state of the pipeline:
      - current system known to the server
      - raw contents of the log buffer
      - world API data for the current system (if available)
      - the exact context block Claude would receive right now
    Use this to verify the pipeline end-to-end before writing the system prompt.
    """
    return {
        "systems_indexed": len(world_api._system_index),
        "route_engine_ready": route_engine.ready(),
    }


@admin_router.get("/logs/stream", dependencies=[Depends(require_token)])
async def logs_stream():
    """SSE stream of live server log lines. Sends recent history first, then live."""
    q: asyncio.Queue = asyncio.Queue()
    for line in _log_history:
        await q.put(line)
    _log_clients.append(q)

    async def generate():
        yield ": keep-alive\n\n"
        try:
            while True:
                line = await q.get()
                yield f"data: {json.dumps({'line': line})}\n\n"
        except asyncio.CancelledError:
            pass
        finally:
            try:
                _log_clients.remove(q)
            except ValueError:
                pass

    return StreamingResponse(generate(), media_type="text/event-stream",
                             headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})
