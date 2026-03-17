"""
Client-side radius search for Windows log-agent.

Provides lightweight local radius search without killmails or structures
(server-only features). Loads systems from shared systems.json and calculates
spatial queries client-side.
"""

import os
import json
import math
import logging
from typing import Optional, Dict, List, Union

log = logging.getLogger(__name__)

# Module-level instance (lazy-loaded)
_radius_calculator = None


class ClientRadiusCalculator:
    """
    Lightweight client-side radius search calculator.

    Loads systems.json from parent/data/systems.json and provides
    spatial distance calculations + local filtering (planets, heat only).
    No killmails or structures (server-only).
    """

    def __init__(self, systems_path: str = None):
        """
        Initialize ClientRadiusCalculator.

        Args:
            systems_path: Optional path to systems.json.
                         Defaults to ../data/systems.json relative to this file.
        """
        if systems_path is None:
            # Resolve relative to log-agent directory
            log_agent_dir = os.path.dirname(os.path.abspath(__file__))
            systems_path = os.path.normpath(
                os.path.join(log_agent_dir, "..", "data", "systems.json")
            )
        self.systems_path = systems_path
        self.systems: Dict[str, dict] = {}  # {system_id: {name, x, y, z, ...}}
        self._load_systems()

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

    def search(
        self,
        center_system: str,
        radius_ly: float,
        filters: Optional[List[str]] = None,
        top_n: int = 10,
        skip_heat_traps: bool = False,
    ) -> dict:
        """
        Search for systems within a radius and filter by criteria.

        Args:
            center_system: Center system name (e.g., "UR8-K7K")
            radius_ly: Search radius in light-years
            filters: List of filter types to apply: ["planets", "heat"]
                     (Client supports only planets and heat; no killmails or structures)
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
                    "heat": { "count": 5, "systems": [...] }
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

            elif filter_type == "heat":
                result["filters"]["heat"] = self._filter_heat(all_systems, effective_top_n)

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


def init_radius_calculator(systems_path: str = None) -> ClientRadiusCalculator:
    """
    Initialize the module-level radius calculator instance.

    Args:
        systems_path: Optional path to systems.json

    Returns:
        The global ClientRadiusCalculator instance
    """
    global _radius_calculator
    _radius_calculator = ClientRadiusCalculator(systems_path=systems_path)
    return _radius_calculator


def search(
    center_system: str,
    radius_ly: float,
    filters: Optional[List[str]] = None,
    top_n: int = 10,
    skip_heat_traps: bool = False,
) -> dict:
    """
    Convenience function to search using the module-level instance.

    Requires init_radius_calculator() to have been called first.

    Args:
        center_system: Center system name
        radius_ly: Search radius in light-years
        filters: List of filter types: ["planets", "heat"]
        top_n: Maximum results per filter
        skip_heat_traps: Exclude warm/hot systems

    Returns:
        Search result dict
    """
    global _radius_calculator
    if _radius_calculator is None:
        raise RuntimeError("Radius calculator not initialized. Call init_radius_calculator() first.")
    return _radius_calculator.search(
        center_system=center_system,
        radius_ly=radius_ly,
        filters=filters,
        top_n=top_n,
        skip_heat_traps=skip_heat_traps,
    )
