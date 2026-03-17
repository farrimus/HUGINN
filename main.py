from fastapi import FastAPI, Depends, Request, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.responses import StreamingResponse, JSONResponse, Response, FileResponse
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from dotenv import load_dotenv
from pydantic import BaseModel, ConfigDict, field_validator
from typing import Optional
import os
import re
import json
import asyncio
import logging
import jwt as pyjwt
from dataclasses import asdict, fields as dc_fields

from src.log_buffer import log_buffer
from src.auth import require_token
from src.claude_client import claude
from src.context_builder import build_context_block
from src.world_api import world_api
from src.route_engine import route_engine
from src.ship_profile import (
    ShipProfile, FUEL_QUALITY, FUEL_CATEGORY, SHIPS, load_profile, save_profile
)
from src.structure_auth import nonce_store, verify_sui_personal_message, issue_jwt, decode_jwt, lookup_character
from src.deal_store import deal_store, DEAL_MESSAGES_DEFAULT, DEAL_DURATION_HOURS_DEFAULT
from src.structure_profile import StructureProfile, load_profile as load_structure_profile, save_profile as save_structure_profile
from src.structure_client import structure_client, lobby_client, build_structure_context, detect_alerts
from src.nova_client import nova_client
from src.location_index import location_index
from src.token_manager import TokenManager
from src.endpoints.auth import auth_router, init_auth, validate_token

log = logging.getLogger(__name__)

load_dotenv()

# ---------------------------------------------------------------------------
# Live log broadcaster — streams server log lines to connected SSE clients
# ---------------------------------------------------------------------------
from collections import deque

_log_history: deque = deque(maxlen=200)
_log_clients: list[asyncio.Queue] = []
_log_loop: asyncio.AbstractEventLoop | None = None

class _LogBroadcastHandler(logging.Handler):
    def emit(self, record: logging.LogRecord):
        line = self.format(record)
        _log_history.append(line)
        if _log_loop and not _log_loop.is_closed():
            for q in list(_log_clients):
                _log_loop.call_soon_threadsafe(q.put_nowait, line)

_broadcast_handler = _LogBroadcastHandler()
_broadcast_handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s"))
root_logger = logging.getLogger()
root_logger.setLevel(logging.INFO)
root_logger.addHandler(_broadcast_handler)

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

_EVE_FRONTIER_PACKAGE = os.environ.get(
    "EVE_FRONTIER_PACKAGE",
    "0xd12a70c74c1e759445d6f209b01d43d860e97fcf2ef72ccbbd00afd828043f75",
)
_VPS_SUI_ADDRESS = os.environ.get("VPS_SUI_ADDRESS", "")
_ITEM_DEPOSIT_EVENT = f"{_EVE_FRONTIER_PACKAGE}::ephemeral_inventory::ItemDepositedEvent"
_ITEM_DEPOSIT_WINDOW_MS = 600_000  # 10 minutes

from contextlib import asynccontextmanager

@asynccontextmanager
async def lifespan(app):
    global _log_loop
    _log_loop = asyncio.get_event_loop()

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

# Initialize token manager and auth endpoints
token_manager = TokenManager(key_dir=".keys")
init_auth(token_manager)
app.include_router(auth_router)

@app.get("/health")
async def health():
    return {"status": "ok", "systems_indexed": len(world_api._system_index)}

@app.post("/admin/rebuild-index", dependencies=[Depends(require_token)])
async def rebuild_index():
    count = await world_api.rebuild_index()
    return {"systems_indexed": count}

@app.post("/admin/rebuild-location-index", dependencies=[Depends(require_token)])
async def rebuild_location_index():
    """Rebuild LocationRevealedEvent index from chain. Requires X-Server-Token."""
    count = await location_index.rebuild()
    return {"entries_indexed": count}

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
    ship_type:      Optional[str]   = None
    extra_cargo_kg: Optional[float] = None

@app.get("/ship-profile", dependencies=[Depends(require_token)])
async def get_ship_profile():
    p = load_profile()
    return {
        **asdict(p),
        "jump_range_ly": p.jump_range(),
        "fuel_budget_ly": p.fuel_budget(),
        "fuel_types":    FUEL_QUALITY,
        "ships":         {name: {"mass": s["mass"], "specific_heat": s["specific_heat"],
                                 "fuel_category": s["fuel_category"]}
                          for name, s in SHIPS.items()},
    }

