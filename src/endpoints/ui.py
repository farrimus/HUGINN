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
from fastapi.responses import FileResponse

ui_router = APIRouter()


@ui_router.get("/config")
async def get_config():
    """Return server configuration for the frontend (tenant, etc.)."""
    return {"tenant": os.getenv("DEPLOYMENT_ENV", "utopia")}


@ui_router.get("/")
async def index():
    """Serve the React CLI companion app."""
    return FileResponse("frontend/dist/index.html")


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
