from fastapi import FastAPI, Depends, Request, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.responses import StreamingResponse, JSONResponse, Response
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from dotenv import load_dotenv
from pydantic import BaseModel, ConfigDict
from typing import Optional
import os
import re
import json
import asyncio
import logging
import jwt as pyjwt

from src.log_buffer import log_buffer
from src.auth import require_token
from src.claude_client import claude
from src.context_builder import build_context_block
from src.world_api import world_api
from src.route_engine import route_engine
from src.ship_profile import (
    ShipProfile, FUEL_QUALITY, load_profile, save_profile
)
from src.structure_auth import nonce_store, verify_sui_personal_message, issue_jwt, decode_jwt, lookup_character
from src.structure_profile import StructureProfile, load_profile as load_structure_profile, save_profile as save_structure_profile
from src.structure_client import structure_client, build_structure_context, detect_alerts
from src.nova_client import nova_client

log = logging.getLogger(__name__)

load_dotenv()

from contextlib import asynccontextmanager

@asynccontextmanager
async def lifespan(app):
    # Run index build in background — don't block startup
    # The index loads from disk instantly if cached; API fetch retries on DNS failure
    asyncio.create_task(world_api.load_or_build_index())
    yield

app = FastAPI(title="Ship AI Companion", lifespan=lifespan)
app.mount("/static", StaticFiles(directory="static"), name="static")

@app.get("/health")
async def health():
    return {"status": "ok", "systems_indexed": len(world_api._system_index)}

@app.post("/admin/rebuild-index", dependencies=[Depends(require_token)])
async def rebuild_index():
    count = await world_api.rebuild_index()
    return {"systems_indexed": count}

@app.get("/data/gate-graph", dependencies=[Depends(require_token)])
async def gate_graph(request: Request):
    """Serve the prebuilt gate adjacency graph for client-side route calculation."""
    path = os.path.join(os.path.dirname(__file__), "data", "gate_graph.json")
    if not os.path.exists(path):
        return JSONResponse(status_code=503, content={"detail": "Gate graph not built yet. POST /admin/rebuild-index."})
    with open(path) as f:
        data = json.load(f)
    etag = f'"{data.get("built_at", "unknown")}"'
    if request.headers.get("if-none-match") == etag:
        return Response(status_code=304)
    return JSONResponse(content=data, headers={"ETag": etag, "Cache-Control": "public, max-age=3600"})

class ShipProfileRequest(BaseModel):
    hull_mass:      Optional[float] = None
    current_mass:   Optional[float] = None
    specific_heat:  Optional[float] = None
    adaptive_level: Optional[int]   = None
    fuel_type:      Optional[str]   = None
    fuel_quantity:  Optional[float] = None
    external_temp:  Optional[float] = None

@app.get("/ship-profile", dependencies=[Depends(require_token)])
async def get_ship_profile():
    p = load_profile()
    from dataclasses import asdict
    return {
        **asdict(p),
        "jump_range_m":  p.jump_range(),
        "jump_range_ly": p.jump_range() / 9_460_000_000_000_000.0,
        "fuel_budget_m": p.fuel_budget(),
        "fuel_types":    FUEL_QUALITY,
    }

@app.post("/ship-profile", dependencies=[Depends(require_token)])
async def set_ship_profile(req: ShipProfileRequest):
    current = load_profile()
    updated = current.with_overrides(**req.model_dump())
    if req.fuel_type and req.fuel_type not in FUEL_QUALITY:
        return JSONResponse(status_code=400, content={
            "detail": f"Unknown fuel type '{req.fuel_type}'. Valid: {list(FUEL_QUALITY)}"
        })
    save_profile(updated)
    from dataclasses import asdict
    return {**asdict(updated), "jump_range_m": updated.jump_range(), "fuel_budget_m": updated.fuel_budget()}