@app.post("/ship-profile", dependencies=[Depends(require_token)])
async def set_ship_profile(req: ShipProfileRequest):
    # Validate ship_type
    if req.ship_type is not None and req.ship_type not in SHIPS:
        return JSONResponse(status_code=422, content={
            "detail": f"Unknown ship type '{req.ship_type}'. Valid: {sorted(SHIPS)}"
        })
    # Validate fuel_type
    if req.fuel_type is not None and req.fuel_type not in FUEL_QUALITY:
        return JSONResponse(status_code=422, content={
            "detail": f"Unknown fuel type '{req.fuel_type}'. Valid: {list(FUEL_QUALITY)}"
        })
    # Validate fuel_type vs ship fuel_category
    current = load_profile()
    effective_ship = req.ship_type or current.ship_type
    if req.fuel_type is not None and effective_ship is not None:
        ship_cat = SHIPS[effective_ship]["fuel_category"]
        fuel_cat = FUEL_CATEGORY.get(req.fuel_type, "")
        if fuel_cat != ship_cat:
            return JSONResponse(status_code=422, content={
                "detail": f"Fuel type '{req.fuel_type}' ({fuel_cat}) incompatible "
                          f"with ship '{effective_ship}' ({ship_cat} only)"
            })
    # Validate extra_cargo_kg
    if req.extra_cargo_kg is not None and req.extra_cargo_kg < 0:
        return JSONResponse(status_code=422, content={"detail": "extra_cargo_kg must be >= 0"})

    overrides = req.model_dump()
    # If ship_type provided, auto-fill hull_mass and specific_heat
    if req.ship_type is not None:
        ship = SHIPS[req.ship_type]
        overrides["hull_mass"]     = ship["mass"]
        overrides["specific_heat"] = ship["specific_heat"]
        # If no fuel_type provided, reset to default for this ship's category
        if req.fuel_type is None:
            default_fuel = "D1" if ship["fuel_category"] == "basic" else "SOF-40"
            overrides["fuel_type"] = current.fuel_type if (
                FUEL_CATEGORY.get(current.fuel_type) == ship["fuel_category"]
            ) else default_fuel

    updated = current.with_overrides(**overrides)
    save_profile(updated)
    return {**asdict(updated), "jump_range_ly": updated.jump_range(),
            "fuel_budget_ly": updated.fuel_budget()}


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
    cost_mode:      str             = "jumps"  # "jumps" or "fuel"

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
        if result is None:
            log_buffer.current_route = None
            log_buffer.pending_alternative = None
            return JSONResponse(status_code=404, content={
                "detail": f"No route found from '{origin}' to '{req.destination}'."
            })
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
        result = route_engine.route(origin, req.destination, profile,
                                    cost_mode=req.cost_mode)
        if result["type"] == "no_route" and not req.gate_only:
            bfs_result = route_engine.bfs(origin, req.destination)
            if bfs_result:
                result = bfs_result
                result["type"] = "route_planned"

        if result["type"] == "no_route":
            log_buffer.current_route = result
            log_buffer.pending_alternative = None
            return JSONResponse(status_code=404, content={
                "detail": f"No route found from '{origin}' to '{req.destination}'."
            })

    # Store both primary and alternative atomically
    primary = {k: v for k, v in result.items() if k != "alternative"}
    primary["alternative"] = None  # standalone copy has no nested alternative
    alternative = result.get("alternative")

    log_buffer.current_route      = primary
    log_buffer.pending_alternative = alternative
    log_buffer.add({"type": "route_planned", **primary})
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
        "current_system":           log_buffer.current_system,
        "systems_indexed":          len(world_api._system_index),
        "buffer_events":            log_buffer.get_recent(50),
        "live_sessions":            log_buffer.get_live(),
        "world_api_data":           system_data,
        "context_block":            context,
        "pending_structure_alerts": log_buffer.pending_structure_alerts,
    }

@app.get("/logs/stream", dependencies=[Depends(require_token)])
async def logs_stream():
    """SSE stream of live server log lines. Sends recent history first, then live."""
    q: asyncio.Queue = asyncio.Queue()
    for line in _log_history:
        await q.put(line)
    _log_clients.append(q)

    async def generate():
        yield ": keep-alive\n\n"
        try:
            while True:
                line = await q.get()
                yield f"data: {json.dumps({'line': line})}\n\n"
        except asyncio.CancelledError:
            pass
        finally:
            try:
                _log_clients.remove(q)
            except ValueError:
                pass

    return StreamingResponse(generate(), media_type="text/event-stream",
                             headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})


