# src/structure_persistence.py
import json
import os
import re
import logging
import fcntl
from dataclasses import dataclass, field, asdict, fields
from typing import Optional

log = logging.getLogger(__name__)


def _get_default_base_dir() -> str:
    """Get default structures directory (environment-specific)."""
    from src.config import get_data_path
    return get_data_path("structures", env_specific=True)

OWNER_FIELDS = {"shield_pct", "fuel_pct", "services_online", "services_total",
                "tier_registry_object_id", "routine_alerts", "owner_address"}
TRIBE_FIELDS = OWNER_FIELDS  # tribe sees everything owner sees except management
VETTED_HIDDEN = {"shield_pct", "fuel_pct", "services_online", "services_total",
                 "tier_registry_object_id", "routine_alerts", "owner_address"}


@dataclass
class StructureProfile:
    assembly_id:            str
    owner_address:          str
    structure_name:         str             = ""
    structure_type:         str             = "Smart Storage Unit"
    system_name:            str             = ""
    system_id:              int             = 0
    region_name:            str             = ""
    tier_registry_object_id: str            = ""
    created_at:             str             = ""   # ISO8601, set on first save
    item_id:                Optional[str]   = None  # serialized game item ID (e.g. "1000000019552")
    # Location — set manually via /system, or proved via Sui signature
    location:               Optional[dict]  = None  # {"system": "Audn", "proved": false, "set_at": "..."}
    # Live status — set manually or via future polling
    shield_pct:             float           = 100.0
    fuel_pct:               float           = 100.0
    services_online:        int             = 0
    services_total:         int             = 0
    # Routine alerts (queued for browser display)
    routine_alerts:         list            = field(default_factory=list)
    # Cached inventory snapshot (updated on first-message enrichment)
    cached_inventory:       Optional[dict]  = None
    # Connected assembly IDs (polled from on-chain node fields)
    connected_assembly_ids: list            = field(default_factory=list)
    # Resolved connected assembly objects [{object_id, type_name, status}]
    connected_assemblies:   list            = field(default_factory=list)
    # SSU inventory snapshot [{type_name, quantity}]
    ssu_inventory:          list            = field(default_factory=list)

    def __post_init__(self):
        if not self.structure_name:
            self.structure_name = self.assembly_id

    def as_dict_for_tier(self, tier: str) -> dict:
        """Return profile dict with fields filtered by access tier."""
        d = asdict(self)
        if tier in ("OWNER", "TRIBE"):
            return d
        if tier == "VETTED":
            return {k: v for k, v in d.items() if k not in VETTED_HIDDEN}
        # NONE — only bare identity
        return {"assembly_id": d["assembly_id"], "structure_name": d["structure_name"],
                "structure_type": d["structure_type"], "system_name": d["system_name"]}


_SAFE_ID_RE = re.compile(r'^[a-zA-Z0-9_\-]{1,100}$')


def profile_path(assembly_id: str, base_dir: str = None) -> str:
    if not _SAFE_ID_RE.match(assembly_id):
        raise ValueError(f"Invalid assembly_id: {assembly_id!r}")
    if base_dir is None:
        base_dir = _get_default_base_dir()
    return os.path.join(base_dir, f"{assembly_id}.json")


def load_profile(assembly_id: str, base_dir: str = None) -> Optional[StructureProfile]:
    if base_dir is None:
        base_dir = _get_default_base_dir()
    try:
        path = profile_path(assembly_id, base_dir)
    except ValueError as e:
        log.warning("Invalid assembly_id in load_profile: %s", e)
        return None
    if not os.path.exists(path):
        return None
    try:
        data = json.loads(open(path).read())
        known = {f.name for f in fields(StructureProfile)}
        filtered = {k: v for k, v in data.items() if k in known}
        return StructureProfile(**filtered)
    except Exception as e:
        log.warning("Failed to load structure profile %s: %s", assembly_id, e)
        return None


def save_profile(profile: StructureProfile, base_dir: str = None):
    import datetime
    if base_dir is None:
        base_dir = _get_default_base_dir()
    path = profile_path(profile.assembly_id, base_dir)  # raises ValueError for invalid id
    try:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        if not profile.created_at:
            profile.created_at = datetime.datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")
        with open(path, "w") as f:
            fcntl.flock(f.fileno(), fcntl.LOCK_EX)
            try:
                json.dump(asdict(profile), f, indent=2)
            finally:
                fcntl.flock(f.fileno(), fcntl.LOCK_UN)
    except ValueError:
        raise  # re-raise — caller must handle invalid assembly_id
    except Exception as e:
        log.warning("Failed to save structure profile %s: %s", profile.assembly_id, e)
