"""
Structure management endpoints — profiles, locations, chat.

Endpoints:
- GET /structure/{assembly_id}                  — Get structure profile
- POST /structure/{assembly_id}                 — Update structure profile (full)
- PATCH /structure/{assembly_id}                — Update structure profile (partial)
- GET /structure/{assembly_id}/onchain          — Get on-chain object IDs and metadata
- POST /structure/{assembly_id}/location/manual — Set manual structure location
- POST /structure/{assembly_id}/location/reveal — Prove location via Sui signature
- POST /structure-chat                          — Stream chat response from structure AI
"""

import os
import json
import logging
from datetime import datetime, timezone
from typing import Optional
from fastapi import APIRouter, HTTPException, Depends
from fastapi.responses import StreamingResponse, JSONResponse
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

from src.structure_persistence import StructureProfile, load_profile as load_structure_profile, save_profile as save_structure_profile
from src.location_index import location_index
from src.schemas import StructureProfileUpdate, LocationManualRequest, LocationRevealRequest, StructureChatRequest
from src.deal_store import deal_store
from src.world_api import world_api
from src.structure_client import structure_client, lobby_client, build_structure_context, detect_alerts
from src.memory_store import get_memory_store
from src.tools import (
    assess_threat_level,
    get_structure_status,
    detect_alerts as detect_alerts_tool,
    analyze_killmail_patterns,
    query_memory_events,
    plan_evasion_route,
)

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


