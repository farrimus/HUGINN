"""
Companion chat endpoint — structure AI chat.

Endpoints:
- POST /companion/chat    — Chat with the structure's companion AI (JSON response)
- POST /companion/stream  — Same, but streamed as SSE with tool use and visual panel events
"""

import asyncio
import os
import json
import logging
import re
from typing import Optional, List, AsyncGenerator
from fastapi import APIRouter, HTTPException, Header
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from anthropic import Anthropic, AsyncAnthropic

from src.structure_persistence import StructureProfile, load_profile, save_profile
from src.prompt_loader import load_prompt

_ASSEMBLY_ID_RE = re.compile(r"^0x[0-9a-fA-F]{1,64}$")


def _ship_context_block(wallet_address: str = "") -> str:
    """Return a compact ship profile block for HUGINN's context.

    If wallet_address is provided and the player's session has a saved ship
    profile, uses that. Falls back to the global ship_profile.json.
    """
    try:
        from src.ship_profile import load_profile as load_ship_profile, FUEL_PROPERTIES, SHIPS, ShipProfile
        p = None
        if wallet_address:
            from src.session_store import load_session
            session = load_session(wallet_address)
            if session and session.ship_profile:
                valid = set(ShipProfile.__dataclass_fields__)
                p = ShipProfile(**{k: v for k, v in session.ship_profile.items() if k in valid})
        if p is None:
            p = load_ship_profile()
        # Enrich from catalog — session only stores fuel/quantity, not hull physics
        if p.ship_type and p.ship_type in SHIPS:
            cat = SHIPS[p.ship_type]
            p = p.with_overrides(
                hull_mass=cat.get("mass"),
                specific_heat=cat.get("specific_heat"),
            )
        ship_def = SHIPS.get(p.ship_type or "", {}) if p.ship_type else {}

        fuel_props = FUEL_PROPERTIES.get(p.fuel_type, {})
        quality    = fuel_props.get("quality", 0)
        mass_kg    = fuel_props.get("mass_kg", 0)
        r_ly       = p.jump_range()
        budget_ly  = p.fuel_budget()

        # Filter valid fuels to only those compatible with this ship's category.
        ship_cat  = ship_def.get("fuel_category")
        fuel_list = ", ".join(
            f"{k}(q={v['quality']},m={v['mass_kg']}kg)"
            for k, v in FUEL_PROPERTIES.items()
            if ship_cat is None or v["category"] == ship_cat
        )

        class_name = ship_def.get("class_name", "")
        type_str   = f"{p.ship_type} [{class_name}]" if class_name else (p.ship_type or "unknown")
        ship_line  = (f"\nSHIP: {type_str} | {p.fuel_type} x {int(p.fuel_quantity)}u"
                      f" | JUMP {r_ly:.0f} LY | BUDGET {budget_ly:.0f} LY | ADAPTIVE {p.adaptive_level}")
        return ship_line
    except Exception:
        return ""

log = logging.getLogger(__name__)

companion_router = APIRouter()

COMPANION_SYSTEM_PROMPT = load_prompt("companion")


class CompanionChatRequest(BaseModel):
    assembly_id: str            # blockchain object ID (0x...)
    message: str
    history: List[dict] = []
    owner_address: str = ""     # Signature (wallet address) of the visiting shell
    character_name: str = ""    # name carried by the visiting shell's Signature
    item_id: str = ""           # game serialized item ID (e.g. "1000000019552")
    assembly_name: str = ""     # human name from dapp-kit SmartAssemblyResponse.name
    assembly_type: str = ""     # type name from SmartAssemblyResponse.typeDetails.name
    assembly_state: str = ""    # state enum from SmartAssemblyResponse.state
    system_name: str = ""       # solar system name (auto from solarSystem or /system command)
    system_id: int = 0          # solar system ID from SmartAssemblyResponse.solarSystem.id
    debug: bool = False         # set by /debug CLI command — triggers session dump
    disabled_tools: List[str] = []
    tenant: str = ""            # forwarded from frontend EntityContext; falls back to DEPLOYMENT_ENV


