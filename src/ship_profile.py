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

FUEL_CONSTANT = 1e-7          # per kg
MAX_TEMP      = 150.0         # game units
HEAT_CONSTANT = 3.0           # denominator in jump formula
NO_JUMP_TEMP  = 90.0          # external temp threshold


@dataclass
class ShipProfile:
    hull_mass:      float = 10_000_000.0   # kg — base hull
    current_mass:   float = 11_000_000.0   # kg — hull + fuel + cargo
    specific_heat:  float = 1_000_000.0    # thermal capacity stat
    adaptive_level: int   = 0              # adaptive upgrade level (0 = none)
    fuel_type:      str   = "SOF-80"       # fuel type key
    fuel_quantity:  float = 500.0          # units of fuel
    external_temp:  float = 0.0            # current external temperature

    def can_jump(self) -> bool:
        return self.external_temp < NO_JUMP_TEMP

    def jump_range(self) -> float:
        """Max single-jump distance in meters."""
        if not self.can_jump():
            return 0.0
        c_eff   = self.specific_heat * (1.0 + self.adaptive_level * 0.02)
        delta_t = MAX_TEMP - self.external_temp
        return (delta_t * c_eff * self.hull_mass) / (HEAT_CONSTANT * self.current_mass)

    def fuel_budget(self) -> float:
        """Total jump distance available in meters given current fuel."""
        quality = FUEL_QUALITY.get(self.fuel_type, 0.0)
        if quality == 0.0:
            return 0.0
        return (self.fuel_quantity * quality) / (FUEL_CONSTANT * self.current_mass)

    def fuel_for_distance(self, meters: float) -> float:
        """Fuel units consumed for a given jump distance."""
        quality = FUEL_QUALITY.get(self.fuel_type, 1.0)
        return meters * FUEL_CONSTANT * self.current_mass / quality

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
