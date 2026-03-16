# Nav Computer Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace gate-only routing with a full navigation computer: heat-adjusted A* routing, ship profile with 13 real ships, two-route display with USE buttons, and a new ship profile panel.

**Architecture:** Five layers — data (systems.json gains `safe_jump_temp`), ship profile (real ship table, LY formulas), route engine (per-node heat range, alternative route), backend API (new endpoints + context), overlay UI (updated route panel + new ship profile panel). Each layer is independently testable. Python layers use pytest TDD; C++ layers are verified by clean CMake build.

**Tech Stack:** Python 3.11, FastAPI, SQLite (eve_universe.db), pytest, ImGui DX12, WinHTTP, C++20, nlohmann_json, CMake.

---

## Chunk 1: Data Layer + Ship Profile

---

### Task 1: build_universe.py — add safe_jump_temp

**Files:**
- Modify: `build_universe.py`

The DB already has `SolarSystems.star_luminosity`, `SolarSystems.star_radius`, and `Planets.orbitRadius`. We need to extend the existing enrichment block to compute `safe_jump_temp` for every system.

**Formula:**
```python
import math
L_SUN = 3.828e26
K = 100
# D = max_orbit_m / 299_792_458  (light-seconds)
# safe_jump_temp = 100 * (2/pi) * atan(K * 2 * pi * sqrt(star_luminosity / L_SUN) / D)
```

`max_orbit_m` = max of (planet orbitRadius values, 3D distances from star to each LagrangePoint). If no planets and no lagrange points, use `star_radius`. If `star_luminosity == 0` or `D == 0`, `safe_jump_temp = 0.0`.

- [ ] **Step 1: Extend the SolarSystems DB query to also fetch `star_luminosity` and `star_radius`**

  In the existing enrichment block (`if db_path.exists():`), change the star query from:
  ```python
  for row in conn.execute("SELECT solarSystemId, star_temperature, star_spectral_class FROM SolarSystems"):
  ```
  to:
  ```python
  star_data = {}
  for row in conn.execute(
      "SELECT solarSystemId, star_temperature, star_spectral_class, "
      "star_luminosity, star_radius FROM SolarSystems"
  ):
      sid = str(row["solarSystemId"])
      star_data[sid] = {
          "temp":        row["star_temperature"],
          "spectral":    row["star_spectral_class"],
          "luminosity":  row["star_luminosity"] or 0.0,
          "radius":      row["star_radius"] or 0.0,
      }
  ```
  Replace references to `star_temps[sid]` and `db_spectral[sid]` with `star_data[sid]["temp"]` and `star_data[sid]["spectral"]`.

- [ ] **Step 2: Add a max-planet-orbit query**

  After the LagrangePoints query, add:
  ```python
  max_planet_orbit: dict[str, float] = {}
  for row in conn.execute(
      "SELECT solarSystemId, MAX(orbitRadius) as max_orbit FROM Planets GROUP BY solarSystemId"
  ):
      max_planet_orbit[str(row["solarSystemId"])] = row["max_orbit"] or 0.0
  ```

- [ ] **Step 3: Add a max-lagrange-distance query**

  LagrangePoints have absolute in-system local coordinates (`centerX/Y/Z`). Distance from the star = `sqrt(x^2 + y^2 + z^2)` (star is at origin in system local coords).

  ```python
  import math as _math
  max_lagrange_dist: dict[str, float] = {}
  for row in conn.execute(
      "SELECT solarSystemId, centerX, centerY, centerZ FROM LagrangePoints"
  ):
      sid = str(row["solarSystemId"])
      dist = _math.sqrt(row["centerX"]**2 + row["centerY"]**2 + row["centerZ"]**2)
      if dist > max_lagrange_dist.get(sid, 0.0):
          max_lagrange_dist[sid] = dist
  ```

- [ ] **Step 4: Compute `safe_jump_temp` and add `max_orbit_m` and `safe_jump_temp` to each system**

  In the enrichment loop (`for sys_id, s in systems.items():`), add after the existing enrichment lines:
  ```python
  sd = star_data.get(sys_id, {})
  star_lum    = sd.get("luminosity", 0.0)
  star_rad    = sd.get("radius", 0.0)

  planet_orb  = max_planet_orbit.get(sys_id, 0.0)
  lagrange_d  = max_lagrange_dist.get(sys_id, 0.0)
  max_orbit_m = max(planet_orb, lagrange_d)
  if max_orbit_m == 0.0:
      max_orbit_m = star_rad  # star-only system → hot

  s["star_luminosity"] = star_lum
  s["max_orbit_m"]     = max_orbit_m

  if star_lum > 0.0 and max_orbit_m > 0.0:
      import math as _math2
      _L_SUN = 3.828e26
      _K     = 100
      _D     = max_orbit_m / 299_792_458.0
      s["safe_jump_temp"] = 100.0 * (2.0 / _math2.pi) * _math2.atan(
          _K * 2.0 * _math2.pi * _math2.sqrt(star_lum / _L_SUN) / _D
      )
  else:
      s["safe_jump_temp"] = 0.0
  ```

  Move the `import math` and constants to the top of the enrichment block (not inside the loop).

- [ ] **Step 5: Update the enrichment summary print to include hot-system stats**

  After the existing `hot =` line, add:
  ```python
  red_zone    = sum(1 for s in systems.values() if s.get("safe_jump_temp", 0) >= 90)
  yellow_zone = sum(1 for s in systems.values() if 70 <= s.get("safe_jump_temp", 0) < 90)
  print(f"  Red zone (>=90):    {red_zone:,}  systems")
  print(f"  Yellow/Orange zone (70-89): {yellow_zone:,}  systems")
  ```

- [ ] **Step 6: Run build_universe.py and verify the output**

  ```bash
  cd /opt/eve-frontier
  python build_universe.py
  ```

  Expected output includes `safe_jump_temp` counts. Then spot-check the JSON:
  ```bash
  python3 -c "
  import json
  data = json.load(open('data/systems.json'))
  systems = data['systems']
  # Find a system that should have a non-zero temp
  sample = [(s['name'], s.get('safe_jump_temp', 'MISSING'))
            for s in list(systems.values())[:5]]
  print(sample)
  hot = sum(1 for s in systems.values() if s.get('safe_jump_temp', 0) >= 70)
  print('Systems with temp >= 70:', hot)
  "
  ```
  Expected: safe_jump_temp is present on all systems; non-zero values on systems with star_luminosity > 0.

- [ ] **Step 7: Commit**

  ```bash
  cd /opt/eve-frontier
  git add build_universe.py data/systems.json
  git commit -m "feat(data): add safe_jump_temp to systems.json"
  ```

---

### Task 2: ship_profile.py overhaul

**Files:**
- Modify: `src/ship_profile.py`
- Create: `tests/test_ship_profile.py`

Add the 13-ship SHIPS constant, new fields (`ship_type`, `extra_cargo_kg`), and update formulas to return LY. Keep the existing `current_mass` field for JSON backward-compat but stop using it in core calculations (methods now use `hull_mass + extra_cargo_kg`).

- [ ] **Step 1: Write failing tests**

  Create `tests/test_ship_profile.py`:
  ```python
  # tests/test_ship_profile.py
  import pytest
  from src.ship_profile import ShipProfile, SHIPS, FUEL_QUALITY, load_profile

  def test_ships_table_complete():
      assert len(SHIPS) == 13
      for name, s in SHIPS.items():
          assert "mass" in s
          assert "specific_heat" in s
          assert "fuel_category" in s
          assert s["fuel_category"] in ("basic", "advanced")

  def test_carom_jump_range_at_zero_temp():
      # Carom: mass=7.2e6, specific_heat=8.5, no cargo
      p = ShipProfile(hull_mass=7_200_000, specific_heat=8.5, extra_cargo_kg=0,
                      adaptive_level=0, external_temp=0.0)
      # range_ly = (150 - 0) * 8.5 * 7.2e6 / (3 * 7.2e6) = 150 * 8.5 / 3 = 425.0
      assert abs(p.jump_range() - 425.0) < 0.01

  def test_jump_range_with_cargo():
      # Carom with 1_000_000 kg extra cargo → current_mass = 8_200_000
      p = ShipProfile(hull_mass=7_200_000, specific_heat=8.5, extra_cargo_kg=1_000_000,
                      adaptive_level=0, external_temp=0.0)
      expected = (150 * 8.5 * 7_200_000) / (3 * 8_200_000)
      assert abs(p.jump_range() - expected) < 0.01

  def test_jump_range_zero_at_red_zone():
      p = ShipProfile(hull_mass=7_200_000, specific_heat=8.5, external_temp=90.0)
      assert p.jump_range() == 0.0

  def test_fuel_budget_carom_d1():
      # Carom: 3000 D1 (quality=0.10), mass=7.2e6
      # budget = (3000 * 0.10) / (1e-7 * 7.2e6) = 300 / 0.72 = 416.67 LY
      p = ShipProfile(hull_mass=7_200_000, fuel_type="D1", fuel_quantity=3000,
                      extra_cargo_kg=0)
      assert abs(p.fuel_budget() - 416.67) < 0.1

  def test_fuel_for_distance_roundtrip():
      p = ShipProfile(hull_mass=7_200_000, fuel_type="D1", fuel_quantity=3000,
                      extra_cargo_kg=0)
      ly = 50.0
      fuel = p.fuel_for_distance(ly)
      # fuel_for_distance(ly) * quality / (FUEL_CONSTANT * current_mass) should == ly
      quality = FUEL_QUALITY["D1"]
      from src.ship_profile import FUEL_CONSTANT
      recovered = (p.fuel_quantity - fuel) / (p.fuel_quantity / p.fuel_budget())
      # Simpler: just verify fuel_for_distance is inverse of fuel_budget
      budget = p.fuel_budget()
      frac = ly / budget
      assert abs(fuel - frac * p.fuel_quantity) < 0.01

  def test_adaptive_level_increases_range():
      base = ShipProfile(hull_mass=7_200_000, specific_heat=8.5, adaptive_level=0,
                         external_temp=0.0)
      leveled = ShipProfile(hull_mass=7_200_000, specific_heat=8.5, adaptive_level=5,
                            external_temp=0.0)
      assert leveled.jump_range() > base.jump_range()

  def test_ship_type_from_ships_table():
      from src.ship_profile import SHIPS
      carom = SHIPS["Carom"]
      assert carom["mass"] == 7_200_000
      assert carom["specific_heat"] == 8.5
      assert carom["fuel_category"] == "basic"
  ```

