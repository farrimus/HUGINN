# src/route_engine.py
import json
import os
import math
import logging
import bisect
import heapq
from collections import deque
from typing import Optional

from src.ship_profile import ShipProfile, T_MAX, HEAT_CONSTANT

log = logging.getLogger(__name__)

SYSTEMS_PATH = os.path.normpath(
    os.path.join(os.path.dirname(__file__), "..", "data", "systems.json")
)

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

    def _load(self):
        try:
            mtime = os.path.getmtime(SYSTEMS_PATH)
        except FileNotFoundError:
            return
        if mtime <= self._mtime:
            return
        try:
            with open(SYSTEMS_PATH, encoding="utf-8") as f:
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

    def _node_range_ly(self, sid: str, profile: ShipProfile) -> float:
        """Compute direct-jump range (LY) from a given system node.

        Uses safe_jump_temp from systems.json (the ambient node temperature).
        profile.external_temp is intentionally not used here — that field
        reflects the player's current actual temperature, not the node's
        ambient temperature used for route planning.
        """
        temp = self._systems.get(sid, {}).get("safe_jump_temp", 0.0)
        if temp >= 90.0:
            return 0.0
        c_eff = profile.specific_heat * (1.0 + profile.adaptive_level * 0.02)
        cur_mass = profile.hull_mass + profile.extra_cargo_kg
        return ((T_MAX - temp) * c_eff * profile.hull_mass) / (HEAT_CONSTANT * cur_mass)

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
    ) -> Optional[tuple]:
        """
        Hybrid A* / Dijkstra router.

        cost_mode="jumps" (default):
            Minimise hop count. Gates and direct jumps both cost 1.
            Heuristic: straight-line dist / max possible range.

        cost_mode="fuel":
            Minimise total direct-jump LY (Dijkstra).
            Gate hops cost 0. Direct jumps cost their distance in LY.
            Heuristic: 0 (pure Dijkstra — gates make any lower bound inadmissible).

        Returns (path_ids, edge_types, total_ly) or None.
        """
        c_eff = profile.specific_heat * (1.0 + profile.adaptive_level * 0.02)
        cur_mass = profile.hull_mass + profile.extra_cargo_kg
        global_max_range = (T_MAX * c_eff * profile.hull_mass) / (HEAT_CONSTANT * cur_mass) if cur_mass > 0 else 0.0

        dx, dy, dz = self._pos_ly(d_id)
        fuel_mode = (cost_mode == "fuel")

        def heuristic(sid: str) -> float:
            if fuel_mode:
                return 0.0  # gates are free → no admissible lower bound on fuel
            x, y, z = self._pos_ly(sid)
            dist = math.sqrt((x - dx)**2 + (y - dy)**2 + (z - dz)**2)
            if global_max_range <= 0:
                return float("inf")
            return dist / global_max_range

        # heap: (f, g_cost, sid, path_ids, edge_types, acc_ly)
        # g_cost = jump count (jumps mode) or accumulated LY (fuel mode)
        heap = [(heuristic(o_id), 0.0, o_id, [o_id], [], 0.0)]
        best: dict = {}  # sid → best g_cost seen

        while heap:
            f, g_cost, cur_id, path, edge_types, acc_ly = heapq.heappop(heap)

            if cur_id == d_id:
                return (path, edge_types, acc_ly)

            if cur_id in best and best[cur_id] <= g_cost:
                continue
            best[cur_id] = g_cost

            cx, cy, cz = self._pos_ly(cur_id)

            # Gate neighbours — free in fuel mode, 1 jump in jumps mode
            gate_step = 0.0 if fuel_mode else 1.0
            for nb in self._systems.get(cur_id, {}).get("gate_links", []):
                nb_id = str(nb)
                g_new = g_cost + gate_step
                if nb_id not in best or best[nb_id] > g_new:
                    heapq.heappush(heap, (g_new + heuristic(nb_id), g_new, nb_id,
                                          path + [nb_id], edge_types + ["gate"], acc_ly))

            # Direct jump neighbours
            node_range = self._node_range_ly(cur_id, profile)
            if node_range > 0.0:
                for nb_id in self._spatial.within_range(cx, cy, cz, node_range):
                    if nb_id == cur_id:
                        continue
                    if exclude_direct and nb_id in exclude_direct and nb_id != d_id:
                        continue
                    d_jump = self._dist_ly(cur_id, nb_id)
                    g_new = g_cost + (d_jump if fuel_mode else 1.0)
                    if nb_id not in best or best[nb_id] > g_new:
                        heapq.heappush(heap, (g_new + heuristic(nb_id), g_new, nb_id,
                                              path + [nb_id], edge_types + ["direct"],
                                              acc_ly + d_jump))
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
            return self._no_route(destination, profile)

        node_range = self._node_range_ly(o_id, profile)
        log.info("Route %s → %s | mode=%s | origin temp %.1f° | range %.1f LY | %s %s %.0fu",
                 origin, destination, cost_mode,
                 self._systems.get(o_id, {}).get("safe_jump_temp", 0.0),
                 node_range, profile.ship_type or "?", profile.fuel_type, profile.fuel_quantity)

        if o_id == d_id:
            return {
                "type":           "route_planned",
                "path":           [self._name(o_id)],
                "jumps":          0,
                "jump_types":     [],
                "total_ly":       0.0,
                "fuel_used":      0.0,
                "fuel_remaining": profile.fuel_quantity,
                "hot_systems":    [],
                "alternative":    None,
                "warnings":       [],
            }

        primary = self._run_astar(o_id, d_id, profile, cost_mode=cost_mode)
        if primary is None:
            log.warning("Route: no path found %s → %s", origin, destination)
            return self._no_route(destination, profile)

        path_ids, edge_types, total_ly = primary
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
            alt = self._run_astar(o_id, d_id, profile, exclude_direct=exclude, cost_mode=cost_mode)
            if alt is not None:
                alt_ids, alt_edges, alt_ly = alt
                if alt_ids != path_ids:
                    alternative = self._format_result(
                        alt_ids, alt_edges, alt_ly, profile
                    )

        result = self._format_result(path_ids, edge_types, total_ly, profile,
                                     hot_systems=hot_systems, alternative=alternative)
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
    ) -> dict:
        names      = [self._name(sid) for sid in path_ids]
        fuel_used  = round(profile.fuel_for_distance(total_ly), 2)
        fuel_rem   = round(profile.fuel_quantity - fuel_used, 2)
        warnings   = [w for sid in path_ids[1:] if (w := self._security_warning(sid))]
        if fuel_used > profile.fuel_quantity:
            warnings.append(
                f"fuel needed: {fuel_used:.0f}u — carrying {profile.fuel_quantity:.0f}u "
                f"({fuel_used - profile.fuel_quantity:.0f}u short). Refuel en route."
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

    def _no_route(self, destination: str, profile: ShipProfile) -> dict:
        return {
            "type":           "no_route",
            "path":           [],
            "jumps":          0,
            "jump_types":     [],
            "total_ly":       0.0,
            "fuel_used":      0.0,
            "fuel_remaining": profile.fuel_quantity,
            "hot_systems":    [],
            "alternative":    None,
            "warnings":       [f"No route found to {destination}"],
        }


route_engine = RouteEngine()
