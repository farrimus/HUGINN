"""
Search and discovery endpoints — radius search, structure records, killmails.

Endpoints:
- GET /structures                          — List all loaded structures
- POST /search/radius                      — Search for systems within a radius
- POST /structures/record                  — Record a structure location
- GET /structures/locations                — Get all recorded structure locations
- GET /api/radius_search/{assembly_id}    — Get cached radius search (or build on-demand)
- GET /api/radius_search/{assembly_id}/kills — Refresh kills data for cached search
"""

import logging
from datetime import datetime, timezone
from fastapi import APIRouter, HTTPException, Depends

from src.utils import require_token
from src.radius_search import RadiusSearch
from src.structure_persistence import load_profile as load_structure_profile
from src.schemas import RadiusSearchRequest, RecordStructureRequest

log = logging.getLogger(__name__)

search_router = APIRouter()

# Initialize radius search singleton
radius_search = RadiusSearch()


@search_router.get("/structures", tags=["structure"])
async def list_structures():
    """List all loaded structures.

    Public endpoint (no auth required). Used by debug UI to populate dropdowns.

    Returns 503 if structure configuration is unavailable.

    Returns:
        {
          "structures": [
            {
              "id": "keep-7a",
              "system_name": "JITA",
              "owner_address": "0x442f...",
              "services": ["repair"],
              "polling_enabled": true
            }
          ],
          "count": 1
        }
    """
    try:
        # Access structures cache from app state
        # This will be set by main.py lifespan
        structures = getattr(search_router, '_structures_cache', [])

        return {
            "structures": [
                {
                    "id": s["id"],
                    "system_name": s["system_name"],
                    "owner_address": s["owner_address"],
                    "services": s.get("services", []),
                    "polling_enabled": s.get("polling_enabled", True),
                }
                for s in structures
            ],
            "count": len(structures),
        }
    except Exception as e:
        log.error(f"Failed to prepare structure list: {e}")
        from fastapi.responses import JSONResponse
        return JSONResponse(
            status_code=503,
            content={"detail": "Structure configuration unavailable"}
        )


@search_router.post("/search/radius", dependencies=[Depends(require_token)])
async def search_radius(req: RadiusSearchRequest):
    """Search for systems within a radius and apply filters."""
    try:
        result = await radius_search.search(
            center_system=req.center_system,
            radius_ly=req.radius_ly,
            filters=req.filters,
            killmail_hours=req.killmail_hours,
            top_n=req.top_n,
            skip_heat_traps=req.skip_heat_traps,
        )
        return {"data": result}
    except Exception as e:
        log.error("search_radius failed: %s", e)
        raise HTTPException(status_code=500, detail=f"Search failed: {str(e)}")


@search_router.post("/structures/record", dependencies=[Depends(require_token)])
async def record_structure(req: RecordStructureRequest):
    """Record a structure location in the radius search index."""
    try:
        timestamp = datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z')
        radius_search.structure_locations[req.assembly_id] = {
            "system_name": req.system_name,
            "reported_by": req.reported_by,
            "tribe": req.tribe,
            "discovered_at": timestamp,
            "source": "manual",
        }
        await radius_search._save_structure_locations()
        return {
            "data": {
                "assembly_id": req.assembly_id,
                "system_name": req.system_name,
                "reported_by": req.reported_by,
                "tribe": req.tribe,
                "discovered_at": timestamp,
            }
        }
    except Exception as e:
        log.error("record_structure failed: %s", e)
        raise HTTPException(status_code=500, detail=f"Failed to record structure: {str(e)}")


@search_router.get("/structures/locations", dependencies=[Depends(require_token)])
async def get_structures_locations():
    """Get all recorded structure locations."""
    try:
        structures = []
        for struct_id, struct_data in radius_search.structure_locations.items():
            structures.append({
                "assembly_id": struct_id,
                "system_name": struct_data.get("system_name"),
                "reported_by": struct_data.get("reported_by"),
                "tribe": struct_data.get("tribe"),
                "discovered_at": struct_data.get("discovered_at"),
            })
        return {"data": {"structures": structures}}
    except Exception as e:
        log.error("get_structures_locations failed: %s", e)
        raise HTTPException(status_code=500, detail=f"Failed to retrieve structures: {str(e)}")


@search_router.get("/api/radius_search/{assembly_id}")
async def get_radius_search_cache(assembly_id: str):
    """
    Get radius search cache for a structure.

    On cache miss: builds cache on-demand and returns data.
    On cache hit: returns cached data immediately.

    No auth required (public data).

    Args:
        assembly_id: Structure assembly ID (slug)

    Returns:
        {
            "data": {
                "assembly_id": "keep-7a",
                "center_system": "UR8-K7K",
                "radius_ly": 100,
                "static_data_loaded_at": "2026-03-22T12:34:56Z",
                "kills_last_updated": "2026-03-22T12:34:56Z",
                "systems": [...]
            }
        }
    """
    try:
        # Try to load existing cache
        cache = radius_search.load_cache(assembly_id)

        if cache is None:
            # Cache miss: build on-demand
            profile = load_structure_profile(assembly_id)
            center_system = profile.system_name if profile else None

            if not center_system:
                log.warning(f"Structure profile not found for {assembly_id}, using fallback center system")
                center_system = "UR8-K7K"

            # Build cache
            cache = await radius_search.build_cache(
                assembly_id=assembly_id,
                center_system=center_system,
                radius_ly=100.0
            )
            log.info(f"Built radius search cache for {assembly_id} (on-demand)")
        else:
            log.debug(f"Loaded radius search cache for {assembly_id} (hit)")

        return {"data": cache}
    except Exception as e:
        log.error(f"get_radius_search_cache failed for {assembly_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@search_router.get("/api/radius_search/{assembly_id}/kills")
async def refresh_radius_search_kills(assembly_id: str):
    """
    Refresh kills data for a cached radius search.

    Returns latest kills/24h for systems in existing cache.
    Called on page load to update kills column.

    No auth required (public data).

    Args:
        assembly_id: Structure assembly ID (slug)

    Returns:
        {
            "kills_updated": "2026-03-22T12:35:00Z",
            "systems": {
                "UR8-K7K": 5,
                "TEST-NEARBY": 3,
                ...
            }
        }
    """
    try:
        cache = await radius_search.refresh_cache_kills(assembly_id)

        # Return just the kills map (for client-side update)
        kills_map = {}
        for system in cache["systems"]:
            kills_map[system["name"]] = system["kills_24h"]

        return {
            "kills_updated": cache["kills_last_updated"],
            "systems": kills_map
        }
    except ValueError as e:
        # Cache not found
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        log.error(f"refresh_radius_search_kills failed for {assembly_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))
