# src/route_engine.py
import json
import os
import math
import logging
import bisect
import heapq
from collections import deque
from typing import Optional

from src.ship_profile import ShipProfile, T_MAX, HEAT_CONSTANT, NO_JUMP_TEMP

log = logging.getLogger(__name__)

LY_METERS = 9_460_730_472_580_800.0  # IAU light-year in meters
WARM_SYSTEM_TEMP = 70.0  # systems at or above this temp trigger alternative route


class _SpatialIndex:
    """
    Lightweight 3D spatial index operating in light-years.
    Sorts by X-axis and uses binary search to narrow candidates.
    """
    def __init__(self):
        self._xs:   list[float] = []
        self._data: list[tuple] = []  # (x_ly, y_ly, z_ly, sid)

    def build(self, ly_coords: dict):
        """Build index from {sid: (x_ly, y_ly, z_ly)} dict."""
        entries = [(x, y, z, sid) for sid, (x, y, z) in ly_coords.items()]
        entries.sort(key=lambda e: e[0])
        self._data = entries
        self._xs   = [e[0] for e in entries]

    def within_range(self, cx: float, cy: float, cz: float, r: float) -> list[str]:
        """Return system IDs within Euclidean distance r LY of (cx, cy, cz)."""
        lo = bisect.bisect_left(self._xs,  cx - r)
        hi = bisect.bisect_right(self._xs, cx + r)
        result = []
        r2 = r * r
        for i in range(lo, hi):
            x, y, z, sid = self._data[i]
            dy = y - cy
            if abs(dy) > r:
                continue
            dz = z - cz
            if abs(dz) > r:
                continue
            if (x - cx)**2 + dy*dy + dz*dz <= r2:
                result.append(sid)
        return result