class RouteRequest(BaseModel):
    origin:         Optional[str]   = None
    destination:    str
    # Optional per-request ship overrides (hypothetical mode)
    hull_mass:      Optional[float] = None
    current_mass:   Optional[float] = None
    specific_heat:  Optional[float] = None
    adaptive_level: Optional[int]   = None
    fuel_type:      Optional[str]   = None
    fuel_quantity:  Optional[float] = None
    external_temp:  Optional[float] = None
    gate_only:      bool            = False  # force gate-only BFS

@app.post("/route", dependencies=[Depends(require_token)])
async def plan_route(req: RouteRequest):
    """Compute route and store it in the live context."""
    origin = (req.origin or log_buffer.current_system or "").strip()
    if not origin:
        return JSONResponse(status_code=400, content={"detail": "No origin — provide origin or be in a known system."})
    if not route_engine.ready():
        return JSONResponse(status_code=503, content={"detail": "systems.json not loaded."})

    if req.gate_only:
        result = route_engine.bfs(origin, req.destination)
    else:
        profile = load_profile().with_overrides(
            hull_mass=req.hull_mass,
            current_mass=req.current_mass,
            specific_heat=req.specific_heat,
            adaptive_level=req.adaptive_level,
            fuel_type=req.fuel_type,
            fuel_quantity=req.fuel_quantity,
            external_temp=req.external_temp,
        )
        result = route_engine.route(origin, req.destination, profile)
        if result is None:
            # fall back to gate-only
            result = route_engine.bfs(origin, req.destination)

    if result is None:
        return JSONResponse(status_code=404, content={
            "detail": f"No route found from '{origin}' to '{req.destination}'."
        })
    log_buffer.add({"type": "route_planned", **result})
    return result

@app.get("/debug", dependencies=[Depends(require_token)])
async def debug():
    """
    Returns the full live state of the pipeline:
      - current system known to the server
      - raw contents of the log buffer
      - world API data for the current system (if available)
      - the exact context block Claude would receive right now
    Use this to verify the pipeline end-to-end before writing the system prompt.
    """
    system_data = await world_api.get_system(log_buffer.current_system) if log_buffer.current_system else None
    context = build_context_block(
        system_data=system_data,
        log_events=log_buffer.get_recent(50),
        current_system=log_buffer.current_system,
        live_sessions=log_buffer.get_live(),
    )
    return {
        "current_system":  log_buffer.current_system,
        "systems_indexed": len(world_api._system_index),
        "buffer_events":   log_buffer.get_recent(50),
        "live_sessions":   log_buffer.get_live(),
        "world_api_data":  system_data,
        "context_block":   context,
    }

class LogEvent(BaseModel):
    model_config = ConfigDict(extra="allow")
    type: str

@app.post("/log/ingest", dependencies=[Depends(require_token)])
async def ingest_log(event: LogEvent):
    data = event.model_dump()
    if data.get("in_progress"):
        log_buffer.set_live([data])
    else:
        log_buffer.add(data)
        if event.type in ("combat_summary", "mining_summary"):
            log_buffer.clear_live(event.type)
        if event.type == "system_change" and data.get("system"):
            asyncio.create_task(world_api.get_system(data["system"]))
    return {"accepted": True}

class ChatRequest(BaseModel):
    message: str
    history: list = []

class ChallengeRequest(BaseModel):
    structure_id: str

class VerifyRequest(BaseModel):
    address: str
    signature: str
    nonce: str
    structure_id: str
    nova_registry_object_id: Optional[str] = None  # required on first owner auth

class StructureChatRequest(BaseModel):
    message: str
    history: list = []
    structure_id: str

class StructureProfileUpdate(BaseModel):
    structure_name: Optional[str] = None
    fuel_pct: Optional[float] = None
    shield_pct: Optional[float] = None
    services_online: Optional[int] = None
    services_total: Optional[int] = None
    docked_count: Optional[int] = None

_bearer = HTTPBearer(auto_error=False)

