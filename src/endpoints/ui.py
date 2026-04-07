"""
UI route handlers — serve React app and config.

Endpoints:
- GET /      — React CLI companion app (main UI, no-cache)
- GET /app   — SPA entry (no-cache; /app/... assets served by StaticFiles mount in main.py)
- GET /config — Server config for frontend (tenant)
"""

import os

from fastapi import APIRouter
from fastapi.responses import FileResponse

ui_router = APIRouter()

_NO_CACHE_HEADERS = {
    "Cache-Control": "no-cache, no-store, must-revalidate",
    "Pragma": "no-cache",
    "Expires": "0",
}


@ui_router.get("/config")
async def get_config():
    """Return server configuration for the frontend (tenant, etc.)."""
    return {"tenant": os.getenv("DEPLOYMENT_ENV", "utopia")}


@ui_router.get("/")
async def index():
    """Serve the React CLI companion app."""
    return FileResponse("frontend/dist/index.html", headers=_NO_CACHE_HEADERS)


@ui_router.get("/app")
async def app_entry():
    """SPA entry — served no-cache so browsers always pick up new JS bundles after rebuild."""
    return FileResponse("frontend/dist/index.html", headers=_NO_CACHE_HEADERS)
