from fastapi import FastAPI, Depends, Request, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.responses import StreamingResponse, JSONResponse, Response, FileResponse
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
from src.structure_client import structure_client, lobby_client, build_structure_context, detect_alerts
from src.nova_client import nova_client

log = logging.getLogger(__name__)

load_dotenv()

# Server-side registry map: structure_id -> Nova AccessRegistry object ID.
# This avoids passing the full 66-char hex ID through the in-game browser URL bar,
# which truncates it. The client sends nova_registry_object_id as a hint (or omits it);
# the server always prefers its own configured value.
_STRUCTURE_REGISTRY_MAP: dict[str, str] = {}
_registry_env = os.environ.get("NOVA_REGISTRY_OBJECT_ID", "")
_registry_structure = os.environ.get("NOVA_REGISTRY_STRUCTURE_ID", "keep-7a")
if _registry_env:
    _STRUCTURE_REGISTRY_MAP[_registry_structure] = _registry_env

def _registry_for(structure_id: str, client_hint: Optional[str] = None) -> Optional[str]:
    """Return the best registry object ID for a structure. Server map takes priority."""
    return _STRUCTURE_REGISTRY_MAP.get(structure_id) or client_hint

from contextlib import asynccontextmanager

@asynccontextmanager
async def lifespan(app):
    # World API index (existing)
    asyncio.create_task(world_api.load_or_build_index())

    # Bootstrap memory store
    _structure_id = os.environ.get("NOVA_REGISTRY_STRUCTURE_ID", "keep-7a")
    from src.memory_store import get_memory_store
    get_memory_store(_structure_id)  # creates dirs if missing

    # Start SSU background polling
    _ssu_object_id = os.environ.get("SSU_OBJECT_ID", "")
    from src.structure_profile import load_profile as load_structure_profile_fn
    _profile = load_structure_profile_fn(_structure_id)
    _system_id = _profile.system_id if _profile else 0

    from src.ssu_poller import start_background_tasks
    start_background_tasks(_structure_id, _ssu_object_id, _system_id)

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

@app.get("/data/systems", dependencies=[Depends(require_token)])
async def get_systems(request: Request):
    """Serve systems.json for client-side RouteCalculator. ~7 MB; ETag + 304 supported."""
    path = os.path.join(os.path.dirname(__file__), "data", "systems.json")
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
    structure_type: Optional[str] = None
    system_name:    Optional[str] = None
    fuel_pct:       Optional[float] = None
    shield_pct:     Optional[float] = None
    services_online: Optional[int] = None
    services_total:  Optional[int] = None
    docked_count:   Optional[int] = None

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
_SLASH_ROUTE_RE = re.compile(r'^/route\s+(.+)$', re.IGNORECASE)

def _extract_route_destination(message: str) -> Optional[str]:
    m = _ROUTE_RE.search(message)
    return m.group(1) if m else None

@app.get("/current-route", dependencies=[Depends(require_token)])
async def get_current_route():
    """Return the active route stored in log_buffer, or null."""
    return {"route": log_buffer.current_route}

@app.post("/route/clear", dependencies=[Depends(require_token)])
async def clear_route():
    """Clear the active route."""
    log_buffer.current_route = None
    return {"cleared": True}

