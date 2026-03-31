# src/ship_profile.py
import json
import os
import logging
from dataclasses import dataclass, asdict, field
from typing import Optional

log = logging.getLogger(__name__)

# Full fuel type data from World API /v2/types (fetched 2026-03-28, utopia tenant).
# mass_kg: cargo mass per unit (tank fuel is massless).
# volume_m3: cargo volume per unit (all identical at 0.28).
# quality: jump efficiency multiplier used in fuel_budget / fuel_for_distance.
# category: ship fuel compatibility group.
FUEL_PROPERTIES: dict[str, dict] = {
    "D1":     {"type_id": 88335, "quality": 0.10, "mass_kg": 20, "volume_m3": 0.28, "category": "basic"},
    "D2":     {"type_id": 88319, "quality": 0.15, "mass_kg": 30, "volume_m3": 0.28, "category": "basic"},
    "SOF-40": {"type_id": 84868, "quality": 0.40, "mass_kg": 25, "volume_m3": 0.28, "category": "advanced"},
    "EU-40":  {"type_id": 78516, "quality": 0.40, "mass_kg": 25, "volume_m3": 0.28, "category": "advanced"},
    "SOF-80": {"type_id": 78515, "quality": 0.80, "mass_kg": 30, "volume_m3": 0.28, "category": "advanced"},
    "EU-90":  {"type_id": 78437, "quality": 0.90, "mass_kg": 30, "volume_m3": 0.28, "category": "advanced"},
}

# Derived lookups kept for backward compatibility
FUEL_QUALITY:   dict[str, float] = {k: v["quality"]  for k, v in FUEL_PROPERTIES.items()}
FUEL_CATEGORY:  dict[str, str]   = {k: v["category"] for k, v in FUEL_PROPERTIES.items()}

# Minimum fuel quality per category — the baseline each ship's specific_heat is calibrated against.
# D1 (0.10) = weakest basic fuel. SOF-40 (0.40) = weakest advanced fuel.
# quality_factor = current_quality / base_quality
# D1 Reflex = 1.0x, D2 Reflex = 1.5x, SOF-40 Lai = 1.0x, EU-90 Lai = 2.25x
BASE_FUEL_QUALITY: dict[str, float] = {
    "basic":    0.10,  # D1
    "advanced": 0.40,  # SOF-40
}

