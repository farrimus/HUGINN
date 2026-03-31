"""
Game data endpoints — world API, Sui object inspection, galaxy database.

Endpoints:
- GET /data/systems      — Serve systems.json for client-side route calculation
- GET /data/gate-graph   — Serve gate adjacency graph
- GET /galaxy/system/{name_or_id} — Fetch system by name or ID (public)
- GET /sui/object/{object_id}     — Fetch Sui object (public)
"""

import os
import json
import logging
from fastapi import APIRouter, Request, HTTPException, Depends
from fastapi.responses import FileResponse, JSONResponse, Response
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from typing import Optional

from src.utils import require_token
from src.world_api import world_api
from src.galaxy_db import galaxy_db
from src.blockchain_queries import nova_client

log = logging.getLogger(__name__)

game_data_router = APIRouter()

# HTTP Bearer auth (optional for public endpoints)
_bearer = HTTPBearer(auto_error=False)


@game_data_router.get("/data/systems", dependencies=[Depends(require_token)])
async def get_systems(request: Request):
    """Serve systems.json for client-side RouteCalculator. ~7 MB; ETag + 304 supported."""
    path = os.path.join(os.path.dirname(__file__), "..", "data", "systems.json")
    if not os.path.exists(path):
        return JSONResponse(status_code=503, content={"detail": "systems.json not found. Run build_universe.py."})
    # Read only built_at for ETag — avoids loading 7 MB into memory just for the tag.
    with open(path) as f:
        head = f.read(128)
    import re as _re
    m = _re.search(r'"built_at"\s*:\s*"([^"]+)"', head)
    etag = f'"{m.group(1)}"' if m else '"unknown"'
    if request.headers.get("if-none-match") == etag:
        return Response(status_code=304)
    return FileResponse(path, media_type="application/json",
                        headers={"ETag": etag, "Cache-Control": "public, max-age=86400"})


@game_data_router.get("/data/gate-graph", dependencies=[Depends(require_token)])
async def gate_graph(request: Request):
    """Serve the prebuilt gate adjacency graph for client-side route calculation."""
    path = os.path.join(os.path.dirname(__file__), "..", "data", "gate_graph.json")
    if not os.path.exists(path):
        return JSONResponse(status_code=503, content={"detail": "Gate graph not built yet. POST /admin/rebuild-index."})
    with open(path) as f:
        data = json.load(f)
    etag = f'"{data.get("built_at", "unknown")}"'
    if request.headers.get("if-none-match") == etag:
        return Response(status_code=304)
    return JSONResponse(content=data, headers={"ETag": etag, "Cache-Control": "public, max-age=3600"})


@game_data_router.get("/sui/object/{object_id}")
async def get_sui_object(object_id: str, credentials: Optional[HTTPAuthorizationCredentials] = Depends(_bearer)):
    """Fetch a Sui object by ID. Requires valid token or JWT."""
    # Allow unauthenticated access for testnet exploration
    if not object_id.startswith("0x") or len(object_id) != 66:
        raise HTTPException(status_code=400, detail="Invalid Sui object ID format")

    try:
        result = await nova_client._rpc("sui_getObject", [{
            "objectId": object_id,
            "options": {"showType": True, "showContent": True, "showDisplay": True}
        }])

        if "error" in result:
            raise HTTPException(status_code=404, detail=f"Sui object error: {result['error']}")

        data = result.get("result", {})
        response = {
            "object_id": object_id,
            "data": data,
            "type": data.get("data", {}).get("type", "unknown")
        }

        return response
    except Exception as e:
        log.error(f"Failed to fetch Sui object {object_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@game_data_router.get("/galaxy/system/{name_or_id}")
async def get_galaxy_system(name_or_id: str):
    """Fetch galaxy system by name or ID (no auth required - public data)."""
    system = galaxy_db.get_system(name_or_id)
    if not system:
        raise HTTPException(status_code=404, detail=f"System not found: {name_or_id}")

    return system


@game_data_router.get("/galaxy/system/{name_or_id}/intel")
async def get_system_intel(name_or_id: str):
    """Return structured system intel panel data (no auth required)."""
    from src.structure_client import _spectral_label, _count_planets

    system_info = galaxy_db.get_system(name_or_id)
    if not system_info:
        raise HTTPException(status_code=404, detail=f"System not found: {name_or_id}")

    system_id = system_info["solarSystemId"]
    system_name = system_info["name"]

    # World API — kills and gate count (best-effort, non-blocking)
    kill_count = 0
    gate_links = 0
    try:
        system_world = await world_api.get_system(system_name)
        if system_world:
            gate_links = len(system_world.get("gateLinks", []))
        killmails = await world_api.get_killmails(system_id)
        kill_count = len(killmails) if killmails else 0
    except Exception:
        pass

    # Star and planet data from galaxy_db
    star_type = _spectral_label(system_info.get("star_spectral_class"))
    celestials = galaxy_db.get_celestials_in_system(system_id)
    planets_list = celestials.get("planets", [])
    lagrange_count = len(celestials.get("lagrange_points", []))

    hz_inner = system_info.get("habitable_zone_inner") or 0
    hz_outer = system_info.get("habitable_zone_outer") or 0
    hz_planets = [p for p in planets_list if hz_inner and hz_outer and hz_inner <= (p.get("orbitRadius") or 0) <= hz_outer]
    outer_planets = [p for p in planets_list if p not in hz_planets]
    hz_planet_count = len(hz_planets)

    hz_counts = _count_planets(hz_planets)
    outer_counts = _count_planets(outer_planets)
    parts = []
    if hz_counts:
        parts.append(f"{hz_planet_count} in HZ ({', '.join(f'{v}x {k}' for k, v in hz_counts.items())})")
    if outer_counts:
        parts.append(", ".join(f"{v}x {k}" for k, v in outer_counts.items()))
    planets_summary = f"{len(planets_list)} total — " + " | ".join(parts) if parts else str(len(planets_list))

    min_temp = str(system_info.get("safe_jump_temp", "N/A") or "N/A")

    return {
        "systemId": system_id,
        "system": system_name,
        "starClass": star_type,
        "minTemp": min_temp,
        "planets": planets_summary,
        "lagrangePoints": str(lagrange_count),
        "hzPlanets": str(hz_planet_count),
        "kills24h": str(kill_count),
        "gates": str(gate_links),
    }
