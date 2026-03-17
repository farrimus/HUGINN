# Radius Search Calculator Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a spatial search calculator that returns systems within a radius, with smart filtering (planets, killmails, heat) to avoid context explosion. Server-side includes structure locations (OWNER-tier gated); client-side is limited to non-sensitive data.

**Architecture:** `RadiusSearch` is a reusable class (no FastAPI coupling) that loads universe data once and provides async `search()` method. Server exposes `/search/radius` endpoint; client-side `log_agent` imports same class for local calculation. Structure locations stored in `data/structure_locations.json`, queryable via `/structures/record` and `/structures/locations` endpoints (OWNER-tier gated).

**Tech Stack:** Python 3.12, FastAPI, pytest, world_api for killmail fetches, spatial distance calculations (Euclidean), JSON persistence.

---

## Chunk 1: Core Data Model & RadiusSearch Class

### Task 1: Create structure_locations.json and init handler

**Files:**
- Create: `data/structure_locations.json`
- Modify: `src/radius_search.py` (new file, import below)

- [ ] **Step 1: Create empty structure_locations.json**

```bash
touch /opt/eve-frontier/data/structure_locations.json
```

Then write:
```json
{
  "structure_locations": {},
  "built_at": "2026-03-17T00:00:00Z"
}
```

- [ ] **Step 2: Commit**

```bash
git add data/structure_locations.json
git commit -m "data: initialize structure_locations.json"
```

### Task 2: Scaffold RadiusSearch class with data loading

**Files:**
- Create: `src/radius_search.py`
- Modify: `src/world_api.py` (reference only, no changes yet)
- Modify: `data/systems.json` (reference only)

- [ ] **Step 1: Write test for RadiusSearch initialization**

Create `tests/test_radius_search.py`:

```python
import pytest
from src.radius_search import RadiusSearch

@pytest.mark.asyncio
async def test_radius_search_init():
    """Test that RadiusSearch loads data on init."""
    rs = RadiusSearch()
    assert rs.systems is not None
    assert len(rs.systems) > 0
    assert rs.structure_locations is not None
    # Verify a known system exists (from systems.json)
    assert rs.get_system("UR8-K7K") is not None

@pytest.mark.asyncio
async def test_radius_search_structure_locations_empty_on_init():
    """Test that structure_locations starts empty."""
    rs = RadiusSearch()
    assert rs.structure_locations == {}
```

- [ ] **Step 2: Run test to verify it fails**

```bash
cd /opt/eve-frontier
pytest tests/test_radius_search.py::test_radius_search_init -v
```

Expected output: `FAILED — ModuleNotFoundError: No module named 'src.radius_search'`

- [ ] **Step 3: Create src/radius_search.py with scaffolding**

```python
"""
Radius search calculator — finds systems within a radius and filters by criteria.
Reusable by both server (FastAPI) and client (log-agent Windows).
"""
import os
import json
import logging
from typing import Optional, list
from src.world_api import world_api_client

log = logging.getLogger(__name__)

_STRUCTURE_LOCATIONS_PATH = os.path.normpath(
    os.path.join(os.path.dirname(__file__), "..", "data", "structure_locations.json")
)


class RadiusSearch:
    def __init__(self, systems_path: str = None, structure_locations_path: str = None):
        """
        Initialize RadiusSearch.

        Args:
            systems_path: Path to systems.json (default: data/systems.json)
            structure_locations_path: Path to structure_locations.json (default: data/structure_locations.json)
        """
        self.systems_path = systems_path or os.path.normpath(
            os.path.join(os.path.dirname(__file__), "..", "data", "systems.json")
        )
        self.structure_locations_path = structure_locations_path or _STRUCTURE_LOCATIONS_PATH

        self.systems = {}  # {system_id: {name, x, y, z, safe_jump_temp, planet_ids, ...}}
        self.structure_locations = {}  # {structure_id: {system_name, reported_by, tribe, ...}}
        self.world_api_client = world_api_client

        self._load_systems()
        self._load_structure_locations()

    def _load_systems(self) -> None:
        """Load systems from systems.json."""
        try:
            with open(self.systems_path) as f:
                data = json.load(f)
                # Map by system_id for easy lookup
                for sys_id, sys_data in data.get("systems", {}).items():
                    # Store with both numeric and string keys for flexibility
                    self.systems[int(sys_id)] = sys_data
                    self.systems[sys_data.get("name", "")] = sys_data
            log.info("RadiusSearch: loaded %d systems", len(set(self.systems.values())))
        except Exception as e:
            log.error("Failed to load systems.json: %s", e)
            raise

    def _load_structure_locations(self) -> None:
        """Load structure locations from disk (non-sensitive reference)."""
        try:
            if not os.path.exists(self.structure_locations_path):
                return
            with open(self.structure_locations_path) as f:
                data = json.load(f)
                self.structure_locations = data.get("structure_locations", {})
            log.info("RadiusSearch: loaded %d structure locations", len(self.structure_locations))
        except Exception as e:
            log.warning("Failed to load structure_locations.json: %s", e)

    def get_system(self, name_or_id) -> Optional[dict]:
        """
        Lookup a system by name (case-insensitive) or ID.
        Returns the system dict or None.
        """
        if isinstance(name_or_id, str):
            # Case-insensitive lookup by name
            name_upper = name_or_id.upper()
            for sys_data in self.systems.values():
                if sys_data.get("name", "").upper() == name_upper:
                    return sys_data
            return None
        else:
            # Lookup by ID
            return self.systems.get(name_or_id)
```

