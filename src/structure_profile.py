# src/structure_profile.py
import json
import os
import re
import logging
from dataclasses import dataclass, field, asdict, fields
from typing import Optional

log = logging.getLogger(__name__)

_DEFAULT_BASE_DIR = os.path.normpath(os.path.join(os.path.dirname(__file__), "..", "data", "structures"))

OWNER_FIELDS = {"shield_pct", "fuel_pct", "services_online", "services_total", "docked_count",
                "nova_registry_object_id", "routine_alerts", "owner_character_id", "owner_address"}
TRIBE_FIELDS = OWNER_FIELDS  # tribe sees everything owner sees except management
VETTED_HIDDEN = {"shield_pct", "fuel_pct", "services_online", "services_total",
                 "docked_count", "nova_registry_object_id", "routine_alerts",
                 "owner_character_id", "owner_address"}


@dataclass
class StructureProfile:
    structure_id:           str
    owner_address:          str
    structure_name:         str             = ""
    structure_type:         str             = "Smart Storage Unit"
    system_name:            str             = ""
    owner_character_id:     int             = 0
    nova_registry_object_id: str            = ""
    created_at:             str             = ""   # ISO8601, set on first save
    # Live status (updated by structure-chat context evaluation)
    shield_pct:             float           = 100.0
    fuel_pct:               float           = 100.0
    services_online:        int             = 0
    services_total:         int             = 0
    docked_count:           int             = 0
    # Routine alerts (queued for browser display)
    routine_alerts:         list            = field(default_factory=list)
    # Universe data (set at profile creation from STRUCTURE_SYSTEM_NAME + galaxy_db)
    region_name:            str             = ""
    system_id:              int             = 0

    def __post_init__(self):
        if not self.structure_name:
            self.structure_name = self.structure_id

    def as_dict_for_tier(self, tier: str) -> dict:
        """Return profile dict with fields filtered by access tier."""
        d = asdict(self)
        if tier in ("OWNER", "TRIBE"):
            return d
        if tier == "VETTED":
            return {k: v for k, v in d.items() if k not in VETTED_HIDDEN}
        # NONE — only bare identity
        return {"structure_id": d["structure_id"], "structure_name": d["structure_name"],
                "structure_type": d["structure_type"], "system_name": d["system_name"]}


_SAFE_ID_RE = re.compile(r'^[a-zA-Z0-9_\-]{1,64}$')


def profile_path(structure_id: str, base_dir: str = _DEFAULT_BASE_DIR) -> str:
    if not _SAFE_ID_RE.match(structure_id):
        raise ValueError(f"Invalid structure_id: {structure_id!r}")
    return os.path.join(base_dir, f"{structure_id}.json")


def load_profile(structure_id: str, base_dir: str = _DEFAULT_BASE_DIR) -> Optional[StructureProfile]:
    try:
        path = profile_path(structure_id, base_dir)
    except ValueError as e:
        log.warning("Invalid structure_id in load_profile: %s", e)
        return None
    if not os.path.exists(path):
        return None
    try:
        data = json.loads(open(path).read())
        known = {f.name for f in fields(StructureProfile)}
        filtered = {k: v for k, v in data.items() if k in known}
        return StructureProfile(**filtered)
    except Exception as e:
        log.warning("Failed to load structure profile %s: %s", structure_id, e)
        return None


def save_profile(profile: StructureProfile, base_dir: str = _DEFAULT_BASE_DIR):
    import datetime
    path = profile_path(profile.structure_id, base_dir)  # raises ValueError for invalid id
    try:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        if not profile.created_at:
            profile.created_at = datetime.datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")
        with open(path, "w") as f:
            json.dump(asdict(profile), f, indent=2)
    except ValueError:
        raise  # re-raise — caller must handle invalid structure_id
    except Exception as e:
        log.warning("Failed to save structure profile %s: %s", profile.structure_id, e)