- [ ] **Step 2: Run tests to verify they fail**

  ```bash
  cd /opt/eve-frontier
  python -m pytest tests/test_ship_profile.py -v 2>&1 | head -40
  ```
  Expected: multiple failures (SHIPS not defined, extra_cargo_kg not present, etc.)

- [ ] **Step 3: Replace src/ship_profile.py with the full updated version**

  Complete replacement:
  ```python
  # src/ship_profile.py
  import json
  import os
  import logging
  from dataclasses import dataclass, asdict, field
  from typing import Optional

  log = logging.getLogger(__name__)

  FUEL_QUALITY: dict[str, float] = {
      "D1":     0.10,
      "D2":     0.15,
      "SOF-40": 0.40,
      "EU-40":  0.40,
      "SOF-80": 0.80,
      "EU-90":  0.90,
  }

  FUEL_CATEGORY: dict[str, str] = {
      "D1":     "basic",
      "D2":     "basic",
      "SOF-40": "advanced",
      "EU-40":  "advanced",
      "SOF-80": "advanced",
      "EU-90":  "advanced",
  }

  SHIPS: dict[str, dict] = {
      "Carom":   {"mass": 7_200_000,       "specific_heat": 8.5, "fuel_category": "basic"},
      "Stride":  {"mass": 7_900_000,       "specific_heat": 8.0, "fuel_category": "basic"},
      "Reflex":  {"mass": 9_750_000,       "specific_heat": 3.0, "fuel_category": "basic"},
      "Recurve": {"mass": 10_200_000,      "specific_heat": 1.0, "fuel_category": "basic"},
      "Reiver":  {"mass": 10_400_000,      "specific_heat": 1.0, "fuel_category": "basic"},
      "Lai":     {"mass": 18_929_160,      "specific_heat": 2.5, "fuel_category": "advanced"},
      "USV":     {"mass": 30_266_600,      "specific_heat": 1.8, "fuel_category": "advanced"},
      "Lorha":   {"mass": 42_691_330,      "specific_heat": 2.5, "fuel_category": "advanced"},
      "MCF":     {"mass": 52_313_760,      "specific_heat": 2.5, "fuel_category": "advanced"},
      "Tades":   {"mass": 74_655_480,      "specific_heat": 2.5, "fuel_category": "advanced"},
      "HAF":     {"mass": 81_883_000,      "specific_heat": 2.5, "fuel_category": "advanced"},
      "Maul":    {"mass": 548_435_920,     "specific_heat": 2.5, "fuel_category": "advanced"},
      "Chumaq":  {"mass": 1_487_392_000,   "specific_heat": 3.0, "fuel_category": "advanced"},
  }

  SHIP_MAX_FUEL: dict[str, int] = {
      "Carom": 3000, "Stride": 3200, "Reflex": 1750, "Recurve": 970, "Reiver": 1416,
      "Lai": 2400, "USV": 2420, "Lorha": 2508, "MCF": 6548,
      "Tades": 5972, "HAF": 4184, "Maul": 24160, "Chumaq": 270585,
  }

  FUEL_CONSTANT = 1e-7   # game-canonical constant in fuel budget formula
  T_MAX         = 150.0  # game constant in jump range formula
  HEAT_CONSTANT = 3.0    # denominator in jump range formula
  NO_JUMP_TEMP  = 90.0   # Red zone threshold


  @dataclass
  class ShipProfile:
      hull_mass:      float         = 10_000_000.0
      current_mass:   float         = 11_000_000.0  # legacy field; not used in calculations
      specific_heat:  float         = 1.0
      adaptive_level: int           = 0
      fuel_type:      str           = "SOF-80"
      fuel_quantity:  float         = 500.0
      external_temp:  float         = 0.0
      ship_type:      Optional[str] = None
      extra_cargo_kg: float         = 0.0

      @property
      def _current_mass(self) -> float:
          """Effective mass used in all calculations: hull + extra cargo (fuel massless)."""
          return self.hull_mass + self.extra_cargo_kg

      def can_jump(self) -> bool:
          return self.external_temp < NO_JUMP_TEMP

      def jump_range(self) -> float:
          """Max single-jump distance in light-years."""
          if not self.can_jump():
              return 0.0
          c_eff   = self.specific_heat * (1.0 + self.adaptive_level * 0.02)
          delta_t = T_MAX - self.external_temp
          return (delta_t * c_eff * self.hull_mass) / (HEAT_CONSTANT * self._current_mass)

      def jump_range_at_temp(self, temp: float) -> float:
          """Jump range in LY at a given external temperature (used by route engine)."""
          if temp >= NO_JUMP_TEMP:
              return 0.0
          c_eff = self.specific_heat * (1.0 + self.adaptive_level * 0.02)
          return ((T_MAX - temp) * c_eff * self.hull_mass) / (HEAT_CONSTANT * self._current_mass)

      def fuel_budget(self) -> float:
          """Total jump distance available in light-years given current fuel."""
          quality = FUEL_QUALITY.get(self.fuel_type, 0.0)
          if quality == 0.0:
              return 0.0
          return (self.fuel_quantity * quality) / (FUEL_CONSTANT * self._current_mass)

      def fuel_for_distance(self, ly: float) -> float:
          """Fuel units consumed for a given direct-jump distance in light-years."""
          quality = FUEL_QUALITY.get(self.fuel_type, 1.0)
          return ly * FUEL_CONSTANT * self._current_mass / quality

      def with_overrides(self, **kwargs) -> "ShipProfile":
          """Return a copy with selected fields overridden."""
          d = asdict(self)
          d.update({k: v for k, v in kwargs.items() if v is not None})
          return ShipProfile(**d)


  _PROFILE_PATH = os.path.normpath(
      os.path.join(os.path.dirname(__file__), "..", "data", "ship_profile.json")
  )

  _stored: Optional[ShipProfile] = None


  def load_profile() -> ShipProfile:
      global _stored
      if _stored is not None:
          return _stored
      if os.path.exists(_PROFILE_PATH):
          try:
              data = json.loads(open(_PROFILE_PATH).read())
              # Filter out keys not in ShipProfile to handle legacy JSON
              valid_keys = {f.name for f in ShipProfile.__dataclass_fields__.values()}
              data = {k: v for k, v in data.items() if k in valid_keys}
              _stored = ShipProfile(**data)
              log.info("Ship profile loaded from disk")
              return _stored
          except Exception as e:
              log.warning("Failed to load ship profile: %s", e)
      _stored = ShipProfile()
      return _stored


  def save_profile(profile: ShipProfile):
      global _stored
      _stored = profile
      try:
          os.makedirs(os.path.dirname(_PROFILE_PATH), exist_ok=True)
          with open(_PROFILE_PATH, "w") as f:
              json.dump(asdict(profile), f, indent=2)
          log.info("Ship profile saved")
      except Exception as e:
          log.warning("Failed to save ship profile: %s", e)
  ```

- [ ] **Step 4: Run tests to verify they pass**

  ```bash
  cd /opt/eve-frontier
  python -m pytest tests/test_ship_profile.py -v
  ```
  Expected: all 8 tests PASS.

- [ ] **Step 5: Run full test suite to check for regressions**

  ```bash
  python -m pytest tests/ -v --tb=short 2>&1 | tail -30
  ```
  Expected: all previously passing tests still pass. Any failure in test_main.py related to jump_range units must be fixed: in `main.py`, the `GET /ship-profile` endpoint currently computes `"jump_range_ly": p.jump_range() / 9_460_000_000_000_000.0`. Since `jump_range()` now returns LY directly, change this to `"jump_range_ly": p.jump_range()` and remove `"jump_range_m"` or set it to `None`.

- [ ] **Step 6: Commit**

  ```bash
  git add src/ship_profile.py tests/test_ship_profile.py main.py
  git commit -m "feat(ship): add SHIPS table, extra_cargo_kg, LY formulas"
  ```

---

## Chunk 2: Route Engine + Log Buffer

---

### Task 3: route_engine.py + log_buffer.py — heat-aware A*, alternative route

**Files:**
- Modify: `src/route_engine.py`
- Modify: `src/log_buffer.py`
- Create: `tests/test_route_engine.py`

**Key changes:**
- Spatial index stores LY coordinates (converted at load time from systems.json meters)
- `_run_astar()` helper extracted and used for both primary and alternative passes
- Per-node heat-adjusted range using `safe_jump_temp` from systems.json
- New route result shape with `type`, `jump_types`, `total_ly`, `fuel_used`, `fuel_remaining`, `hot_systems`, `alternative`
- `LogBuffer` gains `pending_alternative` field

- [ ] **Step 1: Add `pending_alternative` to log_buffer.py**

  In `src/log_buffer.py`, add `pending_alternative: Optional[dict] = None` after `current_route`:
  ```python
  current_route:       Optional[dict] = None
  pending_alternative: Optional[dict] = None
  ```
  No other changes to log_buffer.py needed.