async def require_structure_jwt(credentials: HTTPAuthorizationCredentials = Depends(_bearer)):
    """FastAPI dependency: validate structure JWT, return decoded payload."""
    if not credentials:
        raise HTTPException(status_code=401, detail="Missing Authorization header")
    try:
        return decode_jwt(credentials.credentials)
    except pyjwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Session expired — reconnect wallet")
    except Exception:
        raise HTTPException(status_code=401, detail="Invalid session token")

_ROUTE_RE = re.compile(
    r"(?:plot|plan|calculate|find|set|fly|navigate|go|travel|head|get)\s+"
    r"(?:a\s+)?(?:route|course|path)?\s*(?:to|toward(?:s)?)\s+([\w][\w\-]*[\w])",
    re.IGNORECASE,
)

def _extract_route_destination(message: str) -> Optional[str]:
    m = _ROUTE_RE.search(message)
    return m.group(1) if m else None

@app.post("/chat", dependencies=[Depends(require_token)])
async def chat(req: ChatRequest):
    # Auto-plot route if message contains a navigation intent
    dest = _extract_route_destination(req.message)
    if dest and route_engine.ready():
        origin = log_buffer.current_system or ""
        if origin:
            result = route_engine.bfs(origin, dest)
            if result:
                log_buffer.add({"type": "route_planned", **result})

    system_data = await world_api.get_system(log_buffer.current_system) if log_buffer.current_system else None
    context = build_context_block(
        system_data=system_data,
        log_events=log_buffer.get_recent(10),
        current_system=log_buffer.current_system,
        live_sessions=log_buffer.get_live(),
        current_route=log_buffer.current_route,
        structure_alerts=log_buffer.pop_structure_alerts(),
    )

    def event_stream():
        try:
            for chunk in claude.stream(req.message, req.history, context):
                yield f"data: {json.dumps({'text': chunk})}\n\n"
        except Exception as e:
            import logging
            logging.getLogger(__name__).error("Stream error: %s", e)
            yield f"data: {json.dumps({'error': 'Stream interrupted. Ship systems error.'})}\n\n"
        yield "data: [DONE]\n\n"

    return StreamingResponse(event_stream(), media_type="text/event-stream")


@app.post("/auth/challenge")
async def auth_challenge(req: ChallengeRequest):
    """Issue a nonce for wallet signing. No auth required."""
    nonce = nonce_store.issue()
    return {"nonce": nonce, "structure_id": req.structure_id, "expires_in_seconds": 300}


@app.post("/auth/verify")
async def auth_verify(req: VerifyRequest):
    """
    Verify signed nonce, resolve access tier from Nova AccessRegistry, return JWT.
    On first-ever owner auth: auto-creates structure profile.
    """
    # 1. Consume nonce (single-use, TTL-checked)
    if not nonce_store.consume(req.nonce):
        raise HTTPException(status_code=400, detail="Invalid or expired nonce")

    # 2. Verify Sui signature
    try:
        verify_sui_personal_message(req.nonce.encode(), req.signature, req.address)
    except Exception as e:
        log.warning("Signature verification failed for address %s: %s", req.address, e)
        raise HTTPException(status_code=401, detail="Signature verification failed")

    # 3. Lookup character via World API (non-fatal — auth proceeds even if lookup fails)
    character_id = 0
    character_name = req.address[:12] + "..."
    char_data = await lookup_character(req.address)
    if char_data:
        character_id = char_data.get("id", 0)
        character_name = char_data.get("name", character_name) or character_name

    # 4. Resolve access tier
    tier = "NONE"
    profile = load_structure_profile(req.structure_id)

    if profile is None:
        # First-ever auth — check if this address is the on-chain owner
        if req.nova_registry_object_id:
            registry = await nova_client.get_access_registry(req.nova_registry_object_id)
            if registry and nova_client.resolve_tier(req.address, registry) == "OWNER":
                # Auto-create profile
                profile = StructureProfile(
                    structure_id=req.structure_id,
                    owner_address=req.address,
                    owner_character_id=character_id,
                    nova_registry_object_id=req.nova_registry_object_id,
                )
                try:
                    save_structure_profile(profile)
                except ValueError as e:
                    raise HTTPException(status_code=400, detail=f"Invalid structure_id: {e}")
                tier = "OWNER"
        if tier == "NONE":
            raise HTTPException(status_code=403, detail="No structure profile exists. Owner must authenticate first.")
    else:
        if req.address.lower() == profile.owner_address.lower():
            tier = "OWNER"
        elif profile.nova_registry_object_id:
            registry = await nova_client.get_access_registry(profile.nova_registry_object_id)
            if registry:
                tier = nova_client.resolve_tier(req.address, registry)

    # 5. Issue JWT
    token = issue_jwt({
        "address": req.address,
        "character_id": character_id,
        "character_name": character_name,
        "tier": tier,
        "structure_id": req.structure_id,
    })
    return {"token": token, "tier": tier, "character_name": character_name, "character_id": character_id}


