# structure_client

## Overview
Claude streaming clients for the Structure AI. Two personas: `StructureClient` (full operational access for authorized pilots) and `LobbyClient` (read-only for outsiders). Separate from `claude_client` (Ship AI). Provides context building and alert detection for Structure AI interactions.

## When Should an Agent Use This Module?
- Running Structure AI chat for authorized pilots (OWNER/TRIBE tiers)
- Running lobby/registry chat for outsiders (VETTED/public)
- Building context blocks from structure state (fuel, shields, alerts)
- Detecting and formatting structure alerts

## Key API
| Symbol | Type | Purpose | Agent Instruction |
|--------|------|---------|------------------|
| `structure_client` | object | Global StructureClient singleton | Use for operator/tribe pilot chat |
| `structure_client.stream(message, history, context_block, profile, tier, character_name, character_id)` | method | Yield response text chunks for Structure AI | Call from Structure AI chat route |
| `lobby_client` | object | Global LobbyClient singleton | Use for VETTED and public access chat |
| `lobby_client.stream(message, history, profile, character_name)` | method | Yield response text chunks for lobby | Call from structure lobby/registry route |
| `build_structure_context(profile, tier, memory_text, kills_nearby)` | function | Build [STRUCTURE SENSORS] context block | Call before passing to stream() |
| `detect_alerts(profile)` | function | Evaluate structure state, return alert list | Call periodically to check for shield/fuel alerts |

### Data Structures
**StructureProfile** (from `structure_profile` module)
```python
@dataclass
class StructureProfile:
    structure_name: str
    structure_type: str
    system_name: str
    region_name: str
    system_id: int
    shield_pct: float
    fuel_pct: float
    services_online: int
    services_total: int
    docked_pilots: list
    connected_assembly_ids: list
    connected_assemblies: list
    ssu_inventory: list
    routine_alerts: list
```

**Alert** (returned by `detect_alerts`)
```python
{
    "type": "structure_alert",
    "structure_id": str,
    "structure_name": str,
    "severity": "urgent" | "routine",  # urgent: <20% shield or <10% fuel; routine: <25% fuel
    "message": str,  # Human-readable alert message
    "ts": int  # Unix timestamp
}
```

## Critical Gotchas & Pitfalls for Agents
• **Two separate personas:** Do not use `claude_client` (Ship AI) for structures — this module has distinct system prompts.
• **Tier logic in prompts:** System prompts encode tier behavior — StructureClient streams full operational data to OWNER/TRIBE, LobbyClient never reveals internals.
• **build_structure_context filters by tier:** Pass the correct tier (OWNER/TRIBE/VETTED/public) — context builder redacts sensitive fields automatically.
• **Gate graph cached at import:** Module loads `gate_graph.json` at import time. If file is missing, routing context will be incomplete (logged as warning).
• **detect_alerts is synchronous:** Call immediately before streaming; it evaluates current profile state and returns a new list each time.

## Architecture
```
StructureClient (OWNER/TRIBE):
  Input: message, history, structure_profile, tier, character info
  ↓
  build_structure_context(profile, tier, ...) → formats sensor data
  build_system_prompt(profile, tier, character_name, id) → inject vars
  ↓
  Anthropic API (streaming) with STRUCTURE_SYSTEM_PROMPT
  ↓
  Yield text chunks

LobbyClient (VETTED/public):
  Input: message, history, structure_profile, character info
  ↓
  Anthropic API (streaming) with LOBBY_SYSTEM_PROMPT
  ↓
  Limited response, no operational data
  ↓
  Yield text chunks
```

## Agent Guidance
**Primary Workflow for Structure Chat**
1. Fetch structure_profile, access tier, character info from auth
2. Call `detect_alerts(profile)` to check for urgent/routine alerts
3. Call `build_structure_context(profile, tier, memory_text, kills_nearby)` to format sensor block
4. Call `structure_client.stream(message, history, context, profile, tier, character_name, id)` and yield chunks

**Primary Workflow for Lobby Chat**
1. Fetch structure_profile, character info from auth
2. Call `lobby_client.stream(message, history, profile, character_name)` and yield chunks
3. No need to build context or detect alerts — LobbyClient has no access to internals

**Best Practices & Anti-Patterns**
- Always / Call `detect_alerts()` before streaming to catch urgent conditions
- Always / Pass correct tier to `build_structure_context()` — it redacts automatically
- Always / Use `structure_client` for OWNER/TRIBE, `lobby_client` for VETTED/public
- Always / Include `[STRUCTURE SENSORS]` block when calling `structure_client.stream()`
- Never / Use Ship AI prompt for structures — voice and persona are different
- Never / Pass operational data in message to `lobby_client` — it refuses to acknowledge it

**Cross-Module Dependencies**
- Depends on: `anthropic` SDK (streaming), `structure_profile` (state), `memory_store` (pilot notes), `galaxy_db` (universe context)
- Used by: `main.py` structure chat routes, Structure AI endpoints

## Progressive Disclosure
**Read this main file by default.**

**Load deeper files ONLY when:**
- You need tier logic: read `/docs/ref/structure-ai.md` section on access tiers
- You need [STRUCTURE SENSORS] format details: read `/docs/ref/structure-ai.md` section on context
- You need structure profile schema: read `/docs/modules/structure_profile.md`
- You need persona voice: read `/intent.md` for EVE Frontier lore and character guidelines