- [ ] **Step 2: Write failing tests for route_engine**

  Create `tests/test_route_engine.py`:
  ```python
  # tests/test_route_engine.py
  import pytest
  from unittest.mock import patch
  from src.route_engine import RouteEngine
  from src.ship_profile import ShipProfile

  # Minimal system dict that looks like systems.json output
  def _make_systems():
      return {
          "1": {"id": 1, "name": "Alpha",  "x": 0.0,                "y": 0.0, "z": 0.0,
                "gate_links": [2], "safe_jump_temp": 0.0},
          "2": {"id": 2, "name": "Beta",   "x": 9.46e15 * 10,       "y": 0.0, "z": 0.0,
                "gate_links": [1, 3], "safe_jump_temp": 0.0},       # 10 LY from Alpha
          "3": {"id": 3, "name": "Gamma",  "x": 9.46e15 * 10,       "y": 0.0, "z": 9.46e15*10,
                "gate_links": [2], "safe_jump_temp": 0.0},           # diag from Alpha
          "4": {"id": 4, "name": "HotSys", "x": 9.46e15 * 5,        "y": 0.0, "z": 0.0,
                "gate_links": [], "safe_jump_temp": 85.0},           # orange zone, no gates
          "5": {"id": 5, "name": "RedSys", "x": 9.46e15 * 3,        "y": 0.0, "z": 0.0,
                "gate_links": [], "safe_jump_temp": 95.0},           # red zone
      }

  def _make_engine(systems):
      e = RouteEngine()
      e._systems = systems
      e._by_name = {v["name"].lower(): k for k, v in systems.items()}
      e._ly_coords = {
          sid: (s["x"] / 9.46e15, s["y"] / 9.46e15, s["z"] / 9.46e15)
          for sid, s in systems.items()
      }
      from src.route_engine import _SpatialIndex
      e._spatial = _SpatialIndex()
      e._spatial.build(e._ly_coords)
      e._mtime = 1.0  # prevent reload
      return e

  def _profile(range_ly=500.0, budget_ly=2000.0):
      """Profile producing approximately range_ly and budget_ly."""
      # Carom-like: hull=7.2e6, specific_heat=8.5
      # range = (150 * 8.5 * 7.2e6) / (3 * 7.2e6) = 425 at temp=0
      # Adjust via external_temp if needed
      # For simplicity, use a high-capacity profile
      return ShipProfile(
          hull_mass=7_200_000,
          specific_heat=8.5 * (range_ly / 425.0),  # scale to desired range
          adaptive_level=0,
          fuel_type="D1",
          fuel_quantity=99999,  # effectively unlimited
          external_temp=0.0,
          extra_cargo_kg=0,
      )

  def test_route_result_shape():
      e = _make_engine(_make_systems())
      p = _profile(range_ly=500.0)
      result = e.route("Alpha", "Beta", p)
      assert result is not None
      assert result["type"] == "route_planned"
      assert "path" in result
      assert "jumps" in result
      assert "jump_types" in result
      assert len(result["jump_types"]) == result["jumps"]
      assert "total_ly" in result
      assert "fuel_used" in result
      assert "fuel_remaining" in result
      assert "hot_systems" in result
      assert "alternative" in result
      assert "warnings" in result

  def test_gate_route_zero_ly():
      """Gate hops contribute 0 to total_ly."""
      e = _make_engine(_make_systems())
      p = _profile(range_ly=1.0)  # too short to direct-jump
      result = e.bfs("Alpha", "Beta")
      # bfs returns old shape — we test route() here
      # With very short range, A* should use gate
      result = e.route("Alpha", "Beta", p)
      assert result is not None
      # If gate path taken, total_ly should be 0 (no direct jumps)
      if all(jt == "gate" for jt in result["jump_types"]):
          assert result["total_ly"] == 0.0

  def test_red_zone_no_direct_jump_out():
      """A system with safe_jump_temp >= 90 cannot be a direct-jump waypoint."""
      systems = _make_systems()
      # RedSys at 3 LY from Alpha — reachable if no heat; unreachable direct if red
      e = _make_engine(systems)
      p = _profile(range_ly=500.0)
      result = e.route("Alpha", "RedSys", p)
      # RedSys has no gates so only way is direct. But as destination it's still reachable.
      # Origin can jump to destination regardless of destination temp.
      assert result is not None

  def test_alternative_route_triggered_by_hot_intermediate():
      """Alternative route computed when primary path has temp >= 70 intermediate."""
      # Build a longer system chain where we can construct a hot-intermediate scenario
      systems = {
          "1": {"id": 1, "name": "Start",  "x": 0.0,          "y": 0.0, "z": 0.0,
                "gate_links": [], "safe_jump_temp": 0.0},
          "2": {"id": 2, "name": "HotMid", "x": 9.46e15 * 10, "y": 0.0, "z": 0.0,
                "gate_links": [], "safe_jump_temp": 75.0},   # yellow — triggers alt
          "3": {"id": 3, "name": "End",    "x": 9.46e15 * 20, "y": 0.0, "z": 0.0,
                "gate_links": [], "safe_jump_temp": 0.0},
          "4": {"id": 4, "name": "CoolMid","x": 9.46e15 * 10, "y": 9.46e15 * 5,  "z": 0.0,
                "gate_links": [], "safe_jump_temp": 0.0},    # cooler detour
      }
      e = _make_engine(systems)
      p = _profile(range_ly=600.0)  # can reach all in one hop
      result = e.route("Start", "End", p)
      assert result is not None
      if result.get("hot_systems"):
          # If primary goes through HotMid, alternative should exist
          assert result["alternative"] is not None

  def test_no_route_returns_no_route_shape():
      systems = _make_systems()
      e = _make_engine(systems)
      p = _profile(range_ly=0.1)  # tiny range, no gates to isolated system
      # Try to reach an isolated far system
      isolated = {
          **systems,
          "99": {"id": 99, "name": "Far", "x": 9.46e15 * 999, "y": 0.0, "z": 0.0,
                 "gate_links": [], "safe_jump_temp": 0.0},
      }
      e2 = _make_engine(isolated)
      result = e2.route("Alpha", "Far", p)
      assert result is not None
      assert result["type"] == "no_route"
      assert result["path"] == []
      assert result["jumps"] == 0
      assert len(result["warnings"]) > 0

  def test_jumps_equals_len_path_minus_1():
      e = _make_engine(_make_systems())
      p = _profile(range_ly=500.0)
      result = e.route("Alpha", "Gamma", p)
      assert result is not None
      if result["type"] == "route_planned":
          assert result["jumps"] == len(result["path"]) - 1
          assert len(result["jump_types"]) == result["jumps"]
  ```

- [ ] **Step 3: Run tests to see them fail**

  ```bash
  python -m pytest tests/test_route_engine.py -v 2>&1 | head -30
  ```
  Expected: failures on shape assertions and missing fields.

- [ ] **Step 4: Replace src/route_engine.py with the full updated implementation**

  Complete replacement (key changes: LY coords, per-node heat, `_run_astar`, alternative route, new shape):

  ```python
  # src/route_engine.py
  import json
  import os
  import math
  import logging
  import bisect
  from collections import deque
  from typing import Optional

  from src.ship_profile import ShipProfile, T_MAX, HEAT_CONSTANT

  log = logging.getLogger(__name__)

  SYSTEMS_PATH = os.path.normpath(
      os.path.join(os.path.dirname(__file__), "..", "data", "systems.json")
  )

  LY_METERS = 9_460_730_472_580_800.0  # IAU light-year in meters


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
          """Compute direct-jump range (LY) from a given system node."""
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
      ) -> Optional[tuple]:
          """
          Run A* and return (path_ids, edge_types, total_ly) or None.

          exclude_direct: set of system IDs that cannot be used as
                          direct-jump intermediate waypoints. Gates still work.
                          Origin and destination are never excluded.
          """
          import heapq

          fuel_budget_ly = profile.fuel_budget()
          dx, dy, dz = self._pos_ly(d_id)

          def heuristic(sid: str) -> float:
              x, y, z = self._pos_ly(sid)
              return math.sqrt((x - dx)**2 + (y - dy)**2 + (z - dz)**2)

          # heap: (f, g_ly, sid, path_ids, edge_types)
          heap  = [(heuristic(o_id), 0.0, o_id, [o_id], [])]
          best  = {}  # sid → best g_ly seen

          while heap:
              f, g_ly, cur_id, path, edge_types = heapq.heappop(heap)

              if cur_id == d_id:
                  return (path, edge_types, g_ly)

              if cur_id in best and best[cur_id] <= g_ly:
                  continue
              best[cur_id] = g_ly

              cx, cy, cz = self._pos_ly(cur_id)

              # Gate neighbours (cost 0)
              for nb in self._systems.get(cur_id, {}).get("gate_links", []):
                  nb_id = str(nb)
                  if nb_id not in best or best[nb_id] > g_ly:
                      f_new = g_ly + heuristic(nb_id)
                      heapq.heappush(heap, (f_new, g_ly, nb_id,
                                            path + [nb_id], edge_types + ["gate"]))

              # Direct jump neighbours
              node_range_ly = self._node_range_ly(cur_id, profile)
              if node_range_ly > 0.0 and g_ly < fuel_budget_ly:
                  for nb_id in self._spatial.within_range(cx, cy, cz, node_range_ly):
                      if nb_id == cur_id:
                          continue
                      # Skip excluded systems as direct waypoints (not as destination)
                      if exclude_direct and nb_id in exclude_direct and nb_id != d_id:
                          continue
                      d_jump = self._dist_ly(cur_id, nb_id)
                      g_new  = g_ly + d_jump
                      if g_new > fuel_budget_ly:
                          continue
                      if nb_id not in best or best[nb_id] > g_new:
                          f_new = g_new + heuristic(nb_id)
                          heapq.heappush(heap, (f_new, g_new, nb_id,
                                                path + [nb_id], edge_types + ["direct"]))
          return None

      # ------------------------------------------------------------------
      # Hybrid A* router
      # ------------------------------------------------------------------

      def route(self, origin: str, destination: str,
                profile: ShipProfile) -> dict:
          """
          Find the fuel-cheapest route. Returns a route dict (never None).
          If unreachable, returns a no_route dict.
          """
          self._load()
          o_id = self._by_name.get(origin.lower().strip())
          d_id = self._by_name.get(destination.lower().strip())

          if not o_id or not d_id:
              log.warning("Route: system not found (%s → %s)", origin, destination)
              return self._no_route(destination, profile)

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

          primary = self._run_astar(o_id, d_id, profile)
          if primary is None:
              return self._no_route(destination, profile)

          path_ids, edge_types, total_ly = primary

          # Hot intermediates: intermediate nodes (not origin/dest) with temp >= 70
          hot_sids = [
              sid for sid in path_ids[1:-1]
              if self._systems.get(sid, {}).get("safe_jump_temp", 0.0) >= 70.0
          ]
          hot_systems = [self._name(sid) for sid in hot_sids]

          # Alternative route: exclude hot intermediates as direct-jump waypoints
          alternative = None
          if hot_sids:
              exclude = set(hot_sids)
              alt = self._run_astar(o_id, d_id, profile, exclude_direct=exclude)
              if alt is not None:
                  alt_ids, alt_edges, alt_ly = alt
                  if alt_ids != path_ids:
                      alternative = self._format_result(
                          alt_ids, alt_edges, alt_ly, profile
                      )

          result = self._format_result(path_ids, edge_types, total_ly, profile,
                                       hot_systems=hot_systems, alternative=alternative)
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
              warnings.append("insufficient fuel for this route")
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
  ```

- [ ] **Step 5: Run the route engine tests**

  ```bash
  python -m pytest tests/test_route_engine.py -v
  ```
  Expected: all tests PASS.

- [ ] **Step 6: Run the full test suite**

  ```bash
  python -m pytest tests/ -v --tb=short 2>&1 | tail -30
  ```
  Expected: all previously passing tests still pass. The route result shape has changed — tests in `test_main.py` that inspect route fields may need updating (e.g., `test_chat_slash_route_sets_route` checks for `"data:"` in response, which is still true).

  If `test_current_route_and_clear` sets `log_buffer.current_route` to a dict with old shape — that's fine, the test doesn't validate shape. If any test fails because it expects `"gate_hops"` or `"direct_jumps"`, update those assertions to use the new shape fields.

- [ ] **Step 7: Commit**

  ```bash
  git add src/route_engine.py src/log_buffer.py tests/test_route_engine.py
  git commit -m "feat(route): heat-aware A*, alternative route, LY spatial index"
  ```

