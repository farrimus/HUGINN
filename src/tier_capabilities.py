"""
src/tier_capabilities.py

Single source of truth for what each tier can access.

To change a tier's abilities:
  - Edit TIERS (tools list, nav items, permissions)
  - Edit AI_LEVELS if the AI's behavior description needs updating
  - Mirror nav_items changes in frontend/src/features/tierCapabilities.ts
"""

# ---------------------------------------------------------------------------
# Tier definitions
# ---------------------------------------------------------------------------

TIERS: dict = {
    "NONE": {
        "label":      "Guest",
        "ai_level":   "lobby",
        "can_signal": False,
        "can_admin":  False,
        # Nav bar items this tier can see (admin feature flags still gate on/off)
        "nav_items":  ["recon", "route", "upload"],
        # AI tools available to Claude for this tier
        "tools": [
            "assess_threat",
            "get_system_intel",
            "radius_search",
            "plan_route",
            "recon_scan",
            "lookup_item_type",
            "query_intel",
            "query_system_knowledge",
            "search_lore",
        ],
    },
    "VETTED": {
        "label":      "Vetted Pilot",
        "ai_level":   "vetted",
        "can_signal": False,
        "can_admin":  False,
        "nav_items":  ["recon", "route", "upload"],
        "tools": [
            "assess_threat",
            "get_system_intel",
            "radius_search",
            "plan_route",
            "recon_scan",
            "lookup_item_type",
            "query_intel",
            "query_system_knowledge",
            "log_intel",
            "record_field_observation",
            "search_lore",
        ],
    },
    "TRIBE": {
        "label":      "Tribe Member",
        "ai_level":   "full",
        "can_signal": True,
        "can_admin":  False,
        "nav_items":  [
            "recon", "route", "upload",
            "network", "inventory", "assets", "nodes",
            "signal", "board", "tribe", "courier", "watches",
        ],
        "tools": [
            "assess_threat",
            "get_system_intel",
            "radius_search",
            "plan_route",
            "recon_scan",
            "lookup_item_type",
            "query_intel",
            "query_system_knowledge",
            "log_intel",
            "record_field_observation",
            "search_memory",
            "get_memory_summary",
            "get_pilot_profile",
            "manage_watcher",
            "manage_courier",
            "manage_tribe",
            "calculate_build_options",
            "search_lore",
        ],
    },
    "OWNER": {
        "label":      "Owner",
        "ai_level":   "full",
        "can_signal": True,
        "can_admin":  True,
        "nav_items":  [
            "recon", "route", "upload",
            "network", "inventory", "assets", "nodes",
            "signal", "board", "tribe", "courier", "watches",
        ],
        "tools": [
            "assess_threat",
            "get_system_intel",
            "radius_search",
            "plan_route",
            "recon_scan",
            "lookup_item_type",
            "query_intel",
            "query_system_knowledge",
            "log_intel",
            "record_field_observation",
            "search_memory",
            "get_memory_summary",
            "get_pilot_profile",
            "manage_watcher",
            "manage_courier",
            "manage_tribe",
            "calculate_build_options",
            "search_lore",
        ],
    },
}

# ---------------------------------------------------------------------------
# AI behavior descriptions — injected into HUGINN's context per request
# ---------------------------------------------------------------------------

AI_LEVELS: dict = {
    "lobby": (
        "Unknown visitor. Public geography and general assistance only. "
        "Reveal nothing about fuel, shield, services, inventory, assemblies, or tribe activity."
    ),
    "vetted": (
        "Known pilot. Acknowledge by name. You may confirm structure status and general system info. "
        "Do not reveal fuel levels, inventory counts, or tribe activity."
    ),
    "full": (
        "Trusted contact. Full access: fuel, shield, services, inventory, "
        "connected assemblies, tribe activity."
    ),
}

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def get_tier(tier: str) -> dict:
    """Return capabilities for the given tier, falling back to NONE."""
    return TIERS.get(tier, TIERS["NONE"])


def ai_instruction(tier: str) -> str:
    """Return the AI behavior instruction for the given tier."""
    level = get_tier(tier)["ai_level"]
    return AI_LEVELS[level]


def allowed_tools(tier: str) -> list[str]:
    """Return the list of tool names available for this tier."""
    return get_tier(tier)["tools"]


def blocked_tools(tier: str, all_tools: list[str]) -> list[str]:
    """Return tool names that should be excluded for this tier."""
    allowed = set(allowed_tools(tier))
    return [t for t in all_tools if t not in allowed]


def can_access(tier: str, permission: str) -> bool:
    """Check a boolean permission (e.g. 'can_signal', 'can_admin')."""
    return bool(get_tier(tier).get(permission, False))