def _authenticate(x_api_key: Optional[str]) -> None:
    """Check X-Api-Key header against API_KEY env var. If no key configured, allow all (dev)."""
    api_key = os.environ.get("API_KEY", "")
    if not api_key:
        return
    if x_api_key != api_key:
        raise HTTPException(status_code=401, detail="Unauthorized")


def _get_or_create_profile(req: CompanionChatRequest) -> StructureProfile:
    """Load existing profile or create one, then enrich from dapp-kit fields in the request."""
    profile = load_profile(req.assembly_id)
    if profile is None:
        profile = StructureProfile(
            assembly_id=req.assembly_id,
            owner_address=req.owner_address,
            item_id=req.item_id or None,
        )

    # Enrich profile with authoritative dapp-kit data from the request.
    # Only overwrite defaults — never overwrite data that was set intentionally.
    changed = profile.created_at == ""  # new profile always needs a save
    if req.owner_address and not profile.owner_address:
        profile.owner_address = req.owner_address
        changed = True
    if req.item_id and not profile.item_id:
        profile.item_id = req.item_id
        changed = True
    if req.assembly_name and profile.structure_name == profile.assembly_id:
        profile.structure_name = req.assembly_name
        changed = True
    if req.assembly_type and profile.structure_type == "Smart Storage Unit":
        profile.structure_type = req.assembly_type
        changed = True
    if req.system_name and not profile.system_name:
        profile.system_name = req.system_name
        changed = True
    if req.system_id and not profile.system_id:
        profile.system_id = req.system_id
        changed = True

    if changed:
        save_profile(profile)
        log.info("companion: profile saved for %s (name=%s type=%s sys=%s)",
                 req.assembly_id[:16], profile.structure_name[:24],
                 profile.structure_type, profile.system_name or "-")
    return profile


def _pilot_record_block(assembly_id: str, owner_address: str) -> str:
    """Return a PILOT RECORD block from memory_store, or empty string if no record exists."""
    if not owner_address:
        return ""
    try:
        from src.memory_store import get_memory_store
        store = get_memory_store(assembly_id)
        pilot = store.get_pilot(owner_address)
        if not pilot:
            return ""
        last_updated = pilot.get("last_seen", "unknown")
        lines = [
            f"\nPILOT RECORD (last updated: {last_updated} — may not reflect current state):",
        ]
        name = pilot.get("character_name", "")
        if name:
            lines.append(f"  NAME: {name}")
        lines += [
            f"  VISITS: {pilot.get('visit_count', 0)}",
            f"  FIRST SEEN: {pilot.get('first_seen', 'unknown')[:10]}",
            f"  LAST SEEN: {pilot.get('last_seen', 'unknown')[:10]}",
            f"  KNOWN TIER: {pilot.get('tier', 'NONE')}",
        ]
        return "\n".join(lines)
    except Exception:
        return ""