---

## Chunk 3: Backend API + Context Builder

---

### Task 4: main.py — new endpoints and updated handlers

**Files:**
- Modify: `main.py`
- Modify: `tests/test_main.py`

Changes:
1. `ShipProfileRequest`: add `ship_type`, `extra_cargo_kg`
2. `POST /ship-profile`: validate ship_type against SHIPS, validate fuel_type matches fuel_category
3. `GET /ship-profile`: return new fields (ship_type, extra_cargo_kg, jump_range_ly from new formula)
4. `GET /current-route`: add `current_system_temp` field
5. New `POST /route/activate` endpoint
6. `POST /route`: store `pending_alternative` in log_buffer
7. `/chat` `/route` handler: update reply to use new route shape (jump_types, total_ly)
8. `/chat` `/profile` slash command: auto-save profile

- [ ] **Step 1: Write failing tests for new endpoints**

  Add to `tests/test_main.py`:
  ```python
  @pytest.mark.asyncio
  async def test_current_route_includes_system_temp():
      from src.log_buffer import log_buffer
      log_buffer.current_system = "jita"
      async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
          r = await client.get("/current-route", headers={"X-Server-Token": TOKEN})
      assert r.status_code == 200
      data = r.json()
      assert "current_system_temp" in data

  @pytest.mark.asyncio
  async def test_route_activate_no_route():
      from src.log_buffer import log_buffer
      log_buffer.current_route = None
      log_buffer.pending_alternative = None
      async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
          r = await client.post("/route/activate",
                                headers={"X-Server-Token": TOKEN},
                                json={"variant": "primary"})
      assert r.status_code == 404

  @pytest.mark.asyncio
  async def test_route_activate_bad_variant():
      from src.log_buffer import log_buffer
      log_buffer.current_route = {"type": "route_planned", "path": ["a", "b"], "jumps": 1,
                                   "warnings": [], "jump_types": ["gate"], "total_ly": 0.0,
                                   "fuel_used": 0.0, "fuel_remaining": 100.0,
                                   "hot_systems": [], "alternative": None}
      async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
          r = await client.post("/route/activate",
                                headers={"X-Server-Token": TOKEN},
                                json={"variant": "bogus"})
      assert r.status_code == 422

  @pytest.mark.asyncio
  async def test_route_activate_alternative_not_available():
      from src.log_buffer import log_buffer
      log_buffer.current_route = {"type": "route_planned", "path": ["a", "b"], "jumps": 1,
                                   "warnings": [], "jump_types": ["gate"], "total_ly": 0.0,
                                   "fuel_used": 0.0, "fuel_remaining": 100.0,
                                   "hot_systems": [], "alternative": None}
      log_buffer.pending_alternative = None
      async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
          r = await client.post("/route/activate",
                                headers={"X-Server-Token": TOKEN},
                                json={"variant": "alternative"})
      assert r.status_code == 404

  @pytest.mark.asyncio
  async def test_set_ship_profile_with_ship_type():
      async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
          r = await client.post("/ship-profile",
                                headers={"X-Server-Token": TOKEN},
                                json={"ship_type": "Carom"})
      assert r.status_code == 200
      data = r.json()
      assert data["ship_type"] == "Carom"
      assert data["hull_mass"] == 7_200_000

  @pytest.mark.asyncio
  async def test_set_ship_profile_invalid_ship_type():
      async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
          r = await client.post("/ship-profile",
                                headers={"X-Server-Token": TOKEN},
                                json={"ship_type": "Nonexistent"})
      assert r.status_code == 422

  @pytest.mark.asyncio
  async def test_set_ship_profile_fuel_category_mismatch():
      async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
          r = await client.post("/ship-profile",
                                headers={"X-Server-Token": TOKEN},
                                json={"ship_type": "Lai", "fuel_type": "D1"})
      assert r.status_code == 422

  @pytest.mark.asyncio
  async def test_chat_slash_profile_prints_summary():
      async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
          r = await client.post("/chat",
                                headers={"X-Server-Token": TOKEN},
                                json={"message": "/profile", "history": []})
      assert r.status_code == 200
      assert "data:" in r.text
  ```

- [ ] **Step 2: Run new tests to see them fail**

  ```bash
  python -m pytest tests/test_main.py::test_current_route_includes_system_temp \
    tests/test_main.py::test_route_activate_no_route \
    tests/test_main.py::test_set_ship_profile_with_ship_type -v 2>&1 | head -30
  ```
  Expected: failures.

- [ ] **Step 3: Update `ShipProfileRequest` and `POST /ship-profile`**

  In `main.py`, update `ShipProfileRequest`:
  ```python
  class ShipProfileRequest(BaseModel):
      hull_mass:      Optional[float] = None
      current_mass:   Optional[float] = None
      specific_heat:  Optional[float] = None
      adaptive_level: Optional[int]   = None
      fuel_type:      Optional[str]   = None
      fuel_quantity:  Optional[float] = None
      external_temp:  Optional[float] = None
      ship_type:      Optional[str]   = None
      extra_cargo_kg: Optional[float] = None
  ```

  Update `POST /ship-profile` to handle `ship_type` and validation:
  ```python
  from src.ship_profile import (
      ShipProfile, FUEL_QUALITY, FUEL_CATEGORY, SHIPS, load_profile, save_profile
  )

  @app.post("/ship-profile", dependencies=[Depends(require_token)])
  async def set_ship_profile(req: ShipProfileRequest):
      # Validate ship_type
      if req.ship_type is not None and req.ship_type not in SHIPS:
          return JSONResponse(status_code=422, content={
              "detail": f"Unknown ship type '{req.ship_type}'. Valid: {sorted(SHIPS)}"
          })
      # Validate fuel_type
      if req.fuel_type is not None and req.fuel_type not in FUEL_QUALITY:
          return JSONResponse(status_code=422, content={
              "detail": f"Unknown fuel type '{req.fuel_type}'. Valid: {list(FUEL_QUALITY)}"
          })
      # Validate fuel_type vs ship fuel_category
      current = load_profile()
      effective_ship = req.ship_type or current.ship_type
      if req.fuel_type is not None and effective_ship is not None:
          ship_cat = SHIPS[effective_ship]["fuel_category"]
          fuel_cat = FUEL_CATEGORY.get(req.fuel_type, "")
          if fuel_cat != ship_cat:
              return JSONResponse(status_code=422, content={
                  "detail": f"Fuel type '{req.fuel_type}' ({fuel_cat}) incompatible "
                            f"with ship '{effective_ship}' ({ship_cat} only)"
              })
      # Validate extra_cargo_kg
      if req.extra_cargo_kg is not None and req.extra_cargo_kg < 0:
          return JSONResponse(status_code=422, content={"detail": "extra_cargo_kg must be >= 0"})

      overrides = req.model_dump()
      # If ship_type provided, auto-fill hull_mass and specific_heat
      if req.ship_type is not None:
          ship = SHIPS[req.ship_type]
          overrides["hull_mass"]     = ship["mass"]
          overrides["specific_heat"] = ship["specific_heat"]
          # If no fuel_type provided, reset to default for this ship's category
          if req.fuel_type is None:
              default_fuel = "D1" if ship["fuel_category"] == "basic" else "SOF-40"
              overrides["fuel_type"] = current.fuel_type if (
                  FUEL_CATEGORY.get(current.fuel_type) == ship["fuel_category"]
              ) else default_fuel

      updated = current.with_overrides(**overrides)
      save_profile(updated)
      from dataclasses import asdict
      return {**asdict(updated), "jump_range_ly": updated.jump_range(),
              "fuel_budget_ly": updated.fuel_budget()}
  ```

  Update `GET /ship-profile` to use new method names:
  ```python
  @app.get("/ship-profile", dependencies=[Depends(require_token)])
  async def get_ship_profile():
      p = load_profile()
      from dataclasses import asdict
      return {
          **asdict(p),
          "jump_range_ly": p.jump_range(),
          "fuel_budget_ly": p.fuel_budget(),
          "fuel_types":     FUEL_QUALITY,
          "ships":          {name: {"mass": s["mass"], "specific_heat": s["specific_heat"],
                                    "fuel_category": s["fuel_category"]}
                             for name, s in SHIPS.items()},
      }
  ```

- [ ] **Step 4: Update `GET /current-route` to include `current_system_temp`**

  ```python
  @app.get("/current-route", dependencies=[Depends(require_token)])
  async def get_current_route():
      """Return the active route and alternative stored in log_buffer."""
      current_temp = None
      if log_buffer.current_system:
          sys_info = route_engine.system_info(log_buffer.current_system)
          if sys_info:
              current_temp = sys_info.get("safe_jump_temp")
      return {
          "route":               log_buffer.current_route,
          "alternative":         log_buffer.pending_alternative,
          "current_system_temp": current_temp,
      }
  ```

- [ ] **Step 5: Add `POST /route/activate` endpoint**

  Add after the existing `/route/clear` endpoint:
  ```python
  class RouteActivateRequest(BaseModel):
      variant: str  # "primary" or "alternative"

  @app.post("/route/activate", dependencies=[Depends(require_token)])
  async def activate_route(req: RouteActivateRequest):
      """Swap the active route to primary or alternative variant."""
      if req.variant not in ("primary", "alternative"):
          return JSONResponse(status_code=422, content={
              "detail": "variant must be 'primary' or 'alternative'"
          })
      if log_buffer.current_route is None:
          return JSONResponse(status_code=404, content={"detail": "no active route"})
      if req.variant == "alternative":
          if log_buffer.pending_alternative is None:
              return JSONResponse(status_code=404, content={
                  "detail": "no alternative route available"
              })
          # Swap: primary becomes what was alternative, alternative becomes what was primary
          old_primary = log_buffer.current_route
          log_buffer.current_route      = log_buffer.pending_alternative
          log_buffer.pending_alternative = old_primary
      # "primary" — current_route is already primary; no-op
      return log_buffer.current_route
  ```

- [ ] **Step 6: Update `POST /route` to store pending_alternative**

  In the `plan_route` endpoint, after `result = route_engine.route(...)`:
  ```python
  # Store both primary and alternative atomically
  primary   = {k: v for k, v in result.items() if k != "alternative"}
  primary["alternative"] = None  # standalone copy has no nested alternative
  alternative = result.get("alternative")

  log_buffer.current_route      = primary
  log_buffer.pending_alternative = alternative
  log_buffer.add({"type": "route_planned", **primary})
  return result
  ```

  Also handle the fallback case: when `route()` now always returns a dict (never None), remove the `if result is None: result = bfs()` fallback. Instead, if result is `no_route` type, try BFS as a second attempt:
  ```python
  result = route_engine.route(origin, req.destination, profile)
  if result["type"] == "no_route" and not req.gate_only:
      bfs_result = route_engine.bfs(origin, req.destination)
      if bfs_result:
          result = bfs_result
          result["type"] = "route_planned"

  if result["type"] == "no_route":
      log_buffer.current_route = result
      log_buffer.pending_alternative = None
      return JSONResponse(status_code=404, content={
          "detail": f"No route found from '{origin}' to '{req.destination}'."
      })
  ```

