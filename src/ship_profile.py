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
    try:
        os.makedirs(os.path.dirname(_PROFILE_PATH), exist_ok=True)
        with open(_PROFILE_PATH, "w") as f:
            json.dump(asdict(profile), f, indent=2)
        log.info("Ship profile saved")
    except Exception as e:
        log.warning("Failed to save ship profile: %s", e)