def _build_context(profile: StructureProfile, req: CompanionChatRequest) -> str:
    """Minimal context (used on subsequent messages and as fallback)."""
    lines = [
        f"STRUCTURE: {profile.structure_name} ({profile.structure_type})",
    ]
    if profile.system_name:
        lines.append(f"SYSTEM: {profile.system_name}")
    if profile.region_name:
        lines.append(f"REGION: {profile.region_name}")
    if req.character_name:
        lines.append(f"SHELL: {req.character_name}")
    if req.owner_address:
        lines.append(f"SIGNATURE: {req.owner_address}")

    # Cached inventory (updated on first-message enrichment)
    inv = profile.cached_inventory
    if inv and inv.get("items"):
        used = inv.get("used_m3", 0)
        cap_pct = inv.get("capacity_percent")
        pct_str = f" ({cap_pct:.1f}%)" if cap_pct is not None else ""
        lines.append(f"\nINVENTORY: {inv.get('item_count', len(inv['items']))} types, {used:.0f} m³{pct_str}")
        for item in inv["items"][:5]:
            lines.append(f"  {item['quantity']}x {item['type_name']}")

    lines.append(_ship_context_block(req.owner_address))

    # Global network registry (all structures combined)
    try:
        from src.log_intel_store import load_known_types
        kt = load_known_types()
        registry_lines = []
        if kt.get("items"):
            registry_lines.append(f"  ITEMS: {', '.join(kt['items'][:30])}")
        if kt.get("hostiles"):
            registry_lines.append(f"  ENEMIES: {', '.join(kt['hostiles'][:20])}")
        if kt.get("ores"):
            registry_lines.append(f"  ORES: {', '.join(kt['ores'][:20])}")
        if registry_lines:
            lines.append("\nNETWORK REGISTRY:\n" + "\n".join(registry_lines))
    except Exception:
        pass

    pilot_block = _pilot_record_block(profile.assembly_id, req.owner_address)
    if pilot_block:
        lines.append(pilot_block)

    # Field reports — always included so intel persists across messages
    try:
        from src.intel_store import get_intel_store
        intel = get_intel_store(profile.assembly_id)
        recent = intel.get_recent(4)
        if recent:
            lines.append("\nFIELD REPORTS (pilot-logged):")
            for r in recent:
                by = r.get("reported_by", "unknown")
                lines.append(f"  [{r['id']}] {by}: {r['content'][:120]}")
    except Exception:
        pass

    return "\n".join(lines)