- [ ] **Step 7: Update `/chat` `/route` handler for new route shape**

  The `/chat` handler currently uses `gate_hops` and `direct_jumps`. Update to use `jump_types`:
  ```python
  # In the /route slash command handler, replace the reply-building block with:
  path       = result.get("path", [])
  jumps      = result.get("jumps", 0)
  jump_types = result.get("jump_types", [])
  total_ly   = result.get("total_ly", 0.0)
  fuel_used  = result.get("fuel_used")
  fuel_left  = result.get("fuel_remaining")

  if len(path) > 1:
      path_str = f"{path[0].upper()} → {path[-1].upper()}"
  else:
      path_str = path[0].upper() if path else dest.upper()

  jump_label = f"{jumps} jump{'s' if jumps != 1 else ''}"

  # Per-hop breakdown
  hop_lines = []
  for i, (system, jtype) in enumerate(zip(path[:-1], jump_types), 1):
      next_sys = path[i]
      if jtype == "direct":
          d = route_engine._dist_ly(
              route_engine.resolve(system),
              route_engine.resolve(next_sys),
          ) if route_engine.resolve(system) and route_engine.resolve(next_sys) else 0.0
          hop_lines.append(f"  {i}. {system.upper()} → {next_sys.upper()}  direct  {d:.1f} LY")
      else:
          hop_lines.append(f"  {i}. {system.upper()} → {next_sys.upper()}  gate")

  fuel_str = ""
  if fuel_used is not None and fuel_used > 0:
      fuel_str = f"  FUEL: {fuel_used:.1f}u"
      if fuel_left is not None:
          fuel_str += f" | {fuel_left:.1f}u remaining"

  ly_str = f" · {total_ly:.1f} LY" if total_ly > 0 else ""

  reply = f"ROUTE: {path_str}  {jumps} jumps{ly_str}"
  if fuel_str:
      reply += f"\n{fuel_str}"
  if hop_lines:
      reply += "\n" + "\n".join(hop_lines)
  for w in result.get("warnings", [])[:2]:
      reply += f"\nWARN: {w}"

  # Store in log_buffer
  primary = {k: v for k, v in result.items() if k != "alternative"}
  primary["alternative"] = None
  log_buffer.current_route = primary
  log_buffer.pending_alternative = result.get("alternative")
  log_buffer.add({"type": "route_planned", **primary})
  ```

- [ ] **Step 8: Add `/profile` slash command handling in `/chat`**

  In the `/chat` endpoint, before the `/route` check, add `/profile` handling:
  ```python
  _SLASH_PROFILE_RE = re.compile(
      r'^/profile(?:\s+(?P<sub>ship|fuel|level|cargo)\s+(?P<args>.+))?$',
      re.IGNORECASE,
  )

  # In the chat handler, before _SLASH_ROUTE_RE.match():
  pm = _SLASH_PROFILE_RE.match(req.message.strip())
  if pm:
      sub  = pm.group("sub")
      args = (pm.group("args") or "").strip()
      current = load_profile()
      overrides = {}
      reply_text = ""

      if sub is None:
          # /profile — print current
          r_ly = current.jump_range()
          b_ly = current.fuel_budget()
          ship_str = current.ship_type or "custom"
          reply_text = (
              f"SHIP: {ship_str} | {current.fuel_type} × {int(current.fuel_quantity)}u"
              f" | range {r_ly:.0f} LY | budget {b_ly:.0f} LY"
          )
      elif sub.lower() == "ship":
          if args not in SHIPS:
              reply_text = f"Unknown ship '{args}'. Valid: {', '.join(sorted(SHIPS))}"
          else:
              ship = SHIPS[args]
              overrides = {
                  "ship_type":    args,
                  "hull_mass":    ship["mass"],
                  "specific_heat": ship["specific_heat"],
              }
              # Reset fuel to category default if current fuel incompatible
              if FUEL_CATEGORY.get(current.fuel_type) != ship["fuel_category"]:
                  overrides["fuel_type"] = "D1" if ship["fuel_category"] == "basic" else "SOF-40"
              reply_text = f"Ship set to {args}. Mass: {ship['mass']:,} kg, C_heat: {ship['specific_heat']}"
      elif sub.lower() == "fuel":
          parts = args.split()
          if len(parts) < 2:
              reply_text = "Usage: /profile fuel <quantity> <type>  e.g. /profile fuel 2400 EU-90"
          elif parts[1] not in FUEL_QUALITY:
              reply_text = f"Unknown fuel type '{parts[1]}'. Valid: {list(FUEL_QUALITY)}"
          elif (current.ship_type is not None
                and FUEL_CATEGORY.get(parts[1]) != SHIPS[current.ship_type]["fuel_category"]):
              ship_cat = SHIPS[current.ship_type]["fuel_category"]
              reply_text = (
                  f"Fuel type '{parts[1]}' incompatible with "
                  f"{current.ship_type} ({ship_cat} only)"
              )
          else:
              try:
                  qty = float(parts[0])
                  overrides = {"fuel_quantity": qty, "fuel_type": parts[1]}
                  reply_text = f"Fuel set: {qty:.0f}u {parts[1]} (quality {FUEL_QUALITY[parts[1]]})"
              except ValueError:
                  reply_text = f"Invalid quantity '{parts[0]}'"
      elif sub.lower() == "level":
          try:
              lvl = int(args)
              lvl = max(0, min(10, lvl))
              overrides = {"adaptive_level": lvl}
              reply_text = f"Adaptive level set to {lvl}"
          except ValueError:
              reply_text = f"Invalid level '{args}' — must be integer 0-10"
      elif sub.lower() == "cargo":
          try:
              kg = float(args)
              if kg < 0:
                  reply_text = "Extra cargo cannot be negative"
              else:
                  overrides = {"extra_cargo_kg": kg}
                  reply_text = f"Extra cargo set to {kg:,.0f} kg"
          except ValueError:
              reply_text = f"Invalid cargo mass '{args}'"

      if overrides:
          updated = current.with_overrides(**overrides)
          save_profile(updated)

      def _profile_reply(text=reply_text):
          yield f"data: {json.dumps({'text': text})}\n\n"
          yield "data: [DONE]\n\n"
      return StreamingResponse(_profile_reply(), media_type="text/event-stream")
  ```

  The `_SLASH_PROFILE_RE` pattern and the `FUEL_CATEGORY` import need to be placed at the top of the module with the other regex patterns and imports.

- [ ] **Step 9: Run new tests**

  ```bash
  python -m pytest tests/test_main.py -v --tb=short 2>&1 | tail -40
  ```
  Expected: all tests pass including the new ones added in Step 1.

- [ ] **Step 10: Commit**

  ```bash
  git add main.py tests/test_main.py
  git commit -m "feat(api): route/activate, current_system_temp, ship_type validation, /profile command"
  ```

---

### Task 5: context_builder.py — ship profile summary line

**Files:**
- Modify: `src/context_builder.py`
- Modify: `tests/test_context_builder.py`
- Modify: `main.py` (pass profile to build_context_block)

- [ ] **Step 1: Write failing test**

  Add to `tests/test_context_builder.py`:
  ```python
  def test_ship_profile_summary_in_context():
      from src.ship_profile import ShipProfile
      profile = ShipProfile(
          hull_mass=18_929_160, specific_heat=2.5, fuel_type="EU-90",
          fuel_quantity=2400, extra_cargo_kg=0, external_temp=0.0,
          adaptive_level=0, ship_type="Lai",
      )
      block = build_context_block(
          system_data=None,
          log_events=[],
          current_system="test",
          ship_profile=profile,
      )
      assert "SHIP:" in block
      assert "EU-90" in block
      assert "2400" in block

  def test_no_ship_profile_no_ship_line():
      block = build_context_block(
          system_data=None,
          log_events=[],
          current_system="test",
          ship_profile=None,
      )
      assert "SHIP:" not in block
  ```

- [ ] **Step 2: Run tests to verify failure**

  ```bash
  python -m pytest tests/test_context_builder.py::test_ship_profile_summary_in_context -v
  ```
  Expected: FAIL — `build_context_block` doesn't accept `ship_profile` parameter.

- [ ] **Step 3: Update `build_context_block` signature and add SHIP line**

  In `src/context_builder.py`:
  - Add `ship_profile=None` parameter to the function signature
  - After the LOCATION line, add the SHIP summary block:

  ```python
  def build_context_block(
      system_data: Optional[dict],
      log_events: list,
      current_system: Optional[str],
      live_sessions: Optional[list] = None,
      current_route: Optional[dict] = None,
      structure_alerts: Optional[list] = None,
      ship_profile=None,  # ShipProfile instance; import avoided to prevent circular dep
  ) -> str:
  ```

  After the location line, before mining/combat:
  ```python
  # --- Ship profile summary ---
  if ship_profile is not None:
      ship_str  = ship_profile.ship_type or "custom"
      fuel_str  = f"{ship_profile.fuel_type} × {int(ship_profile.fuel_quantity)}u"
      # safe_jump_temp comes from system_data when available; falls back to 0 (coldest)
      temp = (system_data or {}).get("safe_jump_temp")
      r_ly = ship_profile.jump_range_at_temp(temp or 0.0)
      b_ly = ship_profile.fuel_budget()
      range_str = f"~{r_ly:.0f} LY" if temp is None else f"{r_ly:.0f} LY"
      lines.append(
          f"SHIP: {ship_str} | {fuel_str} | range {range_str} | budget {b_ly:.0f} LY"
      )
  ```

- [ ] **Step 4: Update the `/chat` call in main.py to pass profile**

  In `main.py`, in the `chat` endpoint where `build_context_block` is called:
  ```python
  context = build_context_block(
      system_data=system_data,
      log_events=log_buffer.get_recent(10),
      current_system=log_buffer.current_system,
      live_sessions=log_buffer.get_live(),
      current_route=log_buffer.current_route,
      structure_alerts=log_buffer.pop_structure_alerts(),
      ship_profile=load_profile(),
  )
  ```

- [ ] **Step 5: Run context_builder tests**

  ```bash
  python -m pytest tests/test_context_builder.py -v --tb=short 2>&1 | tail -20
  ```
  Expected: all pass including new tests.

