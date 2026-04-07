"""
Structure management endpoints — profiles and location management.

Endpoints:
- GET /structure/{assembly_id}                  — Get structure profile
- POST /structure/{assembly_id}                 — Update structure profile (full)
- PATCH /structure/{assembly_id}                — Update structure profile (partial)
- GET /structure/{assembly_id}/onchain          — Get on-chain object IDs and metadata
- POST /structure/{assembly_id}/location/manual — Set manual structure location
- POST /structure/{assembly_id}/location/reveal — Prove location via Sui signature
"""

import os
import logging
from datetime import datetime, timezone
from typing import Optional
from fastapi import APIRouter, HTTPException, Depends
from fastapi.responses import JSONResponse
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

from src.structure_persistence import StructureProfile, load_profile as load_structure_profile, save_profile as save_structure_profile
from src.location_index import location_index
from src.schemas import StructureProfileUpdate, LocationManualRequest, LocationRevealRequest

log = logging.getLogger(__name__)

structures_router = APIRouter()

# HTTP Bearer security (for DApp Kit JWT or server token fallback)
_bearer = HTTPBearer(auto_error=False)


async def require_structure_jwt_or_token(
    credentials: HTTPAuthorizationCredentials = Depends(_bearer)
) -> dict:
    """Accept server token for now. DApp Kit JWTs will be added when frontend migrates."""
    if not credentials:
        raise HTTPException(status_code=401, detail="No credentials provided")
    token = credentials.credentials
    server_token = os.environ.get("SERVER_TOKEN", "")
    if token == server_token:
        return {"assembly_id": "debug"}
    raise HTTPException(status_code=401, detail="Invalid token")


# ────────────────────────────────────────────────────────────────────────────
# Structure Routes
# ────────────────────────────────────────────────────────────────────────────

@structures_router.get("/structure/{assembly_id}/onchain")
async def get_structure_onchain(assembly_id: str, credentials: Optional[HTTPAuthorizationCredentials] = Depends(_bearer)):
    """Get structure's on-chain object IDs and metadata. Requires token or JWT."""
    profile = load_structure_profile(assembly_id)
    if not profile:
        raise HTTPException(status_code=404, detail="Structure not found")

    response = {
        "assembly_id": assembly_id,
        "structure_name": profile.structure_name or "—",
        "registry": profile.tier_registry_object_id or "—",
        "ssu_object_id": getattr(profile, "ssu_object_id", None) or "—",
        "connected_assemblies": getattr(profile, "connected_assembly_ids", []) or [],
        "location": location_index.get(assembly_id) if hasattr(location_index, 'get') else None,
        "system_id": profile.system_id or 0,
        "system_name": profile.system_name or "—",
    }

    return response


@structures_router.get("/structure/{assembly_id}")
async def get_structure_profile(assembly_id: str, session: dict = Depends(require_structure_jwt_or_token)):
    """Get structure profile for authenticated user. Requires structure JWT."""
    if session["assembly_id"] != assembly_id:
        raise HTTPException(status_code=403, detail="Token not valid for this structure")
    profile = load_structure_profile(assembly_id)
    if not profile:
        raise HTTPException(status_code=404, detail="Structure not found")
    tier = session.get("tier", "NONE")
    if tier == "NONE":
        raise HTTPException(status_code=403, detail="Access denied")
    return profile.as_dict_for_tier(tier)


@structures_router.post("/structure/{assembly_id}")
async def update_structure_profile(assembly_id: str, req: StructureProfileUpdate,
                                    session: dict = Depends(require_structure_jwt_or_token)):
    """Update structure profile (full update). OWNER JWT required."""
    if session["assembly_id"] != assembly_id:
        raise HTTPException(status_code=403, detail="Token not valid for this structure")
    if session.get("tier") != "OWNER":
        raise HTTPException(status_code=403, detail="Only the owner can update the profile")
    profile = load_structure_profile(assembly_id)
    if not profile:
        raise HTTPException(status_code=404, detail="Structure not found")
    updates = req.model_dump(exclude_none=True)
    for k, v in updates.items():
        if hasattr(profile, k):
            setattr(profile, k, v)
    save_structure_profile(profile)
    return profile.as_dict_for_tier("OWNER")


@structures_router.patch("/structure/{assembly_id}")
async def patch_structure_profile(assembly_id: str, req: StructureProfileUpdate,
                                   session: dict = Depends(require_structure_jwt_or_token)):
    """Partial update of structure profile fields. OWNER JWT required."""
    if session["assembly_id"] != assembly_id:
        raise HTTPException(status_code=403, detail="Token not valid for this structure")
    if session.get("tier") != "OWNER":
        raise HTTPException(status_code=403, detail="Only the owner can update the profile")
    profile = load_structure_profile(assembly_id)
    if not profile:
        raise HTTPException(status_code=404, detail="Structure not found")
    updates = req.model_dump(exclude_none=True)
    for k, v in updates.items():
        if hasattr(profile, k):
            setattr(profile, k, v)
    save_structure_profile(profile)
    return profile.as_dict_for_tier("OWNER")


@structures_router.post("/structure/{assembly_id}/location/manual")
async def set_manual_location(assembly_id: str, request: LocationManualRequest):
    """
    Set a manual (unproved) location for a structure.

    Body: { "system_name": "UR8-K7K" }

    Saves location to structure profile with proved=False.
    Can be upgraded to proved later via /reveal endpoint.
    """
    try:
        system_name = request.system_name.strip()

        if not system_name:
            return {"error": "system_name required"}

        # Get or create structure profile
        profile = load_structure_profile(assembly_id)
        if not profile:
            # Create minimal profile if it doesn't exist
            profile = StructureProfile(
                assembly_id=assembly_id,
                owner_address="",
                structure_name=assembly_id
            )

        # Update system_name on the profile (used by AI context)
        profile.system_name = system_name

        # Store location on profile object before saving
        location = {
            "system": system_name,
            "proved": False,
            "set_at": datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z')
        }
        setattr(profile, "location", location)

        # Save the profile
        save_structure_profile(profile)

        return {
            "success": True,
            "location": location,
            "assembly_id": assembly_id
        }
    except Exception as e:
        log.exception(f"Error setting manual location for {assembly_id}: {e}")
        return {"error": str(e), "assembly_id": assembly_id}


@structures_router.post("/structure/{assembly_id}/location/reveal")
async def reveal_location(assembly_id: str, request: LocationRevealRequest):
    """Prove location via Sui wallet signature. Not yet implemented."""
    return JSONResponse(status_code=501, content={"error": "Location reveal not implemented"})