async def _preload_context(req: CompanionChatRequest, profile: StructureProfile) -> str:
    """
    Async context builder. Fetches enriched entity data from EntityResolver.

    Only runs full pre-load on first message (history empty). Subsequent messages
    use the minimal context to avoid latency cost.

    Hard deadline: 1.9s — returns minimal context on timeout, never fails the request.
    """
    # Subsequent messages: minimal context only
    if req.history:
        return _build_context(profile, req)

    # Validate assembly ID format
    if not _ASSEMBLY_ID_RE.match(req.assembly_id):
        return _build_context(profile, req)

    try:
        from src.entity_resolver import get_resolver_for_tenant
        _tenant = req.tenant or os.getenv("DEPLOYMENT_ENV", "utopia")
        resolver = get_resolver_for_tenant(_tenant)
    except RuntimeError:
        log.debug("companion: EntityResolver not initialized, using minimal context")
        return _build_context(profile, req)

    async def _enrich() -> str:
        try:
            full = await resolver.get_assembly_full(req.assembly_id)
        except Exception as e:
            log.warning("companion: preload get_assembly_full failed: %s", e)
            return _build_context(profile, req)

        if not full:
            return _build_context(profile, req)

        asm  = full.get("assembly") or {}
        char = full.get("owner_character")
        es   = full.get("energy_source")

        lines = [
            f"STRUCTURE: {asm.get('name') or profile.structure_name} "
            f"({asm.get('assembly_type', profile.structure_type)}, "
            f"{_fmt_status(asm.get('status'))})",
        ]

        # Owner
        if char:
            char_name = char.get("name") or char.get("metadata", {}).get("name") or ""
            tribe_id  = char.get("tribe_id") or ""
            if char_name:
                lines.append(f"OWNER: {char_name} (tribeId: {tribe_id})")

        if req.character_name:
            lines.append(f"SHELL: {req.character_name}")

        # System
        system_name = req.system_name or profile.system_name
        if system_name:
            sys_info = resolver.get_system(system_name)
            if sys_info:
                sec  = sys_info.get("security") or sys_info.get("securityStatus") or ""
                sec_str = f" | SEC {sec:.2f}" if isinstance(sec, (int, float)) else ""
                region = sys_info.get("regionName") or ""
                lines.append(f"SYSTEM: {system_name}{sec_str}")
                if region:
                    lines.append(f"REGION: {region}")
            else:
                lines.append(f"SYSTEM: {system_name}")

        # Network node / fuel
        if es:
            fuel = es.get("fuel") or {}
            if isinstance(fuel, dict):
                fuel = fuel.get("fields") or fuel
            qty      = int(fuel.get("quantity") or 0)
            cap      = int(fuel.get("max_capacity") or 0)
            unit_vol = int(fuel.get("unit_volume") or 0)
            burn_ms  = int(fuel.get("burn_rate_in_ms") or 0)
            is_burning = bool(fuel.get("is_burning", False))
            eff_max  = cap // unit_vol if unit_vol > 0 else cap
            fuel_pct = round(qty * 100.0 / eff_max, 2) if eff_max > 0 else 0.0

            if is_burning and burn_ms > 0:
                units_per_hr    = 3_600_000.0 / burn_ms
                hours_remaining = qty / units_per_hr if units_per_hr > 0 else 0.0
                days_remaining  = hours_remaining / 24.0
                fuel_line = (f"FUEL: {fuel_pct:.0f}% — ~{days_remaining:.1f}d remaining "
                             f"({units_per_hr:.2f} units/hr)")
            elif cap > 0:
                fuel_line = f"FUEL: {fuel_pct:.0f}% — NOT BURNING"
            else:
                fuel_line = None

            node_name   = es.get("name") or ""
            node_status = _fmt_status(es.get("status"))
            lines.append(f"\nNETWORK NODE: {node_name} ({node_status})")
            if fuel_line:
                lines.append(f"  {fuel_line}")

            # Connected assemblies (brief, cap 8)
            connected_ids = es.get("connected_assembly_ids") or []
            if connected_ids:
                connected_ids = [str(c) for c in connected_ids if c][:8]
                conn_parts = []
                for cid in connected_ids[:8]:
                    ca = await resolver.get_assembly(cid)
                    if ca:
                        conn_parts.append(
                            f"{ca.get('name') or cid[:10]}"
                            f"({ca.get('assembly_type','?')},{_fmt_status(ca.get('status'))})"
                        )
                if conn_parts:
                    conn_str = ", ".join(conn_parts)
                    if len(conn_str) > 300:
                        conn_str = conn_str[:297] + "..."
                    lines.append(f"  CONNECTED ({len(connected_ids)}): {conn_str}")

        # SSU inventory — fetch, display, cache in profile, update known items
        if asm.get("assembly_type") == "SmartStorageUnit":
            try:
                inv = await resolver.get_inventory(req.assembly_id)
                if inv and inv.get("items"):
                    cap_pct = inv.get("capacity_percent")
                    used    = inv.get("used_capacity", 0)
                    top = sorted(inv["items"], key=lambda x: x["quantity"], reverse=True)[:5]
                    lines.append(
                        f"\nINVENTORY: {len(inv['items'])} types, {used:.0f} m³"
                        + (f" ({cap_pct:.1f}%)" if cap_pct is not None else "")
                    )
                    for item in top:
                        lines.append(f"  {item['quantity']}x {item['type_name']}")
                    # Cache for subsequent messages
                    profile.cached_inventory = {
                        "item_count": len(inv["items"]),
                        "used_m3": used,
                        "capacity_percent": cap_pct,
                        "items": [{"type_name": it["type_name"], "quantity": it["quantity"]}
                                  for it in sorted(inv["items"], key=lambda x: x["quantity"], reverse=True)[:10]],
                    }
                    save_profile(profile)
                    # Register items to global network registry
                    try:
                        from src.log_intel_store import register_items
                        register_items([it["type_name"] for it in inv["items"] if it.get("type_name")])
                    except Exception as e:
                        log.debug("companion: register_items failed: %s", e)
            except Exception as e:
                log.debug("companion: inventory preload failed: %s", e)

        lines.append(_ship_context_block(req.owner_address))

        # Global network registry (all structures combined)
        try:
            from src.log_intel_store import load_known_types
            kt = load_known_types()
            registry_lines = []
            if kt.get("items"):
                registry_lines.append(f"  ITEMS: {', '.join(kt['items'][:30])}")
            if kt.get("hostiles"):
                registry_lines.append(f"  ENEMIES: {', '.join(kt['hostiles'][:20])}")
            if kt.get("ores"):
                registry_lines.append(f"  ORES: {', '.join(kt['ores'][:20])}")
            if registry_lines:
                lines.append("\nNETWORK REGISTRY:\n" + "\n".join(registry_lines))
        except Exception as e:
            log.debug("companion: network registry inject failed: %s", e)

        # Pilot record
        pilot_block = _pilot_record_block(profile.assembly_id, req.owner_address)
        if pilot_block:
            lines.append(pilot_block)

        # Field reports — injected here AND in _build_context so always present
        try:
            from src.intel_store import get_intel_store
            intel = get_intel_store(req.assembly_id)
            recent = intel.get_recent(4)
            if recent:
                lines.append("\nFIELD REPORTS (pilot-logged):")
                for r in recent:
                    by = r.get("reported_by", "unknown")
                    lines.append(f"  [{r['id']}] {by}: {r['content'][:120]}")
        except Exception as e:
            log.debug("companion: intel inject failed: %s", e)

        context = "\n".join(lines)
        if len(context) > 3500:
            context = context[:3497] + "..."
        return context

    try:
        return await asyncio.wait_for(_enrich(), timeout=1.9)
    except asyncio.TimeoutError:
        log.warning("companion: preload context timed out for %s, using minimal", req.assembly_id)
        return _build_context(profile, req)
    except Exception as e:
        log.warning("companion: preload context error: %s", e)
        return _build_context(profile, req)