@structures_router.post("/structure-chat")
async def structure_chat(req: StructureChatRequest, session: dict = Depends(require_structure_jwt_or_token)):
    """
    Stream chat response from structure AI. Requires structure JWT.

    Uses context-once tool pattern:
    1. Fetch all context ONCE (profile, killmails, memory events)
    2. Build context dict
    3. Define tool definitions for Claude
    4. Stream Claude with tool_use enabled
    """
    if session["assembly_id"] != req.assembly_id:
        raise HTTPException(status_code=403, detail="Token not valid for this structure")
    tier = session.get("tier", "NONE")

    # PATRON: consume one message token before any expensive work.
    # DealStore enforces both messages_remaining and expires_at.
    if tier == "PATRON":
        if not deal_store.consume_message(session.get("address", ""), req.assembly_id):
            raise HTTPException(
                status_code=402,
                detail="Deal exhausted or expired. Visit /auth/deal/offer to make a new deal.",
            )
    # NONE falls through — routed to lobby_client in event_stream below.

    profile = load_structure_profile(req.assembly_id)
    if not profile:
        raise HTTPException(status_code=404, detail="Structure not found")

    # ────────────────────────────────────────────────────────────────────────────
    # PHASE 1: Fetch context ONCE
    # ────────────────────────────────────────────────────────────────────────────

    # Detect alerts and route urgent ones
    alerts = detect_alerts(profile)
    urgent = [a for a in alerts if a["severity"] == "urgent"]
    routine = [a for a in alerts if a["severity"] == "routine"]

    if routine:
        profile.routine_alerts = (profile.routine_alerts + routine)[-10:]
        save_structure_profile(profile)

    # Fetch memory events ONCE
    memory_events = []
    memory_text = ""
    mem_store = get_memory_store(req.assembly_id)
    if mem_store:
        try:
            events_path = os.path.join(
                os.path.dirname(__file__), "..", "data", "memory", req.assembly_id, "events.jsonl"
            )
            if os.path.exists(events_path):
                with open(events_path) as f:
                    for line in f:
                        try:
                            memory_events.append(json.loads(line.strip()))
                        except Exception:
                            pass
            summary = mem_store.get_summary()
            memory_text = summary.get("text", "")
        except Exception as e:
            log.warning(f"Memory fetch failed: {e}")

    # Fetch killmails ONCE
    killmails = []
    if profile.system_id:
        try:
            killmails = await world_api.get_killmails(system_id=profile.system_id)
            if not isinstance(killmails, list):
                killmails = []
        except Exception as e:
            log.warning(f"Killmail fetch failed: {e}")
            killmails = []

    # ────────────────────────────────────────────────────────────────────────────
    # PHASE 2: Build context dict (passed to all tools)
    # ────────────────────────────────────────────────────────────────────────────

    context = {
        "structure": {
            "assembly_id": profile.assembly_id,
            "structure_name": profile.structure_name,
            "structure_type": profile.structure_type,
            "system_id": profile.system_id,
            "system_name": profile.system_name,
            "region_name": profile.region_name,
            "shield_pct": profile.shield_pct,
            "fuel_pct": profile.fuel_pct,
            "services_online": profile.services_online,
            "services_total": profile.services_total,
            "docked_ships": getattr(profile, "docked_ships", []),
        },
        "killmails": killmails,
        "memory_events": memory_events,
        "system_name": profile.system_name,
        "tier": tier,
    }

    # ────────────────────────────────────────────────────────────────────────────
    # PHASE 3: Define 6 tool definitions for Claude
    # ────────────────────────────────────────────────────────────────────────────

    tool_definitions = [
        {
            "name": "assess_threat_level",
            "description": "Assess threat level based on recent killmails in the system. Returns threat level (LOW/MEDIUM/HIGH/CRITICAL) with kill count and recommendation.",
            "input_schema": {
                "type": "object",
                "properties": {
                    "hours_lookback": {
                        "type": "integer",
                        "description": "How many hours to look back (default 24)",
                        "default": 24,
                    }
                },
                "required": [],
            },
        },
        {
            "name": "get_structure_status",
            "description": "Get formatted structure status including location, shield, fuel, services, and docked ships.",
            "input_schema": {
                "type": "object",
                "properties": {},
                "required": [],
            },
        },
        {
            "name": "detect_alerts",
            "description": "Detect active alerts on the structure (shield/fuel warnings).",
            "input_schema": {
                "type": "object",
                "properties": {},
                "required": [],
            },
        },
        {
            "name": "analyze_killmail_patterns",
            "description": "Analyze patterns in recent killmails to identify threats and escalation.",
            "input_schema": {
                "type": "object",
                "properties": {},
                "required": [],
            },
        },
        {
            "name": "query_memory_events",
            "description": "Query memory events with optional filtering. Returns formatted memory summary.",
            "input_schema": {
                "type": "object",
                "properties": {
                    "filters": {
                        "type": "object",
                        "description": "Optional filter criteria (e.g., {\"type\": \"raid\"})",
                        "additionalProperties": True,
                    }
                },
                "required": [],
            },
        },
        {
            "name": "plan_evasion_route",
            "description": "Plan an evasion route from current structure to a destination system.",
            "input_schema": {
                "type": "object",
                "properties": {
                    "destination": {
                        "type": "string",
                        "description": "Target system name",
                    }
                },
                "required": ["destination"],
            },
        },
    ]

    # ────────────────────────────────────────────────────────────────────────────
    # PHASE 4: Stream Claude with tool definitions
    # ────────────────────────────────────────────────────────────────────────────

    def event_stream():
        yield ": keep-alive\n\n"
        try:
            if tier in ("VETTED", "NONE"):
                # Lobby client: no tools, no operational data
                gen = lobby_client.stream(
                    message=req.message,
                    history=req.history,
                    profile=profile,
                    character_name=session.get("character_name", "[Unknown]"),
                )
                for chunk in gen:
                    yield f"data: {json.dumps({'text': chunk})}\n\n"
            else:
                # OWNER/TRIBE: use tools with context-once pattern
                from anthropic import Anthropic
                client = Anthropic(api_key=os.environ.get("ANTHROPIC_API_KEY"))

                # Build system prompt
                system_prompt = structure_client.build_system_prompt(
                    profile, tier,
                    session.get("character_name", "[Unknown]"),
                    session.get("character_id", 0),
                )

                # Build initial messages with context
                messages = list(req.history[-40:])
                context_block = build_structure_context(
                    profile, tier,
                    memory_text=memory_text,
                    kills_nearby=len([k for k in killmails if k.get("time") or k.get("timestamp")]),
                    threat_context="",
                )
                messages.append({
                    "role": "user",
                    "content": f"[STRUCTURE SENSORS]\n{context_block}\n\n[PILOT]\n{req.message}"
                })

                # Agentic loop: stream Claude response, handle tools, continue loop
                while True:
                    # Stream from Claude
                    response = client.messages.create(
                        model="claude-sonnet-4-6",
                        max_tokens=1024,
                        system=system_prompt,
                        messages=messages,
                        tools=tool_definitions,
                    )

                    # Process response content blocks
                    tool_calls = []
                    for content_block in response.content:
                        if content_block.type == 'text':
                            # Yield text chunks
                            yield f"data: {json.dumps({'text': content_block.text})}\n\n"
                        elif content_block.type == 'tool_use':
                            # Collect tool call for batch processing
                            tool_calls.append(content_block)

                    # Add assistant message to history
                    messages.append({"role": "assistant", "content": response.content})

                    # If no tool calls, we're done
                    if not tool_calls:
                        break

                    # Execute all tool calls and collect results
                    tool_results = []
                    for tool_call in tool_calls:
                        tool_name = tool_call.name
                        tool_input = tool_call.input

                        # Execute tool from src.tools
                        tool_result = None
                        try:
                            if tool_name == "assess_threat_level":
                                hours = tool_input.get("hours_lookback", 24)
                                tool_result = assess_threat_level(context, hours)
                            elif tool_name == "get_structure_status":
                                tool_result = get_structure_status(context)
                            elif tool_name == "detect_alerts":
                                tool_result = detect_alerts_tool(context)
                            elif tool_name == "analyze_killmail_patterns":
                                tool_result = analyze_killmail_patterns(context)
                            elif tool_name == "query_memory_events":
                                filters = tool_input.get("filters")
                                tool_result = query_memory_events(context, filters)
                            elif tool_name == "plan_evasion_route":
                                destination = tool_input.get("destination", "")
                                tool_result = plan_evasion_route(context, destination)
                            else:
                                tool_result = f"Unknown tool: {tool_name}"
                        except Exception as e:
                            tool_result = f"Tool error: {str(e)}"
                            log.warning(f"Tool execution failed: {tool_name}: {e}")

                        tool_results.append({
                            "type": "tool_result",
                            "tool_use_id": tool_call.id,
                            "content": tool_result,
                        })
                        yield f"data: {json.dumps({'tool_use': tool_name, 'result': tool_result})}\n\n"

                    # Add tool results to messages
                    messages.append({"role": "user", "content": tool_results})

                    # Check stop reason to see if we should continue
                    if response.stop_reason != "tool_use":
                        break
        except Exception as e:
            # Categorize error for user feedback
            error_msg = "Chat service error"
            try:
                from anthropic import RateLimitError, APITimeoutError, APIConnectionError
                if isinstance(e, RateLimitError):
                    error_msg = "Service rate limited, please retry in a moment"
                    log.warning("structure/chat: rate limit (structure_id=%s, tier=%s)",
                                profile.assembly_id, tier)
                elif isinstance(e, APITimeoutError):
                    error_msg = "Service timeout, please retry"
                    log.warning("structure/chat: timeout (structure_id=%s, tier=%s)",
                                profile.assembly_id, tier)
                elif isinstance(e, APIConnectionError):
                    error_msg = "Service unavailable"
                    log.error("structure/chat: connection error (structure_id=%s, tier=%s): %s",
                              profile.assembly_id, tier, str(e)[:100])
                else:
                    log.error("structure/chat: unexpected error (structure_id=%s, tier=%s, message_len=%d): %s",
                              profile.assembly_id, tier, len(req.message), e, exc_info=True)
            except ImportError:
                log.error("structure/chat: error (structure_id=%s): %s",
                          profile.assembly_id, e, exc_info=True)

            yield f"data: {json.dumps({'error': error_msg})}\n\n"
        finally:
            yield "data: [DONE]\n\n"
            try:
                if mem_store:
                    mem_store.rebuild_summary()
            except Exception as e_rebuild:
                log.warning("Summary rebuild failed: %s", e_rebuild)

    return StreamingResponse(event_stream(), media_type="text/event-stream")