class LogEvent(BaseModel):
    model_config = ConfigDict(extra="allow")
    type: str

@app.post("/log/ingest")
async def ingest_log(event: LogEvent, token_payload = Depends(validate_token)):
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

    @field_validator('address')
    @classmethod
    def validate_address(cls, v: str) -> str:
        if not v or not v.startswith('0x') or len(v) != 66:
            raise ValueError('address must be 0x followed by 64 hexadecimal characters')
        try:
            int(v[2:], 16)
        except ValueError:
            raise ValueError('address contains non-hexadecimal characters')
        return v.lower()


class DealOfferRequest(BaseModel):
    structure_id: str
    address: str


class DealClaimRequest(BaseModel):
    nonce: str
    address: str
    structure_id: str
    signature: str
    payment_method: str          # "item" | "sui" | "info"
    proof: dict = {}             # payment_method-specific evidence

    @field_validator('address')
    @classmethod
    def validate_address(cls, v: str) -> str:
        if not v or not v.startswith('0x') or len(v) != 66:
            raise ValueError('address must be 0x followed by 64 hexadecimal characters')
        try:
            int(v[2:], 16)
        except ValueError:
            raise ValueError('address contains non-hexadecimal characters')
        return v.lower()

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
_SLASH_PROFILE_RE = re.compile(
    r'^/profile(?:\s+(?P<sub>ship|fuel|level|cargo)\s+(?P<args>.+))?$',
    re.IGNORECASE,
)

def _extract_route_destination(message: str) -> Optional[str]:
    m = _ROUTE_RE.search(message)
    return m.group(1) if m else None

@app.get("/current-route", dependencies=[Depends(require_token)])
async def get_current_route():
    """Return the active route and alternative stored in log_buffer."""
    current_temp = None
    if log_buffer.current_system:
        sys_info = route_engine.system_info(log_buffer.current_system)
        if sys_info:
            current_temp = sys_info.get("safe_jump_temp")
    return {
        "route":               log_buffer.current_route,
        "alternative":         log_buffer.pending_alternative,
        "current_system_temp": current_temp,
    }

@app.post("/route/clear", dependencies=[Depends(require_token)])
async def clear_route():
    """Clear the active route."""
    log_buffer.current_route = None
    return {"cleared": True}

class RouteActivateRequest(BaseModel):
    variant: str  # "primary" or "alternative"

@app.post("/route/activate", dependencies=[Depends(require_token)])
async def activate_route(req: RouteActivateRequest):
    """Swap the active route to primary or alternative variant."""
    if req.variant not in ("primary", "alternative"):
        return JSONResponse(status_code=422, content={
            "detail": "variant must be 'primary' or 'alternative'"
        })
    if log_buffer.current_route is None:
        return JSONResponse(status_code=404, content={"detail": "no active route"})
    if req.variant == "alternative":
        if log_buffer.pending_alternative is None:
            return JSONResponse(status_code=404, content={
                "detail": "no alternative route available"
            })
        # Swap: primary becomes what was alternative, alternative becomes what was primary
        old_primary = log_buffer.current_route
        log_buffer.current_route      = log_buffer.pending_alternative
        log_buffer.pending_alternative = old_primary
    # "primary" — current_route is already primary; no-op
    log_buffer.add({"type": "route_planned", **{k: v for k, v in log_buffer.current_route.items() if k != "alternative"}})
    return log_buffer.current_route

