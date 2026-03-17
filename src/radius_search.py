"""
Radius search module for EVE Frontier structures.

Provides spatial querying of structures within a given distance from a reference system.
"""

import os
import json
import logging
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

    def load_structures(self) -> int:
        """
        Load structures from cache file.

        Returns:
            Number of structures loaded.
        """
        raise NotImplementedError("Feature not yet implemented")

    async def search(
        self,
        system_name: str,
        radius_ly: float,
        heat_threshold: Optional[float] = None,
        planet_threshold: Optional[int] = None,
    ) -> List[dict]:
        """
        Search for structures within radius of a system.

        Args:
            system_name: Reference system name
            radius_ly: Search radius in light-years
            heat_threshold: Minimum star temperature (optional)
            planet_threshold: Minimum planet count (optional)

        Returns:
            List of matching structures with metadata.
        """
        raise NotImplementedError("Feature not yet implemented")
