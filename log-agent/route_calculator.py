# log-agent/route_calculator.py
#
# Client-side RouteCalculator. Runs on the Windows gaming PC.
# Downloads systems.json from the server (ETag-cached), builds an in-memory
# graph, runs BFS gate routing, and produces route_planned events.
#
# Usage:
#   calc = RouteCalculator(server_url, server_token, data_dir=".")
#   event = calc.handle_command("/route JITA", current_system="UTR-SN4")
#   if event:
#       send_event(event)  # POST to /log/ingest

import os
import json
import logging
from collections import deque

try:
    import requests
    _HAS_REQUESTS = True
except ImportError:
    _HAS_REQUESTS = False

log = logging.getLogger(__name__)

# Hot star threshold in Kelvin (B and O class — jump disruption risk)
HOT_TEMP_K = 10_000

# "Rich system" threshold — notable for resource gathering / exploration
RICH_PLANET_COUNT = 7

# Planet types worth calling out in highlights
_RESOURCE_TYPES = {"Temperate Planet", "Water-Oceanic Planet", "Lava Planet",
                   "Barren Planet", "Gas Giant"}

_ROUTE_CMD_RE = None  # compiled on first use


def _parse_command(message: str):
    """Parse '/route DESTINATION' from a chat message. Returns dest string or None."""
    import re
    text = message.strip()
    m = re.match(r'^/route\s+(.+)$', text, re.IGNORECASE)
    return m.group(1).strip() if m else None


