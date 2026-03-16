"""
Resolves EVE Frontier type IDs to human-readable names.
Loaded once from data/type_names_all.json at import time.
"""
import json
import os
import logging

log = logging.getLogger(__name__)

_DATA_PATH = os.path.join(os.path.dirname(__file__), "..", "data", "type_names_all.json")

def _load() -> dict:
    try:
        with open(_DATA_PATH, encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        log.warning("type_names: could not load %s: %s", _DATA_PATH, e)
        return {}

_TYPE_NAMES: dict = _load()


def get_type_name(type_id) -> str:
    """Return human-readable name for a type_id (int or str). Returns 'Unknown' if not found."""
    if type_id is None:
        return "Unknown"
    return _TYPE_NAMES.get(str(type_id)) or "Unknown"
