"""
System knowledge graph endpoints.

Public read-only intel: what enemies and ores have been confirmed in each solar system
across all pilots and all time.

Endpoints:
- GET /system-knowledge/{system_name}  — full system profile
- GET /system-knowledge/search         — ?q=<name>&type=enemy|ore
- GET /system-knowledge/stats          — global graph statistics
"""

from fastapi import APIRouter, Query
from fastapi.responses import JSONResponse

system_knowledge_router = APIRouter(prefix="/system-knowledge", tags=["system-knowledge"])


@system_knowledge_router.get("/stats")
async def get_stats():
    """Global knowledge graph statistics: systems mapped, sighting counts, top entities."""
    from src import system_knowledge
    return system_knowledge.get_stats()


@system_knowledge_router.get("/search")
async def search(
    q: str = Query(..., description="Enemy or ore name to search"),
    type: str | None = Query(None, description="Filter by type: 'enemy' or 'ore'"),
):
    """Cross-system search for an enemy type or ore type."""
    from src import system_knowledge
    entry_type = type if type in ("enemy", "ore") else None
    results = system_knowledge.search_entity(q, entry_type=entry_type)
    return {"query": q, "type": entry_type, "results": results}


@system_knowledge_router.get("/{system_name}")
async def get_system(system_name: str):
    """Full knowledge profile for a solar system."""
    from src import system_knowledge
    result = system_knowledge.query_system(system_name)
    if not result.get("found"):
        return JSONResponse(status_code=404, content={"found": False, "system_name": system_name})
    return result
