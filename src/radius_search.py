"""
Radius search module for EVE Frontier structures.

Provides spatial querying of structures within a given distance from a reference system.
"""

import os
import json
import logging
import math
import time
from typing import Optional, Dict, List, Union

from src.world_api import world_api

log = logging.getLogger(__name__)

# Path to structure locations cache
_STRUCTURE_LOCATIONS_PATH = os.path.join(
    os.path.dirname(__file__), "..", "data", "structure_locations.json"
)

# Backward compatibility export
structure_locations_path = _STRUCTURE_LOCATIONS_PATH


class RadiusSearch:
    """
    Spatial index and search engine for EVE Frontier structures.

    Loads structure locations from disk cache, calculates distances,
    and returns filtered results within a given radius.
    """

    def __init__(self, systems_path: str = None, structure_locations_path: str = None):
        """
        Initialize RadiusSearch.

        Args:
            systems_path: Optional path to systems.json. Defaults to data/systems.json.
            structure_locations_path: Optional path to structure_locations.json.
                                     Defaults to data/structure_locations.json.
        """
        self.systems_path = systems_path or os.path.normpath(
            os.path.join(os.path.dirname(__file__), "..", "data", "systems.json")
        )
        self.structure_locations_path = structure_locations_path or _STRUCTURE_LOCATIONS_PATH
        self.systems: Dict[str, dict] = {}  # {system_id: {name, x, y, z, ...}}
        self.structure_locations: Dict[str, dict] = {}  # {...}
        self.world_api_client = world_api
        self._load_systems()
        self._load_structure_locations()

    def _load_systems(self) -> None:
        """Load systems from systems.json."""
        try:
            with open(self.systems_path, 'r') as f:
                data = json.load(f)
            if 'systems' in data and isinstance(data['systems'], dict):
                self.systems = data['systems']
                log.info(f"Loaded {len(self.systems)} systems from {self.systems_path}")
            else:
                log.warning(f"systems.json missing 'systems' key or it's not a dict")
        except FileNotFoundError:
            log.warning(f"systems.json not found at {self.systems_path}")
        except json.JSONDecodeError:
            log.error(f"Invalid JSON in {self.systems_path}")
        except Exception as e:
            log.error(f"Error loading systems: {e}")

    def _load_structure_locations(self) -> None:
        """Load structure locations from disk."""
        try:
            with open(self.structure_locations_path, 'r') as f:
                data = json.load(f)
            if 'structure_locations' in data and isinstance(data['structure_locations'], dict):
                self.structure_locations = data['structure_locations']
                log.info(f"Loaded {len(self.structure_locations)} structure locations")
            else:
                # If key doesn't exist or isn't a dict, initialize to empty
                self.structure_locations = {}
                log.debug(f"structure_locations.json structure_locations key empty or missing")
        except FileNotFoundError:
            log.warning(f"structure_locations.json not found at {self.structure_locations_path}")
            self.structure_locations = {}
        except json.JSONDecodeError:
            log.error(f"Invalid JSON in {self.structure_locations_path}")
            self.structure_locations = {}
        except Exception as e:
            log.error(f"Error loading structure locations: {e}")
            self.structure_locations = {}

    def get_system(self, name_or_id: Union[str, int]) -> Optional[dict]:
        """
        Lookup a system by name (case-insensitive) or ID.

        Args:
            name_or_id: System name (string, case-insensitive) or system ID (int or str).

        Returns:
            System dict if found, None otherwise.
        """
        # Try direct ID lookup first
        system_id_str = str(name_or_id)
        if system_id_str in self.systems:
            return self.systems[system_id_str]

        # If it's not an ID match, try case-insensitive name lookup
        if isinstance(name_or_id, str):
            name_lower = name_or_id.lower()
            for system_id, system_data in self.systems.items():
                if isinstance(system_data, dict):
                    system_name = system_data.get('name')
                    if system_name and isinstance(system_name, str) and system_name.lower() == name_lower:
                        return system_data

        return None

    def _distance_ly(self, sys_a: dict, sys_b: dict) -> float:
        """
        Calculate Euclidean distance between two systems in light-years.

        EVE coordinates are in meters. 1 light-year = 9.461e15 meters.

        Args:
            sys_a: System dict with optional x, y, z keys (defaults to 0 if missing)
            sys_b: System dict with optional x, y, z keys (defaults to 0 if missing)

        Returns:
            Distance in light-years as a float.
        """
        # Light-year in meters
        ly_in_meters = 9.461e15

        # Extract coordinates, defaulting to 0 if missing
        x_a = sys_a.get('x', 0)
        y_a = sys_a.get('y', 0)
        z_a = sys_a.get('z', 0)

        x_b = sys_b.get('x', 0)
        y_b = sys_b.get('y', 0)
        z_b = sys_b.get('z', 0)

        # Calculate Euclidean distance in meters
        dx = x_b - x_a
        dy = y_b - y_a
        dz = z_b - z_a

        distance_m = math.sqrt(dx**2 + dy**2 + dz**2)

        # Convert to light-years
        distance_ly = distance_m / ly_in_meters

        return distance_ly

    def classify_heat(self, system: dict) -> str:
        """
        Classify a system by temperature.

        Returns: "cool" (< 70°), "warm" (70–89°), or "hot" (>= 90°)
        """
        temp = system.get("safe_jump_temp", 0)
        if temp is None:
            temp = 0
        if temp >= 90:
            return "hot"
        elif temp >= 70:
            return "warm"
        else:
            return "cool"

    def count_planets(self, system: dict) -> int:
        """Count planets in a system from planet_ids."""
        planet_ids = system.get("planet_ids", [])
        return len(planet_ids) if planet_ids else 0

    def is_heat_trap(self, system: dict) -> bool:
        """Return True if system is warm (>= 70°) or hot (>= 90°)."""
        temp = system.get("safe_jump_temp", 0)
        if temp is None:
            temp = 0
        return temp >= 70

    def find_systems_within_radius(
        self, center_name: str, radius_ly: float
    ) -> List[dict]:
        """
        Find all systems within a radius from a center system.

        Args:
            center_name: Name of the center system (case-insensitive)
            radius_ly: Search radius in light-years

        Returns:
            List of systems within radius, sorted by distance (closest first).
            Each system includes an added "distance_ly" field.
            Returns empty list if center system not found or has no coordinates.
        """
        # Find the center system
        center_system = self.get_system(center_name)
        if center_system is None:
            return []

        # Check if center system has coordinates
        if not all(key in center_system for key in ['x', 'y', 'z']):
            return []

        # Find all systems within radius
        results = []
        for system_id, system_data in self.systems.items():
            if not isinstance(system_data, dict):
                continue

            # Skip systems without coordinates
            if not all(key in system_data for key in ['x', 'y', 'z']):
                continue

            # Calculate distance
            distance = self._distance_ly(center_system, system_data)

            # Include if within radius
            if distance <= radius_ly:
                # Add distance_ly field to the result
                result_system = dict(system_data)
                result_system['distance_ly'] = distance
                results.append(result_system)

        # Sort by distance (closest first)
        results.sort(key=lambda s: s['distance_ly'])

        return results

    def load_structures(self) -> int:
        """
        Load structures from cache file.

        Returns:
            Number of structures loaded.
        """
        raise NotImplementedError("Feature not yet implemented")

    # ------------------------------------------------------------------
    # Killmail methods
    # ------------------------------------------------------------------

    async def get_killmails_for_system(self, system_id: int, hours: int = 24) -> list:
        """Fetch killmails for a system and filter by recency.

        Args:
            system_id: Solar system ID to fetch killmails for
            hours: Window in hours to filter by (default 24)

        Returns:
            List of top 10 killmails sorted by most recent first,
            or empty list on API errors
        """
        if not self.world_api_client:
            log.warning("world_api_client not initialized")
            return []

        try:
            killmails = await self.world_api_client.get_killmails(system_id)
            if not killmails:
                return []

            filtered = self.filter_killmails_by_recency(killmails, hours)
            return filtered[:10]
        except Exception as e:
            log.warning("get_killmails_for_system(%d) failed: %s", system_id, e)
            return []

    def filter_killmails_by_recency(self, killmails: list, hours: int) -> list:
        """Filter killmails by timestamp within a hours window.

        Args:
            killmails: List of killmail dicts with 'timestamp' field
            hours: Number of hours to include (from now backwards)

        Returns:
            List of killmails within window, sorted by recency (newest first)
        """
        if not killmails:
            return []

        now = time.time()
        cutoff = now - (hours * 3600)

        filtered = []
        for km in killmails:
            if not isinstance(km, dict):
                continue
            ts = km.get("timestamp")
            if ts is None:
                continue
            # Handle both Unix timestamps (seconds) and milliseconds
            ts_seconds = ts / 1000 if ts > 100000000000 else ts
            if ts_seconds >= cutoff:
                filtered.append(km)

        # Sort by timestamp descending (newest first)
        filtered.sort(key=lambda km: km.get("timestamp", 0), reverse=True)
        return filtered

    def get_most_recent_killmail_timestamp(self, killmails: list) -> Optional[float]:
        """Get the most recent killmail timestamp from a list.

        Args:
            killmails: List of killmail dicts with 'timestamp' field

        Returns:
            Most recent timestamp as float, or None if list is empty
        """
        if not killmails:
            return None

        timestamps = []
        for km in killmails:
            if isinstance(km, dict):
                ts = km.get("timestamp")
                if ts is not None:
                    timestamps.append(ts)

        return max(timestamps) if timestamps else None

    async def search(
        self,
        center_system: str,
        radius_ly: float,
        filters: Optional[List[str]] = None,
        killmail_hours: int = 24,
        top_n: int = 10,
        skip_heat_traps: bool = False,
    ) -> dict:
        """
        Search for systems within a radius and filter by criteria.

        Args:
            center_system: Center system name (e.g., "UR8-K7K")
            radius_ly: Search radius in light-years
            filters: List of filter types to apply: ["planets", "killmails", "heat", "structures"]
            killmail_hours: Killmail lookback period (default 24)
            top_n: How many results per filter (default 10)
            skip_heat_traps: If True, exclude warm/hot systems (>= 70°)

        Returns:
            Dict with structure:
            {
                "center": "UR8-K7K",
                "radius_ly": 100,
                "total_systems": 156,
                "scan_summary": "156 systems within 100 LY",
                "filters": {
                    "planets": { "count": 10, "systems": [...] },
                    "killmails": { "count": 3, "systems": [...] },
                    "heat": { "count": 5, "systems": [...] },
                    "structures": { "count": 2, "systems": [...] }
                }
            }
        """
        filters = filters or []

        # Find all systems within radius
        all_systems = self.find_systems_within_radius(center_system, radius_ly)

        if not all_systems:
            return {
                "center": center_system,
                "radius_ly": radius_ly,
                "total_systems": 0,
                "scan_summary": f"0 systems within {radius_ly} LY",
                "filters": {}
            }

        # Apply skip_heat_traps if requested
        if skip_heat_traps:
            all_systems = [s for s in all_systems if not self.is_heat_trap(s)]

        result = {
            "center": center_system,
            "radius_ly": radius_ly,
            "total_systems": len(all_systems),
            "scan_summary": f"{len(all_systems)} systems within {radius_ly} LY",
            "filters": {}
        }

        # Thresholding: if < 20 systems, return all; otherwise limit to top N per filter
        threshold = 20
        effective_top_n = len(all_systems) if len(all_systems) < threshold else top_n

        # Apply filters
        for filter_type in filters:
            if filter_type == "planets":
                result["filters"]["planets"] = self._filter_planets(all_systems, effective_top_n)

            elif filter_type == "killmails":
                # Async call
                result["filters"]["killmails"] = await self._filter_killmails(all_systems, effective_top_n, killmail_hours)

            elif filter_type == "heat":
                result["filters"]["heat"] = self._filter_heat(all_systems, effective_top_n)

            elif filter_type == "structures":
                # Structures are only included if requested
                result["filters"]["structures"] = self._filter_structures(all_systems, effective_top_n)

        return result

    def _filter_planets(self, systems: List[dict], top_n: int) -> dict:
        """
        Filter systems by planet count (highest first).

        Args:
            systems: List of systems to filter
            top_n: Maximum number of systems to return

        Returns:
            Dict with "count" and "systems" keys
        """
        systems_with_planets = [
            {
                **sys,
                "planets": self.count_planets(sys)
            }
            for sys in systems
        ]

        # Sort by planet count descending
        sorted_sys = sorted(systems_with_planets, key=lambda s: s["planets"], reverse=True)

        return {
            "count": len([s for s in systems_with_planets if s["planets"] > 0]),
            "systems": [
                {
                    "name": s["name"],
                    "distance_ly": s["distance_ly"],
                    "planets": s["planets"],
                    "safe_jump_temp": s.get("safe_jump_temp", 0)
                }
                for s in sorted_sys[:top_n]
            ]
        }

    async def _filter_killmails(self, systems: List[dict], top_n: int, hours: int) -> dict:
        """
        Filter systems by recent killmails (most kills first).

        Args:
            systems: List of systems to filter
            top_n: Maximum number of systems to return
            hours: Lookback window in hours

        Returns:
            Dict with "count" and "systems" keys
        """
        systems_with_kills = []

        for sys in systems:
            sys_id = sys.get("id")
            if not sys_id:
                continue

            killmails = await self.get_killmails_for_system(sys_id, hours=hours)
            if killmails:
                most_recent_ts = self.get_most_recent_killmail_timestamp(killmails)
                systems_with_kills.append({
                    "system": sys,
                    "kill_count": len(killmails),
                    "most_recent_ts": most_recent_ts
                })

        # Sort by kill count descending
        sorted_sys = sorted(systems_with_kills, key=lambda s: s["kill_count"], reverse=True)

        return {
            "count": len(systems_with_kills),
            "systems": [
                {
                    "name": s["system"]["name"],
                    "distance_ly": s["system"]["distance_ly"],
                    "kills": s["kill_count"],
                    "most_recent_kill_hours_ago": self._hours_since(s["most_recent_ts"])
                }
                for s in sorted_sys[:top_n]
            ]
        }

    def _filter_heat(self, systems: List[dict], top_n: int) -> dict:
        """
        Filter systems by heat level (warm/hot systems only).

        Args:
            systems: List of systems to filter
            top_n: Maximum number of systems to return

        Returns:
            Dict with "count" and "systems" keys
        """
        heat_trap_systems = [
            {
                **sys,
                "heat_class": self.classify_heat(sys)
            }
            for sys in systems if self.is_heat_trap(sys)
        ]

        # Sort by temp descending (hottest first)
        sorted_sys = sorted(heat_trap_systems, key=lambda s: s.get("safe_jump_temp", 0), reverse=True)

        return {
            "count": len(heat_trap_systems),
            "systems": [
                {
                    "name": s["name"],
                    "distance_ly": s["distance_ly"],
                    "safe_jump_temp": s.get("safe_jump_temp", 0),
                    "heat_class": s["heat_class"]
                }
                for s in sorted_sys[:top_n]
            ]
        }

    def _filter_structures(self, systems: List[dict], top_n: int) -> dict:
        """
        Filter systems that have recorded structures.

        Args:
            systems: List of systems to filter
            top_n: Maximum number of systems to return

        Returns:
            Dict with "count" and "systems" keys
        """
        systems_with_structures = []

        for sys in systems:
            sys_name = sys.get("name", "")
            structures_in_sys = [
                {
                    "structure_id": struct_id,
                    **struct_data
                }
                for struct_id, struct_data in self.structure_locations.items()
                if struct_data.get("system_name", "").upper() == sys_name.upper()
            ]

            if structures_in_sys:
                systems_with_structures.append({
                    "system": sys,
                    "structures": structures_in_sys
                })

        # Sort by distance ascending (closest first)
        sorted_sys = sorted(systems_with_structures, key=lambda s: s["system"]["distance_ly"])

        return {
            "count": len(systems_with_structures),
            "systems": [
                {
                    "name": s["system"]["name"],
                    "distance_ly": s["system"]["distance_ly"],
                    "structures": s["structures"]
                }
                for s in sorted_sys[:top_n]
            ]
        }

    def _hours_since(self, timestamp: Optional[float]) -> Optional[float]:
        """
        Return hours elapsed since timestamp.

        Args:
            timestamp: Unix timestamp (seconds)

        Returns:
            Hours elapsed, rounded to 1 decimal place, or None if timestamp is None/0
        """
        if not timestamp:
            return None
        return round((time.time() - timestamp) / 3600, 1)

    async def _save_structure_locations(self) -> None:
        """
        Save structure locations to disk.

        Writes structure_locations dict to JSON file with built_at timestamp.
        Creates parent directory if needed. Logs success and errors appropriately.
        """
        try:
            # Ensure parent directory exists
            parent_dir = os.path.dirname(self.structure_locations_path)
            if parent_dir:
                os.makedirs(parent_dir, exist_ok=True)

            # Prepare data with timestamp
            data = {
                "structure_locations": self.structure_locations,
                "built_at": time.time(),
            }

            # Write to file
            with open(self.structure_locations_path, 'w') as f:
                json.dump(data, f, indent=2)

            log.info(f"Saved {len(self.structure_locations)} structures to {self.structure_locations_path}")
        except Exception as e:
            log.error(f"Error saving structure locations: {e}")
