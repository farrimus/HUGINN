# src/route_engine.py
import json
import os
import math
import logging
import bisect
from collections import deque
from typing import Optional

from src.ship_profile import ShipProfile

log = logging.getLogger(__name__)

SYSTEMS_PATH = os.path.normpath(
    os.path.join(os.path.dirname(__file__), "..", "data", "systems.json")
)

LY_METERS = 9_460_000_000_000_000.0  # 1 light-year in meters


class _SpatialIndex:
    """
    Lightweight 3D spatial index: sorts systems by X and uses binary search
    to narrow range candidates before checking exact distance. No dependencies.
    """
    def __init__(self):
        # sorted list of (x, y, z, system_id_str)
        self._xs: list[float] = []
        self._data: list[tuple] = []  # (x, y, z, sid)

    def build(self, systems: dict):
        entries = []
        for sid, s in systems.items():
            x, y, z = s.get("x", 0), s.get("y", 0), s.get("z", 0)
            entries.append((x, y, z, sid))
        entries.sort(key=lambda e: e[0])
        self._data = entries
        self._xs   = [e[0] for e in entries]

    def within_range(self, cx: float, cy: float, cz: float, r: float) -> list[str]:
        """Return system IDs within Euclidean distance r of (cx, cy, cz)."""
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
        self._systems: dict  = {}   # id (str) → system dict
        self._by_name: dict  = {}   # lowercase name → id (str)
        self._spatial        = _SpatialIndex()
        self._mtime: float   = 0.0

    # ------------------------------------------------------------------
    # Loading
    # ------------------------------------------------------------------

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
            self._spatial.build(self._systems)
            self._mtime = mtime
            log.info("systems.json loaded: %d systems", len(self._systems))
        except Exception as e:
            log.warning("Failed to load systems.json: %s", e)

    def ready(self) -> bool:
        self._load()
        return bool(self._systems)

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def resolve(self, name: str) -> Optional[str]:
        """Return system ID (str) for a name, or None."""
        self._load()
        return self._by_name.get(name.lower().strip())

    def system_info(self, name: str) -> Optional[dict]:
        self._load()
        sid = self._by_name.get(name.lower().strip())
        return self._systems.get(sid) if sid else None

    def _dist(self, sid_a: str, sid_b: str) -> float:
        a = self._systems.get(sid_a)
        b = self._systems.get(sid_b)
        if not (a and b):
            return math.inf
        dx, dy, dz = a["x"] - b["x"], a["y"] - b["y"], a["z"] - b["z"]
        return math.sqrt(dx*dx + dy*dy + dz*dz)

    def _pos(self, sid: str) -> tuple:
        s = self._systems.get(sid, {})
        return s.get("x", 0), s.get("y", 0), s.get("z", 0)

    def _name(self, sid: str) -> str:
        return self._systems.get(sid, {}).get("name", sid)

    def _security_warning(self, sid: str) -> Optional[str]:
        s = self._systems.get(sid, {})
        sec = s.get("security")
        if sec is not None and float(sec) <= 0.0:
            return f"{self._name(sid)} is null-sec"
        return None

    # ------------------------------------------------------------------
    # Gate-only BFS (free, no ship params needed)
    # ------------------------------------------------------------------

    def bfs(self, origin: str, destination: str) -> Optional[dict]:
        """Shortest gate-hop route. Returns None if no gate path exists."""
        self._load()
        o_id = self._by_name.get(origin.lower().strip())
        d_id = self._by_name.get(destination.lower().strip())
        if not o_id or not d_id:
            return None
        if o_id == d_id:
            return {"path": [self._name(o_id)], "jumps": 0,
                    "gate_hops": 0, "direct_jumps": 0, "warnings": []}

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
                    return {"path": names, "jumps": len(names) - 1,
                            "gate_hops": len(names) - 1, "direct_jumps": 0,
                            "warnings": warnings}
                visited.add(nb_id)
                queue.append(full)
        return None

    # ------------------------------------------------------------------
    # Hybrid A* router (gate hops free + direct jumps cost fuel)
    # ------------------------------------------------------------------

    def route(self, origin: str, destination: str,
              profile: ShipProfile) -> Optional[dict]:
        """
        Find the fuel-cheapest route using gate hops (free) and direct jumps.
        Uses A* with 3D Euclidean heuristic.
        Returns None if destination is unreachable within fuel budget.
        """
        import heapq

        self._load()
        o_id = self._by_name.get(origin.lower().strip())
        d_id = self._by_name.get(destination.lower().strip())
        if not o_id or not d_id:
            log.warning("Route: system not found (%s → %s)", origin, destination)
            return None

        if o_id == d_id:
            return {"path": [self._name(o_id)], "jumps": 0,
                    "gate_hops": 0, "direct_jumps": 0,
                    "total_distance_m": 0.0, "fuel_used": 0.0,
                    "fuel_remaining": profile.fuel_quantity,
                    "warnings": []}

        jump_range   = profile.jump_range()
        fuel_budget  = profile.fuel_budget()

        if jump_range <= 0:
            return None  # can't jump (too hot or no thermal capacity)

        dx, dy, dz = self._pos(d_id)

        def heuristic(sid: str) -> float:
            x, y, z = self._pos(sid)
            return math.sqrt((x - dx)**2 + (y - dy)**2 + (z - dz)**2)

        # heap: (f, g_dist, system_id, path_list, edge_types)
        # g_dist = total direct-jump distance so far (gate hops are free)
        start_h = heuristic(o_id)
        heap    = [(start_h, 0.0, o_id, [o_id], [])]
        best    = {}  # sid → best g_dist seen

        while heap:
            f, g, cur_id, path, edge_types = heapq.heappop(heap)

            if cur_id == d_id:
                names    = [self._name(s) for s in path]
                gate_h   = edge_types.count("gate")
                direct_h = edge_types.count("direct")
                fuel_used = profile.fuel_for_distance(g)
                warnings = [w for s in path[1:] if (w := self._security_warning(s))]
                if fuel_used > profile.fuel_quantity:
                    warnings.append("insufficient fuel for this route")
                return {
                    "path":            names,
                    "jumps":           len(names) - 1,
                    "gate_hops":       gate_h,
                    "direct_jumps":    direct_h,
                    "total_distance_m": g,
                    "total_distance_ly": g / LY_METERS,
                    "fuel_used":       round(fuel_used, 2),
                    "fuel_remaining":  round(profile.fuel_quantity - fuel_used, 2),
                    "warnings":        warnings,
                }

            if cur_id in best and best[cur_id] <= g:
                continue
            best[cur_id] = g

            cx, cy, cz = self._pos(cur_id)

            # --- Gate neighbours (cost 0) ---
            for nb in self._systems.get(cur_id, {}).get("gate_links", []):
                nb_id = str(nb)
                if nb_id not in best or best[nb_id] > g:
                    f_new = g + heuristic(nb_id)
                    heapq.heappush(heap, (f_new, g, nb_id,
                                          path + [nb_id], edge_types + ["gate"]))

            # --- Direct jump neighbours (cost = distance) ---
            if g < fuel_budget:
                for nb_id in self._spatial.within_range(cx, cy, cz, jump_range):
                    if nb_id == cur_id:
                        continue
                    d_jump = self._dist(cur_id, nb_id)
                    g_new  = g + d_jump
                    if g_new > fuel_budget:
                        continue
                    if nb_id not in best or best[nb_id] > g_new:
                        f_new = g_new + heuristic(nb_id)
                        heapq.heappush(heap, (f_new, g_new, nb_id,
                                              path + [nb_id], edge_types + ["direct"]))

        return None  # unreachable


route_engine = RouteEngine()