def _is_debug_session(req: "CompanionChatRequest") -> bool:
    """Return True if debug dumping is active (client flag or HUGINN_DEBUG env var)."""
    return req.debug or bool(os.environ.get("HUGINN_DEBUG"))


def _write_debug_dump(messages: list, req: "CompanionChatRequest",
                       system_prompt: str = "", tools: list = None) -> str:
    """Write a human-readable session dump to debug/ and return the file path."""
    import datetime
    date = datetime.datetime.utcnow().strftime("%Y%m%d")
    short_id = req.assembly_id.replace("0x", "")[:10]
    filename = f"debug_{short_id}_{date}.txt"
    debug_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "debug")
    os.makedirs(debug_dir, exist_ok=True)
    path = os.path.join(debug_dir, filename)

    lines = [
        "=== HUGINN DEBUG DUMP ===",
        f"Last updated : {datetime.datetime.utcnow().isoformat()}Z",
        f"Assembly  : {req.assembly_id}",
        f"Character : {req.character_name or '-'}",
        f"System    : {req.system_name or '-'}",
        f"Messages  : {len(messages)}",
        "",
    ]

    # System prompt
    if system_prompt:
        lines.append("=" * 60)
        lines.append("SYSTEM PROMPT")
        lines.append("=" * 60)
        lines.append(system_prompt)
        lines.append("")

    # Tools
    if tools:
        lines.append("=" * 60)
        lines.append(f"TOOLS ({len(tools)} registered)")
        lines.append("=" * 60)
        for t in tools:
            name = t.get("name", "?")
            desc = t.get("description", "")
            lines.append(f"  [{name}] {desc}")
        lines.append("")

    for i, msg in enumerate(messages):
        role = msg.get("role", "?").upper()
        content = msg.get("content", "")
        lines.append(f"{'='*60}")
        lines.append(f"[{i+1}] {role}")
        lines.append(f"{'='*60}")
        if isinstance(content, str):
            lines.append(content)
        elif isinstance(content, list):
            for block in content:
                if not isinstance(block, dict):
                    lines.append(str(block))
                    continue
                btype = block.get("type", "?")
                if btype == "text":
                    lines.append(block.get("text", ""))
                elif btype == "tool_use":
                    lines.append(f"[TOOL CALL: {block['name']}  id={block.get('id','')}]")
                    lines.append(json.dumps(block.get("input", {}), indent=2))
                elif btype == "tool_result":
                    lines.append(f"[TOOL RESULT  tool_use_id={block.get('tool_use_id','')}]")
                    lines.append(str(block.get("content", "")))
                else:
                    lines.append(json.dumps(block, indent=2))
        lines.append("")

    with open(path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))

    return path