@app.post("/chat", dependencies=[Depends(require_token)])
async def chat(req: ChatRequest):
    # Handle /profile command directly — no Claude needed
    pm = _SLASH_PROFILE_RE.match(req.message.strip())
    if pm:
        sub  = pm.group("sub")
        args = (pm.group("args") or "").strip()
        current = load_profile()
        overrides = {}
        reply_text = ""

        if sub is None:
            # /profile — print current
            r_ly = current.jump_range()
            b_ly = current.fuel_budget()
            ship_str = current.ship_type or "custom"
            reply_text = (
                f"SHIP: {ship_str} | {current.fuel_type} x {int(current.fuel_quantity)}u"
                f" | range {r_ly:.0f} LY | budget {b_ly:.0f} LY"
            )
        elif sub.lower() == "ship":
            if args not in SHIPS:
                reply_text = f"Unknown ship '{args}'. Valid: {', '.join(sorted(SHIPS))}"
            else:
                ship = SHIPS[args]
                overrides = {
                    "ship_type":    args,
                    "hull_mass":    ship["mass"],
                    "specific_heat": ship["specific_heat"],
                }
                # Reset fuel to category default if current fuel incompatible
                if FUEL_CATEGORY.get(current.fuel_type) != ship["fuel_category"]:
                    overrides["fuel_type"] = "D1" if ship["fuel_category"] == "basic" else "SOF-40"
                reply_text = f"Ship set to {args}. Mass: {ship['mass']:,} kg, C_heat: {ship['specific_heat']}"
        elif sub.lower() == "fuel":
            parts = args.split()
            if len(parts) < 2:
                reply_text = "Usage: /profile fuel <quantity> <type>  e.g. /profile fuel 2400 EU-90"
            elif parts[1] not in FUEL_QUALITY:
                reply_text = f"Unknown fuel type '{parts[1]}'. Valid: {list(FUEL_QUALITY)}"
            elif (current.ship_type is not None
                  and FUEL_CATEGORY.get(parts[1]) != SHIPS[current.ship_type]["fuel_category"]):
                ship_cat = SHIPS[current.ship_type]["fuel_category"]
                reply_text = (
                    f"Fuel type '{parts[1]}' incompatible with "
                    f"{current.ship_type} ({ship_cat} only)"
                )
            else:
                try:
                    qty = float(parts[0])
                    overrides = {"fuel_quantity": qty, "fuel_type": parts[1]}
                    reply_text = f"Fuel set: {qty:.0f}u {parts[1]} (quality {FUEL_QUALITY[parts[1]]})"
                except ValueError:
                    reply_text = f"Invalid quantity '{parts[0]}'"
        elif sub.lower() == "level":
            try:
                lvl = int(args)
                lvl = max(0, min(10, lvl))
                overrides = {"adaptive_level": lvl}
                reply_text = f"Adaptive level set to {lvl}"
            except ValueError:
                reply_text = f"Invalid level '{args}' — must be integer 0-10"
        elif sub.lower() == "cargo":
            try:
                kg = float(args)
                if kg < 0:
                    reply_text = "Extra cargo cannot be negative"
                else:
                    overrides = {"extra_cargo_kg": kg}
                    reply_text = f"Extra cargo set to {kg:,.0f} kg"
            except ValueError:
                reply_text = f"Invalid cargo mass '{args}'"

        if overrides:
            updated = current.with_overrides(**overrides)
            save_profile(updated)

        def _profile_reply(text=reply_text):
            yield f"data: {json.dumps({'text': text})}\n\n"
            yield "data: [DONE]\n\n"
        return StreamingResponse(_profile_reply(), media_type="text/event-stream")

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

        # Try hybrid A* (gates + direct jumps with fuel calc) then fall back to gate-only BFS
        profile = load_profile()
        result = route_engine.route(origin, dest, profile)
        if result["type"] == "no_route":
            bfs_result = route_engine.bfs(origin, dest)
            if bfs_result:
                result = bfs_result

        if result is None or result.get("type") == "no_route":
            reply = f"NO ROUTE: {origin.upper()} -> {dest.upper()} — systems unreachable within fuel range."
        else:
            path       = result.get("path", [])
            jumps      = result.get("jumps", 0)
            jump_types = result.get("jump_types", [])
            total_ly   = result.get("total_ly", 0.0)
            fuel_used  = result.get("fuel_used")
            fuel_left  = result.get("fuel_remaining")

            if len(path) > 1:
                path_str = f"{path[0].upper()} -> {path[-1].upper()}"
            else:
                path_str = path[0].upper() if path else dest.upper()

            jump_label = f"{jumps} jump{'s' if jumps != 1 else ''}"

            # Per-hop breakdown
            hop_lines = []
            for i, (system, jtype) in enumerate(zip(path[:-1], jump_types), 1):
                next_sys = path[i]
                if jtype == "direct":
                    sid_a = route_engine.resolve(system)
                    sid_b = route_engine.resolve(next_sys)
                    d = route_engine._dist_ly(sid_a, sid_b) if sid_a and sid_b else 0.0
                    hop_lines.append(f"  {i}. {system.upper()} -> {next_sys.upper()}  direct  {d:.1f} LY")
                else:
                    hop_lines.append(f"  {i}. {system.upper()} -> {next_sys.upper()}  gate")

            fuel_str = ""
            if fuel_used is not None and fuel_used > 0:
                fuel_str = f"  FUEL: {fuel_used:.1f}u"
                if fuel_left is not None:
                    fuel_str += f" | {fuel_left:.1f}u remaining"

            ly_str = f" · {total_ly:.1f} LY" if total_ly > 0 else ""

            reply = f"ROUTE: {path_str}  {jumps} jumps{ly_str}"
            if fuel_str:
                reply += f"\n{fuel_str}"
            if hop_lines:
                reply += "\n" + "\n".join(hop_lines)
            for w in result.get("warnings", [])[:2]:
                reply += f"\nWARN: {w}"

            # Store in log_buffer
            primary = {k: v for k, v in result.items() if k != "alternative"}
            primary["alternative"] = None
            log_buffer.current_route = primary
            log_buffer.pending_alternative = result.get("alternative")
            log_buffer.add({"type": "route_planned", **primary})

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
    from src.ssu_poller import get_player_structures_in_system
    _nearby = get_player_structures_in_system(log_buffer.current_system) if log_buffer.current_system else []
    context = build_context_block(
        system_data=system_data,
        log_events=log_buffer.get_recent(10),
        current_system=log_buffer.current_system,
        live_sessions=log_buffer.get_live(),
        current_route=log_buffer.current_route,
        structure_alerts=log_buffer.pop_structure_alerts(),
        ship_profile=load_profile(),
        nearby_structures=_nearby,
    )

    def event_stream():
        yield ": keep-alive\n\n"
        try:
            for chunk in claude.stream(req.message, req.history, context):
                yield f"data: {json.dumps({'text': chunk})}\n\n"
        except Exception as e:
            log.error("Stream error: %s", e)
            yield f"data: {json.dumps({'error': f'Stream error: {type(e).__name__}'})}\n\n"
        yield "data: [DONE]\n\n"

    return StreamingResponse(event_stream(), media_type="text/event-stream")


class StructureDebugChatRequest(BaseModel):
    structure_id: str
    message: str
    history: list = []


@app.post("/structure-debug/chat", dependencies=[Depends(require_token)])
async def structure_debug_chat(req: StructureDebugChatRequest):
    profile = load_structure_profile(req.structure_id)
    if not profile:
        raise HTTPException(status_code=404, detail="Structure profile not found")

    alerts = detect_alerts(profile)
    urgent  = [a for a in alerts if a["severity"] == "urgent"]
    routine = [a for a in alerts if a["severity"] == "routine"]
    for alert in urgent:
        log_buffer.add_structure_alert(alert)
    if routine:
        profile.routine_alerts = (profile.routine_alerts + routine)[-10:]
        save_structure_profile(profile)

    from src.memory_store import get_memory_store
    mem_store = get_memory_store(req.structure_id)
    summary = mem_store.get_summary()
    memory_text = summary.get("text", "")

    context = build_structure_context(profile, "OWNER", memory_text=memory_text)

    def event_stream():
        yield ": keep-alive\n\n"
        try:
            for chunk in structure_client.stream(
                message=req.message,
                history=req.history,
                context_block=context,
                profile=profile,
                tier="OWNER",
                character_name="[DEV CONSOLE]",
                character_id=0,
            ):
                yield f"data: {json.dumps({'text': chunk})}\n\n"
        except Exception as e:
            log.error("Structure debug chat stream error: %s", e)
            yield f"data: {json.dumps({'error': f'Stream error: {type(e).__name__}'})}\n\n"
        finally:
            yield "data: [DONE]\n\n"
            try:
                mem_store.rebuild_summary()
            except Exception as e_rebuild:
                log.warning("Summary rebuild failed: %s", e_rebuild)

    return StreamingResponse(event_stream(), media_type="text/event-stream")


@app.get("/structure-debug/{structure_id}", dependencies=[Depends(require_token)])
async def structure_debug_get(structure_id: str):
    profile = load_structure_profile(structure_id)
    if not profile:
        raise HTTPException(status_code=404, detail="Structure profile not found")
    return asdict(profile)