class RouteCalculator:
    """
    Gate-only BFS router. Loads systems.json from server (ETag-cached).

    Fields added by build_universe.py enrichment (if present):
      star_temperature, hot_system, planet_count, planet_types, lagrange_count
    """

    def __init__(self, server_url: str, server_token: str, data_dir: str = "."):
        self.server_url   = server_url.rstrip("/")
        self.server_token = server_token
        self.cache_path   = os.path.join(data_dir, "systems.json")
        self._etag        = None
        self._loaded      = False

        # Graph structures (populated by _load_from_data)
        self.systems: dict[int, dict]  = {}   # id → system dict
        self.name_index: dict[str, int] = {}  # lowercase name → id

    # ------------------------------------------------------------------
    # Data loading
    # ------------------------------------------------------------------

    def ensure_loaded(self) -> bool:
        """
        Download systems.json if the cached copy is stale or missing.
        Falls back to local cache if server is unreachable.
        Returns True if data is available.
        """
        if not _HAS_REQUESTS:
            log.warning("RouteCalculator: requests not available, loading from cache only")
            if os.path.exists(self.cache_path):
                self._load_from_file()
            return self._loaded

        headers = {"X-Server-Token": self.server_token}
        if self._etag:
            headers["If-None-Match"] = self._etag

        try:
            r = requests.get(
                f"{self.server_url}/data/systems",
                headers=headers,
                timeout=30,
                stream=True,
            )
            if r.status_code == 304:
                log.debug("systems.json up to date (304)")
                if not self._loaded and os.path.exists(self.cache_path):
                    self._load_from_file()
                return self._loaded
            if r.status_code == 200:
                os.makedirs(os.path.dirname(self.cache_path) or ".", exist_ok=True)
                with open(self.cache_path, "wb") as f:
                    for chunk in r.iter_content(chunk_size=65536):
                        f.write(chunk)
                self._etag = r.headers.get("ETag")
                log.info("systems.json downloaded (%d KB)", os.path.getsize(self.cache_path) // 1024)
                self._load_from_file()
                return self._loaded
            log.warning("systems.json download failed: HTTP %d", r.status_code)
        except Exception as e:
            log.warning("systems.json download error: %s", e)

        # Fallback: use cached file if present
        if not self._loaded and os.path.exists(self.cache_path):
            log.info("Using cached systems.json")
            self._load_from_file()
        return self._loaded

    def _load_from_file(self):
        try:
            with open(self.cache_path, encoding="utf-8") as f:
                data = json.load(f)
            self._load_from_data(data)
            log.info("RouteCalculator: loaded %d systems", len(self.systems))
        except Exception as e:
            log.error("RouteCalculator: failed to load systems.json: %s", e)

    def _load_from_data(self, data: dict):
        """Build in-memory graph from systems.json dict."""
        raw = data.get("systems", {})
        self.systems = {}
        self.name_index = {}
        for sid_str, s in raw.items():
            sid = int(sid_str)
            self.systems[sid] = s
            name = s.get("name")
            if name:
                self.name_index[name.lower()] = sid
        self._loaded = bool(self.systems)

    # ------------------------------------------------------------------
    # Routing
    # ------------------------------------------------------------------

    def resolve_name(self, name: str) -> int | None:
        """Case-insensitive system name → ID. Returns None if not found."""
        return self.name_index.get(name.lower().strip())

    def bfs(self, origin_id: int, dest_id: int) -> list[int] | None:
        """
        Gate-only BFS. Returns ordered list of system IDs (origin inclusive)
        or None if no gate path exists.
        """
        if origin_id == dest_id:
            return [origin_id]
        visited = {origin_id}
        queue = deque([(origin_id, [origin_id])])
        while queue:
            current, path = queue.popleft()
            s = self.systems.get(current)
            if not s:
                continue
            for nb_id in (s.get("gate_links") or []):
                nb_id = int(nb_id)
                if nb_id == dest_id:
                    return path + [dest_id]
                if nb_id not in visited:
                    visited.add(nb_id)
                    queue.append((nb_id, path + [nb_id]))
        return None

    def _build_warnings(self, path_ids: list[int]) -> list[str]:
        """Flag hot systems on the route (not origin, not dest)."""
        warnings = []
        for sid in path_ids[1:-1]:  # intermediate hops only
            s = self.systems.get(sid, {})
            if s.get("hot_system"):
                temp = s.get("star_temperature", 0)
                cls  = s.get("spectral_class", "?")
                name = (s.get("name") or str(sid)).upper()
                warnings.append(
                    f"{name}: {cls}-class star ({temp:.0f}K) — jump disruption risk"
                )
        return warnings

    def _build_highlights(self, path_ids: list[int]) -> list[str]:
        """Note planet-rich systems on the route worth stopping at."""
        highlights = []
        for sid in path_ids:
            s = self.systems.get(sid, {})
            count = s.get("planet_count", 0)
            if count >= RICH_PLANET_COUNT:
                types = s.get("planet_types", {})
                # Show up to 3 most common resource types
                notable = [t.replace(" Planet", "").replace(" Giant", "")
                           for t in types if t in _RESOURCE_TYPES][:3]
                name = (s.get("name") or str(sid)).upper()
                type_str = ", ".join(notable) if notable else "mixed"
                highlights.append(
                    f"{name}: {count} planets ({type_str}) — resource-rich"
                )
        return highlights

    def route(self, origin_name: str, dest_name: str) -> dict | None:
        """
        Find a gate route and return a route_planned event dict, or None on failure.
        Includes warnings (hot stars) and highlights (planet-rich systems).
        """
        if not self.ensure_loaded():
            log.warning("RouteCalculator: no system data available")
            return None

        origin_id = self.resolve_name(origin_name)
        dest_id   = self.resolve_name(dest_name)

        if origin_id is None:
            log.warning("RouteCalculator: unknown origin %r", origin_name)
            return {"type": "route_planned", "error": f"Unknown system: {origin_name}",
                    "path": [], "jumps": 0, "warnings": [], "highlights": []}
        if dest_id is None:
            log.warning("RouteCalculator: unknown destination %r", dest_name)
            return {"type": "route_planned", "error": f"Unknown system: {dest_name}",
                    "path": [], "jumps": 0, "warnings": [], "highlights": []}

        path_ids = self.bfs(origin_id, dest_id)
        if path_ids is None:
            log.info("RouteCalculator: no gate path %s → %s", origin_name, dest_name)
            return {
                "type":       "route_planned",
                "origin":     origin_name.lower(),
                "destination": dest_name.lower(),
                "path":       [],
                "jumps":      0,
                "gate_hops":  0,
                "direct_jumps": 0,
                "warnings":   [f"No gate route found to {dest_name.upper()} — systems may be in disconnected clusters"],
                "highlights": [],
                "est_time_min": None,
            }

        path_names = [
            (self.systems[sid].get("name") or str(sid)).lower()
            for sid in path_ids
        ]

        return {
            "type":         "route_planned",
            "origin":       path_names[0],
            "destination":  path_names[-1],
            "path":         path_names,
            "jumps":        len(path_ids) - 1,
            "gate_hops":    len(path_ids) - 1,
            "direct_jumps": 0,
            "warnings":     self._build_warnings(path_ids),
            "highlights":   self._build_highlights(path_ids),
            "est_time_min": None,
        }

    # ------------------------------------------------------------------
    # Command handler (called from log_agent)
    # ------------------------------------------------------------------

    def handle_command(self, message: str, current_system: str | None) -> dict | None:
        """
        Parse a /route command from chat and return a route_planned event.
        Returns None if the message is not a /route command.
        """
        dest = _parse_command(message)
        if dest is None:
            return None

        origin = current_system or ""
        if not origin:
            log.warning("RouteCalculator: /route called but current system unknown")
            return {
                "type": "route_planned",
                "error": "Current system unknown — jump to a system first",
                "path": [], "jumps": 0, "warnings": [], "highlights": [],
            }

        log.info("RouteCalculator: /route %s → %s", origin, dest)
        return self.route(origin, dest)