# Ship catalog. Fields sourced from World API /v2/ships/{type_id} unless noted.
# specific_heat   = physics.heat.heatCapacity (game-canonical name used in formulas)
# conductance     = physics.heat.conductance  (heat dissipation rate; higher = cools faster)
# max_velocity    = physics.maximumVelocity   (subwarp speed, m/s)
# inertia_modifier= physics.inertiaModifier   (agility; lower = snappier)
# structure_hp    = health.structure          (shield and armor are 0 on all ships)
# fuel_capacity   = fuelCapacity              (tank size in fuel units)
# cpu_output      = cpuOutput                 (fitting budget, CPU tf)
# powergrid_output= powergridOutput           (fitting budget, PG MW)
# capacitor_capacity = capacitor.capacity     (cap energy)
# slots           = {high, medium, low}       (module fitting slots)
#
# Carom, Stride, Lai — not found in World API on either Utopia or Stillness.
# Their physics data (mass, specific_heat, fuel_capacity) is from game client probes.
SHIPS: dict[str, dict] = {
    # ── In /v2/types but not /v2/ships — ship stats not yet in API ───────────
    "Carom": {
        "type_id":       91107,
        "class_name":    "Corvette",
        "fuel_category": "basic",
        "mass":          7_200_000,
        "specific_heat": 8.5,
        "fuel_capacity": 3000,
    },
    "Stride": {
        "type_id":       91106,
        "class_name":    "Corvette",
        "fuel_category": "basic",
        "mass":          7_900_000,
        "specific_heat": 8.0,
        "fuel_capacity": 3200,
    },
    "Lai": {
        "type_id":       82425,
        "class_name":    "Frigate",
        "fuel_category": "advanced",
        "mass":          18_929_160,
        "specific_heat": 2.5,
        "fuel_capacity": 2400,
    },

    # ── Corvettes (basic fuel) ────────────────────────────────────────────────
    "Wend": {
        "type_id":            87698,
        "class_name":         "Shuttle",
        "fuel_category":      "basic",
        "mass":               6_800_000,
        "specific_heat":      2.0,
        "conductance":        1.5,
        "fuel_capacity":      200,
        "structure_hp":       750,
        "max_velocity":       260,
        "inertia_modifier":   0.46,
        "cpu_output":         30,
        "powergrid_output":   30,
        "capacitor_capacity": 32,
        "slots":              {"high": 1, "medium": 3, "low": 0},
    },
    "Reflex": {
        "type_id":            87847,
        "class_name":         "Corvette",
        "fuel_category":      "basic",
        "mass":               9_750_000,
        "specific_heat":      3.0,
        "conductance":        0.875,
        "fuel_capacity":      1750,
        "structure_hp":       1250,
        "max_velocity":       260,
        "inertia_modifier":   0.34,
        "cpu_output":         32,
        "powergrid_output":   35,
        "capacitor_capacity": 50,
        "slots":              {"high": 2, "medium": 4, "low": 1},
    },
    "Recurve": {
        "type_id":            87846,
        "class_name":         "Corvette",
        "fuel_category":      "basic",
        "mass":               10_400_000,
        "specific_heat":      1.0,
        "conductance":        0.875,
        "fuel_capacity":      970,
        "structure_hp":       1650,
        "max_velocity":       405,
        "inertia_modifier":   0.20,
        "cpu_output":         35,
        "powergrid_output":   50,
        "capacitor_capacity": 50,
        "slots":              {"high": 2, "medium": 3, "low": 1},
    },
    "Reiver": {
        "type_id":            87848,
        "class_name":         "Corvette",
        "fuel_category":      "basic",
        "mass":               10_200_000,
        "specific_heat":      1.0,
        "conductance":        0.875,
        "fuel_capacity":      1416,
        "structure_hp":       1900,
        "max_velocity":       435,
        "inertia_modifier":   0.40,
        "cpu_output":         35,
        "powergrid_output":   50,
        "capacitor_capacity": 50,
        "slots":              {"high": 2, "medium": 2, "low": 2},
    },

    # ── Frigates (advanced fuel) ──────────────────────────────────────────────
    "USV": {
        "type_id":            81609,
        "class_name":         "Frigate",
        "fuel_category":      "advanced",
        "mass":               30_266_600,
        "specific_heat":      1.8,
        "conductance":        0.55,
        "fuel_capacity":      2420,
        "structure_hp":       2160,
        "max_velocity":       280,
        "inertia_modifier":   0.20,
        "cpu_output":         30,
        "powergrid_output":   110,
        "capacitor_capacity": 45,
        "slots":              {"high": 2, "medium": 3, "low": 4},
    },
    "Lorha": {
        "type_id":            82426,
        "class_name":         "Frigate",
        "fuel_category":      "advanced",
        "mass":               31_369_320,
        "specific_heat":      2.5,
        "conductance":        0.625,
        "fuel_capacity":      2508,
        "structure_hp":       2155,
        "max_velocity":       450,
        "inertia_modifier":   0.30,
        "cpu_output":         32,
        "powergrid_output":   110,
        "capacitor_capacity": 30,
        "slots":              {"high": 0, "medium": 2, "low": 4},
    },
    "MCF": {
        "type_id":            81904,
        "class_name":         "Frigate",
        "fuel_category":      "advanced",
        "mass":               52_313_800,
        "specific_heat":      2.5,
        "conductance":        0.625,
        "fuel_capacity":      6548,
        "structure_hp":       2400,
        "max_velocity":       410,
        "inertia_modifier":   0.20,
        "cpu_output":         60,
        "powergrid_output":   100,
        "capacitor_capacity": 40,
        "slots":              {"high": 2, "medium": 3, "low": 2},
    },
    "HAF": {
        "type_id":            82424,
        "class_name":         "Frigate",
        "fuel_category":      "advanced",
        "mass":               81_883_000,
        "specific_heat":      2.5,
        "conductance":        0.625,
        "fuel_capacity":      4184,
        "structure_hp":       2650,
        "max_velocity":       440,
        "inertia_modifier":   0.25,
        "cpu_output":         45,
        "powergrid_output":   140,
        "capacitor_capacity": 50,
        "slots":              {"high": 2, "medium": 3, "low": 3},
    },

    # ── Destroyer (advanced fuel) ─────────────────────────────────────────────
    "Tades": {
        "type_id":            81808,
        "class_name":         "Destroyer",
        "fuel_category":      "advanced",
        "mass":               74_655_504,
        "specific_heat":      2.5,
        "conductance":        0.625,
        "fuel_capacity":      5972,
        "structure_hp":       2600,
        "max_velocity":       420,
        "inertia_modifier":   0.15,
        "cpu_output":         125,
        "powergrid_output":   280,
        "capacitor_capacity": 65,
        "slots":              {"high": 3, "medium": 4, "low": 2},
    },

    # ── Cruiser (advanced fuel) ───────────────────────────────────────────────
    "Maul": {
        "type_id":            82430,
        "class_name":         "Cruiser",
        "fuel_category":      "advanced",
        "mass":               548_435_968,
        "specific_heat":      2.5,
        "conductance":        1.25,
        "fuel_capacity":      24160,
        "structure_hp":       4400,
        "max_velocity":       400,
        "inertia_modifier":   0.04,
        "cpu_output":         150,
        "powergrid_output":   2450,
        "capacitor_capacity": 80,
        "slots":              {"high": 4, "medium": 3, "low": 3},
    },

    # ── Combat Battlecruiser (advanced fuel) ──────────────────────────────────
    "Chumaq": {
        "type_id":            81611,
        "class_name":         "Combat Battlecruiser",
        "fuel_category":      "advanced",
        "mass":               1_739_489_520,
        "specific_heat":      3.0,
        "conductance":        0.35,
        "fuel_capacity":      270585,
        "structure_hp":       6250,
        "max_velocity":       170,
        "inertia_modifier":   0.02,
        "cpu_output":         145,
        "powergrid_output":   2520,
        "capacitor_capacity": 80,
        "slots":              {"high": 0, "medium": 5, "low": 7},
    },
}