@app.post("/structure-debug/{structure_id}", dependencies=[Depends(require_token)])
async def structure_debug_post(structure_id: str, request: Request):
    body = await request.json()
    profile = load_structure_profile(structure_id)
    if not profile:
        if "owner_address" not in body:
            raise HTTPException(status_code=404, detail="Profile not found. Include owner_address to create.")
        profile = StructureProfile(structure_id=structure_id, owner_address=body["owner_address"])
    known = {f.name for f in dc_fields(StructureProfile)}
    for k, v in body.items():
        if k in known and k != "structure_id":
            setattr(profile, k, v)
    try:
        save_structure_profile(profile)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return asdict(profile)


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


@app.post("/auth/deal/offer")
async def deal_offer(req: DealOfferRequest):
    """
    Issue a nonce and return deal terms for PATRON access.
    No auth required — public endpoint for strangers.
    """
    nonce = nonce_store.issue()
    return {
        "nonce": nonce,
        "structure_id": req.structure_id,
        "expires_in_seconds": 300,
        "terms": {
            "messages": DEAL_MESSAGES_DEFAULT,
            "duration_hours": DEAL_DURATION_HOURS_DEFAULT,
            "payment_options": ["item", "sui", "info"],
        },
    }


@app.post("/auth/deal/claim")
async def deal_claim(req: DealClaimRequest):
    """
    Verify wallet signature + payment proof, issue PATRON JWT.

    payment_method="item": server queries suix_queryEvents for a recent
        ItemDepositedEvent from req.address. No proof field needed.
    payment_method="sui": req.proof must contain {"tx_digest": "0x..."}.
        Server calls sui_getTransactionBlock to verify sender and receiver.
    payment_method="info": req.proof must contain {"structure_ids": ["0x..."]}.
        Server reads each via sui_getObject and stores in memory.
    """
    # 1. Consume nonce
    if not nonce_store.consume(req.nonce):
        raise HTTPException(status_code=400, detail="Invalid or expired nonce")

    # 2. Verify wallet signature (reuse existing helper)
    try:
        verify_sui_personal_message(req.nonce.encode(), req.signature, req.address)
    except Exception as e:
        log.warning("deal_claim: signature failed for %s: %s", req.address, e)
        raise HTTPException(status_code=401, detail="Signature verification failed")

    # 3. Verify payment
    if req.payment_method == "item":
        await _verify_item_deposit(req.address, req.structure_id)
    elif req.payment_method == "sui":
        await _verify_sui_payment(req.address, req.proof)
    elif req.payment_method == "info":
        await _process_info_trade(req.address, req.structure_id, req.proof)
    else:
        raise HTTPException(status_code=400, detail=f"Unknown payment_method: {req.payment_method!r}")

    # 4. Lookup character (non-fatal)
    character_id = 0
    character_name = req.address[:12] + "..."
    char_data = await lookup_character(req.address)
    if char_data:
        character_id = char_data.get("id", 0)
        character_name = char_data.get("name", character_name) or character_name

    # 5. Issue deal record + PATRON JWT
    rec = deal_store.issue(req.address, req.structure_id, req.payment_method)
    token = issue_jwt({
        "address": req.address,
        "character_id": character_id,
        "character_name": character_name,
        "tier": "PATRON",
        "structure_id": req.structure_id,
    })

    # 6. Upsert pilot profile (same as /auth/verify)
    from src.memory_store import get_memory_store
    mem = get_memory_store(req.structure_id)
    mem.upsert_pilot(
        address=req.address,
        character_name=character_name,
        character_id=character_id,
        tier="PATRON",
    )

    return {
        "token": token,
        "tier": "PATRON",
        "character_name": character_name,
        "character_id": character_id,
        "messages_remaining": rec.messages_remaining,
        "expires_at": rec.expires_at,
    }


async def _verify_item_deposit(address: str, structure_id: str) -> None:
    """Query suix_queryEvents for a recent ItemDepositedEvent from address.
    Raises HTTPException 402 if no qualifying event found.
    """
    import time as _time
    try:
        result = await nova_client._rpc("suix_queryEvents", [
            {"MoveEventType": _ITEM_DEPOSIT_EVENT},
            None,   # cursor = latest page
            50,     # limit
            True,   # descending (newest first)
        ])
    except Exception as e:
        log.warning("_verify_item_deposit: RPC failed: %s", e)
        raise HTTPException(status_code=502, detail="Chain query failed — try again")

    events = result.get("result", {}).get("data") or []
    cutoff_ms = (_time.time() - _ITEM_DEPOSIT_WINDOW_MS / 1000) * 1000

    for event in events:
        sender = event.get("sender", "").lower()
        ts_ms = int(event.get("timestampMs") or 0)
        if sender == address.lower() and ts_ms >= cutoff_ms:
            return  # found a qualifying deposit

    raise HTTPException(
        status_code=402,
        detail="No recent item deposit found. Drag any item into the SSU within 10 minutes of requesting a deal, then claim.",
    )


