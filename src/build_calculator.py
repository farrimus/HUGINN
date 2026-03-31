"""
src/build_calculator.py

Pure build calculator — no I/O, no app imports.

Given inventory, NetworkNode status, and L-point count, computes:
  - What structures are fully buildable right now
  - What structures are almost buildable (with exact shortfalls)
  - Tier-0 field deployables (always calculable regardless of network)
  - NetworkNode status and shortfalls

Used by the calculate_build_options AI tool in ai_tools.py.
"""

import json
import os
from typing import Optional


def _load_build_tree() -> dict:
    """Load build_tree.json from data/. Returns parsed dict."""
    path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "build_tree.json")
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


# Module-level cache — loaded once per process
_BUILD_TREE: Optional[dict] = None


def _get_tree() -> dict:
    global _BUILD_TREE
    if _BUILD_TREE is None:
        _BUILD_TREE = _load_build_tree()
    return _BUILD_TREE


def _norm(s: str) -> str:
    """Normalize a material name for fuzzy matching.

    Handles plurality and casing differences between the game API
    (e.g. 'Building Foams') and the build tree ('Building Foams').
    Strips trailing 's' so 'Foams'/'Foam' both match.
    """
    return s.strip().lower().rstrip("s")


def _build_inv_lookup(inventory: dict) -> dict:
    """Return {normalized_name: quantity} for fast lookup."""
    return {_norm(k): v for k, v in inventory.items()}


def _check_materials(recipe_materials: dict, inv_lookup: dict) -> dict:
    """Return {item: shortfall} for items where inventory < required. Empty = fully stocked."""
    shortfalls = {}
    for item, qty_needed in recipe_materials.items():
        have = inv_lookup.get(_norm(item), 0)
        if have < qty_needed:
            shortfalls[item] = qty_needed - have
    return shortfalls


def _completion_pct(recipe_materials: dict, inv_lookup: dict) -> float:
    """0.0–1.0 fraction of total required materials already in inventory."""
    total_needed = sum(recipe_materials.values())
    if total_needed == 0:
        return 1.0
    total_have = sum(
        min(inv_lookup.get(_norm(item), 0), qty)
        for item, qty in recipe_materials.items()
    )
    return total_have / total_needed


def calculate(
    inventory: dict,
    has_network: bool,
    lagrange_count: int,
) -> dict:
    """
    Compute build options given current state.

    Args:
        inventory:       {type_name: quantity} from SSU or cargo
        has_network:     True if a NetworkNode is online on this structure's network
        lagrange_count:  Number of L-points in the current system (from galaxy_db)

    Returns dict with keys:
        can_build_now       list[str]    — structures fully stocked
        almost_buildable    list[dict]   — [{name, shortfalls, pct_ready}], sorted by pct_ready DESC
        field_deployables   list[str]    — Tier-0 structures buildable anywhere right now
        has_network         bool
        lagrange_points     int
        network_node_status str          — "online"|"buildable"|"need_materials"|"no_anchor"
        network_node_shortfalls dict     — {item: qty_short}, empty if not applicable
    """
    tree = _get_tree()
    structures = tree.get("structures", [])
    nn_recipe = tree.get("network_node", {})
    nn_materials = nn_recipe.get("materials", {})

    inv_lookup = _build_inv_lookup(inventory)

    # --- NetworkNode status ---
    nn_shortfalls = {}
    if has_network:
        nn_status = "online"
    elif lagrange_count == 0:
        nn_status = "no_anchor"
    else:
        nn_shortfalls = _check_materials(nn_materials, inv_lookup)
        nn_status = "need_materials" if nn_shortfalls else "buildable"

    # --- Evaluate each structure ---
    can_build_now = []
    almost_buildable = []
    field_deployables = []

    for s in structures:
        requires_network = s.get("requires_network", True)
        materials = s.get("materials", {})
        name = s["name"]

        # Skip network-dependent structures if no network and no prospect
        if requires_network and not has_network:
            # Still show shortfalls — useful for planning
            shortfalls = _check_materials(materials, inv_lookup)
            pct = _completion_pct(materials, inv_lookup)
            almost_buildable.append({
                "name": name,
                "shortfalls": shortfalls,
                "pct_ready": pct,
                "requires_network": True,
            })
            continue

        shortfalls = _check_materials(materials, inv_lookup)
        pct = _completion_pct(materials, inv_lookup)

        if not shortfalls:
            if not requires_network:
                field_deployables.append(name)
            else:
                can_build_now.append(name)
        else:
            entry = {
                "name": name,
                "shortfalls": shortfalls,
                "pct_ready": pct,
                "requires_network": requires_network,
            }
            almost_buildable.append(entry)

    # Sort almost_buildable: closest to complete first
    almost_buildable.sort(key=lambda x: x["pct_ready"], reverse=True)

    return {
        "can_build_now": can_build_now,
        "almost_buildable": almost_buildable,
        "field_deployables": field_deployables,
        "has_network": has_network,
        "lagrange_points": lagrange_count,
        "network_node_status": nn_status,
        "network_node_shortfalls": nn_shortfalls,
        "inventory_item_count": len(inventory),
    }


def _fmt_shortfalls(shortfalls: dict, max_items: int = 3) -> str:
    """Format shortfall dict as compact string: 'need 5 Printed Circuits, 8 Carbon Weave'."""
    if not shortfalls:
        return ""
    parts = [f"{qty}x {item}" for item, qty in list(shortfalls.items())[:max_items]]
    suffix = f" +{len(shortfalls) - max_items} more" if len(shortfalls) > max_items else ""
    return "need " + ", ".join(parts) + suffix