def _fmt_status(val, _depth: int = 0) -> str:
    if val is None:
        return "UNKNOWN"
    if isinstance(val, str):
        return val
    if isinstance(val, dict) and _depth < 3:
        for key in ("@variant", "variant", "name"):
            v = val.get(key)
            if isinstance(v, str):
                return v
        v = val.get("status")
        if v is not None:
            return _fmt_status(v, _depth + 1)
    return str(val)


@companion_router.post("/companion/chat")
async def companion_chat(
    req: CompanionChatRequest,
    x_api_key: Optional[str] = Header(default=None),
):
    """
    Chat with the structure's companion AI.

    Returns a plain JSON response for now. Streaming will be added in a follow-up.
    Auth: X-Api-Key header checked against API_KEY env var (open if not set).
    """
    _authenticate(x_api_key)

    profile = _get_or_create_profile(req)
    context = await _preload_context(req, profile)

    # Build message list: bounded history + new message with context injected
    messages = list(req.history[-20:])
    messages.append({
        "role": "user",
        "content": f"[STRUCTURE SENSORS]\n{context}\n\n[SHELL]\n{req.message}",
    })

    client = Anthropic(api_key=os.environ.get("ANTHROPIC_API_KEY"))
    try:
        response = client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=1024,
            system=COMPANION_SYSTEM_PROMPT,
            messages=messages,
        )
        reply = response.content[0].text if response.content else ""
    except Exception as e:
        log.error("companion/chat: Claude error: %s", e)
        raise HTTPException(status_code=502, detail="AI service error")

    return {"response": reply, "assembly_id": profile.assembly_id}


# Maps Claude tool names → frontend ToolType strings (panel identifiers)
_TOOL_TO_PANEL = {
    "get_system_intel": "system_intel",
    "get_pilot_profile": "pilot_profile",
    "search_memory": "memory_search",
    "get_memory_summary": "memory_summary",
    "plan_route": "route_planned",
    "calculate_build_options": "build_options",
}