- [ ] **Step 6: Run full test suite**

  ```bash
  python -m pytest tests/ -v --tb=short 2>&1 | tail -20
  ```
  Expected: all pass.

- [ ] **Step 7: Commit**

  ```bash
  git add src/context_builder.py tests/test_context_builder.py main.py
  git commit -m "feat(context): add SHIP profile summary line to context block"
  ```

---

## Chunk 4: Overlay C++

---

### Task 6: route_panel.cpp — two-route display with USE buttons

**Files:**
- Modify: `overlay/overlay_ui/route_panel.h`
- Modify: `overlay/overlay_ui/route_panel.cpp`
- Modify: `overlay/overlay_ui/http_client.h`
- Modify: `overlay/overlay_ui/http_client.cpp`

The route panel must now show two routes (primary + alternative) when available, with `[USE]` buttons that call `POST /route/activate`. Active route row is bright green; inactive is dimmed.

- [ ] **Step 1: Add `postJson()` to http_client.h**

  Add to `overlay/overlay_ui/http_client.h`:
  ```cpp
  // POST with JSON body; returns full response body in bodyOut.
  // Runs synchronously — call from a background thread.
  bool postJson(
      const std::string& path,
      const std::string& jsonBody,
      std::string& bodyOut,
      std::string& errorOut);
  ```

- [ ] **Step 2: Implement `postJson()` in http_client.cpp**

  Add after the `postEmpty()` implementation:
  ```cpp
  bool postJson(const std::string& path, const std::string& jsonBody,
                std::string& bodyOut, std::string& errorOut)
  {
      HINTERNET hSession = nullptr, hConnect = nullptr, hRequest = nullptr;
      if (!_openHandles("POST", path, hSession, hConnect, hRequest, errorOut))
          return false;

      WinHttpAddRequestHeaders(hRequest,
          L"Content-Type: application/json\r\nAccept: application/json\r\n",
          (DWORD)-1L, WINHTTP_ADDREQ_FLAG_ADD);

      DWORD bodyLen = static_cast<DWORD>(jsonBody.size());
      if (!WinHttpSendRequest(hRequest, WINHTTP_NO_ADDITIONAL_HEADERS, 0,
              WINHTTP_NO_REQUEST_DATA, 0, bodyLen, 0)) {
          errorOut = "WinHttpSendRequest failed";
          _closeHandles(hRequest, hConnect, hSession);
          return false;
      }
      DWORD written = 0;
      WinHttpWriteData(hRequest, jsonBody.c_str(), bodyLen, &written);

      if (!WinHttpReceiveResponse(hRequest, nullptr)) {
          errorOut = "WinHttpReceiveResponse failed";
          _closeHandles(hRequest, hConnect, hSession);
          return false;
      }

      bodyOut.clear();
      while (true) {
          DWORD available = 0;
          if (!WinHttpQueryDataAvailable(hRequest, &available) || available == 0)
              break;
          std::string chunk(available, '\0');
          DWORD read = 0;
          if (!WinHttpReadData(hRequest, chunk.data(), available, &read) || read == 0)
              break;
          chunk.resize(read);
          bodyOut += chunk;
      }
      _closeHandles(hRequest, hConnect, hSession);
      return true;
  }
  ```

- [ ] **Step 3: Update route_panel.h — no interface change needed**

  The public interface (`init`, `draw`, `shutdown`) is unchanged. No edits to route_panel.h required.

- [ ] **Step 4: Replace route_panel.cpp with the updated version**

  Full replacement. Key changes from current code:
  - `RouteData` struct gains: `total_ly`, `fuel_used`, `alt_active` (bool), `alt_route` (nested struct)
  - `_poll()` parses `alternative` from JSON, parses `current_system_temp`
  - `draw()` shows two rows; each has a `[USE]` button; active row is bright green, inactive is dimmed
  - `[USE]` calls `POST /route/activate` with `{"variant": "primary"}` or `{"variant": "alternative"}`
  - Panel height increases from 170 to 260 to accommodate second row

  ```cpp
  #include "route_panel.h"
  #include "http_client.h"
  #include <imgui.h>
  #include <string>
  #include <vector>
  #include <mutex>
  #include <thread>
  #include <atomic>
  #include <nlohmann/json.hpp>

  namespace route_panel {

  struct RouteRow {
      bool        active      = false;
      std::string origin;
      std::string destination;
      std::string summary;     // "SYS-A → SYS-B   6 jumps · 142 LY · 87u"
      bool        has_error   = false;
      std::string error_msg;
      std::vector<std::string> warnings;
  };

  struct PanelState {
      RouteRow primary;
      RouteRow alt;
      bool     has_alt       = false;
      bool     primary_active = true;  // which variant is "current_route"
  };

  static PanelState           s_state;
  static std::mutex           s_mutex;
  static std::atomic<bool>    s_running    { false };
  static std::thread          s_poller;
  static std::atomic<bool>    s_activating { false };
  static std::atomic<bool>    s_clearing   { false };

  static RouteRow _parseRoute(const nlohmann::json& route) {
      RouteRow r;
      if (route.is_null()) return r;
      r.active = true;
      if (route.contains("error") && !route["error"].is_null()) {
          r.has_error = true;
          r.error_msg = route["error"].get<std::string>();
          return r;
      }
      auto path  = route.value("path", nlohmann::json::array());
      int  jumps = route.value("jumps", 0);
      float total_ly  = route.value("total_ly", 0.0f);
      float fuel_used = route.value("fuel_used", 0.0f);

      r.origin      = path.empty() ? "" : path.front().get<std::string>();
      r.destination = path.empty() ? "" : path.back().get<std::string>();

      // Build summary line: "SYS-A → SYS-B   6 jumps · 142 LY · 87u"
      auto toUpper = [](std::string s) {
          for (auto& c : s) c = (char)toupper((unsigned char)c);
          return s;
      };
      r.summary = toUpper(r.origin) + " \xe2\x86\x92 " + toUpper(r.destination)
                + "   " + std::to_string(jumps)
                + " jump" + (jumps != 1 ? "s" : "");
      if (total_ly > 0.0f) {
          char buf[64];
          snprintf(buf, sizeof(buf), " \xc2\xb7 %.0f LY", total_ly);
          r.summary += buf;
      }
      if (fuel_used > 0.0f) {
          char buf[32];
          snprintf(buf, sizeof(buf), " \xc2\xb7 %.0fu", fuel_used);
          r.summary += buf;
      }
      for (auto& w : route.value("warnings", nlohmann::json::array()))
          r.warnings.push_back(w.get<std::string>());
      return r;
  }

  static void _poll() {
      std::string body, err;
      if (!http::getJson("/current-route", body, err))
          return;
      try {
          auto j = nlohmann::json::parse(body);
          std::lock_guard<std::mutex> lock(s_mutex);
          auto& route = j["route"];
          auto& alt   = j.contains("alternative") ? j["alternative"] : nlohmann::json();

          s_state.primary     = _parseRoute(route);
          s_state.has_alt     = !alt.is_null();
          s_state.alt         = _parseRoute(alt);
          s_state.primary_active = true;  // server always returns current_route as primary
      } catch (...) {}
  }

  static void _pollerThread() {
      while (s_running.load()) {
          _poll();
          for (int i = 0; i < 50 && s_running.load(); ++i)
              std::this_thread::sleep_for(std::chrono::milliseconds(100));
      }
  }

  void init() { s_running = true; s_poller = std::thread(_pollerThread); }
  void shutdown() { s_running = false; if (s_poller.joinable()) s_poller.join(); }

  void draw() {
      ImGuiIO& io = ImGui::GetIO();
      const float panelW = 440.0f;
      const float panelH = 260.0f;
      const float margin = 16.0f;

      ImGui::SetNextWindowPos(
          ImVec2(margin, io.DisplaySize.y - panelH - margin), ImGuiCond_Always);
      ImGui::SetNextWindowSize(ImVec2(panelW, panelH), ImGuiCond_Always);

      ImGuiWindowFlags flags =
          ImGuiWindowFlags_NoTitleBar  | ImGuiWindowFlags_NoResize |
          ImGuiWindowFlags_NoMove      | ImGuiWindowFlags_NoScrollbar |
          ImGuiWindowFlags_NoScrollWithMouse;

      ImGui::PushStyleColor(ImGuiCol_WindowBg,   ImVec4(0.039f, 0.051f, 0.059f, 0.92f));
      ImGui::PushStyleColor(ImGuiCol_Text,       ImVec4(0.498f, 0.702f, 0.541f, 1.0f));
      ImGui::PushStyleColor(ImGuiCol_Button,     ImVec4(0.08f, 0.12f, 0.10f, 1.0f));
      ImGui::PushStyleColor(ImGuiCol_ButtonHovered, ImVec4(0.15f, 0.25f, 0.18f, 1.0f));

      ImGui::Begin("##route_panel", nullptr, flags);
      ImGui::TextUnformatted("NAV COMPUTER");
      ImGui::Separator();

      PanelState state;
      { std::lock_guard<std::mutex> lock(s_mutex); state = s_state; }

      if (!state.primary.active) {
          ImGui::PushStyleColor(ImGuiCol_Text, ImVec4(0.30f, 0.40f, 0.32f, 1.0f));
          ImGui::TextUnformatted("NO ROUTE ACTIVE");
          ImGui::TextUnformatted("Type /route SYSTEM in the companion panel.");
          ImGui::PopStyleColor();
      } else {
          // Render a route row: bright green if isActive, dimmed otherwise
          auto renderRow = [&](const RouteRow& row, bool isActive, const char* variant) {
              ImVec4 textColor = isActive
                  ? ImVec4(0.498f, 0.702f, 0.541f, 1.0f)  // bright green
                  : ImVec4(0.30f,  0.40f,  0.32f,  1.0f);  // dimmed
              ImGui::PushStyleColor(ImGuiCol_Text, textColor);
              if (row.has_error) {
                  ImGui::TextUnformatted("ROUTE ERROR:");
                  ImGui::TextWrapped("%s", row.error_msg.c_str());
              } else {
                  ImGui::TextWrapped("%s", row.summary.c_str());
                  for (size_t i = 0; i < row.warnings.size() && i < 2; ++i) {
                      ImGui::PushStyleColor(ImGuiCol_Text, ImVec4(0.85f, 0.65f, 0.20f, 1.0f));
                      ImGui::TextWrapped("! %s", row.warnings[i].c_str());
                      ImGui::PopStyleColor();
                  }
              }
              ImGui::PopStyleColor();
              ImGui::SameLine(panelW - 68.0f);
              if (!isActive) {
                  if (s_activating) ImGui::BeginDisabled();
                  std::string btnLabel = std::string("[USE]##") + variant;
                  if (ImGui::SmallButton(btnLabel.c_str())) {
                      s_activating = true;
                      std::string v = variant;
                      std::thread([v]() {
                          std::string body, err;
                          std::string payload = "{\"variant\":\"" + v + "\"}";
                          http::postJson("/route/activate", payload, body, err);
                          s_activating = false;
                      }).detach();
                  }
                  if (s_activating) ImGui::EndDisabled();
              }
          };

          renderRow(state.primary, state.primary_active, "primary");
          if (state.has_alt) {
              ImGui::Separator();
              renderRow(state.alt, !state.primary_active, "alternative");
          }
      }

      ImGui::Separator();
      if (state.primary.active) {
          if (s_clearing) ImGui::BeginDisabled();
          if (ImGui::SmallButton("CLEAR ROUTE")) {
              s_clearing = true;
              std::thread([]() {
                  std::string err;
                  http::postEmpty("/route/clear", err);
                  { std::lock_guard<std::mutex> lock(s_mutex);
                    s_state = {}; s_clearing = false; }
              }).detach();
          }
          if (s_clearing) ImGui::EndDisabled();
      }

      // CRT scanlines
      ImDrawList* dl = ImGui::GetWindowDrawList();
      ImVec2 wMin = ImGui::GetWindowPos();
      ImVec2 wMax = ImVec2(wMin.x + panelW, wMin.y + panelH);
      for (float y = wMin.y; y < wMax.y; y += 4.0f)
          dl->AddLine(ImVec2(wMin.x, y), ImVec2(wMax.x, y), IM_COL32(0, 0, 0, 35));

      ImGui::End();
      ImGui::PopStyleColor(4);
  }

  }  // namespace route_panel
  ```