# Derived for convenience — fuel tank size per ship.
SHIP_MAX_FUEL: dict[str, int] = {k: v["fuel_capacity"] for k, v in SHIPS.items() if "fuel_capacity" in v}

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

    def quality_factor(self) -> float:
        """Fuel quality multiplier relative to the ship's minimum fuel type.
        D1 Reflex = 1.0x baseline. D2 Reflex = 1.5x. SOF-40 Lai = 1.0x. EU-90 Lai = 2.25x."""
        quality  = FUEL_QUALITY.get(self.fuel_type, 0.0)
        cat      = FUEL_CATEGORY.get(self.fuel_type, "basic")
        base     = BASE_FUEL_QUALITY.get(cat, quality)
        return quality / base if base > 0 else 1.0

    def jump_range(self) -> float:
        """Max single-jump distance in light-years."""
        if not self.can_jump():
            return 0.0
        c_eff   = self.specific_heat * (1.0 + self.adaptive_level * 0.02)
        delta_t = T_MAX - self.external_temp
        return (delta_t * c_eff * self.hull_mass) / (HEAT_CONSTANT * self._current_mass)

    def jump_range_at_temp(self, safe_jump_temp: float) -> float:
        """Jump range in LY at a given external temperature (used by route engine)."""
        if safe_jump_temp >= NO_JUMP_TEMP:
            return 0.0
        c_eff = self.specific_heat * (1.0 + self.adaptive_level * 0.02)
        return ((T_MAX - safe_jump_temp) * c_eff * self.hull_mass) / (HEAT_CONSTANT * self._current_mass)

    def fuel_budget(self) -> float:
        """Total jump distance available in light-years given current fuel."""
        quality = FUEL_QUALITY.get(self.fuel_type, 0.0)
        if quality == 0.0:
            return 0.0
        return (self.fuel_quantity * quality) / (FUEL_CONSTANT * self._current_mass)

    def fuel_for_distance(self, ly: float) -> float:
        """Fuel units consumed for a given direct-jump distance in light-years."""
        quality = FUEL_QUALITY.get(self.fuel_type, 0.0)
        if quality == 0.0:
            return 0.0
        return ly * FUEL_CONSTANT * self._current_mass / quality

    def with_overrides(self, **kwargs) -> "ShipProfile":
        """Return a copy with selected fields overridden."""
        d = asdict(self)
        d.update({k: v for k, v in kwargs.items() if v is not None})
        return ShipProfile(**d)


_stored: Optional[ShipProfile] = None


def _profile_path() -> str:
    """Get path to ship profile (shared across environments)."""
    from src.config import get_data_path
    return get_data_path("ship_profile.json", env_specific=False)


def load_profile() -> ShipProfile:
    global _stored
    if _stored is not None:
        return _stored
    path = _profile_path()
    if os.path.exists(path):
        try:
            data = json.loads(open(path).read())
            # Filter out keys not in ShipProfile to handle legacy JSON
            valid_keys = {f for f in ShipProfile.__dataclass_fields__}
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
    path = _profile_path()
    try:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w") as f:
            json.dump(asdict(profile), f, indent=2)
        log.info("Ship profile saved")
    except Exception as e:
        log.warning("Failed to save ship profile: %s", e)