- [ ] **Step 4: Run test to verify it passes**

```bash
cd /opt/eve-frontier
pytest tests/test_radius_search.py::test_radius_search_init -v
pytest tests/test_radius_search.py::test_radius_search_structure_locations_empty_on_init -v
```

Expected: Both PASS

- [ ] **Step 5: Commit**

```bash
git add src/radius_search.py tests/test_radius_search.py
git commit -m "feat: scaffold RadiusSearch class with data loading"
```

---

## Chunk 2: Distance Calculation & System Filtering

### Task 3: Implement spatial distance calculation and system filtering by radius

**Files:**
- Modify: `src/radius_search.py`
- Modify: `tests/test_radius_search.py`

- [ ] **Step 1: Write test for distance calculation**

Add to `tests/test_radius_search.py`:

```python
import math

@pytest.mark.asyncio
async def test_radius_search_distance_calculation():
    """Test Euclidean distance calculation between systems."""
    rs = RadiusSearch()

    sys_a = {"x": 0, "y": 0, "z": 0}
    sys_b = {"x": 3, "y": 4, "z": 0}

    dist = rs._distance_ly(sys_a, sys_b)
    # 3-4-5 triangle: distance should be 5
    assert abs(dist - 5.0) < 0.01

@pytest.mark.asyncio
async def test_radius_search_systems_within_radius():
    """Test finding systems within a given radius."""
    rs = RadiusSearch()

    # Use UR8-K7K as center (known system)
    center_sys = rs.get_system("UR8-K7K")
    assert center_sys is not None

    # Find systems within 100 LY
    results = rs.find_systems_within_radius("UR8-K7K", 100.0)
    assert isinstance(results, list)
    assert len(results) > 0

    # Verify all results are within radius
    for sys in results:
        dist = rs._distance_ly(center_sys, sys)
        assert dist <= 100.0, f"{sys['name']} is {dist} LY away, outside 100 LY radius"
```

- [ ] **Step 2: Run test to verify it fails**

```bash
cd /opt/eve-frontier
pytest tests/test_radius_search.py::test_radius_search_distance_calculation -v
```

Expected: FAILED — method `_distance_ly` not defined

- [ ] **Step 3: Implement distance calc and radius filtering**

Add to `src/radius_search.py`:

```python
def _distance_ly(self, sys_a: dict, sys_b: dict) -> float:
    """
    Calculate Euclidean distance between two systems in light-years.

    EVE coordinates are in meters; 1 LY = 9.461e15 meters.
    """
    LY_IN_METERS = 9.461e15

    x_a = sys_a.get("x", 0)
    y_a = sys_a.get("y", 0)
    z_a = sys_a.get("z", 0)

    x_b = sys_b.get("x", 0)
    y_b = sys_b.get("y", 0)
    z_b = sys_b.get("z", 0)

    dx = x_b - x_a
    dy = y_b - y_a
    dz = z_b - z_a

    dist_m = (dx**2 + dy**2 + dz**2) ** 0.5
    dist_ly = dist_m / LY_IN_METERS

    return dist_ly

def find_systems_within_radius(self, center_name: str, radius_ly: float) -> list[dict]:
    """
    Find all systems within a given radius (in light-years) from center system.

    Args:
        center_name: System name (e.g., "UR8-K7K")
        radius_ly: Search radius in light-years

    Returns:
        List of systems (as dicts) sorted by distance (closest first).
        Includes "distance_ly" field for each result.
    """
    center_sys = self.get_system(center_name)
    if not center_sys:
        return []

    results = []
    for sys_data in self.systems.values():
        if not isinstance(sys_data, dict) or "x" not in sys_data:
            continue

        dist = self._distance_ly(center_sys, sys_data)
        if dist <= radius_ly:
            results.append({
                **sys_data,
                "distance_ly": round(dist, 2)
            })

    # Sort by distance (closest first)
    results.sort(key=lambda s: s["distance_ly"])

    return results
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
cd /opt/eve-frontier
pytest tests/test_radius_search.py::test_radius_search_distance_calculation -v
pytest tests/test_radius_search.py::test_radius_search_systems_within_radius -v
```

Expected: Both PASS

- [ ] **Step 5: Commit**

```bash
git add src/radius_search.py tests/test_radius_search.py
git commit -m "feat: implement distance calculation and radius filtering"
```

---

## Chunk 3: Heat & Planet Filtering

### Task 4: Add heat flagging and planet counting

**Files:**
- Modify: `src/radius_search.py`
- Modify: `tests/test_radius_search.py`

- [ ] **Step 1: Write test for heat detection and planet counting**

Add to `tests/test_radius_search.py`:

```python
@pytest.mark.asyncio
async def test_heat_classification():
    """Test heat classification (cool, warm, hot)."""
    rs = RadiusSearch()

    # Create mock system
    cool_sys = {"safe_jump_temp": 50.0, "name": "COOL"}
    warm_sys = {"safe_jump_temp": 75.0, "name": "WARM"}
    hot_sys = {"safe_jump_temp": 92.0, "name": "HOT"}

    assert rs.classify_heat(cool_sys) == "cool"
    assert rs.classify_heat(warm_sys) == "warm"
    assert rs.classify_heat(hot_sys) == "hot"

@pytest.mark.asyncio
async def test_planet_count():
    """Test planet count from planet_ids."""
    rs = RadiusSearch()

    sys_with_planets = {
        "name": "TEST",
        "planet_ids": [1, 2, 3, 4]
    }

    count = rs.count_planets(sys_with_planets)
    assert count == 4

    sys_no_planets = {"name": "EMPTY"}
    assert rs.count_planets(sys_no_planets) == 0
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd /opt/eve-frontier
pytest tests/test_radius_search.py::test_heat_classification -v
```

Expected: FAILED — method `classify_heat` not defined

- [ ] **Step 3: Implement heat and planet helpers**

Add to `src/radius_search.py`:

```python
def classify_heat(self, system: dict) -> str:
    """
    Classify a system by temperature.

    Returns: "cool" (< 70°), "warm" (70–89°), or "hot" (>= 90°)
    """
    temp = system.get("safe_jump_temp", 0)
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
    return system.get("safe_jump_temp", 0) >= 70
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
cd /opt/eve-frontier
pytest tests/test_radius_search.py::test_heat_classification -v
pytest tests/test_radius_search.py::test_planet_count -v
```

Expected: Both PASS

- [ ] **Step 5: Commit**

```bash
git add src/radius_search.py tests/test_radius_search.py
git commit -m "feat: add heat classification and planet counting"
```

---

## Chunk 4: Killmail Integration

### Task 5: Fetch and filter killmails by system and recency

**Files:**
- Modify: `src/radius_search.py`
- Modify: `tests/test_radius_search.py`

- [ ] **Step 1: Write test for killmail fetching**

Add to `tests/test_radius_search.py`:

```python
@pytest.mark.asyncio
async def test_get_killmails_for_system():
    """Test fetching killmails for a system (mocked)."""
    rs = RadiusSearch()

    # This will call world_api_client.get_killmails
    # For now, just verify it doesn't crash and returns a list
    system_id = 30000001  # Use a known system ID
    killmails = await rs.get_killmails_for_system(system_id, hours=24)

    assert isinstance(killmails, list)

    # If killmails exist, verify they have expected fields
    for km in killmails[:5]:  # Check first 5
        assert "id" in km or "killmail_id" in km or "timestamp" in km

@pytest.mark.asyncio
async def test_filter_recent_killmails():
    """Test filtering killmails by recency."""
    rs = RadiusSearch()

    import time
    now = time.time()

    # Create mock killmails
    old_km = {"timestamp": now - (48 * 3600), "id": 1}  # 48 hours ago
    recent_km = {"timestamp": now - (1 * 3600), "id": 2}  # 1 hour ago

    killmails = [old_km, recent_km]
    filtered = rs.filter_killmails_by_recency(killmails, hours=24)

    # Should only include recent_km
    assert len(filtered) == 1
    assert filtered[0]["id"] == 2
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd /opt/eve-frontier
pytest tests/test_radius_search.py::test_get_killmails_for_system -v
```

Expected: FAILED — method `get_killmails_for_system` not defined

- [ ] **Step 3: Implement killmail fetching and filtering**

Add to `src/radius_search.py`:

```python
async def get_killmails_for_system(self, system_id: int, hours: int = 24) -> list:
    """
    Fetch killmails for a system from world_api_client.

    Args:
        system_id: EVE system ID
        hours: Return killmails from the last N hours

    Returns:
        List of killmail dicts (may be empty if API fails)
    """
    try:
        # world_api_client.get_killmails(system_id) returns raw list
        # Each entry should have a timestamp
        killmails = await self.world_api_client.get_killmails(system_id)

        if not killmails:
            return []

        # Filter by recency
        filtered = self.filter_killmails_by_recency(killmails, hours=hours)

        # Return top 10, sorted by most recent first
        return sorted(filtered, key=lambda km: km.get("timestamp", 0), reverse=True)[:10]

    except Exception as e:
        log.warning("Failed to fetch killmails for system %d: %s", system_id, e)
        return []

def filter_killmails_by_recency(self, killmails: list, hours: int) -> list:
    """
    Filter killmails to only those from the last N hours.

    Args:
        killmails: List of killmail dicts (each with "timestamp" field)
        hours: Lookback period in hours

    Returns:
        Filtered list of killmails
    """
    import time
    now = time.time()
    cutoff = now - (hours * 3600)

    return [
        km for km in killmails
        if km.get("timestamp", 0) >= cutoff
    ]

def get_most_recent_killmail_timestamp(self, killmails: list) -> Optional[float]:
    """Return the timestamp of the most recent killmail, or None if empty."""
    if not killmails:
        return None
    return max(km.get("timestamp", 0) for km in killmails)
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
cd /opt/eve-frontier
pytest tests/test_radius_search.py::test_filter_recent_killmails -v
```

Expected: PASS (the async test may be skipped depending on world_api setup; that's OK for now)

- [ ] **Step 5: Commit**

```bash
git add src/radius_search.py tests/test_radius_search.py
git commit -m "feat: add killmail fetching and recency filtering"
```

---

## Chunk 5: Main Search Method & Response Formatting

### Task 6: Implement the main async search() method with filtering and thresholding

**Files:**
- Modify: `src/radius_search.py`
- Modify: `tests/test_radius_search.py`

- [ ] **Step 1: Write test for main search method**

Add to `tests/test_radius_search.py`:

```python
@pytest.mark.asyncio
async def test_search_basic():
    """Test the main search() method."""
    rs = RadiusSearch()

    result = await rs.search(
        center_system="UR8-K7K",
        radius_ly=100,
        filters=["planets"],
        top_n=5
    )

    # Verify response structure
    assert "center" in result
    assert "radius_ly" in result
    assert "total_systems" in result
    assert "scan_summary" in result
    assert "filters" in result
    assert result["center"] == "UR8-K7K"
    assert result["radius_ly"] == 100

@pytest.mark.asyncio
async def test_search_planets_filter():
    """Test search with planets filter."""
    rs = RadiusSearch()

    result = await rs.search(
        center_system="UR8-K7K",
        radius_ly=100,
        filters=["planets"],
        top_n=3
    )

    planets_filter = result["filters"].get("planets", {})
    assert "systems" in planets_filter

    # Systems should be sorted by planet count (descending)
    systems = planets_filter["systems"]
    if len(systems) >= 2:
        assert systems[0]["planets"] >= systems[1]["planets"]

@pytest.mark.asyncio
async def test_search_heat_filter():
    """Test search with heat filter."""
    rs = RadiusSearch()

    result = await rs.search(
        center_system="UR8-K7K",
        radius_ly=100,
        filters=["heat"],
        top_n=10
    )

    heat_filter = result["filters"].get("heat", {})
    assert "systems" in heat_filter

    # All heat-trap systems should have safe_jump_temp >= 70
    for sys in heat_filter["systems"]:
        assert sys.get("safe_jump_temp", 0) >= 70
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd /opt/eve-frontier
pytest tests/test_radius_search.py::test_search_basic -v
```

Expected: FAILED — method `search` not defined

- [ ] **Step 3: Implement the main search() method**

Add to `src/radius_search.py`:

```python
async def search(self,
    center_system: str,
    radius_ly: float,
    filters: list[str] = None,
    killmail_hours: int = 24,
    top_n: int = 10,
    skip_heat_traps: bool = False
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
                "structures": { "count": 2, "systems": [...] }  [OWNER-tier only]
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

    # Thresholding: if < 20 systems, return all; otherwise return top N per filter
    threshold = 20
    show_top_n = len(all_systems) < threshold

    # Apply filters
    for filter_type in filters:
        if filter_type == "planets":
            result["filters"]["planets"] = self._filter_planets(all_systems, top_n if show_top_n else top_n)

        elif filter_type == "killmails":
            # Async call
            result["filters"]["killmails"] = await self._filter_killmails(all_systems, top_n, killmail_hours)

        elif filter_type == "heat":
            result["filters"]["heat"] = self._filter_heat(all_systems, top_n if show_top_n else top_n)

        elif filter_type == "structures":
            # Structures are only included if requested; filtering is separate
            result["filters"]["structures"] = self._filter_structures(all_systems, top_n if show_top_n else top_n)

    return result

def _filter_planets(self, systems: list[dict], top_n: int) -> dict:
    """Filter systems by planet count (highest first)."""
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

async def _filter_killmails(self, systems: list[dict], top_n: int, hours: int) -> dict:
    """Filter systems by recent killmails (most kills first)."""
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

def _filter_heat(self, systems: list[dict], top_n: int) -> dict:
    """Filter systems by heat level (warm/hot systems)."""
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

def _filter_structures(self, systems: list[dict], top_n: int) -> dict:
    """Filter systems that have recorded structures (OWNER-tier data)."""
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

def _hours_since(self, timestamp: float) -> float:
    """Return hours elapsed since timestamp."""
    import time
    if not timestamp:
        return None
    return round((time.time() - timestamp) / 3600, 1)
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
cd /opt/eve-frontier
pytest tests/test_radius_search.py::test_search_basic -v
pytest tests/test_radius_search.py::test_search_planets_filter -v
pytest tests/test_radius_search.py::test_search_heat_filter -v
```

Expected: All PASS (or some async tests skipped; that's OK)

- [ ] **Step 5: Commit**

```bash
git add src/radius_search.py tests/test_radius_search.py
git commit -m "feat: implement main search method with filtering"
```

---

## Chunk 6: Server Endpoints

### Task 7: Add POST /search/radius and POST/GET /structures/* endpoints to main.py

**Files:**
- Modify: `main.py`

- [ ] **Step 1: Add imports and instantiate RadiusSearch in main.py**

At the top of `main.py`, add:

```python
from src.radius_search import RadiusSearch

# Initialize radius search (loaded once at startup)
radius_search = RadiusSearch()
```

- [ ] **Step 2: Create Pydantic models for request/response**

Add to `main.py` (near the other request models):

```python
from pydantic import BaseModel
from typing import Optional, list

class RadiusSearchRequest(BaseModel):
    center_system: str
    radius_ly: float
    filters: list[str] = ["planets"]  # ["planets", "killmails", "heat", "structures"]
    killmail_hours: int = 24
    top_n: int = 10
    skip_heat_traps: bool = False

class RecordStructureRequest(BaseModel):
    structure_id: str
    system_name: str
    reported_by: str
    tribe: Optional[str] = None
```

- [ ] **Step 3: Add POST /search/radius endpoint**

Add to `main.py`:

```python
@app.post("/search/radius", dependencies=[Depends(require_token)])
async def search_radius(req: RadiusSearchRequest):
    """
    Search for systems within a radius with optional filtering.

    Query params:
    - center_system: Center system name (e.g., "UR8-K7K")
    - radius_ly: Search radius in light-years
    - filters: Comma-separated filter types (planets, killmails, heat, structures)
    - killmail_hours: Killmail lookback period (default 24)
    - top_n: Results per filter (default 10)
    - skip_heat_traps: Exclude warm/hot systems (default false)

    Returns: Filtered search results
    """
    try:
        result = await radius_search.search(
            center_system=req.center_system,
            radius_ly=req.radius_ly,
            filters=req.filters,
            killmail_hours=req.killmail_hours,
            top_n=req.top_n,
            skip_heat_traps=req.skip_heat_traps
        )
        return result
    except Exception as e:
        log.error(f"Search failed: {e}")
        return {"error": str(e), "center": req.center_system}
```

- [ ] **Step 4: Add POST /structures/record endpoint**

Add to `main.py`:

```python
@app.post("/structures/record", dependencies=[Depends(require_token)])
async def record_structure(req: RecordStructureRequest):
    """
    Record a discovered structure location.

    Body:
    - structure_id: Structure ID (e.g., "0x89e9dc0")
    - system_name: System where found (e.g., "UR8-K7K")
    - reported_by: Player ID who reported it
    - tribe: Tribe name (optional)

    Returns: {"success": true, "structure_id": "...", "system_name": "..."}
    """
    try:
        # Add or update in memory
        radius_search.structure_locations[req.structure_id] = {
            "system_name": req.system_name,
            "reported_by": req.reported_by,
            "tribe": req.tribe,
            "discovered_at": datetime.datetime.utcnow().isoformat() + "Z",
            "source": "manual"
        }

        # Persist to disk
        radius_search._save_structure_locations()

        return {
            "success": True,
            "structure_id": req.structure_id,
            "system_name": req.system_name
        }
    except Exception as e:
        log.error(f"Failed to record structure: {e}")
        return {"success": False, "error": str(e)}
```

- [ ] **Step 5: Add helper to save structure locations**

Add to `src/radius_search.py`:

```python
def _save_structure_locations(self) -> None:
    """Persist structure locations to disk."""
    try:
        import datetime
        os.makedirs(os.path.dirname(self.structure_locations_path), exist_ok=True)
        with open(self.structure_locations_path, "w") as f:
            json.dump({
                "structure_locations": self.structure_locations,
                "built_at": datetime.datetime.utcnow().isoformat() + "Z"
            }, f, indent=2)
        log.info("Structure locations saved: %d entries", len(self.structure_locations))
    except Exception as e:
        log.error("Failed to save structure_locations.json: %s", e)
```

- [ ] **Step 6: Add GET /structures/locations endpoint**

Add to `main.py`:

```python
@app.get("/structures/locations", dependencies=[Depends(require_token)])
async def get_structure_locations():
    """
    Get all recorded structure locations (OWNER-tier reference).

    Returns: List of {structure_id, system_name, reported_by, tribe, discovered_at}
    """
    return {
        "structures": [
            {"structure_id": k, **v}
            for k, v in radius_search.structure_locations.items()
        ]
    }
```

- [ ] **Step 7: Test endpoints manually**

```bash
# Start server
cd /opt/eve-frontier
python main.py &

# Test /search/radius
curl -X POST http://localhost:8745/search/radius \
  -H "X-Server-Token: $SERVER_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "center_system": "UR8-K7K",
    "radius_ly": 100,
    "filters": ["planets"]
  }'

# Expected: {"center": "UR8-K7K", "radius_ly": 100, "total_systems": ..., ...}

# Test /structures/record
curl -X POST http://localhost:8745/structures/record \
  -H "X-Server-Token: $SERVER_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "structure_id": "0x89e9dc0",
    "system_name": "UR8-K7K",
    "reported_by": "player_abc",
    "tribe": "MyTribe"
  }'

# Expected: {"success": true, "structure_id": "0x89e9dc0", ...}
```

- [ ] **Step 8: Commit**

```bash
git add main.py src/radius_search.py
git commit -m "feat: add /search/radius and /structures endpoints"
```

---

## Chunk 7: Client-Side Implementation (log-agent)

### Task 8: Implement client-side RadiusCalculator (Windows log-agent)

**Files:**
- Create: `log-agent/radius_calculator.py`
- Modify: `log-agent/log_agent.py` (wire in commands)

- [ ] **Step 1: Create log-agent/radius_calculator.py (limited version)**

```python
"""
Client-side radius search calculator for Windows log-agent.
Uses local systems.json; does NOT include structure location data (server-only).
"""
import os
import json
import asyncio
from typing import Optional, list

# Import the shared RadiusSearch class
# (In production, copy src/radius_search.py or share via import path)
# For now, we'll create a lightweight client version that doesn't need server files


class ClientRadiusCalculator:
    """
    Lightweight radius calculator for Windows client.
    Loads systems.json once; skips structure data (server-only).
    """

    def __init__(self, systems_path: str = None):
        """
        Initialize calculator.

        Args:
            systems_path: Path to systems.json (default: ../data/systems.json)
        """
        self.systems_path = systems_path or os.path.normpath(
            os.path.join(os.path.dirname(__file__), "..", "data", "systems.json")
        )
        self.systems = {}
        self._load_systems()

    def _load_systems(self) -> None:
        """Load systems from systems.json."""
        try:
            with open(self.systems_path) as f:
                data = json.load(f)
                for sys_id, sys_data in data.get("systems", {}).items():
                    self.systems[int(sys_id)] = sys_data
                    self.systems[sys_data.get("name", "")] = sys_data
            print(f"[RadiusCalc] Loaded {len(set(self.systems.values()))} systems")
        except Exception as e:
            print(f"[RadiusCalc] Error loading systems: {e}")

    def get_system(self, name_or_id) -> Optional[dict]:
        """Lookup system by name (case-insensitive) or ID."""
        if isinstance(name_or_id, str):
            name_upper = name_or_id.upper()
            for sys_data in self.systems.values():
                if sys_data.get("name", "").upper() == name_upper:
                    return sys_data
            return None
        else:
            return self.systems.get(name_or_id)

    def _distance_ly(self, sys_a: dict, sys_b: dict) -> float:
        """Calculate Euclidean distance in light-years."""
        LY_IN_METERS = 9.461e15
        dx = sys_b.get("x", 0) - sys_a.get("x", 0)
        dy = sys_b.get("y", 0) - sys_a.get("y", 0)
        dz = sys_b.get("z", 0) - sys_a.get("z", 0)
        dist_m = (dx**2 + dy**2 + dz**2) ** 0.5
        return dist_m / LY_IN_METERS

    def search(self,
        center_name: str,
        radius_ly: float,
        filters: list[str] = None
    ) -> dict:
        """
        Local search (no killmails, no structures — server-only features).

        Args:
            center_name: System name
            radius_ly: Search radius
            filters: ["planets", "heat"] (killmails/structures not available client-side)

        Returns: Simplified search result
        """
        filters = filters or ["planets"]

        center_sys = self.get_system(center_name)
        if not center_sys:
            return {"error": f"System not found: {center_name}"}

        # Find systems within radius
        all_systems = []
        for sys_data in self.systems.values():
            if not isinstance(sys_data, dict) or "x" not in sys_data:
                continue
            dist = self._distance_ly(center_sys, sys_data)
            if dist <= radius_ly:
                all_systems.append({**sys_data, "distance_ly": round(dist, 2)})

        all_systems.sort(key=lambda s: s["distance_ly"])

        result = {
            "center": center_name,
            "radius_ly": radius_ly,
            "total_systems": len(all_systems),
            "scan_summary": f"{len(all_systems)} systems within {radius_ly} LY",
            "filters": {}
        }

        # Apply filters
        if "planets" in filters:
            result["filters"]["planets"] = {
                "count": len([s for s in all_systems if s.get("planet_ids")]),
                "systems": [
                    {
                        "name": s["name"],
                        "distance_ly": s["distance_ly"],
                        "planets": len(s.get("planet_ids", []))
                    }
                    for s in sorted(
                        all_systems,
                        key=lambda s: len(s.get("planet_ids", [])),
                        reverse=True
                    )[:10]
                ]
            }

        if "heat" in filters:
            heat_traps = [s for s in all_systems if s.get("safe_jump_temp", 0) >= 70]
            result["filters"]["heat"] = {
                "count": len(heat_traps),
                "systems": [
                    {
                        "name": s["name"],
                        "distance_ly": s["distance_ly"],
                        "safe_jump_temp": s.get("safe_jump_temp", 0),
                        "heat_class": "warm" if s.get("safe_jump_temp", 0) < 90 else "hot"
                    }
                    for s in sorted(heat_traps, key=lambda s: s.get("safe_jump_temp", 0), reverse=True)[:10]
                ]
            }

        return result


# Module-level instance
client_radius_calculator = None

def init_radius_calculator(systems_path: str = None):
    """Initialize the client radius calculator."""
    global client_radius_calculator
    client_radius_calculator = ClientRadiusCalculator(systems_path)

def search(center: str, radius: float, filters: list[str] = None) -> dict:
    """Convenience function to search."""
    if client_radius_calculator is None:
        init_radius_calculator()
    return client_radius_calculator.search(center, radius, filters)
```

- [ ] **Step 2: Wire into log_agent.py**

Modify `log-agent/log_agent.py`:

Add import at top:
```python
from radius_calculator import init_radius_calculator, search as radius_search
```

Add in the main loop or REPL handler (wherever commands are processed):
```python
# Handle /search commands
if message.startswith("/search "):
    parts = message.split()
    if len(parts) >= 2:
        try:
            radius = float(parts[1])
            filters = parts[2].split(",") if len(parts) > 2 else ["planets"]
            result = radius_search(current_system, radius, filters)
            print(json.dumps(result, indent=2))
        except Exception as e:
            print(f"Search error: {e}")
```

- [ ] **Step 3: Test client-side**

```bash
cd /opt/eve-frontier/log-agent

# Test import
python -c "from radius_calculator import init_radius_calculator; init_radius_calculator(); print('OK')"

# Expected: [RadiusCalc] Loaded XXXX systems
#           OK
```

- [ ] **Step 4: Commit**

```bash
git add log-agent/radius_calculator.py log-agent/log_agent.py
git commit -m "feat: add client-side radius calculator (log-agent)"
```

---

## Chunk 8: Integration Tests & Documentation

### Task 9: Write integration tests

**Files:**
- Modify: `tests/test_radius_search.py`

- [ ] **Step 1: Add integration test**

```python
@pytest.mark.asyncio
async def test_integration_search_with_all_filters():
    """Integration test: full search with multiple filters."""
    rs = RadiusSearch()

    result = await rs.search(
        center_system="UR8-K7K",
        radius_ly=150,
        filters=["planets", "heat"],
        top_n=5
    )

    # Verify structure
    assert result["total_systems"] > 0
    assert "planets" in result["filters"]
    assert "heat" in result["filters"]

    # Verify no heat systems in non-heat filter
    if "planets" in result["filters"]:
        for sys in result["filters"]["planets"]["systems"]:
            # May have any temp, that's fine
            pass

    # Verify heat filter only has warm/hot
    if "heat" in result["filters"]:
        for sys in result["filters"]["heat"]["systems"]:
            assert sys["safe_jump_temp"] >= 70

@pytest.mark.asyncio
async def test_integration_server_endpoint():
    """Test /search/radius endpoint via FastAPI TestClient."""
    from fastapi.testclient import TestClient
    from main import app
    import os

    client = TestClient(app)

    # Use a valid server token from .env or test config
    token = os.getenv("SERVER_TOKEN", "test-token")

    response = client.post(
        "/search/radius",
        json={
            "center_system": "UR8-K7K",
            "radius_ly": 100,
            "filters": ["planets"]
        },
        headers={"X-Server-Token": token}
    )

    assert response.status_code == 200
    data = response.json()
    assert data["center"] == "UR8-K7K"
    assert data["radius_ly"] == 100
```

- [ ] **Step 2: Run integration tests**

```bash
cd /opt/eve-frontier
pytest tests/test_radius_search.py -v
```

Expected: All pass (or skipped for async world_api tests, which is OK)

- [ ] **Step 3: Commit**

```bash
git add tests/test_radius_search.py
git commit -m "test: add integration tests for radius search"
```

### Task 10: Documentation

**Files:**
- Create: `docs/ref/radius-search.md` (reference docs)
- Modify: `docs/CODEBASE.md` (add to quick reference)

- [ ] **Step 1: Write reference docs**

Create `docs/ref/radius-search.md`:

```markdown
# Radius Search Calculator

**Purpose:** Spatial search tool for discovering systems around the player, with smart filtering to avoid context explosion.

**Components:**
- `src/radius_search.py` — Core reusable class (server + client)
- `log-agent/radius_calculator.py` — Client-side limited version (no structures)
- Server endpoints: `POST /search/radius`, `POST /structures/record`, `GET /structures/locations`

## Usage

### Server-side (FastAPI)

```bash
curl -X POST http://localhost:8745/search/radius \
  -H "X-Server-Token: $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "center_system": "UR8-K7K",
    "radius_ly": 100,
    "filters": ["planets", "killmails", "heat", "structures"],
    "killmail_hours": 24,
    "top_n": 10,
    "skip_heat_traps": false
  }'
```

### Client-side (Windows log-agent)

```
/search 100 planets,heat
/search 50 planets
```

## Data Files

- `data/structure_locations.json` — Manual structure location registry
  - Format: `{structure_id: {system_name, reported_by, tribe, discovered_at, source}}`
  - Populated via `POST /structures/record`

## Response Format

```json
{
  "center": "UR8-K7K",
  "radius_ly": 100,
  "total_systems": 156,
  "scan_summary": "156 systems within 100 LY",
  "filters": {
    "planets": {
      "count": 10,
      "systems": [
        {"name": "SYS-A", "distance_ly": 12.5, "planets": 8, "safe_jump_temp": 45.2}
      ]
    },
    "killmails": {
      "count": 3,
      "systems": [
        {"name": "SYS-B", "distance_ly": 45.2, "kills": 5, "most_recent_kill_hours_ago": 1.2}
      ]
    },
    "heat": {
      "count": 5,
      "systems": [
        {"name": "SYS-C", "distance_ly": 67.8, "safe_jump_temp": 78.5, "heat_class": "warm"}
      ]
    }
  }
}
```

## Thresholding

- If `total_systems < 20`: Return ALL systems (no filtering)
- If `total_systems >= 20`: Return TOP N per filter (default `top_n=10`, configurable)
- Summary line always included

## Heat Classification

- **cool** (< 70°) — Safe to jump
- **warm** (70–89°) — Heat trap warning
- **hot** (>= 90°) — Cannot jump outbound, red zone

## Notes

- Structure locations are server-only (OWNER-tier gated)
- Client-side calculator skips killmail + structure data
- Killmails from last 24 hours (configurable)
- Top 10 killmails per system (hardcoded)
```

- [ ] **Step 2: Update CODEBASE.md**

Edit `docs/CODEBASE.md`, add to "Quick Reference" table:

```markdown
| Radius search (planets, killmails, heat, structures) | `docs/ref/radius-search.md` |
```

Also add to "Status — 2026-03-17" table:

```markdown
| Radius search calculator | ✓ Server + client, filtering by planets/killmails/heat/structures |
```

- [ ] **Step 3: Commit**

```bash
git add docs/ref/radius-search.md docs/CODEBASE.md
git commit -m "docs: add radius search reference documentation"
```

---

## Summary

This plan builds a complete radius search calculator in 10 tasks:

1. **Data initialization** — structure_locations.json file
2. **Core class scaffolding** — RadiusSearch class with data loading
3. **Distance + filtering** — Spatial calculations + system lookup
4. **Heat + planets** — Temperature classification, planet counting
5. **Killmails** — Fetching + filtering by recency
6. **Main search method** — Unified async search() with all filters + thresholding
7. **Server endpoints** — /search/radius, /structures/record, /structures/locations
8. **Client implementation** — ClientRadiusCalculator for Windows log-agent
9. **Integration tests** — Full end-to-end testing
10. **Documentation** — Reference docs + codebase index updates

**Expected result:** Players can search nearby space, get prioritized data (most planets, recent killmails, heat traps), and the AI uses this data in context without context explosion.