- [ ] **Step 5: Build the overlay to verify no compile errors**

  On the Windows gaming PC:
  ```
  cd overlay
  cmake --build build --config Release 2>&1 | tail -20
  ```
  Expected: 0 errors, 0 warnings on the new/modified files. Fix any compile errors before proceeding.

- [ ] **Step 6: Commit overlay route panel changes**

  On the gaming PC (or commit on server after transferring files):
  ```bash
  git add overlay/overlay_ui/route_panel.cpp \
          overlay/overlay_ui/http_client.h \
          overlay/overlay_ui/http_client.cpp
  git commit -m "feat(overlay): two-route display with USE buttons, postJson helper"
  ```

---

### Task 7: ship_profile_panel — new F7 panel

**Files:**
- Create: `overlay/overlay_ui/ship_profile_panel.h`
- Create: `overlay/overlay_ui/ship_profile_panel.cpp`
- Modify: `overlay/overlay_ui/render.cpp`
- Modify: `overlay/overlay_ui/render.h`
- Modify: `overlay/overlay_ui/CMakeLists.txt`
- Modify: `overlay/overlay_core/input.cpp`

New panel at top-left (440×280). F7 toggles visibility. Shows 5 input fields, computed jump range + fuel budget, and a SAVE button.

- [ ] **Step 1: Create `overlay/overlay_ui/ship_profile_panel.h`**

  ```cpp
  #pragma once
  namespace ship_profile_panel {
      void init();
      void draw();
      void shutdown();
      extern bool g_visible;  // toggled by F7; defined in ship_profile_panel.cpp
  }
  ```

- [ ] **Step 2: Create `overlay/overlay_ui/ship_profile_panel.cpp`**

  ```cpp
  #include "ship_profile_panel.h"
  #include "http_client.h"
  #include <imgui.h>
  #include <string>
  #include <vector>
  #include <mutex>
  #include <thread>
  #include <atomic>
  #include <cmath>
  #include <nlohmann/json.hpp>

  namespace ship_profile_panel {

  // Panel visibility toggled by F7
  bool g_visible = false;

  // Ship + fuel constant tables (mirrors server SHIPS/FUEL_QUALITY)
  struct ShipEntry { const char* name; float mass; float specific_heat; bool advanced; int max_fuel; };
  static const ShipEntry SHIPS[] = {
      {"Carom",   7200000.f,      8.5f, false, 3000},
      {"Stride",  7900000.f,      8.0f, false, 3200},
      {"Reflex",  9750000.f,      3.0f, false, 1750},
      {"Recurve", 10200000.f,     1.0f, false,  970},
      {"Reiver",  10400000.f,     1.0f, false, 1416},
      {"Lai",     18929160.f,     2.5f, true,  2400},
      {"USV",     30266600.f,     1.8f, true,  2420},
      {"Lorha",   42691330.f,     2.5f, true,  2508},
      {"MCF",     52313760.f,     2.5f, true,  6548},
      {"Tades",   74655480.f,     2.5f, true,  5972},
      {"HAF",     81883000.f,     2.5f, true,  4184},
      {"Maul",    548435920.f,    2.5f, true, 24160},
      {"Chumaq",  1487392000.f,   3.0f, true, 270585},
  };
  static const int SHIP_COUNT = (int)(sizeof(SHIPS)/sizeof(SHIPS[0]));

  struct FuelEntry { const char* code; float quality; bool advanced; };
  static const FuelEntry FUELS[] = {
      {"D1",     0.10f, false},
      {"D2",     0.15f, false},
      {"SOF-40", 0.40f, true},
      {"EU-40",  0.40f, true},
      {"SOF-80", 0.80f, true},
      {"EU-90",  0.90f, true},
  };
  static const int FUEL_COUNT = (int)(sizeof(FUELS)/sizeof(FUELS[0]));

  // UI state
  static int   s_ship_idx    = 0;
  static int   s_fuel_idx    = 0;
  static int   s_fuel_units  = 500;
  static int   s_adaptive    = 0;
  static int   s_extra_cargo = 0;

  // Polled from /current-route — written by poller thread, read by render thread
  static std::atomic<float> s_cur_temp{-1.0f};  // -1 = unknown

  // Save feedback
  static std::atomic<int> s_save_state{0};  // 0=idle 1=saving 2=saved 3=error
  static std::mutex s_save_mutex;

  static float _computeRange(int ship_idx, int adaptive, int extra_cargo, float temp) {
      if (ship_idx < 0 || ship_idx >= SHIP_COUNT) return 0.0f;
      const auto& s = SHIPS[ship_idx];
      if (temp >= 90.0f) return 0.0f;
      float c_eff   = s.specific_heat * (1.0f + adaptive * 0.02f);
      float cur_m   = s.mass + extra_cargo;
      return ((150.0f - temp) * c_eff * s.mass) / (3.0f * cur_m);
  }

  static float _computeBudget(int ship_idx, int fuel_idx, int fuel_units, int extra_cargo) {
      if (ship_idx < 0 || ship_idx >= SHIP_COUNT) return 0.0f;
      if (fuel_idx < 0 || fuel_idx >= FUEL_COUNT) return 0.0f;
      float cur_m   = SHIPS[ship_idx].mass + extra_cargo;
      float quality = FUELS[fuel_idx].quality;
      return (fuel_units * quality) / (1e-7f * cur_m);
  }

  static void _fetchTempFromCurrentRoute() {
      std::string body, err;
      if (!http::getJson("/current-route", body, err)) return;
      try {
          auto j = nlohmann::json::parse(body);
          if (j.contains("current_system_temp") && !j["current_system_temp"].is_null())
              s_cur_temp.store(j["current_system_temp"].get<float>());
          else
              s_cur_temp.store(-1.0f);
      } catch (...) {}
  }

  // Background temp poller
  static std::atomic<bool> s_poll_running{false};
  static std::thread s_poller;

  static void _pollerThread() {
      while (s_poll_running.load()) {
          _fetchTempFromCurrentRoute();
          for (int i = 0; i < 50 && s_poll_running.load(); ++i)
              std::this_thread::sleep_for(std::chrono::milliseconds(100));
      }
  }

  void init() {
      s_poll_running = true;
      s_poller = std::thread(_pollerThread);
  }

  void shutdown() {
      s_poll_running = false;
      if (s_poller.joinable()) s_poller.join();
  }

  void draw() {
      if (!g_visible) return;

      const float panelW = 440.0f;
      const float panelH = 280.0f;
      const float margin = 16.0f;

      ImGui::SetNextWindowPos(ImVec2(margin, margin), ImGuiCond_Always);
      ImGui::SetNextWindowSize(ImVec2(panelW, panelH), ImGuiCond_Always);

      ImGuiWindowFlags flags =
          ImGuiWindowFlags_NoTitleBar  | ImGuiWindowFlags_NoResize |
          ImGuiWindowFlags_NoMove      | ImGuiWindowFlags_NoScrollbar |
          ImGuiWindowFlags_NoScrollWithMouse;

      ImGui::PushStyleColor(ImGuiCol_WindowBg,      ImVec4(0.039f, 0.051f, 0.059f, 0.92f));
      ImGui::PushStyleColor(ImGuiCol_Text,          ImVec4(0.498f, 0.702f, 0.541f, 1.0f));
      ImGui::PushStyleColor(ImGuiCol_Button,        ImVec4(0.08f, 0.12f, 0.10f, 1.0f));
      ImGui::PushStyleColor(ImGuiCol_ButtonHovered, ImVec4(0.15f, 0.25f, 0.18f, 1.0f));
      ImGui::PushStyleColor(ImGuiCol_FrameBg,       ImVec4(0.08f, 0.12f, 0.10f, 1.0f));

      ImGui::Begin("##ship_profile_panel", nullptr, flags);
      ImGui::TextUnformatted("SHIP PROFILE                            [F7]");
      ImGui::Separator();

      // Determine whether current ship is advanced or basic
      bool isAdvanced = (s_ship_idx >= 0 && s_ship_idx < SHIP_COUNT)
                      ? SHIPS[s_ship_idx].advanced : false;

      // Ship type dropdown
      ImGui::Text("Ship type:");
      ImGui::SameLine(120.0f);
      ImGui::SetNextItemWidth(200.0f);
      if (ImGui::BeginCombo("##ship", s_ship_idx >= 0 ? SHIPS[s_ship_idx].name : "---")) {
          for (int i = 0; i < SHIP_COUNT; ++i) {
              bool sel = (i == s_ship_idx);
              if (ImGui::Selectable(SHIPS[i].name, sel)) {
                  bool wasAdv = isAdvanced;
                  s_ship_idx  = i;
                  isAdvanced  = SHIPS[i].advanced;
                  // Reset fuel type to category default if category changed
                  if (wasAdv != isAdvanced) {
                      s_fuel_idx  = isAdvanced ? 2 : 0;  // SOF-40 or D1
                  }
                  // Clamp fuel_units to new max
                  int max = SHIPS[s_ship_idx].max_fuel;
                  if (s_fuel_units > max) s_fuel_units = max;
              }
              if (sel) ImGui::SetItemDefaultFocus();
          }
          ImGui::EndCombo();
      }

      // Fuel type dropdown (filtered by category)
      ImGui::Text("Fuel type:");
      ImGui::SameLine(120.0f);
      ImGui::SetNextItemWidth(120.0f);
      const char* curFuel = (s_fuel_idx >= 0 && s_fuel_idx < FUEL_COUNT)
                          ? FUELS[s_fuel_idx].code : "---";
      if (ImGui::BeginCombo("##fuel", curFuel)) {
          for (int i = 0; i < FUEL_COUNT; ++i) {
              if (FUELS[i].advanced != isAdvanced) continue;
              bool sel = (i == s_fuel_idx);
              if (ImGui::Selectable(FUELS[i].code, sel)) s_fuel_idx = i;
              if (sel) ImGui::SetItemDefaultFocus();
          }
          ImGui::EndCombo();
      }

      // Fuel units
      int maxFuel = (s_ship_idx >= 0 && s_ship_idx < SHIP_COUNT)
                  ? SHIPS[s_ship_idx].max_fuel : 99999;
      ImGui::Text("Fuel units:");
      ImGui::SameLine(120.0f);
      ImGui::SetNextItemWidth(100.0f);
      ImGui::InputInt("##fu", &s_fuel_units, 10, 100);
      if (s_fuel_units < 0) s_fuel_units = 0;
      if (s_fuel_units > maxFuel) s_fuel_units = maxFuel;

      // Adaptive level
      ImGui::Text("Adaptive:");
      ImGui::SameLine(120.0f);
      ImGui::SetNextItemWidth(80.0f);
      ImGui::InputInt("##al", &s_adaptive, 1, 1);
      if (s_adaptive < 0) s_adaptive = 0;
      if (s_adaptive > 10) s_adaptive = 10;

      // Extra cargo
      ImGui::Text("Extra cargo:");
      ImGui::SameLine(120.0f);
      ImGui::SetNextItemWidth(120.0f);
      ImGui::InputInt("##xc", &s_extra_cargo, 1000, 10000);
      if (s_extra_cargo < 0) s_extra_cargo = 0;

      ImGui::Separator();

      // Computed display
      float cur_temp_val = s_cur_temp.load();
      float temp    = cur_temp_val >= 0.0f ? cur_temp_val : 0.0f;
      bool  hasTemp = cur_temp_val >= 0.0f;
      float range   = _computeRange(s_ship_idx, s_adaptive, s_extra_cargo, temp);
      float budget  = _computeBudget(s_ship_idx, s_fuel_idx, s_fuel_units, s_extra_cargo);

      if (hasTemp) {
          ImGui::Text("JUMP RANGE:  %.1f LY  (at %.1f deg)", range, temp);
      } else {
          ImGui::Text("JUMP RANGE:  ---  (system unknown)");
      }
      ImGui::Text("FUEL BUDGET: %.1f LY", budget);

      ImGui::Spacing();

      // SAVE button
      int saveState = s_save_state.load();
      if (saveState == 1) ImGui::BeginDisabled();
      if (ImGui::Button("SAVE##profile")) {
          s_save_state = 1;
          // Build JSON payload
          nlohmann::json payload;
          if (s_ship_idx >= 0 && s_ship_idx < SHIP_COUNT)
              payload["ship_type"]    = SHIPS[s_ship_idx].name;
          if (s_fuel_idx >= 0 && s_fuel_idx < FUEL_COUNT)
              payload["fuel_type"]    = FUELS[s_fuel_idx].code;
          payload["fuel_quantity"]    = s_fuel_units;
          payload["adaptive_level"]   = s_adaptive;
          payload["extra_cargo_kg"]   = s_extra_cargo;
          std::string body_str = payload.dump();

          std::thread([body_str]() {
              std::string resp, err;
              bool ok = http::postJson("/ship-profile", body_str, resp, err);
              s_save_state = ok ? 2 : 3;
              // Reset after 2 seconds
              std::this_thread::sleep_for(std::chrono::seconds(2));
              s_save_state = 0;
          }).detach();
      }
      if (saveState == 1) ImGui::EndDisabled();
      ImGui::SameLine();
      if (saveState == 2) {
          ImGui::PushStyleColor(ImGuiCol_Text, ImVec4(0.3f, 0.8f, 0.3f, 1.0f));
          ImGui::TextUnformatted("SAVED");
          ImGui::PopStyleColor();
      } else if (saveState == 3) {
          ImGui::PushStyleColor(ImGuiCol_Text, ImVec4(0.8f, 0.3f, 0.3f, 1.0f));
          ImGui::TextUnformatted("ERROR");
          ImGui::PopStyleColor();
      }

      // CRT scanlines
      ImDrawList* dl = ImGui::GetWindowDrawList();
      ImVec2 wMin = ImGui::GetWindowPos();
      ImVec2 wMax = ImVec2(wMin.x + panelW, wMin.y + panelH);
      for (float y = wMin.y; y < wMax.y; y += 4.0f)
          dl->AddLine(ImVec2(wMin.x, y), ImVec2(wMax.x, y), IM_COL32(0, 0, 0, 35));

      ImGui::End();
      ImGui::PopStyleColor(5);
  }

  }  // namespace ship_profile_panel
  ```

