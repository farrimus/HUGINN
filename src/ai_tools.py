"""
AI Tools Registry for Claude.

Centralized registry of tools available to Claude API calls.
Currently used by: Structure AI (future: Ship AI, other agents)

Tools are organized by category:
- memory: Memory store queries (search, summarize)
- threat: Threat assessment (analyze kills, threats)
- info: Information retrieval (system data, pilot history)

Each tool has:
- name: Identifier for Claude
- description: Purpose and usage
- input_schema: JSON Schema for parameters
- handler: Python function to execute the tool
"""

import logging
import asyncio
import json
from typing import Dict, Any, Optional, List

log = logging.getLogger(__name__)

# Lazy import to avoid circular dependency
_radius_search = None
def _get_radius_search():
    global _radius_search
    if _radius_search is None:
        from src.radius_search import RadiusSearch
        _radius_search = RadiusSearch()
    return _radius_search


class ToolRegistry:
    """Registry and executor for AI tools."""

    def __init__(self):
        self.tools: Dict[str, Dict[str, Any]] = {}
        self._register_default_tools()

    def _register_default_tools(self):
        """Register all available tools."""
        # --- Memory Tools ---
        self.register_tool(
            name="search_memory",
            category="memory",
            description="Search structure memory for recent events by keyword",
            input_schema={
                "type": "object",
                "properties": {
                    "keyword": {
                        "type": "string",
                        "description": "Search term: 'pirate', 'raid', 'corvette', 'dock', etc."
                    },
                    "days": {
                        "type": "integer",
                        "default": 7,
                        "description": "Lookback period in days"
                    },
                },
                "required": ["keyword"]
            },
            handler=self._tool_search_memory
        )

        self.register_tool(
            name="get_memory_summary",
            category="memory",
            description="Get current memory summary (event tallies and key facts)",
            input_schema={
                "type": "object",
                "properties": {
                    "days": {
                        "type": "integer",
                        "default": 7,
                        "description": "Summary period in days"
                    }
                },
                "required": []
            },
            handler=self._tool_get_memory_summary
        )

        # --- Threat Tools ---
        self.register_tool(
            name="assess_threat",
            category="threat",
            description="Analyze recent kills in a system for threat patterns (aggressors, ship types, escalation)",
            input_schema={
                "type": "object",
                "properties": {
                    "system_id": {
                        "type": "integer",
                        "description": "Solar system ID (optional, defaults to current system)"
                    },
                    "hours_lookback": {
                        "type": "integer",
                        "default": 24,
                        "description": "Time window in hours"
                    },
                    "ship_class": {
                        "type": "string",
                        "description": "Optional ship class to check vulnerability (corvette, frigate, destroyer, cruiser, capital)"
                    }
                },
                "required": []
            },
            handler=self._tool_assess_threat
        )

        self.register_tool(
            name="get_system_intel",
            category="info",
            description="Get system information: security status, star type, planets, recent kill count, gate links",
            input_schema={
                "type": "object",
                "properties": {
                    "system_id": {
                        "type": "integer",
                        "description": "Solar system ID (optional, defaults to current system)"
                    }
                },
                "required": []
            },
            handler=self._tool_get_system_intel
        )

        self.register_tool(
            name="get_pilot_profile",
            category="info",
            description="Get pilot profile: visit count, first visit, last visit, access tier",
            input_schema={
                "type": "object",
                "properties": {
                    "pilot_address": {
                        "type": "string",
                        "description": "Sui wallet address (0x + 64 hex chars). Optional, defaults to current pilot."
                    }
                },
                "required": []
            },
            handler=self._tool_get_pilot_profile
        )

        # --- Spatial Search Tools ---
        self.register_tool(
            name="radius_search",
            category="spatial",
            description="Find systems within a distance and filter by criteria (planets, kills, heat, structures)",
            input_schema={
                "type": "object",
                "properties": {
                    "center_system": {
                        "type": "string",
                        "description": "Center system name (e.g., 'UR8-K7K'). Optional, defaults to current system."
                    },
                    "radius_ly": {
                        "type": "number",
                        "description": "Search radius in light-years (must be > 0). Default: 100"
                    },
                    "filters": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "What to rank by: 'planets' (resources), 'killmails' (danger), 'heat' (hazard), 'structures' (bases). Default: ['planets']"
                    },
                    "top_n": {
                        "type": "integer",
                        "description": "Number of results per filter to return (default 10)"
                    },
                    "killmail_hours": {
                        "type": "integer",
                        "description": "Lookback window for kills in hours (default 24)"
                    },
                    "skip_heat_traps": {
                        "type": "boolean",
                        "description": "Exclude warm/hot systems >= 70°F (default false)"
                    }
                },
                "required": []
            },
            handler=self._tool_radius_search
        )

        # --- Route Tool ---
        self.register_tool(
            name="plan_route",
            category="navigation",
            description=(
                "Calculate a route to a destination system using the route engine. "
                "Returns a full route with jump-by-jump breakdown. Use when the shell asks to "
                "plot, calculate, or find a route, course, or path to a destination. "
                "Accepts an optional specific_heat to model the ship's jump capability. "
                "If the shell mentions their ship's jump range in LY, convert to specific_heat "
                "using: specific_heat = jump_range_ly * HEAT_CONSTANT * mass / (T_MAX * hull_mass) — "
                "or just pass the jump_range_ly and let the engine estimate. "
                "Always call this tool when route planning is requested instead of trying to manually "
                "search systems."
            ),
            input_schema={
                "type": "object",
                "properties": {
                    "destination": {
                        "type": "string",
                        "description": "Destination system name (exact or close match)"
                    },
                    "origin": {
                        "type": "string",
                        "description": "Origin system name. Optional — defaults to current system from context."
                    },
                    "specific_heat": {
                        "type": "number",
                        "description": (
                            "Ship specific heat capacity (determines jump range). "
                            "Wend=1.0 (~50 LY), Recurve=1.0 (~50 LY), Reiver=1.0 (~50 LY), "
                            "USV=1.8 (~90 LY), Lai=2.5 (~125 LY), Lorha=2.5 (~125 LY), "
                            "MCF=2.5 (~125 LY), HAF=2.5 (~125 LY), Tades=2.5 (~125 LY), "
                            "Maul=2.5 (~125 LY), Chumaq=3.0 (~150 LY), Reflex=3.0 (~150 LY), "
                            "Stride=8.0 (~400 LY), Carom=8.5 (~425 LY). "
                            "If the shell states a jump range in LY, omit this and use jump_range_ly instead."
                        )
                    },
                    "jump_range_ly": {
                        "type": "number",
                        "description": (
                            "Ship jump range in LY at 0° ambient. Use this if the shell states their range directly. "
                            "The engine will derive the specific_heat from the stored hull profile. "
                            "Overrides specific_heat if both are provided."
                        )
                    },
                    "cargo_fuel": {
                        "type": "integer",
                        "description": (
                            "Units of fuel carried in the cargo hold (NOT the tank). "
                            "Cargo fuel adds both budget and mass. Tank fuel is massless. "
                            "Ask the shell if they have extra fuel in cargo on long routes."
                        )
                    },
                    "gate_only": {
                        "type": "boolean",
                        "description": "If true, route through gates only (no direct jumps). Default false."
                    }
                },
                "required": ["destination"]
            },
            handler=self._tool_plan_route
        )

        # --- Watcher Tools ---
        self.register_tool(
            name="manage_watcher",
            category="watcher",
            description=(
                "Manage SSU inventory watch rules for the current shell. "
                "Use action='list' to see current rules, action='add' to create a new rule "
                "(requires ssu_id in 0x... format; optional ssu_name, item_filter, threshold, scope), "
                "action='remove' to delete a rule by rule_id. "
                "Use this when the shell asks to watch, monitor, or track an SSU's inventory, "
                "or to list or remove existing watch rules."
            ),
            input_schema={
                "type": "object",
                "properties": {
                    "action": {
                        "type": "string",
                        "enum": ["list", "add", "remove"],
                        "description": "list — show rules; add — create rule; remove — delete rule"
                    },
                    "ssu_id": {
                        "type": "string",
                        "description": "Sui object ID of the SSU to watch (0x...). Required for action=add."
                    },
                    "ssu_name": {
                        "type": "string",
                        "description": "Human-readable name for the SSU (optional, for display)"
                    },
                    "item_filter": {
                        "type": "string",
                        "description": "Item name substring to watch (e.g. 'Tritanium'). None = watch total item count."
                    },
                    "threshold": {
                        "type": "integer",
                        "description": "Alert when count drops below this number. Default 0."
                    },
                    "scope": {
                        "type": "string",
                        "enum": ["personal", "tribe", "all"],
                        "description": "Who can see this rule. Default: personal."
                    },
                    "rule_id": {
                        "type": "string",
                        "description": "Rule ID (or prefix) to remove. Required for action=remove."
                    },
                },
                "required": ["action"]
            },
            handler=self._tool_manage_watcher,
            default_enabled=False,
        )

        # --- Courier Tools ---
        self.register_tool(
            name="manage_courier",
            category="courier",
            description=(
                "Manage courier contracts on the shared contract board. "
                "Use action='list' to see open contracts, action='post' to create a new contract "
                "(requires item_description, from_location, to_location, reward_description), "
                "action='claim' to claim a contract by contract_id. "
                "Use this when the shell asks to post a job, find courier work, "
                "claim a delivery, or check the contract board."
            ),
            input_schema={
                "type": "object",
                "properties": {
                    "action": {
                        "type": "string",
                        "enum": ["list", "post", "claim"],
                        "description": "list — show open contracts; post — create contract; claim — claim by ID"
                    },
                    "item_description": {
                        "type": "string",
                        "description": "What needs to be transported (e.g. '200x Tritanium'). Required for action=post."
                    },
                    "from_location": {
                        "type": "string",
                        "description": "Pickup location (system or SSU name). Required for action=post."
                    },
                    "to_location": {
                        "type": "string",
                        "description": "Destination (system or SSU name). Required for action=post."
                    },
                    "reward_description": {
                        "type": "string",
                        "description": "Reward offered (e.g. '500 ISK equivalent'). Required for action=post."
                    },
                    "expires_at": {
                        "type": "string",
                        "description": "Optional expiry timestamp (ISO 8601). Leave blank for no expiry."
                    },
                    "contract_id": {
                        "type": "string",
                        "description": "Contract ID (or prefix) to claim. Required for action=claim."
                    },
                },
                "required": ["action"]
            },
            handler=self._tool_manage_courier,
            default_enabled=False,
        )

        # --- Tribe Tools ---
        self.register_tool(
            name="manage_tribe",
            category="tribe",
            description=(
                "Check the tribe presence board. "
                "Use action='list' to show online tribe members (requires tribe_id). "
                "Use this when the shell asks who is online, where their tribe mates are, "
                "or what tribe members are active."
            ),
            input_schema={
                "type": "object",
                "properties": {
                    "action": {
                        "type": "string",
                        "enum": ["list"],
                        "description": "Action to perform. Currently: list"
                    },
                    "tribe_id": {
                        "type": "integer",
                        "description": "Tribe ID to query. Required for list."
                    },
                },
                "required": ["action"]
            },
            handler=self._tool_manage_tribe,
            default_enabled=False,
        )

        # --- Intel Tools ---
        self.register_tool(
            name="log_intel",
            category="intel",
            description=(
                "Record a fact that a pilot has reported from outside this structure's sensor range. "
                "Use this when a shell reports enemy behavior, resource locations, crafting knowledge, "
                "hazards, lore discoveries, or any other factual intelligence gathered in the field. "
                "Do not log speculation — only log what the pilot claims to have directly observed or verified. "
                "The entry persists and will be available to future shells who ask about the same topic."
            ),
            input_schema={
                "type": "object",
                "properties": {
                    "content": {
                        "type": "string",
                        "description": "The fact or observation to record, in plain terms. Max 500 chars."
                    },
                    "tags": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Topic tags to aid retrieval. E.g. ['drones', 'UTR-SN4', 'combat']"
                    },
                },
                "required": ["content"]
            },
            handler=self._tool_log_intel
        )

        self.register_tool(
            name="query_intel",
            category="intel",
            description=(
                "Search field intelligence logged by pilots who have visited this structure. "
                "Use this when a shell asks what is known about enemies, resources, hazards, crafting, "
                "or any topic that other pilots may have reported. Always query before saying you have no data."
            ),
            input_schema={
                "type": "object",
                "properties": {
                    "keyword": {
                        "type": "string",
                        "description": "Search term. E.g. 'drones', 'fuel', 'Faulty Scout', 'minerals'"
                    },
                },
                "required": ["keyword"]
            },
            handler=self._tool_query_intel
        )

        self.register_tool(
            name="lookup_item_type",
            category="intel",
            description=(
                "Look up an item, ship, structure, material, or enemy type by name. "
                "Returns official description, category, group, mass, and volume from the game database. "
                "Use this when a shell mentions an unfamiliar item name, enemy designation, or ship class "
                "and you need to identify what it is. Search partial names — e.g. 'Faulty Scout', 'Triglavian', "
                "'Tritanium', 'Smart Storage'. Returns up to 5 matches ranked by relevance."
            ),
            input_schema={
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "Name or partial name to search. Case-insensitive."
                    },
                },
                "required": ["query"]
            },
            handler=self._tool_lookup_item_type
        )

        self.register_tool(
            name="record_field_observation",
            category="intel",
            description=(
                "Record enemy types or ore types found in a specific solar system. "
                "Call this when a pilot explicitly reports what enemies or ores they encountered "
                "in a named system. This writes to the global knowledge graph shared across all "
                "pilots and all time. Use log_intel for unstructured notes instead."
            ),
            input_schema={
                "type": "object",
                "properties": {
                    "system_name": {
                        "type": "string",
                        "description": "Exact solar system name where the sighting occurred.",
                    },
                    "enemies": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Enemy or NPC names encountered in the system.",
                    },
                    "ores": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Ore types found in the system.",
                    },
                },
                "required": ["system_name"],
            },
            handler=self._tool_record_field_observation,
        )

        self.register_tool(
            name="query_system_knowledge",
            category="intel",
            description=(
                "Query the global knowledge graph for what is known about a solar system — "
                "confirmed enemy types and ore types reported by all pilots across all time. "
                "Call this before saying a system has no known data."
            ),
            input_schema={
                "type": "object",
                "properties": {
                    "system_name": {
                        "type": "string",
                        "description": "Solar system name to query.",
                    },
                },
                "required": ["system_name"],
            },
            handler=self._tool_query_system_knowledge,
        )

        # --- Build Tools ---
        self.register_tool(
            name="calculate_build_options",
            category="build",
            description=(
                "Calculate what structures the pilot can build with their current inventory. "
                "Returns buildable structures, shortfalls for nearly-buildable ones, and "
                "NetworkNode/L-point status. Use when the pilot asks about building, crafting, "
                "upgrading, 'what next', 'what can I build', or construction."
            ),
            input_schema={
                "type": "object",
                "properties": {
                    "target": {
                        "type": "string",
                        "description": (
                            "Optional: specific structure name to check (e.g. 'Smart Gate', 'Assembler'). "
                            "If omitted, returns a full assessment of all buildable options."
                        )
                    }
                },
                "required": []
            },
            handler=self._tool_calculate_build_options
        )

        # --- Recon Tool ---
        self.register_tool(
            name="recon_scan",
            category="spatial",
            description="Full area intelligence scan combining spatial search and threat assessment.",
            input_schema={
                "type": "object",
                "properties": {
                    "center_system": {
                        "type": "string",
                        "description": "Center system name. Defaults to current system.",
                    },
                    "radius_ly": {
                        "type": "number",
                        "default": 100.0,
                        "description": "Search radius in light-years.",
                    },
                },
                "required": [],
            },
            handler=self._tool_recon_scan,
        )

        # --- Info Tools (future) ---
        # self.register_tool(
        #     name="get_pilot_history",
        #     category="info",
        #     description="Get pilot's visit history and reputation",
        #     ...
        # )

    def register_tool(
        self,
        name: str,
        category: str,
        description: str,
        input_schema: Dict[str, Any],
        handler: callable,
        default_enabled: bool = True,
    ):
        """Register a new tool."""
        self.tools[name] = {
            "name": name,
            "category": category,
            "description": description,
            "input_schema": input_schema,
            "handler": handler,
            "default_enabled": default_enabled,
        }
        log.debug(f"Registered tool: {name} ({category})")

    def get_tools_for_claude(self, disabled: Optional[List[str]] = None) -> List[Dict[str, Any]]:
        """
        Get tools formatted for Claude API tool_use.

        Descriptions are loaded live from prompts/tools.md on each call so edits
        to that file take effect on server restart without any code changes.
        Falls back to the hardcoded description if a tool section is absent.

        Args:
            disabled: Optional list of tool names to exclude.

        Returns list of tool definitions (without handlers).
        """
        from src.prompt_loader import load_tool_prompts
        live = load_tool_prompts()

        exclude = set(disabled or [])
        result = []
        for tool in self.tools.values():
            if tool["name"] in exclude:
                continue
            desc = (live.get(tool["name"], {}).get("description") or "").strip()
            if not desc:
                desc = tool["description"]  # fallback to hardcoded
            result.append({
                "name": tool["name"],
                "description": desc,
                "input_schema": tool["input_schema"],
            })
        return result

    async def execute_tool(self, name: str, input_dict: Dict[str, Any], context: Dict[str, Any] = None) -> Optional[str]:
        """Execute a tool and return plain text result (backward compatible)."""
        result = await self.execute_tool_structured(name, input_dict, context)
        if isinstance(result, dict):
            return result.get("text", "")
        return str(result) if result is not None else ""

    async def execute_tool_structured(self, name: str, input_dict: Dict[str, Any], context: Dict[str, Any] = None) -> Dict[str, Any]:
        """
        Execute a tool and return {text, structured} dict.

        Args:
            name: Tool name
            input_dict: Input parameters
            context: Optional context dict with system_id, structure_id, character_id, character_address

        Returns:
            {"text": str, "structured": Optional[dict]} where structured matches the
            corresponding TypeScript panel interface (SystemIntelData, ThreatAssessmentData, etc.)
        """
        if name not in self.tools:
            return {"text": f"Error: Tool '{name}' not found", "structured": None}

        tool = self.tools[name]
        try:
            handler = tool["handler"]
            import inspect
            timeout_seconds = 5.0

            if inspect.iscoroutinefunction(handler):
                raw = await asyncio.wait_for(
                    handler(input_dict, context),
                    timeout=timeout_seconds
                )
            else:
                raw = await asyncio.wait_for(
                    asyncio.to_thread(handler, input_dict, context),
                    timeout=timeout_seconds
                )

            if isinstance(raw, dict) and "text" in raw:
                return raw
            # Legacy handler returning plain string
            return {"text": str(raw) if raw is not None else "", "structured": None}
        except asyncio.TimeoutError:
            log.warning(f"Tool execution timed out: {name}")
            return {"text": f"[Tool {name}: timed out after 5s]", "structured": None}
        except Exception as e:
            log.warning(f"Tool execution failed: {name}: {e}")
            return {"text": f"[Tool {name}: unavailable]", "structured": None}

    # ---- Tool Handlers (implementations) ----

    def _tool_search_memory(self, inputs: Dict[str, Any], context: Dict[str, Any] = None) -> Dict[str, Any]:
        """Handler for search_memory tool. Structure AI only."""
        if not context or not context.get("structure_id"):
            return {"text": "[search_memory requires structure_id in context]", "structured": None}

        keyword = inputs.get("keyword", "").strip()
        days = inputs.get("days", 7)

        if not keyword:
            return {"text": "[search_memory requires keyword parameter]", "structured": None}

        try:
            from src.memory_store import get_memory_store
            store = get_memory_store(context["structure_id"])
            events = store.search_events(keyword, days)

            if not events:
                return {
                    "text": f"No events matching '{keyword}' in last {days} days",
                    "structured": {"query": keyword, "results": []},
                }

            lines = [f"Events matching '{keyword}' (last {days} days):"]
            result_items = []
            for event in events[:10]:
                ts = event.get("ts", "")[:10]
                event_type = event.get("type", "unknown")
                data_summary = json.dumps(event.get("data", {}))[:60]
                item = f"{ts} {event_type}: {data_summary}"
                lines.append(f"  • {item}")
                result_items.append(item)

            return {
                "text": "\n".join(lines),
                "structured": {"query": keyword, "results": result_items},
            }
        except Exception as e:
            log.warning(f"search_memory failed: {e}")
            return {"text": f"[search_memory error: {type(e).__name__}]", "structured": None}

    def _tool_get_memory_summary(self, inputs: Dict[str, Any], context: Dict[str, Any] = None) -> Dict[str, Any]:
        """Handler for get_memory_summary tool. Structure AI only."""
        if not context or not context.get("structure_id"):
            return {"text": "[get_memory_summary requires structure_id in context]", "structured": None}

        try:
            import re
            from src.memory_store import get_memory_store
            store = get_memory_store(context["structure_id"])
            summary = store.get_summary()

            text = (summary.get("text", "") if summary else "") or "No recent activity summary available"

            docking_m = re.search(r'(\d+) dockings', text)
            kills_m = re.search(r'(\d+) kills', text)
            access_m = re.search(r'(\d+) access changes', text)

            return {
                "text": text,
                "structured": {
                    "attacks": kills_m.group(1) if kills_m else "0",
                    "contacts": access_m.group(1) if access_m else "0",
                    "docking": docking_m.group(1) if docking_m else "0",
                },
            }
        except Exception as e:
            log.warning(f"get_memory_summary failed: {e}")
            return {"text": f"[get_memory_summary error: {type(e).__name__}]", "structured": None}

    async def _tool_assess_threat(self, inputs: Dict[str, Any], context: Dict[str, Any] = None) -> Dict[str, Any]:
        """Handler for assess_threat tool. General threat analysis."""
        try:
            from datetime import datetime, timezone, timedelta
            from src.world_api import world_api
            from src.threat_assessment import threat_assessment
            from src.memory_store import get_memory_store

            system_id = inputs.get("system_id") or (context.get("system_id") if context else None)
            hours_lookback = inputs.get("hours_lookback", 24)
            ship_class = inputs.get("ship_class")

            if not system_id:
                return {"text": "[assess_threat requires system_id in input or context]", "structured": None}

            from src.blockchain_killmails import load_killmails_for_system
            killmails = load_killmails_for_system(system_id)
            if not killmails:
                killmails = await world_api.get_killmails(system_id)

            memory_events = []
            if context and context.get("structure_id"):
                try:
                    store = get_memory_store(context["structure_id"])
                    events_path = os.path.join(store._root(), "events.jsonl")
                    if os.path.exists(events_path):
                        with open(events_path) as f:
                            for line in f:
                                try:
                                    memory_events.append(json.loads(line.strip()))
                                except:
                                    pass
                except:
                    pass

            threat_context = threat_assessment.assess_ship_threat(
                killmails,
                ship_class or "unknown",
                memory_events,
                hours_lookback=hours_lookback
            )
            from src.prompt_loader import load_tool_prompts
            _no_result = load_tool_prompts().get("assess_threat", {}).get("no_result", "")
            text = threat_context or _no_result or "No significant threat activity detected"

            # Build structured data for ThreatAssessmentData panel
            now = datetime.now(timezone.utc)
            cutoff = now - timedelta(hours=hours_lookback)
            recent = []
            for km in (killmails or []):
                ts_str = km.get("timestamp", "")
                try:
                    ts = datetime.fromisoformat(ts_str.replace("Z", "+00:00"))
                    if ts >= cutoff:
                        recent.append(km)
                except ValueError:
                    pass

            kill_count = len(recent)
            level = "HIGH" if kill_count > 5 else "MEDIUM" if kill_count > 2 else "LOW" if kill_count > 0 else "NONE"

            aggressors: Dict[str, int] = {}
            victim_classes: Dict[str, int] = {}
            for km in recent:
                corp = km.get("attacker_corp") or km.get("primary_attacker", "Unknown")
                aggressors[corp] = aggressors.get(corp, 0) + 1
                ship = km.get("victim_ship_class", "unknown")
                victim_classes[ship] = victim_classes.get(ship, 0) + 1

            top_aggressor = max(aggressors, key=aggressors.get) if aggressors else "none"
            dominant_ship = max(victim_classes, key=victim_classes.get) if victim_classes else "none"
            escalation = threat_assessment._assess_escalation(recent, memory_events)

            return {
                "text": text,
                "structured": {
                    "level": level,
                    "topAggressor": top_aggressor,
                    "dominantShip": dominant_ship,
                    "escalation": escalation,
                },
            }
        except Exception as e:
            log.warning(f"assess_threat failed: {e}")
            return {"text": f"[assess_threat error: {type(e).__name__}]", "structured": None}

    async def _tool_get_system_intel(self, inputs: Dict[str, Any], context: Dict[str, Any] = None) -> Dict[str, Any]:
        """Handler for get_system_intel tool."""
        try:
            from src.world_api import world_api
            from src.galaxy_db import galaxy_db

            system_id = inputs.get("system_id") or (context.get("system_id") if context else None)
            if not system_id:
                from src.prompt_loader import load_tool_prompts
                _no_system = load_tool_prompts().get("get_system_intel", {}).get("no_system", "[get_system_intel: system not set]")
                return {"text": _no_system, "structured": None}

            system_name = None
            system_info = None
            try:
                system_info = galaxy_db.get_system(system_id)
                if system_info:
                    system_name = system_info.get("name")
            except:
                pass

            if not system_name:
                system_name = f"System {system_id}"

            if not system_info:
                return {"text": f"[No data for system {system_id}]", "structured": None}

            system = await world_api.get_system(system_name)
            from src.blockchain_killmails import load_killmails_for_system
            killmails = load_killmails_for_system(system_id) or await world_api.get_killmails(system_id)

            security = system.get("security", "Unknown") if system else "Unknown"
            gate_links = len(system.get("gateLinks", [])) if system else 0
            kill_count = len(killmails) if killmails else 0

            # Star class, planets, and Lagrange points come from galaxy_db
            from src.structure_client import _spectral_label, _count_planets
            star_type = "Unknown"
            planets_summary = "0"
            lagrange_count = 0
            hz_planet_count = 0
            if system_info:
                star_type = _spectral_label(system_info.get("star_spectral_class"))
                celestials = galaxy_db.get_celestials_in_system(system_id)
                planets_list = celestials.get("planets", [])
                lagrange_count = len(celestials.get("lagrange_points", []))

                # Split planets into HZ and non-HZ
                hz_inner = system_info.get("habitable_zone_inner") or 0
                hz_outer = system_info.get("habitable_zone_outer") or 0
                hz_planets = []
                outer_planets = []
                for p in planets_list:
                    orbit = p.get("orbitRadius") or 0
                    if hz_inner and hz_outer and hz_inner <= orbit <= hz_outer:
                        hz_planets.append(p)
                    else:
                        outer_planets.append(p)
                hz_planet_count = len(hz_planets)

                total_planets = len(planets_list)
                hz_counts = _count_planets(hz_planets)
                outer_counts = _count_planets(outer_planets)

                parts = []
                if hz_counts:
                    hz_str = ", ".join(f"{v}x {k}" for k, v in hz_counts.items())
                    parts.append(f"{hz_planet_count} in HZ ({hz_str})")
                if outer_counts:
                    outer_str = ", ".join(f"{v}x {k}" for k, v in outer_counts.items())
                    parts.append(outer_str)

                if parts:
                    planets_summary = f"{total_planets} total — " + " | ".join(parts)
                else:
                    planets_summary = str(total_planets)

            # Jump temperature from galaxy_db
            min_temp = "N/A"
            if system_info:
                temp = system_info.get("safe_jump_temp")
                if temp is not None:
                    min_temp = str(temp)

            intel_parts = [
                f"System: {system_name}",
                f"Security: {security}",
                f"Star: {star_type}",
                f"Planets: {planets_summary}",
                f"Lagrange: {lagrange_count}",
                f"Gates: {gate_links}",
                f"Kills (24h): {kill_count}",
            ]

            return {
                "text": " | ".join(intel_parts),
                "structured": {
                    "systemId": system_id,
                    "system": system_name,
                    "starClass": star_type,
                    "minTemp": min_temp,
                    "planets": planets_summary,
                    "lagrangePoints": str(lagrange_count),
                    "hzPlanets": str(hz_planet_count),
                    "kills24h": str(kill_count),
                    "gates": str(gate_links),
                },
            }
        except Exception as e:
            log.warning(f"get_system_intel failed: {e}")
            return {"text": f"[get_system_intel error: {type(e).__name__}]", "structured": None}

    def _tool_get_pilot_profile(self, inputs: Dict[str, Any], context: Dict[str, Any] = None) -> Dict[str, Any]:
        """Handler for get_pilot_profile tool. Structure AI only."""
        if not context or not context.get("structure_id"):
            return {"text": "[get_pilot_profile requires structure_id in context]", "structured": None}

        pilot_address = inputs.get("pilot_address") or (context.get("character_address") if context else None)

        if not pilot_address:
            return {"text": "[get_pilot_profile requires pilot_address in input or context]", "structured": None}

        try:
            from src.memory_store import get_memory_store
            store = get_memory_store(context["structure_id"])
            pilot = store.get_pilot(pilot_address)

            if not pilot:
                return {"text": f"No profile for pilot {pilot_address[:6]}...", "structured": None}

            profile_parts = [
                f"Pilot: {pilot.get('character_name', 'Unknown')}",
                f"Visits: {pilot.get('visit_count', 0)}",
                f"First: {pilot.get('first_seen', 'unknown')[:10]}",
                f"Last: {pilot.get('last_seen', 'unknown')[:10]}",
                f"Tier: {pilot.get('tier', 'NONE')}",
            ]

            return {
                "text": " | ".join(profile_parts),
                "structured": {
                    "visits": str(pilot.get("visit_count", 0)),
                    "firstVisit": pilot.get("first_seen", "unknown")[:10],
                    "lastVisit": pilot.get("last_seen", "unknown")[:10],
                    "tier": pilot.get("tier", "NONE"),
                },
            }
        except Exception as e:
            log.warning(f"get_pilot_profile failed: {e}")
            return {"text": f"[get_pilot_profile error: {type(e).__name__}]", "structured": None}

    async def _tool_radius_search(self, inputs: Dict[str, Any], context: Dict[str, Any] = None) -> Dict[str, Any]:
        """Handler for radius_search tool."""
        try:
            radius_search = _get_radius_search()

            center_system = inputs.get("center_system") or (context.get("system_name") if context else None)
            radius_ly = inputs.get("radius_ly", 100.0)
            filters = inputs.get("filters", ["planets"])
            top_n = inputs.get("top_n", 10)
            killmail_hours = inputs.get("killmail_hours", 24)
            skip_heat_traps = inputs.get("skip_heat_traps", False)

            if not center_system:
                from src.prompt_loader import load_tool_prompts
                _no_system = load_tool_prompts().get("radius_search", {}).get("no_system", "[radius_search: system not set]")
                return {"text": _no_system, "structured": None}

            if radius_ly <= 0:
                return {"text": "[radius_ly must be > 0]", "structured": None}

            result = await radius_search.search(
                center_system=center_system,
                radius_ly=radius_ly,
                filters=filters,
                killmail_hours=killmail_hours,
                top_n=top_n,
                skip_heat_traps=skip_heat_traps,
            )

            return {
                "text": self._format_radius_search_result(result, center_system, radius_ly, filters),
                "structured": None,  # No visual panel type for radius_search
            }

        except Exception as e:
            log.warning(f"radius_search failed: {e}")
            return {"text": f"[radius_search error: {type(e).__name__}: {str(e)[:100]}]", "structured": None}

    def _format_radius_search_result(self, result: Dict[str, Any], center_system: str, radius_ly: float, filters: List[str]) -> str:
        """Format radius search result for Claude readability."""
        lines = []

        total = result.get("total_systems", 0)
        lines.append(f"SCANNED: {center_system} ± {radius_ly} LY | {total} systems found")

        if total == 0:
            return "\n".join(lines) + "\n(No systems in range)"

        filter_data = result.get("filters", {})

        # Format each filter
        if "planets" in filters and "planets" in filter_data:
            planets_data = filter_data["planets"]
            systems = planets_data.get("systems", [])
            if systems:
                lines.append("\nPLANETS (highest first):")
                for sys in systems[:10]:
                    name = sys.get("name", "Unknown")
                    planets = sys.get("planets", 0)
                    distance = sys.get("distance_ly", 0)
                    temp = sys.get("safe_jump_temp", 0)
                    heat_class = "hot" if temp >= 90 else "warm" if temp >= 70 else "cool"
                    lines.append(f"  • {name} — {planets} planets, {distance:.1f} LY, {heat_class}")

        if "killmails" in filters and "killmails" in filter_data:
            killmail_data = filter_data["killmails"]
            systems = killmail_data.get("systems", [])
            if systems:
                lines.append("\nKILLMAILS (most danger):")
                for sys in systems[:10]:
                    name = sys.get("name", "Unknown")
                    kills = sys.get("kills", 0)
                    distance = sys.get("distance_ly", 0)
                    hours_ago = sys.get("most_recent_kill_hours_ago")
                    time_str = f", {hours_ago:.1f}h ago" if hours_ago else ""
                    lines.append(f"  • {name} — {kills} kills in 24h{time_str}, {distance:.1f} LY")

        if "heat" in filters and "heat" in filter_data:
            heat_data = filter_data["heat"]
            systems = heat_data.get("systems", [])
            if systems:
                lines.append("\nHEAT TRAPS (highest jump temp):")
                for sys in systems[:10]:
                    name = sys.get("name", "Unknown")
                    temp = sys.get("safe_jump_temp", 0)
                    distance = sys.get("distance_ly", 0)
                    heat_class = sys.get("heat_class", "unknown")
                    lines.append(f"  • {name} — {temp}°, {distance:.1f} LY, {heat_class}")

        if "structures" in filters and "structures" in filter_data:
            struct_data = filter_data["structures"]
            systems = struct_data.get("systems", [])
            if systems:
                lines.append("\nSTRUCTURES (closest):")
                for sys in systems[:10]:
                    name = sys.get("name", "Unknown")
                    structures = sys.get("structures", [])
                    distance = sys.get("distance_ly", 0)
                    struct_count = len(structures)
                    lines.append(f"  • {name} — {struct_count} base{'s' if struct_count != 1 else ''}, {distance:.1f} LY")

        return "\n".join(lines)

    async def _tool_recon_scan(self, inputs: Dict[str, Any], context: Dict[str, Any] = None) -> Dict[str, Any]:
        """Handler for recon_scan tool — aggregates radius_search + assess_threat in one call."""
        center = inputs.get("center_system") or ((context or {}).get("system_name", ""))
        radius = inputs.get("radius_ly", 100.0)
        try:
            radius_result, threat_result = await asyncio.gather(
                self._tool_radius_search(
                    {
                        "center_system": center,
                        "radius_ly": radius,
                        "filters": ["killmails", "planets", "structures"],
                        "killmail_hours": 24,
                    },
                    context,
                ),
                self._tool_assess_threat({"hours_lookback": 24}, context),
            )
            combined = (
                f"=== AREA SCAN: {center} / {radius} LY ===\n"
                f"{radius_result.get('text', '')}\n\n"
                f"=== THREAT: {center} ===\n"
                f"{threat_result.get('text', '')}"
            )
            return {"text": combined, "structured": threat_result.get("structured")}
        except Exception as e:
            log.warning(f"recon_scan failed: {e}")
            return {"text": f"[recon_scan error: {type(e).__name__}]", "structured": None}

    async def _tool_plan_route(self, inputs: Dict[str, Any], context: Dict[str, Any] = None) -> Dict[str, Any]:
        """Handler for plan_route tool."""
        try:
            from src.route_engine import route_engine
            from src.ship_profile import load_profile, ShipProfile, T_MAX, HEAT_CONSTANT, FUEL_PROPERTIES, SHIPS

            destination = inputs.get("destination", "").strip()
            if not destination:
                return {"text": "[plan_route requires a destination]", "structured": None}

            # Determine origin from context
            origin = inputs.get("origin", "").strip()
            if not origin and context:
                origin = (context.get("system_name") or context.get("current_system") or "").strip()
            if not origin:
                from src.prompt_loader import load_tool_prompts
                _no_system = load_tool_prompts().get("plan_route", {}).get("no_system", "[plan_route: system not set]")
                return {"text": _no_system, "structured": None}

            if not route_engine.ready():
                return {"text": "[plan_route: route engine not ready — systems.json missing]", "structured": None}

            # Build profile — prefer explicit parameters over stored
            base_profile = load_profile()

            # Enrich from catalog — session only stores fuel/quantity, not hull physics
            if base_profile.ship_type and base_profile.ship_type in SHIPS:
                _cat = SHIPS[base_profile.ship_type]
                base_profile = base_profile.with_overrides(
                    hull_mass=_cat.get("mass"),
                    specific_heat=_cat.get("specific_heat"),
                )

            jump_range_ly = inputs.get("jump_range_ly")
            specific_heat = inputs.get("specific_heat")
            cargo_fuel    = int(inputs.get("cargo_fuel") or 0)

            if jump_range_ly and jump_range_ly > 0:
                qf       = base_profile.quality_factor()
                cur_mass = base_profile.hull_mass + base_profile.extra_cargo_kg
                c_eff    = jump_range_ly * HEAT_CONSTANT * cur_mass / (qf * T_MAX * base_profile.hull_mass)
                specific_heat = c_eff / (1.0 + base_profile.adaptive_level * 0.02)

            # Cargo fuel adds mass; tank fuel does not
            fuel_type     = base_profile.fuel_type
            fuel_mass_kg  = FUEL_PROPERTIES.get(fuel_type, {}).get("mass_kg", 0)
            cargo_mass_kg = cargo_fuel * fuel_mass_kg
            total_fuel    = base_profile.fuel_quantity + cargo_fuel

            profile = base_profile.with_overrides(
                specific_heat=specific_heat,
                fuel_quantity=total_fuel,
                extra_cargo_kg=base_profile.extra_cargo_kg + cargo_mass_kg,
            )

            gate_only = inputs.get("gate_only", False)
            if gate_only:
                result = route_engine.bfs(origin, destination)
                if result is None:
                    result = route_engine._no_route(destination, profile,
                                                    route_engine.resolve(origin),
                                                    route_engine.resolve(destination))
            else:
                result = route_engine.route(origin, destination, profile)

            if result["type"] == "no_route":
                warning_text = " ".join(result.get("warnings", [f"No route to {destination}."]))
                return {"text": warning_text, "structured": None}

            # Build text summary for Claude's response
            jumps = result["jumps"]
            total_ly = result["total_ly"]
            gate_count = result["jump_types"].count("gate") if result.get("jump_types") else 0
            direct_count = result["jump_types"].count("direct") if result.get("jump_types") else 0
            warnings = result.get("warnings", [])

            parts = [f"Route: {origin} → {destination} | {jumps} jumps"]
            if total_ly > 0:
                parts.append(f"{total_ly:.1f} LY direct")
            if gate_count and direct_count:
                parts.append(f"({gate_count} gate, {direct_count} ship jump{'s' if direct_count != 1 else ''})")
            elif gate_count:
                parts.append(f"({gate_count} gate jumps)")
            elif direct_count:
                parts.append(f"({direct_count} ship jump{'s' if direct_count != 1 else ''})")
            if warnings:
                parts.append("| " + " | ".join(warnings))

            return {
                "text": " | ".join(parts),
                "structured": result,
            }

        except Exception as e:
            log.warning(f"plan_route failed: {e}", exc_info=True)
            return {"text": f"[plan_route error: {type(e).__name__}: {e}]", "structured": None}

    async def _tool_manage_watcher(self, inputs: Dict[str, Any], context: Dict[str, Any] = None) -> Dict[str, Any]:
        """Handler for manage_watcher tool."""
        import re
        import uuid as _uuid

        wallet = (context or {}).get("character_address", "").strip()
        if not wallet:
            return {"text": "[manage_watcher: no character_address in context]", "structured": None}

        action = inputs.get("action", "list")

        from src.session_store import load_session, save_session
        session = load_session(wallet)
        if session is None:
            return {"text": "No session found for this shell.", "structured": None}

        if action == "list":
            rules = [r for r in session.watch_list if r.get("active")]
            if not rules:
                return {"text": "No active watch rules.", "structured": {"rules": []}}
            lines = [f"Active watch rules ({len(rules)}):"]
            for r in rules:
                filt = f" item={r['item_filter']!r}" if r.get("item_filter") else " all items"
                name = r.get("ssu_name") or r["ssu_id"][:16]
                lines.append(f"  {r['id'][:8]}  {name}{filt}  threshold={r.get('threshold', 0)}")
            return {"text": "\n".join(lines), "structured": {"rules": rules}}

        elif action == "add":
            ssu_id = inputs.get("ssu_id", "").strip()
            if not ssu_id or not re.match(r"^0x[0-9a-fA-F]{1,64}$", ssu_id):
                return {"text": "ssu_id is required and must be in 0x... format.", "structured": None}
            rule = {
                "id": str(_uuid.uuid4()),
                "wallet_address": wallet,
                "ssu_id": ssu_id,
                "ssu_name": inputs.get("ssu_name"),
                "item_filter": inputs.get("item_filter"),
                "threshold": int(inputs.get("threshold") or 0),
                "scope": inputs.get("scope", "personal"),
                "last_checked": None,
                "last_alert": None,
                "active": True,
            }
            session.watch_list.append(rule)
            save_session(session)
            name = rule.get("ssu_name") or ssu_id[:16]
            filt = f" item={rule['item_filter']!r}" if rule.get("item_filter") else ""
            return {
                "text": f"Watch rule added for {name}{filt}, threshold={rule['threshold']}. Rule ID: {rule['id'][:8]}",
                "structured": {"rule": rule},
            }

        elif action == "remove":
            rule_id = inputs.get("rule_id", "").strip()
            if not rule_id:
                return {"text": "rule_id is required for action=remove.", "structured": None}
            before = len(session.watch_list)
            session.watch_list = [r for r in session.watch_list if r.get("id") != rule_id]
            if len(session.watch_list) == before:
                # Try prefix match
                matches = [r for r in session.watch_list if r.get("id", "").startswith(rule_id)]
                if len(matches) == 1:
                    full_id = matches[0]["id"]
                    session.watch_list = [r for r in session.watch_list if r.get("id") != full_id]
                    rule_id = full_id
                else:
                    return {"text": f"Rule not found: {rule_id}", "structured": None}
            save_session(session)
            return {"text": f"Watch rule removed: {rule_id[:8]}", "structured": {"deleted": rule_id}}

        return {"text": f"Unknown action: {action!r}. Use list, add, or remove.", "structured": None}

    async def _tool_manage_courier(self, inputs: Dict[str, Any], context: Dict[str, Any] = None) -> Dict[str, Any]:
        """Handler for manage_courier tool."""
        from dataclasses import asdict

        wallet = (context or {}).get("character_address", "").strip()
        action = inputs.get("action", "list")

        from src.courier_store import load_contracts, create_contract, claim_contract

        if action == "list":
            contracts = load_contracts()
            active = [c for c in contracts if c.status in ("open", "claimed", "in_transit")]
            if not active:
                return {"text": "No active courier contracts on the board.", "structured": {"contracts": []}}
            lines = [f"Courier contracts ({len(active)}):"]
            for c in active:
                reward = c.reward_description
                lines.append(
                    f"  {c.id[:8]}  [{c.status.upper()}]  {c.item_description}  "
                    f"{c.from_location} → {c.to_location}  reward: {reward}  posted by {c.poster_name}"
                )
            return {"text": "\n".join(lines), "structured": {"contracts": [asdict(c) for c in active]}}

        elif action == "post":
            if not wallet:
                return {"text": "[manage_courier: no character_address in context]", "structured": None}
            from src.session_store import load_session
            session = load_session(wallet)
            if session is None:
                return {"text": "No session found for this shell.", "structured": None}
            for field in ("item_description", "from_location", "to_location", "reward_description"):
                if not inputs.get(field, "").strip():
                    return {"text": f"{field} is required for action=post.", "structured": None}
            contract = create_contract(
                poster_wallet=wallet,
                poster_name=session.character_name,
                item_description=inputs["item_description"].strip(),
                from_location=inputs["from_location"].strip(),
                to_location=inputs["to_location"].strip(),
                reward_description=inputs["reward_description"].strip(),
                expires_at=inputs.get("expires_at"),
            )
            return {
                "text": (
                    f"Contract posted. ID: {contract.id[:8]}  "
                    f"{contract.item_description}  {contract.from_location} → {contract.to_location}  "
                    f"reward: {contract.reward_description}"
                ),
                "structured": {"contract": asdict(contract)},
            }

        elif action == "claim":
            if not wallet:
                return {"text": "[manage_courier: no character_address in context]", "structured": None}
            from src.session_store import load_session
            session = load_session(wallet)
            if session is None:
                return {"text": "No session found for this shell.", "structured": None}
            contract_id = inputs.get("contract_id", "").strip()
            if not contract_id:
                return {"text": "contract_id is required for action=claim.", "structured": None}
            # Support prefix match
            if len(contract_id) < 36:
                contracts = load_contracts()
                matches = [c for c in contracts if c.id.startswith(contract_id) and c.status == "open"]
                if len(matches) == 0:
                    return {"text": f"No open contract found matching: {contract_id}", "structured": None}
                if len(matches) > 1:
                    return {"text": f"Ambiguous prefix '{contract_id}' matches {len(matches)} contracts.", "structured": None}
                contract_id = matches[0].id
            try:
                contract = claim_contract(contract_id, wallet, session.character_name)
            except ValueError as e:
                return {"text": str(e), "structured": None}
            return {
                "text": (
                    f"Contract claimed: {contract.id[:8]}  "
                    f"{contract.item_description}  {contract.from_location} → {contract.to_location}  "
                    f"reward: {contract.reward_description}  posted by {contract.poster_name}"
                ),
                "structured": {"contract": asdict(contract)},
            }

        return {"text": f"Unknown action: {action!r}. Use list, post, or claim.", "structured": None}

    async def _tool_manage_tribe(self, inputs: Dict[str, Any], context: Dict[str, Any] = None) -> Dict[str, Any]:
        """Handler for manage_tribe tool."""
        from src.tribe_board import get_presence

        action = inputs.get("action", "list")
        tribe_id = inputs.get("tribe_id")

        if action == "list":
            if not tribe_id:
                return {"text": "tribe_id is required to list tribe presence.", "structured": None}
            try:
                tribe_id = int(tribe_id)
            except (TypeError, ValueError):
                return {"text": "tribe_id must be an integer.", "structured": None}

            members = get_presence(tribe_id)
            if not members:
                return {
                    "text": f"No tribe members currently online for tribe {tribe_id}.",
                    "structured": {"tribe_id": tribe_id, "online": 0, "members": []},
                }

            lines = [f"Tribe {tribe_id} — {len(members)} online:"]
            for m in members:
                lines.append(
                    f"  {m['character_name']}  [{m['status']}]  {m['location']}  "
                    f"last ping: {m['last_ping'][11:16]}z"
                )
            return {
                "text": "\n".join(lines),
                "structured": {"tribe_id": tribe_id, "online": len(members), "members": members},
            }

        return {"text": f"Unknown action: {action!r}. Use: list.", "structured": None}

    def _tool_log_intel(self, inputs: Dict[str, Any], context: Dict[str, Any] = None) -> Dict[str, Any]:
        """Handler for log_intel tool. Stores a pilot-reported fact in the intel store."""
        content = (inputs.get("content") or "").strip()
        if not content:
            return {"text": "No content provided.", "structured": None}

        tags = inputs.get("tags") or []
        structure_id = (context or {}).get("structure_id", "")
        pilot_name = (context or {}).get("pilot_name") or (context or {}).get("character_name") or ""

        if not structure_id:
            return {"text": "Intel store unavailable: no structure context.", "structured": None}

        try:
            from src.intel_store import get_intel_store
            store = get_intel_store(structure_id)
            entry = store.log_intel(content, reported_by=pilot_name, tags=tags)
            return {
                "text": f"Field report logged [{entry['id']}]: {content[:120]}",
                "structured": None,
            }
        except Exception as e:
            log.warning("_tool_log_intel failed: %s", e)
            return {"text": "Failed to log intel.", "structured": None}

    def _tool_query_intel(self, inputs: Dict[str, Any], context: Dict[str, Any] = None) -> Dict[str, Any]:
        """Handler for query_intel tool. Searches pilot-reported field intelligence."""
        keyword = (inputs.get("keyword") or "").strip()
        if not keyword:
            return {"text": "No keyword provided.", "structured": None}

        structure_id = (context or {}).get("structure_id", "")
        if not structure_id:
            return {"text": "Intel store unavailable: no structure context.", "structured": None}

        try:
            from src.intel_store import get_intel_store
            store = get_intel_store(structure_id)
            results = store.query_intel(keyword)
            if not results:
                from src.prompt_loader import load_tool_prompts
                _tmpl = (
                    load_tool_prompts().get("query_intel", {}).get("no_result")
                    or "No field reports found matching '{keyword}'. This unit has no logged intelligence on that topic."
                )
                return {"text": _tmpl.format(keyword=keyword), "structured": None}
            lines = [f"Field intelligence — '{keyword}' ({len(results)} report(s)):"]
            for r in results:
                by = r.get("reported_by", "unknown")
                at = r.get("reported_at", "")[:10]
                lines.append(f"  [{r['id']}] {at} | {by}: {r['content']}")
            return {"text": "\n".join(lines), "structured": None}
        except Exception as e:
            log.warning("_tool_query_intel failed: %s", e)
            return {"text": "Intel query failed.", "structured": None}

    def _tool_record_field_observation(self, inputs: Dict[str, Any], context: Dict[str, Any] = None) -> Dict[str, Any]:
        """Handler for record_field_observation tool. Writes enemy/ore sightings to the global knowledge graph."""
        system_name = (inputs.get("system_name") or "").strip()
        if not system_name:
            return {"text": "system_name is required.", "structured": None}

        enemies = inputs.get("enemies") or []
        ores = inputs.get("ores") or []

        if not enemies and not ores:
            return {"text": "No enemies or ores provided — nothing recorded.", "structured": None}

        pilot_name = (context or {}).get("pilot_name") or (context or {}).get("character_name") or ""

        try:
            from src import system_knowledge
            for name in enemies:
                if name and name.strip():
                    system_knowledge.record_sighting(system_name, "enemy", name.strip(), "ai_tool", pilot_name or None)
            for name in ores:
                if name and name.strip():
                    system_knowledge.record_sighting(system_name, "ore", name.strip(), "ai_tool", pilot_name or None)
        except Exception as e:
            log.warning("_tool_record_field_observation failed: %s", e)
            return {"text": "Failed to record observation.", "structured": None}

        parts = []
        if enemies:
            parts.append(f"enemies: {', '.join(enemies)}")
        if ores:
            parts.append(f"ores: {', '.join(ores)}")
        return {
            "text": f"Recorded in {system_name} — {'; '.join(parts)}.",
            "structured": None,
        }

    def _tool_query_system_knowledge(self, inputs: Dict[str, Any], context: Dict[str, Any] = None) -> Dict[str, Any]:
        """Handler for query_system_knowledge tool. Returns global sightings data for a system."""
        system_name = (inputs.get("system_name") or "").strip()
        if not system_name:
            return {"text": "system_name is required.", "structured": None}

        try:
            from src import system_knowledge
            result = system_knowledge.query_system(system_name)
        except Exception as e:
            log.warning("_tool_query_system_knowledge failed: %s", e)
            return {"text": "Knowledge graph unavailable.", "structured": None}

        if not result.get("found"):
            return {
                "text": f"No data in knowledge graph for '{system_name}'. No pilot has reported this system yet.",
                "structured": {"found": False, "system_name": system_name},
            }

        lines = [f"System knowledge — {system_name}:"]
        if result.get("region"):
            lines.append(f"  Region: {result['region']}")
        lines.append(f"  Visits recorded: {result['visit_count']}")

        enemies = result.get("enemies", [])
        if enemies:
            lines.append(f"  Known enemies ({len(enemies)}):")
            for e in enemies:
                lines.append(f"    {e['value']} (seen {e['sighting_count']}x, last {e['last_seen'][:10]})")
        else:
            lines.append("  Known enemies: none reported")

        ores = result.get("ores", [])
        if ores:
            lines.append(f"  Known ores ({len(ores)}):")
            for o in ores:
                lines.append(f"    {o['value']} (seen {o['sighting_count']}x, last {o['last_seen'][:10]})")
        else:
            lines.append("  Known ores: none reported")

        return {"text": "\n".join(lines), "structured": result}

    def _tool_lookup_item_type(self, inputs: Dict[str, Any], context: Dict[str, Any] = None) -> Dict[str, Any]:
        """Handler for lookup_item_type tool. Searches game type database by name."""
        query = (inputs.get("query") or "").strip()
        if not query:
            return {"text": "No query provided.", "structured": None}

        try:
            from src.entity_resolver import get_entity_resolver
            resolver = get_entity_resolver()
            matches = resolver.search_types_by_name(query, max_results=5)
        except Exception as e:
            log.warning("_tool_lookup_item_type failed: %s", e)
            return {"text": "Game type database unavailable.", "structured": None}

        if not matches:
            return {
                "text": f"No game types found matching '{query}'.",
                "structured": None,
            }

        lines = [f"Game type search — '{query}' ({len(matches)} match(es)):"]
        for m in matches:
            desc = (m["description"] or "").strip()
            desc_snippet = (desc[:200] + "…") if len(desc) > 200 else desc
            lines.append(
                f"\n  [{m['type_id']}] {m['name']}"
                f"\n    Category: {m['categoryName']} / {m['groupName']}"
                f"\n    Mass: {m['mass']}kg  Volume: {m['volume']}m³"
            )
            if desc_snippet:
                lines.append(f"    {desc_snippet}")

        return {
            "text": "\n".join(lines),
            "structured": {"query": query, "matches": matches},
        }


    async def _tool_calculate_build_options(
        self, inputs: Dict[str, Any], context: Dict[str, Any] = None
    ) -> Dict[str, Any]:
        """Handler for calculate_build_options tool."""
        structure_id = (context or {}).get("structure_id")
        system_id = (context or {}).get("system_id")

        # 1. Inventory — profile cache first, fresh fetch fallback
        inventory: Dict[str, int] = {}
        try:
            from src.structure_persistence import load_profile
            profile = load_profile(structure_id) if structure_id else None
            if profile and profile.cached_inventory and profile.cached_inventory.get("items"):
                for item in profile.cached_inventory["items"]:
                    if item.get("type_name"):
                        inventory[item["type_name"]] = item.get("quantity", 0)
            elif structure_id:
                from src.entity_resolver import get_entity_resolver
                resolver = get_entity_resolver()
                inv = await resolver.get_inventory(structure_id)
                if inv and inv.get("items"):
                    for item in inv["items"]:
                        if item.get("type_name"):
                            inventory[item["type_name"]] = item.get("quantity", 0)
        except Exception as e:
            log.debug("_tool_calculate_build_options: inventory fetch failed: %s", e)

        # 2. NetworkNode check + already-built detection
        has_network = False
        already_built: set = set()
        try:
            from src.entity_resolver import get_entity_resolver
            from src.build_calculator import _type_repr_to_build_name
            resolver = get_entity_resolver()
            full = await resolver.get_assembly_full(structure_id)
            energy_source = full and full.get("energy_source")
            has_network = bool(energy_source)

            # Current structure: try to identify its build-tree name
            if full:
                current_asm = full.get("assembly") or {}
                build_name = _type_repr_to_build_name(current_asm.get("type_repr", ""))
                if build_name:
                    already_built.add(build_name)

            # Connected assemblies: read names from the network node
            if energy_source:
                energy_id = energy_source.get("sui_id") or energy_source.get("id")
                if energy_id:
                    net = await resolver.get_network(energy_id)
                    for asm in (net or {}).get("connected_assemblies", []):
                        # Prefer exact name match against build tree
                        asm_name = asm.get("name", "")
                        # Also try type_repr for specific subtype identification
                        tr_name = _type_repr_to_build_name(asm.get("type_repr", ""))
                        if tr_name:
                            already_built.add(tr_name)
                        elif asm_name:
                            already_built.add(asm_name)
        except Exception as e:
            log.debug("_tool_calculate_build_options: assembly/network fetch failed: %s", e)

        # 3. L-point count — synchronous SQLite query
        lagrange_count = 0
        try:
            from src.galaxy_db import galaxy_db
            if system_id:
                celestials = galaxy_db.get_celestials_in_system(int(system_id))
                lagrange_count = len(celestials.get("lagrange_points", []))
        except Exception as e:
            log.debug("_tool_calculate_build_options: galaxy_db query failed: %s", e)

        from src.build_calculator import calculate, format_text_block, format_structured
        result = calculate(inventory, has_network, lagrange_count, already_built=already_built or None)
        target = inputs.get("target", "").strip()

        return {
            "text": format_text_block(result, target=target),
            "structured": format_structured(result, target=target),
        }


# Singleton
ai_tools = ToolRegistry()