class RouteEngine:
    def __init__(self):
        self._systems:   dict  = {}   # id (str) → system dict (meter coords from JSON)
        self._by_name:   dict  = {}   # lowercase name → id (str)
        self._ly_coords: dict  = {}   # id (str) → (x_ly, y_ly, z_ly)
        self._spatial          = _SpatialIndex()
        self._mtime:     float = 0.0

    def _systems_path(self) -> str:
        """Get path to systems.json (shared across environments)."""
        from src.config import get_data_path
        return get_data_path("systems.json", env_specific=False)

    def _load(self):
        path = self._systems_path()
        try:
            mtime = os.path.getmtime(path)
        except FileNotFoundError:
            return
        if mtime <= self._mtime:
            return
        try:
            with open(path, encoding="utf-8") as f:
                data = json.load(f)
            self._systems = data.get("systems", {})
            self._by_name = {
                v["name"].lower(): k
                for k, v in self._systems.items()
                if v.get("name")
            }
            # Convert coordinates to LY at load time
            self._ly_coords = {
                sid: (
                    s.get("x", 0) / LY_METERS,
                    s.get("y", 0) / LY_METERS,
                    s.get("z", 0) / LY_METERS,
                )
                for sid, s in self._systems.items()
            }
            self._spatial.build(self._ly_coords)
            self._mtime = mtime
            log.info("systems.json loaded: %d systems", len(self._systems))
        except Exception as e:
            log.warning("Failed to load systems.json: %s", e)

    def ready(self) -> bool:
        self._load()
        return bool(self._systems)

    def resolve(self, name: str) -> Optional[str]:
        self._load()
        return self._by_name.get(name.lower().strip())

    def system_info(self, name: str) -> Optional[dict]:
        self._load()
        sid = self._by_name.get(name.lower().strip())
        return self._systems.get(sid) if sid else None

    def _pos_ly(self, sid: str) -> tuple:
        return self._ly_coords.get(sid, (0.0, 0.0, 0.0))

    def _dist_ly(self, sid_a: str, sid_b: str) -> float:
        ax, ay, az = self._pos_ly(sid_a)
        bx, by, bz = self._pos_ly(sid_b)
        dx, dy, dz = ax - bx, ay - by, az - bz
        return math.sqrt(dx*dx + dy*dy + dz*dz)

    def _name(self, sid: str) -> str:
        return self._systems.get(sid, {}).get("name", sid)

    def _security_warning(self, sid: str) -> Optional[str]:
        s = self._systems.get(sid, {})
        sec = s.get("security")
        if sec is not None and float(sec) <= 0.0:
            return f"{self._name(sid)} is null-sec"
        return None

    def _range_at_temp(self, ship_temp: float, ambient_temp: float, profile: ShipProfile) -> float:
        """Compute direct-jump range (LY) given ship's current temperature and system ambient."""
        if ambient_temp >= NO_JUMP_TEMP:
            return 0.0
        effective = max(ship_temp, ambient_temp)
        if effective >= T_MAX:
            return 0.0
        c_eff    = profile.specific_heat * (1.0 + profile.adaptive_level * 0.02)
        cur_mass = profile.hull_mass + profile.extra_cargo_kg
        return max(0.0, (T_MAX - effective) * c_eff * profile.hull_mass / (HEAT_CONSTANT * cur_mass))

    def _heat_after_jump(self, ship_temp: float, ambient_temp: float, dist_ly: float, profile: ShipProfile) -> float:
        """Return ship temperature after jumping dist_ly from a system with given ambient."""
        effective = max(ship_temp, ambient_temp)
        c_eff    = profile.specific_heat * (1.0 + profile.adaptive_level * 0.02)
        cur_mass = profile.hull_mass + profile.extra_cargo_kg
        delta    = HEAT_CONSTANT * dist_ly * cur_mass / (c_eff * profile.hull_mass)
        return effective + delta

    def _node_range_ly(self, sid: str, profile: ShipProfile) -> float:
        """Compute direct-jump range from a system node (ship assumed at ambient temp)."""
        temp = self._systems.get(sid, {}).get("safe_jump_temp", 0.0) or 0.0
        return self._range_at_temp(0.0, temp, profile)

    # ------------------------------------------------------------------
    # Gate-only BFS (unchanged interface, updated to match new shape)
    # ------------------------------------------------------------------

    def bfs(self, origin: str, destination: str) -> Optional[dict]:
        """Shortest gate-hop route. Returns None if no gate path exists."""
        self._load()
        o_id = self._by_name.get(origin.lower().strip())
        d_id = self._by_name.get(destination.lower().strip())
        if not o_id or not d_id:
            return None
        if o_id == d_id:
            return {"type": "route_planned", "path": [self._name(o_id)],
                    "path_ids": [int(o_id)],
                    "jumps": 0, "jump_types": [], "total_ly": 0.0,
                    "fuel_used": 0.0, "fuel_remaining": 0.0,
                    "hot_systems": [], "alternative": None, "warnings": []}

        queue: deque = deque([[o_id]])
        visited: set = {o_id}
        while queue:
            path = queue.popleft()
            for nb in self._systems.get(path[-1], {}).get("gate_links", []):
                nb_id = str(nb)
                if nb_id in visited:
                    continue
                full = path + [nb_id]
                if nb_id == d_id:
                    names    = [self._name(s) for s in full]
                    warnings = [w for s in full[1:] if (w := self._security_warning(s))]
                    return {
                        "type":           "route_planned",
                        "path":           names,
                        "path_ids":       [int(s) for s in full],
                        "jumps":          len(names) - 1,
                        "jump_types":     ["gate"] * (len(names) - 1),
                        "total_ly":       0.0,
                        "fuel_used":      0.0,
                        "fuel_remaining": 0.0,
                        "hot_systems":    [],
                        "alternative":    None,
                        "warnings":       warnings,
                    }
                visited.add(nb_id)
                queue.append(full)
        return None

    # ------------------------------------------------------------------
    # Internal A* helper
    # ------------------------------------------------------------------

    def _run_astar(
        self,
        o_id: str,
        d_id: str,
        profile: ShipProfile,
        exclude_direct: Optional[set] = None,
        cost_mode: str = "jumps",
        initial_ship_temp: float = 0.0,
        cooling_stops: bool = False,
    ) -> Optional[tuple]:
        """
        Hybrid A* router with heat accumulation tracking.

        cost_mode="jumps":  minimise hop count (gates + direct both cost 1)
        cost_mode="fuel":   minimise total direct-jump LY (gates cost 0)

        Ship temperature is tracked across hops. Each direct jump heats the
        ship based on distance. A jump is blocked if it would push the ship
        above T_MAX. Gate jumps expose the ship to destination ambient temp
        but add no additional heat.

        Returns (path_ids, edge_types, total_ly, final_ship_temp) or None.
        """
        c_eff    = profile.specific_heat * (1.0 + profile.adaptive_level * 0.02)
        cur_mass = profile.hull_mass + profile.extra_cargo_kg
        global_max_range = (T_MAX * c_eff * profile.hull_mass) / (HEAT_CONSTANT * cur_mass) if cur_mass > 0 else 0.0

        dx, dy, dz = self._pos_ly(d_id)
        fuel_mode = (cost_mode == "fuel")

        def heuristic(sid: str) -> float:
            x, y, z = self._pos_ly(sid)
            dist = math.sqrt((x - dx)**2 + (y - dy)**2 + (z - dz)**2)
            if fuel_mode:
                # dist_to_dest is an admissible lower bound on remaining direct-LY:
                # gates are free but can only reduce cost, never increase it.
                # This gives directional guidance without pure Dijkstra's frontier explosion.
                return dist
            if global_max_range <= 0:
                return float("inf")
            return dist / global_max_range

        # State: (f, g_cost, sid, path_ids, edge_types, acc_ly, ship_temp)
        o_ambient = self._systems.get(o_id, {}).get("safe_jump_temp", 0.0) or 0.0
        start_temp = max(initial_ship_temp, o_ambient)
        heap = [(heuristic(o_id), 0.0, o_id, [o_id], [], 0.0, start_temp)]

        # best[sid] = (best_g, best_temp) — prune if current state is dominated on both axes
        best: dict = {}

        while heap:
            f, g_cost, cur_id, path, edge_types, acc_ly, ship_temp = heapq.heappop(heap)

            if cur_id == d_id:
                return (path, edge_types, acc_ly, ship_temp)

            # Prune if this state is dominated: existing visit ≤ cost AND ≤ temp
            if cur_id in best:
                bg, bt = best[cur_id]
                if bg <= g_cost and bt <= ship_temp:
                    continue
            # Record best state seen (update either axis if improved)
            if cur_id not in best:
                best[cur_id] = (g_cost, ship_temp)
            else:
                bg, bt = best[cur_id]
                best[cur_id] = (min(bg, g_cost), min(bt, ship_temp))

            cx, cy, cz = self._pos_ly(cur_id)
            sys_data = self._systems.get(cur_id, {})
            ambient = sys_data.get("safe_jump_temp", 0.0) or 0.0
            effective_temp = max(ship_temp, ambient)

            # Gate neighbours — no heat penalty, ship absorbs destination ambient
            gate_step = 0.0 if fuel_mode else 1.0
            for nb in sys_data.get("gate_links", []):
                nb_id = str(nb)
                nb_ambient = self._systems.get(nb_id, {}).get("safe_jump_temp", 0.0) or 0.0
                new_temp = max(effective_temp, nb_ambient)
                g_new = g_cost + gate_step
                if nb_id not in best or not (best[nb_id][0] <= g_new and best[nb_id][1] <= new_temp):
                    heapq.heappush(heap, (g_new + heuristic(nb_id), g_new, nb_id,
                                          path + [nb_id], edge_types + ["gate"], acc_ly, new_temp))

            # Direct jump neighbours — range gated by current ship temp
            node_range = self._range_at_temp(ship_temp, ambient, profile)
            if node_range < 0.1:
                continue  # Too hot to make any direct jump from here

            for nb_id in self._spatial.within_range(cx, cy, cz, node_range):
                if nb_id == cur_id:
                    continue
                if exclude_direct and nb_id in exclude_direct and nb_id != d_id:
                    continue
                d_jump = self._dist_ly(cur_id, nb_id)
                if cooling_stops:
                    # Assume ship cools to ambient before each jump (planned cooling stop)
                    new_ship_temp = ambient  # reset to origin ambient before jump
                    heat_result = self._heat_after_jump(0.0, ambient, d_jump, profile)
                    if heat_result >= T_MAX:
                        continue  # Even from cold, this single jump overheats
                    nb_ambient = self._systems.get(nb_id, {}).get("safe_jump_temp", 0.0) or 0.0
                    final_temp = nb_ambient  # cooled again at destination
                else:
                    new_ship_temp = self._heat_after_jump(ship_temp, ambient, d_jump, profile)
                    if new_ship_temp >= T_MAX:
                        continue  # Jump would overheat
                    nb_ambient = self._systems.get(nb_id, {}).get("safe_jump_temp", 0.0) or 0.0
                    final_temp = max(new_ship_temp, nb_ambient)
                g_new = g_cost + (d_jump if fuel_mode else 1.0)
                if nb_id not in best or not (best[nb_id][0] <= g_new and best[nb_id][1] <= final_temp):
                    heapq.heappush(heap, (g_new + heuristic(nb_id), g_new, nb_id,
                                          path + [nb_id], edge_types + ["direct"],
                                          acc_ly + d_jump, final_temp))
        return None

    # ------------------------------------------------------------------
    # Hybrid A* router
    # ------------------------------------------------------------------

    def route(self, origin: str, destination: str,
              profile: ShipProfile, cost_mode: str = "jumps") -> dict:
        """
        Find the fuel-cheapest route. Returns a route dict (never None).
        If unreachable, returns a no_route dict.
        """
        self._load()
        o_id = self._by_name.get(origin.lower().strip())
        d_id = self._by_name.get(destination.lower().strip())

        if not o_id or not d_id:
            unknown = origin if not o_id else destination
            log.warning("Route: system not found: %r", unknown)
            return self._no_route(destination, profile, o_id, d_id)

        node_range = self._node_range_ly(o_id, profile)
        log.info("Route %s → %s | mode=%s | origin temp %.1f° | range %.1f LY | %s %s %.0fu",
                 origin, destination, cost_mode,
                 self._systems.get(o_id, {}).get("safe_jump_temp", 0.0),
                 node_range, profile.ship_type or "?", profile.fuel_type, profile.fuel_quantity)

        if o_id == d_id:
            return {
                "type":           "route_planned",
                "path":           [self._name(o_id)],
                "path_ids":       [int(o_id)],
                "jumps":          0,
                "jump_types":     [],
                "total_ly":       0.0,
                "fuel_used":      0.0,
                "fuel_remaining": profile.fuel_quantity,
                "hot_systems":    [],
                "alternative":    None,
                "warnings":       [],
                "hops":           [],
            }

        cooling_required = False
        primary = self._run_astar(o_id, d_id, profile, cost_mode=cost_mode)
        if primary is None:
            # Strict heat tracking failed — try with cooling stops between direct jumps
            primary = self._run_astar(o_id, d_id, profile, cost_mode=cost_mode, cooling_stops=True)
            if primary is not None:
                cooling_required = True
                log.info("Route found with cooling stops: %s → %s", origin, destination)

        if primary is None:
            log.warning("Route: no path found %s → %s", origin, destination)
            return self._no_route(destination, profile, o_id, d_id)

        path_ids, edge_types, total_ly, _final_temp = primary
        log.info("Route found: %d jumps, %.1f LY direct (%d ship jumps, %d gate jumps)",
                 len(path_ids) - 1, total_ly,
                 edge_types.count("direct"), edge_types.count("gate"))

        # Hot intermediates: intermediate nodes (not origin/dest) with temp >= WARM_SYSTEM_TEMP
        hot_sids = [
            sid for sid in path_ids[1:-1]
            if self._systems.get(sid, {}).get("safe_jump_temp", 0.0) >= WARM_SYSTEM_TEMP
        ]
        hot_systems = [self._name(sid) for sid in hot_sids]

        # Alternative route: exclude hot intermediates as direct-jump waypoints
        alternative = None
        if hot_sids:
            exclude = set(hot_sids)
            alt = self._run_astar(o_id, d_id, profile, exclude_direct=exclude,
                                 cost_mode=cost_mode, cooling_stops=cooling_required)
            if alt is not None:
                alt_ids, alt_edges, alt_ly, _alt_temp = alt
                if alt_ids != path_ids:
                    alternative = self._format_result(
                        alt_ids, alt_edges, alt_ly, profile
                    )

        result = self._format_result(path_ids, edge_types, total_ly, profile,
                                     hot_systems=hot_systems, alternative=alternative,
                                     cooling_required=cooling_required)
        result["cost_mode"] = cost_mode
        return result

    def _format_result(
        self,
        path_ids: list,
        edge_types: list,
        total_ly: float,
        profile: ShipProfile,
        hot_systems: Optional[list] = None,
        alternative: Optional[dict] = None,
        cooling_required: bool = False,
    ) -> dict:
        names      = [self._name(sid) for sid in path_ids]
        fuel_used  = round(profile.fuel_for_distance(total_ly), 2)
        fuel_rem   = round(profile.fuel_quantity - fuel_used, 2)
        warnings   = [w for sid in path_ids[1:] if (w := self._security_warning(sid))]
        if cooling_required:
            direct_count = edge_types.count("direct")
            warnings.append(
                f"Route requires cooling stops before each of the {direct_count} direct jump(s). "
                f"Allow heat to dissipate between jumps or use a cooling module."
            )
        if fuel_used > profile.fuel_quantity:
            warnings.append(
                f"fuel needed: {fuel_used:.0f}u — carrying {profile.fuel_quantity:.0f}u "
                f"({fuel_used - profile.fuel_quantity:.0f}u short). Refuel en route."
            )

        # Heat trap: any stop where ambient floor >= NO_JUMP_TEMP means jump drive is inoperable
        dest_id = path_ids[-1]
        for sid in path_ids[1:]:
            floor_temp = self._systems.get(sid, {}).get("safe_jump_temp", 0.0) or 0.0
            if floor_temp >= NO_JUMP_TEMP:
                sys_name = self._name(sid)
                if sid == dest_id:
                    warnings.append(
                        f"Heat trap: {sys_name} floor {floor_temp:.1f}° — "
                        f"jump drive inoperable on arrival. Departure requires gate travel or cooling module."
                    )
                else:
                    warnings.append(
                        f"Heat trap: {sys_name} floor {floor_temp:.1f}° — "
                        f"cannot jump out en route. Gate exit required."
                    )

        # Per-hop breakdown: distance, dest system temp, dest planet count, jump type
        hops = []
        for i, (sid_a, sid_b, jtype) in enumerate(zip(path_ids, path_ids[1:], edge_types)):
            dist_ly = round(self._dist_ly(sid_a, sid_b), 1) if jtype == "direct" else 0.0
            dest    = self._systems.get(sid_b, {})
            hops.append({
                "from":         names[i],
                "to":           names[i + 1],
                "type":         jtype,
                "distance_ly":  dist_ly,
                "dest_temp":    round(dest.get("safe_jump_temp", 0.0), 1),
                "dest_planets": dest.get("planet_count", 0),
            })

        # Origin system metadata
        origin_sys = self._systems.get(path_ids[0], {})

        return {
            "type":           "route_planned",
            "path":           names,
            "path_ids":       [int(sid) for sid in path_ids],
            "jumps":          len(names) - 1,
            "jump_types":     edge_types,
            "total_ly":       round(total_ly, 2),
            "fuel_used":      fuel_used,
            "fuel_remaining": fuel_rem,
            "hot_systems":    hot_systems or [],
            "alternative":    alternative,
            "warnings":       warnings,
            "hops":           hops,
            "origin_temp":    round(origin_sys.get("safe_jump_temp", 0.0), 1),
            "origin_planets": origin_sys.get("planet_count", 0),
        }

    def _reachable_set(self, start_id: str, profile: Optional[ShipProfile] = None,
                       max_systems: int = 5000) -> set:
        """
        BFS to find all systems reachable from start_id using gates + direct jumps.
        If profile is None, uses gates only.
        Caps at max_systems to bound cost.
        """
        visited = {start_id}
        queue = deque([start_id])
        while queue and len(visited) < max_systems:
            cur = queue.popleft()
            # Gate neighbors
            for nb in self._systems.get(cur, {}).get("gate_links", []):
                nb_id = str(nb)
                if nb_id not in visited:
                    visited.add(nb_id)
                    queue.append(nb_id)
            # Direct jump neighbors (if profile provided)
            if profile:
                cx, cy, cz = self._pos_ly(cur)
                node_range = self._node_range_ly(cur, profile)
                if node_range > 0.1:
                    for nb_id in self._spatial.within_range(cx, cy, cz, node_range):
                        if nb_id not in visited:
                            visited.add(nb_id)
                            queue.append(nb_id)
        return visited

    def _find_min_range_needed(self, o_id: str, d_id: str,
                                profile: Optional[ShipProfile] = None) -> tuple:
        """
        Find the minimum direct-jump range needed to escape origin's reachable cluster
        and reach any system outside it (stepping toward destination).

        Returns (min_gap_ly, nearest_origin_node, nearest_outside_node).
        Strategy: expand origin cluster fully, then for each border node use the
        spatial index to find the nearest system NOT in the cluster.
        This correctly finds the narrowest void the ship must cross.
        """
        orig_cluster = self._reachable_set(o_id, profile)

        # If destination is already in the reachable cluster, no gap
        if d_id in orig_cluster:
            return (0.0, o_id, d_id)

        min_dist = float("inf")
        best_a = o_id
        best_b = d_id

        # For each system in the origin cluster, find the nearest system outside it.
        # Use expanding radius search via the spatial index to keep this fast.
        for a_id in orig_cluster:
            ax, ay, az = self._pos_ly(a_id)
            # Search in increasing radii until we find a non-cluster system
            for radius in (50.0, 150.0, 300.0, 600.0, 1500.0, 5000.0, 30000.0):
                candidates = self._spatial.within_range(ax, ay, az, radius)
                outside = [c for c in candidates if c not in orig_cluster and c != a_id]
                if not outside:
                    continue
                # Find nearest outside system
                for b_id in outside:
                    bx, by, bz = self._pos_ly(b_id)
                    d = math.sqrt((ax-bx)**2 + (ay-by)**2 + (az-bz)**2)
                    if d < min_dist:
                        min_dist = d
                        best_a = a_id
                        best_b = b_id
                break  # Found something at this radius, no need to go wider for this node

        return (min_dist, best_a, best_b)

    def _no_route(self, destination: str, profile: ShipProfile,
                  o_id: Optional[str] = None, d_id: Optional[str] = None) -> dict:
        warnings = []
        if o_id and d_id:
            try:
                min_range, nearest_orig, nearest_dest = self._find_min_range_needed(o_id, d_id, profile)
                orig_name = self._name(nearest_orig)
                dest_name = self._name(nearest_dest)
                # Compute effective range at the specific gap node (accounts for ambient temp)
                node_ambient = self._systems.get(nearest_orig, {}).get("safe_jump_temp", 0.0) or 0.0
                effective_range = self._range_at_temp(0.0, node_ambient, profile)
                if min_range == float("inf"):
                    warnings.append(f"No route to {destination}: destination unreachable.")
                elif min_range <= effective_range:
                    warnings.append(
                        f"No route to {destination}: route blocked (heat accumulation or excluded systems). "
                        f"Gap of {min_range:.1f} LY at {orig_name} is technically in range ({effective_range:.1f} LY) "
                        f"but cannot be chained from this approach."
                    )
                else:
                    shortfall = round(min_range - effective_range, 1)
                    warnings.append(
                        f"No route to {destination}: gap of {min_range:.1f} LY between "
                        f"{orig_name} and {dest_name} — effective range at {orig_name} "
                        f"({node_ambient:.1f}° ambient) is {effective_range:.1f} LY "
                        f"({shortfall:.1f} LY short). Need a ship with higher specific heat."
                    )
            except Exception:
                warnings.append(f"No route found to {destination}.")
        else:
            warnings.append(f"No route found to {destination}.")

        return {
            "type":           "no_route",
            "path":           [],
            "path_ids":       [],
            "jumps":          0,
            "jump_types":     [],
            "total_ly":       0.0,
            "fuel_used":      0.0,
            "fuel_remaining": profile.fuel_quantity,
            "hot_systems":    [],
            "alternative":    None,
            "warnings":       warnings,
            "hops":           [],
        }


route_engine = RouteEngine()