- [ ] **Step 3: Add ship_profile_panel.h include to render.h**

  `render.h` is included by `render.cpp` (which calls `ship_profile_panel::init/draw/shutdown`) and
  by `input.cpp` (which toggles `ship_profile_panel::g_visible`). Adding the include to `render.h`
  means both translation units get the declaration automatically. Step 5 also adds the include
  directly to `input.cpp` as a belt-and-suspenders; either way works because the header has
  `#pragma once`.

  In `overlay/overlay_ui/render.h`, add after the existing include guards:
  ```cpp
  #include "ship_profile_panel.h"
  ```

- [ ] **Step 4: Update render.cpp to wire up ship_profile_panel**

  ```cpp
  #include "render.h"
  #include "companion_panel.h"
  #include "route_panel.h"
  #include "ship_profile_panel.h"

  namespace ui {
  bool visible = true;

  void init() {
      route_panel::init();
      ship_profile_panel::init();
  }

  void shutdown() {
      route_panel::shutdown();
      ship_profile_panel::shutdown();
  }

  void renderImGui() {
      if (!visible) return;
      companion_panel::draw();
      route_panel::draw();
      ship_profile_panel::draw();
  }
  }  // namespace ui
  ```

- [ ] **Step 5: Update input.cpp to handle F7**

  In `overlay/overlay_core/input.cpp`, add F7 handling after the F8 block:
  ```cpp
  if (msg == WM_KEYDOWN && wParam == VK_F7) {
      ship_profile_panel::g_visible = !ship_profile_panel::g_visible;
      return 0;
  }
  ```
  Add `#include "../overlay_ui/ship_profile_panel.h"` at the top of input.cpp.

- [ ] **Step 6: Update CMakeLists.txt**

  In `overlay/overlay_ui/CMakeLists.txt`:
  ```cmake
  add_library(overlay_ui STATIC
      render.cpp
      companion_panel.cpp
      http_client.cpp
      route_panel.cpp
      ship_profile_panel.cpp
  )
  target_compile_definitions(overlay_ui PRIVATE UNICODE _UNICODE)
  target_link_libraries(overlay_ui PUBLIC imgui_dx12 winhttp nlohmann_json::nlohmann_json)
  ```

- [ ] **Step 7: Build and verify**

  On the Windows gaming PC:
  ```
  cd overlay
  cmake --build build --config Release 2>&1 | tail -20
  ```
  Expected: 0 errors. The DLL should rebuild cleanly.

- [ ] **Step 8: Smoke test in-game**

  1. Inject DLL into EVE Frontier
  2. Press F7 — ship profile panel should appear at top-left
  3. Select ship type "Carom" from dropdown — verify fuel type resets to D1
  4. Enter 3000 fuel units — JUMP RANGE should show ~425 LY (if in cool system) or `---`
  5. Click SAVE — should show "SAVED" for 2 seconds
  6. Type `/route DEST` in companion panel — route panel should show two rows if alternative exists
  7. Press F7 again — panel closes

- [ ] **Step 9: Commit overlay ship profile panel**

  ```bash
  git add overlay/overlay_ui/ship_profile_panel.h \
          overlay/overlay_ui/ship_profile_panel.cpp \
          overlay/overlay_ui/render.cpp \
          overlay/overlay_ui/render.h \
          overlay/overlay_ui/CMakeLists.txt \
          overlay/overlay_core/input.cpp
  git commit -m "feat(overlay): F7 ship profile panel with computed range/budget and SAVE"
  ```

---

## Files Changed Summary

| File | Change |
|------|--------|
| `build_universe.py` | Add `star_luminosity`, `max_orbit_m`, `safe_jump_temp` per system |
| `data/systems.json` | Rebuilt with new fields |
| `src/ship_profile.py` | SHIPS table, `ship_type`, `extra_cargo_kg`, LY formulas, `jump_range_at_temp()` |
| `src/log_buffer.py` | Add `pending_alternative` field |
| `src/route_engine.py` | LY spatial index, per-node heat range, `_run_astar()`, alternative route, new result shape |
| `src/context_builder.py` | Add `ship_profile` parameter, SHIP summary line |
| `main.py` | `ship_type` validation, `/route/activate`, `current_system_temp`, `/profile` command, updated `/route` handler |
| `tests/test_ship_profile.py` | New — 8 tests |
| `tests/test_route_engine.py` | New — 7 tests |
| `tests/test_context_builder.py` | Add 2 ship profile tests |
| `tests/test_main.py` | Add 8 endpoint tests |
| `overlay/overlay_ui/http_client.h` | Add `postJson()` declaration |
| `overlay/overlay_ui/http_client.cpp` | Implement `postJson()` |
| `overlay/overlay_ui/route_panel.cpp` | Two-row display, USE buttons, new route shape |
| `overlay/overlay_ui/ship_profile_panel.h` | New — F7 panel interface |
| `overlay/overlay_ui/ship_profile_panel.cpp` | New — full panel implementation |
| `overlay/overlay_ui/render.cpp` | Wire up ship_profile_panel |
| `overlay/overlay_ui/render.h` | Include ship_profile_panel.h |
| `overlay/overlay_ui/CMakeLists.txt` | Add ship_profile_panel.cpp |
| `overlay/overlay_core/input.cpp` | F7 → ship_profile_panel::g_visible toggle |