def format_text_block(result: dict, target: str = "") -> str:
    """
    Format calculate() result as a compact text block for Claude.

    If target is specified, focuses output on that structure only.
    """
    lines = []

    if target:
        # Single-structure lookup
        target_norm = _norm(target)
        tree = _get_tree()
        match = next(
            (s for s in tree.get("structures", []) if _norm(s["name"]) == target_norm),
            None,
        )
        if not match:
            return f"[BUILD CALC] '{target}' not found in build tree."

        inv_lookup = _build_inv_lookup({})  # empty — we'll reuse result
        # Find in result
        all_entries = (
            [{"name": n, "shortfalls": {}, "pct_ready": 1.0} for n in result["can_build_now"]]
            + [{"name": n, "shortfalls": {}, "pct_ready": 1.0} for n in result["field_deployables"]]
            + result["almost_buildable"]
        )
        entry = next((e for e in all_entries if _norm(e["name"]) == target_norm), None)

        lines.append(f"[BUILD CALC] {match['name']}")
        mats = match.get("materials", {})
        for item, qty in mats.items():
            lines.append(f"  Required: {qty}x {item}")
        if entry and not entry["shortfalls"]:
            lines.append("  STATUS: FULLY STOCKED — can build now")
        elif entry:
            lines.append(f"  STATUS: {entry['pct_ready']*100:.0f}% ready")
            for item, short in entry["shortfalls"].items():
                lines.append(f"  SHORT: {short}x {item}")
        if match.get("requires_network") and not result["has_network"]:
            lines.append("  BLOCKED: requires NetworkNode (not online)")
        return "\n".join(lines)

    # Full assessment
    nn_status = result["network_node_status"]
    lp = result["lagrange_points"]

    if nn_status == "online":
        lines.append(f"[BUILD CALC] NetworkNode: ONLINE | L-points: {lp}")
    elif nn_status == "buildable":
        lines.append(f"[BUILD CALC] NetworkNode: CAN BUILD NOW | L-points: {lp}")
    elif nn_status == "need_materials":
        sf = _fmt_shortfalls(result["network_node_shortfalls"])
        lines.append(f"[BUILD CALC] NetworkNode: {sf} | L-points: {lp}")
    else:
        lines.append(f"[BUILD CALC] NetworkNode: NO L-POINT ANCHOR in system")

    if result["can_build_now"]:
        lines.append("CAN BUILD NOW: " + ", ".join(result["can_build_now"]))
    else:
        lines.append("CAN BUILD NOW: none")

    if result["field_deployables"]:
        lines.append("FIELD DEPLOYABLES: " + ", ".join(result["field_deployables"]))

    top = [e for e in result["almost_buildable"] if e["pct_ready"] >= 0.5][:5]
    if top:
        lines.append("ALMOST READY:")
        for e in top:
            if e["shortfalls"]:
                note = _fmt_shortfalls(e["shortfalls"])
            elif e.get("requires_network") and not result["has_network"]:
                note = "needs NetworkNode"
            else:
                note = "stocked"
            lines.append(f"  {e['name']:20s} {e['pct_ready']*100:3.0f}%  ({note})")

    if not result["inventory_item_count"]:
        lines.append("NOTE: No inventory data available — showing full recipe requirements")

    return "\n".join(lines)


def format_structured(result: dict, target: str = "") -> dict:
    """
    Format calculate() result as structured dict for the frontend panel.

    Matches BuildOptionsData TypeScript interface.
    """
    if target:
        target_norm = _norm(target)
        tree = _get_tree()
        match = next(
            (s for s in tree.get("structures", []) if _norm(s["name"]) == target_norm),
            None,
        )
        if match:
            all_entries = (
                [{"name": n, "shortfalls": {}, "pct_ready": 1.0}
                 for n in result["can_build_now"] + result["field_deployables"]]
                + result["almost_buildable"]
            )
            entry = next((e for e in all_entries if _norm(e["name"]) == target_norm), None)
            return {
                "canBuildNow": result["can_build_now"],
                "almostBuildable": [
                    {
                        "name": e["name"],
                        "shortfalls": e["shortfalls"],
                        "pctReady": round(e["pct_ready"], 2),
                    }
                    for e in ([entry] if entry and entry["shortfalls"] else [])
                ],
                "fieldDeployables": result["field_deployables"],
                "hasNetwork": result["has_network"],
                "lagrangePoints": result["lagrange_points"],
                "networkNodeStatus": result["network_node_status"],
                "networkNodeShortfalls": result["network_node_shortfalls"],
                "targetName": match["name"],
                "targetMaterials": match.get("materials", {}),
                "targetBuildable": entry is not None and not entry.get("shortfalls"),
            }

    return {
        "canBuildNow": result["can_build_now"],
        "almostBuildable": [
            {
                "name": e["name"],
                "shortfalls": e["shortfalls"],
                "pctReady": round(e["pct_ready"], 2),
            }
            for e in result["almost_buildable"][:8]
        ],
        "fieldDeployables": result["field_deployables"],
        "hasNetwork": result["has_network"],
        "lagrangePoints": result["lagrange_points"],
        "networkNodeStatus": result["network_node_status"],
        "networkNodeShortfalls": result["network_node_shortfalls"],
    }