@app.post("/chat", dependencies=[Depends(require_token)])
async def chat(req: ChatRequest):
    # Handle /route DEST command directly — no Claude needed
    m = _SLASH_ROUTE_RE.match(req.message.strip())
    if m:
        dest = m.group(1).strip()
        origin = log_buffer.current_system or ""
        if not origin:
            def _no_origin():
                yield f"data: {json.dumps({'text': 'SYSTEM UNKNOWN — jump to a system first.'})}\n\n"
                yield "data: [DONE]\n\n"
            return StreamingResponse(_no_origin(), media_type="text/event-stream")
        if not route_engine.ready():
            def _not_ready():
                yield f"data: {json.dumps({'text': 'Route engine offline — systems.json not loaded.'})}\n\n"
                yield "data: [DONE]\n\n"
            return StreamingResponse(_not_ready(), media_type="text/event-stream")
        result = route_engine.bfs(origin, dest)
        if result is None:
            reply = f"NO GATE ROUTE: {origin.upper()} → {dest.upper()} — disconnected clusters."
        else:
            log_buffer.add({"type": "route_planned", **result})
            path = result.get("path", [])
            jumps = result.get("jumps", 0)
            if len(path) > 5:
                path_str = f"{path[0].upper()} → [{len(path)-2} hops] → {path[-1].upper()}"
            else:
                path_str = " → ".join(p.upper() for p in path)
            reply = f"ROUTE SET: {path_str} ({jumps} jump{'s' if jumps != 1 else ''})"
            for w in result.get("warnings", [])[:3]:
                reply += f"\nWARN: {w}"
        def _route_reply(text=reply):
            yield f"data: {json.dumps({'text': text})}\n\n"
            yield "data: [DONE]\n\n"
        return StreamingResponse(_route_reply(), media_type="text/event-stream")

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
    registry_id = _registry_for(req.structure_id, req.nova_registry_object_id)
    log.info("auth_verify: address=%s structure=%s registry_id=%r (client_hint=%r)",
             req.address, req.structure_id, registry_id, req.nova_registry_object_id)

    if profile is None:
        # First-ever auth — check if this address is the on-chain owner
        if registry_id:
            registry = await nova_client.get_access_registry(registry_id)
            if registry and nova_client.resolve_tier(req.address, registry) == "OWNER":
                # Auto-create profile
                # Resolve system info at creation
                _sys_name = os.environ.get("STRUCTURE_SYSTEM_NAME", "")
                _system_id = 0
                _region_name = ""
                if _sys_name:
                    from src.galaxy_db import galaxy_db as _gdb
                    _sys_row = _gdb.get_system(_sys_name)
                    if _sys_row:
                        _system_id = _sys_row.get("solarSystemId") or 0
                        _region_name = _sys_row.get("regionName") or ""
                        _sys_name = _sys_row.get("name") or _sys_name

                profile = StructureProfile(
                    structure_id=req.structure_id,
                    owner_address=req.address,
                    owner_character_id=character_id,
                    nova_registry_object_id=registry_id,
                    system_name=_sys_name,
                    system_id=_system_id,
                    region_name=_region_name,
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
        elif registry_id or profile.nova_registry_object_id:
            registry = await nova_client.get_access_registry(registry_id or profile.nova_registry_object_id)
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

    # 6. Upsert pilot profile in memory store
    _sid = req.structure_id
    from src.memory_store import get_memory_store
    mem = get_memory_store(_sid)
    mem.upsert_pilot(
        address=req.address,
        character_name=character_name,
        character_id=character_id,
        tier=tier,
    )

    # 7. Backfill system_id / region_name on profile if missing
    if profile and (profile.system_id == 0 or not profile.region_name):
        _sys_name = os.environ.get("STRUCTURE_SYSTEM_NAME", profile.system_name or "")
        if _sys_name:
            from src.galaxy_db import galaxy_db
            sys_row = galaxy_db.get_system(_sys_name)
            if sys_row:
                changed = False
                if profile.system_id == 0:
                    profile.system_id = sys_row.get("solarSystemId") or 0
                    changed = True
                if not profile.region_name:
                    profile.region_name = sys_row.get("regionName") or "Unknown Region"
                    changed = True
                if not profile.system_name:
                    profile.system_name = sys_row.get("name") or _sys_name
                    changed = True
                if changed:
                    try:
                        save_structure_profile(profile)
                        log.info("Profile backfilled: system_id=%d region=%s",
                                 profile.system_id, profile.region_name)
                    except Exception as e:
                        log.warning("Profile backfill save failed: %s", e)

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


@app.patch("/structure/{structure_id}")
async def patch_structure_profile(structure_id: str, req: StructureProfileUpdate,
                                   session: dict = Depends(require_structure_jwt)):
    """Partial update of structure profile fields. OWNER JWT required."""
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

    # Memory
    from src.memory_store import get_memory_store
    mem_store = get_memory_store(req.structure_id)
    summary = mem_store.get_summary()
    memory_text = summary.get("text", "")

    # Kills nearby (best-effort)
    kills_nearby = 0
    if profile.system_id:
        try:
            kills_raw = await world_api.get_killmails(system_id=profile.system_id)
            from datetime import datetime, timezone, timedelta
            cutoff = datetime.now(timezone.utc) - timedelta(hours=2)
            for k in kills_raw:
                t = k.get("time") or k.get("timestamp") or ""
                try:
                    kt = datetime.fromisoformat(t.replace("Z", "+00:00"))
                    if kt >= cutoff:
                        kills_nearby += 1
                except ValueError:
                    pass
        except Exception:
            pass

    context = build_structure_context(
        profile, tier,
        memory_text=memory_text,
        kills_nearby=kills_nearby,
    )

    def event_stream():
        try:
            if tier == "VETTED":
                gen = lobby_client.stream(
                    message=req.message,
                    history=req.history,
                    profile=profile,
                    character_name=session["character_name"],
                )
            else:
                gen = structure_client.stream(
                    message=req.message,
                    history=req.history,
                    context_block=context,
                    profile=profile,
                    tier=tier,
                    character_name=session["character_name"],
                    character_id=session["character_id"],
                )
            for chunk in gen:
                yield f"data: {json.dumps({'text': chunk})}\n\n"
        except Exception as e:
            log.error("Structure chat stream error: %s", e)
            yield f"data: {json.dumps({'error': 'Stream interrupted.'})}\n\n"
        finally:
            yield "data: [DONE]\n\n"
            try:
                mem_store.rebuild_summary()
            except Exception as e_rebuild:
                log.warning("Summary rebuild failed: %s", e_rebuild)

    return StreamingResponse(event_stream(), media_type="text/event-stream")
