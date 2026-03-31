# src/context_builder.py
from typing import Optional


def build_context_block(
    system_data: Optional[dict],
    log_events: list,
    current_system: Optional[str],
    live_sessions: Optional[list] = None,
    current_route: Optional[dict] = None,
    structure_alerts: Optional[list] = None,
    ship_profile=None,  # ShipProfile instance; import avoided to prevent circular dep
    nearby_structures: Optional[list] = None,  # [{type_name, status, fuel_pct, services_online, system_name}]
) -> str:
    lines = []

    # --- Structure alerts (urgent, from Structure AI — prepended for visibility) ---
    for alert in (structure_alerts or []):
        name = alert.get("structure_name", alert.get("structure_id", "Structure"))
        lines.append(f"STRUCTURE ALERT [{name}]: {alert.get('message', '')}")

    # --- Location ---
    system_name = current_system or (system_data or {}).get("name", "unknown")
    location_line = f"LOCATION: {system_name}"
    if system_data:
        security = system_data.get("security")
        if security is not None:
            location_line += f" | security: {security:.1f}"
        kills = system_data.get("kills", [])
        if kills:
            location_line += f" | {len(kills)} recent kill(s) in system"
    lines.append(location_line)

    # --- Player-owned structures in current system ---
    for struct in (nearby_structures or [])[:3]:
        name = struct.get("type_name", "Structure")
        status = struct.get("status", "UNKNOWN")
        fuel_pct = struct.get("fuel_pct")
        svc = struct.get("services_online")
        fuel_str = f" | fuel:{fuel_pct:.0f}%" if fuel_pct is not None else ""
        svc_str = f" | {svc} svc" if svc is not None else ""
        lines.append(f"PLAYER STRUCTURE: {name} ({status}){fuel_str}{svc_str}")

    # --- Ship profile summary ---
    if ship_profile is not None:
        ship_str  = ship_profile.ship_type or "custom"
        fuel_str  = f"{ship_profile.fuel_type} x {round(ship_profile.fuel_quantity)}u"
        # safe_jump_temp comes from system_data when available; falls back to 0 (coldest)
        temp = (system_data or {}).get("safe_jump_temp")
        r_ly = ship_profile.jump_range_at_temp(temp or 0.0)
        b_ly = ship_profile.fuel_budget()
        range_str = f"~{r_ly:.0f} LY" if temp is None else f"{r_ly:.0f} LY"
        lines.append(
            f"SHIP: {ship_str} | {fuel_str} | range {range_str} | budget {b_ly:.0f} LY"
        )

    # --- Partition events by type ---
    combat_summary  = None
    mining_summary  = None
    transitions     = []   # system_change, undock, docking, autopilot, ship_stopping
    chat_events     = []

    for e in log_events:
        t = e.get("type")
        if t == "combat_summary":
            combat_summary = e
        elif t == "mining_summary":
            mining_summary = e
        elif t in ("system_change", "undock", "docking", "autopilot", "ship_stopping", "cargo_full"):
            transitions.append(e)
        elif t == "chat":
            chat_events.append(e)
        # gamelog_raw and others are silently skipped — low signal

    # Live snapshots override buffered summaries
    for e in (live_sessions or []):
        if e.get("type") == "combat_summary":
            combat_summary = e
        elif e.get("type") == "mining_summary":
            mining_summary = e

    # --- Most recent mining session ---
    if mining_summary:
        mat_parts = [f"{mat} \u00d7{qty}" for mat, qty in mining_summary["materials"].items()]
        mat_str   = ", ".join(mat_parts) if mat_parts else "unknown material"
        dur_min   = mining_summary["duration_s"] // 60
        dur_str   = f"{dur_min} min" if dur_min > 0 else "<1 min"
        fulls     = mining_summary.get("cargo_fulls", 0)
        cargo_str = f" | cargo full \u00d7{fulls}" if fulls else ""
        ongoing_str = " (ongoing)" if mining_summary.get("in_progress") else ""
        lines.append(f"MINING{ongoing_str}: {mat_str} over {dur_str}{cargo_str}")

    # --- Most recent combat session ---
    if combat_summary:
        enemy_parts = [
            f"{count} \u00d7 {name}" if count > 0 else name
            for name, count in combat_summary["enemies"].items()
        ]
        enemy_str = ", ".join(enemy_parts) if enemy_parts else "unknown"

        dmg_out = combat_summary.get("damage_out", 0)
        dmg_in  = combat_summary.get("damage_in", 0)

        hits_in  = combat_summary.get("hits_in", {})
        worst_in = max(hits_in, key=hits_in.get) if hits_in else None

        weapons = combat_summary.get("weapons_used", [])
        wpn_str = f" | {', '.join(weapons)}" if weapons else ""

        dmg_str = f"{dmg_out} out / {dmg_in} in"
        if worst_in:
            dmg_str += f" ({worst_in})"

        ongoing_str = " (ongoing)" if combat_summary.get("in_progress") else ""
        lines.append(f"COMBAT{ongoing_str}: {enemy_str} | dmg {dmg_str}{wpn_str}")

    # --- Transition events (state changes, formatted concisely) ---
    if transitions:
        for e in transitions[-5:]:   # cap at last 5
            t = e.get("type")
            if t == "system_change":
                lines.append(f"JUMPED TO: {e.get('system', '?')}")
            elif t == "undock":
                lines.append(f"UNDOCKED: {e.get('station', '?')} \u2192 {e.get('system', '?')}")
            elif t == "docking":
                state = e.get("state")
                if state == "accepted":
                    lines.append("DOCKED")
                elif state == "requested":
                    lines.append(f"DOCKING: {e.get('location', '?')}")
            elif t == "autopilot":
                lines.append(f"AUTOPILOT: {e.get('state', '?')}")
            elif t == "ship_stopping":
                lines.append("SHIP STOPPED")
            elif t == "cargo_full":
                lines.append(f"CARGO FULL: {e.get('module', 'module complete')}")

    # --- Recent chat (other pilots in local, NPC messages) ---
    if chat_events:
        # Deduplicate senders, show count
        senders = list(dict.fromkeys(e.get("sender", "?") for e in chat_events))
        if len(senders) == 1:
            lines.append(f"LOCAL CHAT: {senders[0]} active")
        else:
            lines.append(f"LOCAL CHAT: {len(senders)} pilots active ({', '.join(senders[:3])}{'...' if len(senders) > 3 else ''})")

    # --- Planned route (set by client RouteCalculator via route_planned event) ---
    if current_route:
        error = current_route.get("error")
        if error:
            lines.append(f"ROUTE ERROR: {error}")
        else:
            path     = current_route.get("path", [])
            jumps    = current_route.get("jumps", len(path) - 1 if len(path) > 1 else 0)
            est      = current_route.get("est_time_min")
            warnings = current_route.get("warnings", [])
            highlights = current_route.get("highlights", [])
            if path:
                # Truncate long paths: show first → ... (N hops) → last
                if len(path) > 5:
                    path_str = f"{path[0].upper()} → [{len(path)-2} hops] → {path[-1].upper()}"
                else:
                    path_str = " → ".join(p.upper() for p in path)
                route_str = f"ROUTE PLANNED: {path_str} ({jumps} jump{'s' if jumps != 1 else ''}"
                if est:
                    route_str += f", est {est} min"
                route_str += ")"
                lines.append(route_str)
                # Warnings on their own line — cap at 3
                for w in warnings[:3]:
                    lines.append(f"ROUTE WARN: {w}")
                # Resource/exploration highlights — cap at 2
                for h in highlights[:2]:
                    lines.append(f"ROUTE STOP: {h}")

    block = "\n".join(lines)
    return block[:2000]
