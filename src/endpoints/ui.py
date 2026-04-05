"""
UI route handlers — serve React app and legacy terminals.

Endpoints:
- GET /     — React CLI companion app (main UI)
- GET /legacy-cli — Vanilla JS terminal (fallback)
- GET /ship-ai — Ship AI terminal (legacy)
- GET /debug-terminal — Debug terminal (legacy)
"""

import os

from fastapi import APIRouter
from fastapi.responses import FileResponse, Response

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


@ui_router.get("/demo")
async def demo():
    """Landing page for external visitors without an EVE Frontier wallet."""
    return FileResponse("static/landing.html")


@ui_router.get("/app")
async def app_entry():
    """SPA entry — served no-cache so browsers always pick up new JS bundles after rebuild."""
    return FileResponse("frontend/dist/index.html", headers=_NO_CACHE_HEADERS)


@ui_router.get("/legacy-cli")
async def legacy_cli():
    """Serve the vanilla JS building terminal (legacy)."""
    return FileResponse("static/building-terminal.html")


@ui_router.get("/ship-ai")
async def ship_ai_terminal():
    """Serve the ship AI terminal (legacy)."""
    return FileResponse("static/ship-ai-terminal.html")


@ui_router.get("/debug-terminal")
async def debug_terminal():
    """Serve the debug terminal (legacy)."""
    return FileResponse("static/debug-terminal.html")