async def _verify_sui_payment(address: str, proof: dict) -> None:
    """Verify a SUI coin transfer to VPS address.
    proof must contain {"tx_digest": "0x..."}.
    Raises HTTPException 402 if verification fails.
    """
    if not _VPS_SUI_ADDRESS:
        raise HTTPException(status_code=503, detail="SUI payment not configured on this structure")

    tx_digest = proof.get("tx_digest", "")
    if not tx_digest:
        raise HTTPException(status_code=400, detail="proof.tx_digest required for sui payment")

    try:
        result = await nova_client._rpc("sui_getTransactionBlock", [
            tx_digest,
            {"showInput": True, "showEffects": False, "showBalanceChanges": True},
        ])
    except Exception as e:
        log.warning("_verify_sui_payment: RPC failed: %s", e)
        raise HTTPException(status_code=502, detail="Chain query failed — try again")

    tx_data = result.get("result", {})
    if not tx_data:
        raise HTTPException(status_code=402, detail="Transaction not found on chain")

    # Check sender
    sender = (tx_data.get("transaction", {})
                     .get("data", {})
                     .get("sender", "")).lower()
    if sender != address.lower():
        raise HTTPException(status_code=402, detail="Transaction sender does not match your address")

    # Check balance changes: VPS address received SUI
    balance_changes = tx_data.get("balanceChanges") or []
    vps_received = any(
        bc.get("owner", {}).get("AddressOwner", "").lower() == _VPS_SUI_ADDRESS.lower()
        and int(bc.get("amount", 0)) > 0
        for bc in balance_changes
    )
    if not vps_received:
        raise HTTPException(status_code=402, detail="Transaction does not show SUI sent to this structure's address")


async def _process_info_trade(address: str, structure_id: str, proof: dict) -> None:
    """Player provides structure object IDs as payment.
    Server reads each from chain, stores what it learns.
    Raises HTTPException 400 if no structure_ids provided.
    """
    structure_ids = proof.get("structure_ids") or []
    if not structure_ids:
        raise HTTPException(status_code=400, detail="proof.structure_ids required for info payment")

    from src.memory_store import get_memory_store
    mem = get_memory_store(structure_id)
    learned = []
    for obj_id in structure_ids[:5]:  # cap at 5 to limit RPC calls
        try:
            result = await nova_client._rpc("sui_getObject", [
                obj_id,
                {"showContent": True, "showType": True}
            ])
            data = result.get("result", {}).get("data", {})
            type_str = data.get("type", "unknown")
            learned.append({"object_id": obj_id, "type": type_str})
        except Exception as e:
            log.debug("_process_info_trade: could not read %s: %s", obj_id[:12], e)

    # Store in memory even if chain reads partially failed
    mem.append_event("info_trade", 0, {
        "address": address,
        "structures_offered": structure_ids,
        "structures_read": learned,
    })
    log.info("info_trade: %s offered %d structures, read %d", address[:12], len(structure_ids), len(learned))


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

    # PATRON: consume one message token before any expensive work.
    # DealStore enforces both messages_remaining and expires_at.
    if tier == "PATRON":
        if not deal_store.consume_message(session["address"], req.structure_id):
            raise HTTPException(
                status_code=402,
                detail="Deal exhausted or expired. Visit /auth/deal/offer to make a new deal.",
            )
    # NONE falls through — routed to lobby_client in event_stream below.

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
        yield ": keep-alive\n\n"
        try:
            if tier in ("VETTED", "NONE"):
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
            yield f"data: {json.dumps({'error': f'Stream error: {type(e).__name__}'})}\n\n"
        finally:
            yield "data: [DONE]\n\n"
            try:
                mem_store.rebuild_summary()
            except Exception as e_rebuild:
                log.warning("Summary rebuild failed: %s", e_rebuild)

    return StreamingResponse(event_stream(), media_type="text/event-stream")
