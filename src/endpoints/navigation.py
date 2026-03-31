"""
Navigation endpoints.

GET  /ship-profile — fetch current ship profile
POST /ship-profile — update ship profile (validates ship_type and fuel compatibility)
POST /route        — stateless route calculation. No auth, no log_buffer.
"""

import logging
from dataclasses import asdict
from fastapi import APIRouter, Header, HTTPException
from fastapi.responses import JSONResponse

from src.route_engine import route_engine
from src.ship_profile import (
    load_profile, save_profile, FUEL_PROPERTIES, FUEL_CATEGORY, SHIPS,
    ShipProfile,
)
from src.schemas import RouteRequest, ShipProfileRequest

log = logging.getLogger(__name__)

navigation_router = APIRouter()


@navigation_router.get("/ship-profile")
async def get_ship_profile(x_server_token: str = Header(default="")):
    from src.config import load_config_from_env
    token = load_config_from_env().get("server_token", "")
    if token and x_server_token != token:
        raise HTTPException(status_code=403, detail="Forbidden")
    return asdict(load_profile())


@navigation_router.post("/ship-profile")
async def set_ship_profile(req: ShipProfileRequest, x_server_token: str = Header(default="")):
    from src.config import load_config_from_env
    token = load_config_from_env().get("server_token", "")
    if token and x_server_token != token:
        raise HTTPException(status_code=403, detail="Forbidden")

    # Validate ship_type
    if req.ship_type is not None and req.ship_type not in SHIPS:
        raise HTTPException(status_code=422, detail=f"Unknown ship type '{req.ship_type}'. Valid: {list(SHIPS)}")

    # Determine effective fuel_type for compatibility check
    base = load_profile()
    effective_fuel = req.fuel_type or base.fuel_type
    effective_ship = req.ship_type or base.ship_type

    # Validate fuel category compatibility
    if effective_ship and req.fuel_type:
        ship_cat  = SHIPS[effective_ship]["fuel_category"]
        fuel_cat  = FUEL_CATEGORY.get(effective_fuel)
        if fuel_cat and fuel_cat != ship_cat:
            raise HTTPException(
                status_code=422,
                detail=f"Fuel '{effective_fuel}' ({fuel_cat}) is incompatible with {effective_ship} ({ship_cat} only).",
            )

    # Build updated profile — ship_type auto-fills hull_mass and specific_heat
    overrides = {k: v for k, v in req.model_dump().items() if v is not None}
    if req.ship_type and req.ship_type in SHIPS:
        ship_data = SHIPS[req.ship_type]
        overrides.setdefault("hull_mass",     ship_data["mass"])
        overrides.setdefault("specific_heat", ship_data["specific_heat"])

    updated = base.with_overrides(**overrides)
    save_profile(updated)
    return asdict(updated)


@navigation_router.get("/systems/names")
async def get_system_names():
    """Return all system names for client-side autocomplete."""
    if not route_engine.ready():
        return JSONResponse(status_code=503, content={"detail": "systems.json not loaded."})
    names = list(route_engine._by_name.keys())
    return JSONResponse(content={"names": names})


@navigation_router.post("/route")
async def plan_route(req: RouteRequest):
    """Compute a route. Origin must be provided in the request body."""
    origin = (req.origin or "").strip()
    if not origin:
        return JSONResponse(status_code=400, content={"detail": "No origin — provide origin in request."})
    if not route_engine.ready():
        return JSONResponse(status_code=503, content={"detail": "systems.json not loaded."})

    if req.gate_only:
        result = route_engine.bfs(origin, req.destination)
        if result is None:
            profile = load_profile()
            return JSONResponse(status_code=404, content={
                "detail": f"No gate route from '{origin}' to '{req.destination}'."
            })
        return result

    # Build profile — tank fuel + cargo fuel combined
    base = load_profile()
    fuel_type = req.fuel_type or base.fuel_type
    tank_fuel  = req.fuel_quantity if req.fuel_quantity is not None else base.fuel_quantity
    total_fuel = tank_fuel + req.cargo_fuel

    # Cargo fuel sits in the hold and adds mass. Tank fuel is massless.
    fuel_mass_kg  = FUEL_PROPERTIES.get(fuel_type, {}).get("mass_kg", 0)
    cargo_mass_kg = req.cargo_fuel * fuel_mass_kg

    base_cargo_kg = req.extra_cargo_kg if req.extra_cargo_kg is not None else base.extra_cargo_kg
    profile = base.with_overrides(
        hull_mass=req.hull_mass,
        specific_heat=req.specific_heat,
        adaptive_level=req.adaptive_level,
        fuel_type=fuel_type,
        fuel_quantity=total_fuel,
        external_temp=req.external_temp,
        extra_cargo_kg=base_cargo_kg + cargo_mass_kg,
    )

    result = route_engine.route(origin, req.destination, profile, cost_mode=req.cost_mode)

    # If direct/hybrid route fails, fall back to gate-only
    if result["type"] == "no_route":
        gate = route_engine.bfs(origin, req.destination)
        if gate:
            return gate

    if result["type"] == "no_route":
        return JSONResponse(status_code=404, content={
            "detail": " ".join(result.get("warnings", [f"No route to '{req.destination}'."]))
        })

    return result