@app.get("/structure/{structure_id}")
async def get_structure_profile(structure_id: str, session: dict = Depends(require_structure_jwt)):
    if session["structure_id"] != structure_id:
        raise HTTPException(status_code=403, detail="Token not valid for this structure")
    profile = load_structure_profile(structure_id)
    if not profile:
        raise HTTPException(status_code=404, detail="Structure not found")
    tier = session["tier"]
    if tier == "NONE":
        raise HTTPException(status_code=403, detail="Access denied")
    return profile.as_dict_for_tier(tier)


@app.post("/structure/{structure_id}")
async def update_structure_profile(structure_id: str, req: StructureProfileUpdate,
                                    session: dict = Depends(require_structure_jwt)):
    if session["structure_id"] != structure_id:
        raise HTTPException(status_code=403, detail="Token not valid for this structure")
    if session["tier"] != "OWNER":
        raise HTTPException(status_code=403, detail="Only the owner can update the profile")
    profile = load_structure_profile(structure_id)
    if not profile:
        raise HTTPException(status_code=404, detail="Structure not found")
    updates = req.model_dump(exclude_none=True)
    for k, v in updates.items():
        if hasattr(profile, k):
            setattr(profile, k, v)
    save_structure_profile(profile)
    return profile.as_dict_for_tier("OWNER")


@app.post("/structure-chat")
async def structure_chat(req: StructureChatRequest, session: dict = Depends(require_structure_jwt)):
    if session["structure_id"] != req.structure_id:
        raise HTTPException(status_code=403, detail="Token not valid for this structure")
    tier = session["tier"]
    if tier == "NONE":
        raise HTTPException(status_code=403, detail="Access denied")

    profile = load_structure_profile(req.structure_id)
    if not profile:
        raise HTTPException(status_code=404, detail="Structure not found")

    # Detect alerts and route them
    alerts = detect_alerts(profile)
    urgent = [a for a in alerts if a["severity"] == "urgent"]
    routine = [a for a in alerts if a["severity"] == "routine"]

    for alert in urgent:
        log_buffer.add_structure_alert(alert)

    if routine:
        profile.routine_alerts = (profile.routine_alerts + routine)[-10:]
        save_structure_profile(profile)

    # Fetch local system data for context
    system_data = None
    if profile.system_name:
        system_data = await world_api.get_system(profile.system_name)
    local_kills = len((system_data or {}).get("kills", []))
    local_pilots = 0  # world API doesn't expose pilot count directly

    context = build_structure_context(profile, tier, local_kills=local_kills, local_pilots=local_pilots)

    def event_stream():
        try:
            for chunk in structure_client.stream(
                message=req.message,
                history=req.history,
                context_block=context,
                profile=profile,
                tier=tier,
                character_name=session["character_name"],
                character_id=session["character_id"],
            ):
                yield f"data: {json.dumps({'text': chunk})}\n\n"
        except Exception as e:
            log.error("Structure chat stream error: %s", e)
            yield f"data: {json.dumps({'error': 'Stream interrupted.'})}\n\n"
        yield "data: [DONE]\n\n"

    return StreamingResponse(event_stream(), media_type="text/event-stream")