async def _stream_companion(req: CompanionChatRequest, profile: StructureProfile) -> AsyncGenerator[str, None]:
    """
    Async generator yielding SSE event strings.

    Event shapes (matching SSEMessage in frontend/src/types/terminal.ts):
      data: {"text": "..."}                                         — text chunk
      data: {"tool_result": {"toolName": "...", "data": {...}}}     — visual panel update
      data: {"done": true}                                          — stream complete
      data: {"error": "..."}                                        — error
    """
    client = AsyncAnthropic(api_key=os.environ.get("ANTHROPIC_API_KEY"))
    context_str = await _preload_context(req, profile)

    # Resolve pilot tier from session (set at registration time by /session/register)
    tier = "NONE"
    if req.owner_address:
        from src.session_store import load_session as _load_session
        _session = _load_session(req.owner_address)
        if _session:
            tier = _session.tier
        try:
            from src.memory_store import get_memory_store
            store = get_memory_store(profile.assembly_id)
            store.upsert_pilot(req.owner_address, req.character_name or "", 0, tier)
        except Exception as e:
            log.debug("companion: upsert_pilot failed: %s", e)

    if req.owner_address:
        from src.tier_capabilities import ai_instruction, blocked_tools as _blocked_tools
        context_str += f"\nTIER: {tier} — {ai_instruction(tier)}"

    messages = list(req.history[-20:])
    messages.append({
        "role": "user",
        "content": f"[STRUCTURE SENSORS]\n{context_str}\n\n[SHELL]\n{req.message}",
    })

    from src.ai_tools import ai_tools
    from src.tier_capabilities import blocked_tools as _blocked_tools
    all_tool_names = list(ai_tools.tools.keys())
    tier_blocked = _blocked_tools(tier, all_tool_names)
    combined_disabled = list(set((req.disabled_tools or []) + tier_blocked))
    tools = ai_tools.get_tools_for_claude(disabled=combined_disabled)

    system_name = req.system_name or profile.system_name or ""
    system_id = req.system_id or profile.system_id or None

    # Fallback: derive system_id from name via galaxy_db (covers profiles with manual /system set)
    if not system_id and system_name:
        try:
            from src.galaxy_db import galaxy_db
            sys_info = galaxy_db.get_system(system_name)
            if sys_info:
                system_id = sys_info.get("solarSystemId") or sys_info.get("id")
        except Exception:
            pass

    tool_context = {
        "structure_id": profile.assembly_id,
        "character_address": req.owner_address or "",
        "pilot_name": req.character_name or "",
        "system_name": system_name,
        "system_id": system_id,
        "pilot_tier": tier,
    }

    try:
        while True:
            async with client.messages.stream(
                model="claude-sonnet-4-6",
                max_tokens=1024,
                system=COMPANION_SYSTEM_PROMPT,
                messages=messages,
                tools=tools,
            ) as stream:
                async for event in stream:
                    if (event.type == "content_block_delta"
                            and hasattr(event, "delta")
                            and hasattr(event.delta, "type")
                            and event.delta.type == "text_delta"):
                        yield f"data: {json.dumps({'text': event.delta.text})}\n\n"

                message = await stream.get_final_message()
                stop_reason = message.stop_reason

                if stop_reason == "tool_use":
                    assistant_content = []
                    tool_results_for_claude = []

                    from src.prompt_loader import load_tool_prompts
                    live_prompts = load_tool_prompts()

                    for block in message.content:
                        if block.type == "text":
                            assistant_content.append({"type": "text", "text": block.text})
                        elif block.type == "tool_use":
                            assistant_content.append({
                                "type": "tool_use",
                                "id": block.id,
                                "name": block.name,
                                "input": block.input,
                            })

                            result = await ai_tools.execute_tool_structured(
                                block.name, block.input, context=tool_context
                            )

                            content = result.get("text", "")
                            guidance = live_prompts.get(block.name, {}).get("response_guidance", "").strip()
                            if guidance and not guidance.startswith("<!--"):
                                content = f"{guidance}\n\n{content}"

                            tool_results_for_claude.append({
                                "type": "tool_result",
                                "tool_use_id": block.id,
                                "content": content,
                            })

                            panel_type = _TOOL_TO_PANEL.get(block.name)
                            if panel_type and result.get("structured"):
                                yield f"data: {json.dumps({'tool_result': {'toolName': panel_type, 'data': result['structured']}})}\n\n"

                    messages.append({"role": "assistant", "content": assistant_content})
                    messages.append({"role": "user", "content": tool_results_for_claude})
                    continue

                break

    except Exception as e:
        log.error("companion/stream: error: %s", e)
        yield f"data: {json.dumps({'error': str(e)})}\n\n"

    if _is_debug_session(req):
        try:
            path = _write_debug_dump(messages, req,
                                     system_prompt=COMPANION_SYSTEM_PROMPT,
                                     tools=tools)
            log.info("companion/stream: debug dump written: %s", path)
        except Exception as e:
            log.warning("companion/stream: debug dump failed: %s", e)

    yield f"data: {json.dumps({'done': True})}\n\n"


@companion_router.post("/companion/stream")
async def companion_stream_endpoint(
    req: CompanionChatRequest,
    x_api_key: Optional[str] = Header(default=None),
):
    """
    Stream companion chat response as SSE.

    Emits text chunks and tool results (visual panel updates) as they are produced.
    Auth: X-Api-Key header checked against API_KEY env var (open if not set).
    """
    _authenticate(x_api_key)
    profile = _get_or_create_profile(req)

    return StreamingResponse(
        _stream_companion(req, profile),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )
