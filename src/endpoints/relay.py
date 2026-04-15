"""
Relay companion endpoint for desktop browsers.

Receives transmissions from pilots outside any structure context.
Tier resolved from wallet via AccessRegistry. Ephemeral — no persistence.
"""
import json
import logging
import os
from typing import AsyncGenerator, List

from anthropic import AsyncAnthropic
from fastapi import APIRouter
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

relay_router = APIRouter()
log = logging.getLogger(__name__)


class RelayChatRequest(BaseModel):
    message: str
    history: List[dict] = []
    owner_address: str = ""
    character_name: str = ""
    tenant: str = ""


async def _resolve_tier(owner_address: str) -> str:
    """Resolve tier from AccessRegistry, falling back to saved session."""
    from src.blockchain_queries import sui_rpc_client
    from src.vouch_store import apply_override

    tier = "NONE"
    registry_id = os.environ.get("TIER_REGISTRY_OBJECT_ID", "")
    if registry_id:
        try:
            registry = await sui_rpc_client.get_access_registry(registry_id)
            if registry:
                tier = sui_rpc_client.resolve_tier(owner_address, registry)
                log.debug("relay: chain tier=%s for %s", tier, owner_address[:12])
        except Exception as e:
            log.debug("relay: chain tier lookup failed: %s", e)

    if tier == "NONE":
        try:
            from src.session_store import load_session
            _tenant = os.environ.get("DEPLOYMENT_ENV", "utopia")
            session = load_session(owner_address, tenant=_tenant)
            if session and session.tier != "NONE":
                tier = session.tier
        except Exception:
            pass

    return apply_override(tier, owner_address)


async def _stream_relay(req: RelayChatRequest) -> AsyncGenerator[str, None]:
    """SSE stream for relay chat. No structure context, no tools."""
    from src.prompt_loader import load_prompt
    from src.tier_capabilities import ai_instruction

    client = AsyncAnthropic(api_key=os.environ.get("ANTHROPIC_API_KEY", ""))

    tier = await _resolve_tier(req.owner_address) if req.owner_address else "NONE"

    # Resolve character name from session if not provided
    character_name = req.character_name
    if not character_name and req.owner_address:
        try:
            from src.session_store import load_session
            _tenant = os.environ.get("DEPLOYMENT_ENV", "utopia")
            session = load_session(req.owner_address, tenant=_tenant)
            if session and session.character_name:
                character_name = session.character_name
        except Exception:
            pass

    context_parts = ["MODE: RELAY — no structure anchor."]
    if req.owner_address:
        context_parts.append(f"WALLET: {req.owner_address}")
    if character_name:
        context_parts.append(f"PILOT: {character_name}")
    context_parts.append(
        f"TIER: {tier} — {ai_instruction(tier)}"
        if req.owner_address
        else "TIER: NONE — no wallet connected"
    )

    messages = list(req.history[-10:])
    messages.append({
        "role": "user",
        "content": f"[RELAY]\n{chr(10).join(context_parts)}\n\n[TRANSMISSION]\n{req.message}",
    })

    system_prompt = load_prompt("companion")

    try:
        async with client.messages.stream(
            model=os.environ.get("CLAUDE_MODEL", "claude-sonnet-4-6"),
            max_tokens=300,
            system=system_prompt,
            messages=messages,
        ) as stream:
            async for event in stream:
                if event.type == "content_block_delta" and hasattr(event.delta, "text"):
                    yield f"data: {json.dumps({'text': event.delta.text})}\n\n"
    except Exception as e:
        log.error("relay: stream error: %s", e)
        yield f"data: {json.dumps({'error': str(e)})}\n\n"

    yield f"data: {json.dumps({'done': True})}\n\n"


@relay_router.post("/companion/relay")
async def relay_endpoint(req: RelayChatRequest):
    """Relay chat for desktop browsers. No structure context required."""
    return StreamingResponse(
        _stream_relay(req),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )
