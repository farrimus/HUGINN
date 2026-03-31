# src/log_intel_store.py
"""
Per-pilot log intelligence store — accumulated from player-uploaded flight recorder data.

Tracks what each pilot has encountered across systems: ores mined, hostiles engaged,
systems visited. Keyed by wallet address. Used to enrich future log uploads with
historical context and to filter out already-processed files by date.

Storage:
  data/{env}/log_intel/{wallet}.json   — per-pilot record
  data/{env}/log_intel/_known_types.json — global registry of all ore and hostile names
"""

import os
import re
import json
import logging
from datetime import datetime, timezone

log = logging.getLogger(__name__)

_WALLET_RE = re.compile(r'^0x[0-9a-fA-F]{10,64}$')


def _wallet_safe(wallet: str) -> bool:
    return bool(_WALLET_RE.match(wallet))


def _store_path(wallet: str) -> str:
    from src.config import get_data_path
    return get_data_path(f"log_intel/{wallet.lower()}.json", env_specific=True)


def _known_types_path() -> str:
    from src.config import get_data_path
    return get_data_path("log_intel/_known_types.json", env_specific=True)


def load_known_types() -> dict:
    """Return global registry of all ore and hostile names seen across all uploads."""
    path = _known_types_path()
    if not os.path.exists(path):
        return {"ores": [], "hostiles": []}
    try:
        with open(path) as f:
            return json.load(f)
    except Exception as e:
        log.warning("log_intel_store: load_known_types failed: %s", e)
        return {"ores": [], "hostiles": []}


def _update_known_types(gamelog_events: list[dict]) -> None:
    """Add any new ore or hostile names from this upload to the global registry."""
    path = _known_types_path()
    registry = load_known_types()
    known_ores: set[str] = set(registry["ores"])
    known_hostiles: set[str] = set(registry["hostiles"])

    for ev in gamelog_events:
        ev_type = ev.get("type")
        if ev_type == "mining":
            mat = ev.get("material")
            if mat:
                known_ores.add(mat)
        elif ev_type == "combat_out":
            h = ev.get("target")
            if h:
                known_hostiles.add(h)
        elif ev_type in ("combat_in", "sightline_blocked"):
            h = ev.get("source")
            if h:
                known_hostiles.add(h)

    registry["ores"] = sorted(known_ores)
    registry["hostiles"] = sorted(known_hostiles)
    try:
        with open(path, "w") as f:
            json.dump(registry, f, indent=2)
    except Exception as e:
        log.warning("log_intel_store: _update_known_types save failed: %s", e)


def load(wallet: str) -> dict:
    """Load intel record for wallet. Returns empty record if not found."""
    if not _wallet_safe(wallet):
        return _empty(wallet)
    path = _store_path(wallet)
    if not os.path.exists(path):
        return _empty(wallet)
    try:
        with open(path) as f:
            return json.load(f)
    except Exception as e:
        log.warning("log_intel_store: load failed for %s: %s", wallet, e)
        return _empty(wallet)


def save(wallet: str, record: dict) -> None:
    if not _wallet_safe(wallet):
        log.warning("log_intel_store: invalid wallet, not saving: %s", wallet)
        return
    path = _store_path(wallet)
    try:
        with open(path, "w") as f:
            json.dump(record, f, indent=2)
    except Exception as e:
        log.warning("log_intel_store: save failed for %s: %s", wallet, e)


def _empty(wallet: str) -> dict:
    return {
        "wallet": wallet,
        "last_processed_date": None,
        "systems": {},
        "upload_count": 0,
        "first_upload_at": None,
        "last_upload_at": None,
    }


def get_last_processed_date(wallet: str) -> str | None:
    """Return YYYYMMDD of the most recent file date processed, or None."""
    return load(wallet).get("last_processed_date")


def merge_upload(
    wallet: str,
    gamelog_events: list[dict],
    ts_list: list[str],
    sys_list: list[str],
    newest_file_date: str | None,
) -> dict:
    """
    Merge new upload results into the existing intel record and return the updated record.
    - Mining events accumulate ore quantities per system.
    - Combat events accumulate unique hostile names per system.
    - System visit counts are incremented from the timeline.
    - last_processed_date is advanced to newest_file_date if it's later.
    """
    record = load(wallet)
    systems: dict = record.setdefault("systems", {})
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    # System visit counts from timeline
    seen_in_this_upload: set[str] = set()
    for sys_name in sys_list:
        if sys_name not in seen_in_this_upload:
            entry = systems.setdefault(sys_name, _empty_system())
            entry["visit_count"] = entry.get("visit_count", 0) + 1
            entry["last_seen"] = now
            seen_in_this_upload.add(sys_name)

    # Mining
    for ev in gamelog_events:
        if ev.get("type") != "mining":
            continue
        sys_name = ev.get("system", "unknown")
        material = ev.get("material", "unknown")
        qty = ev.get("quantity", 0)
        entry = systems.setdefault(sys_name, _empty_system())
        ores = entry.setdefault("ores", {})
        ores[material] = ores.get(material, 0) + qty

    # Hostiles from combat (targets of outgoing hits + sources of incoming hits)
    for ev in gamelog_events:
        ev_type = ev.get("type")
        hostile = None
        if ev_type == "combat_out":
            hostile = ev.get("target")
        elif ev_type == "combat_in":
            hostile = ev.get("source")
        elif ev_type == "sightline_blocked":
            hostile = ev.get("source")
        if not hostile:
            continue
        sys_name = ev.get("system", "unknown")
        entry = systems.setdefault(sys_name, _empty_system())
        hostiles: list = entry.setdefault("hostiles", [])
        if hostile not in hostiles:
            hostiles.append(hostile)

    # Advance last_processed_date
    if newest_file_date:
        current = record.get("last_processed_date")
        if current is None or newest_file_date > current:
            record["last_processed_date"] = newest_file_date

    # Upload metadata
    record["upload_count"] = record.get("upload_count", 0) + 1
    record["last_upload_at"] = now
    if not record.get("first_upload_at"):
        record["first_upload_at"] = now

    save(wallet, record)
    _update_known_types(gamelog_events)
    return record


def _empty_system() -> dict:
    return {"visit_count": 0, "last_seen": None, "ores": {}, "hostiles": []}


def format_for_huginn(wallet: str) -> str:
    """
    Return a compact historical context block for HUGINN's prompt.
    Only included if the wallet has prior upload history.
    """
    record = load(wallet)
    systems: dict = record.get("systems", {})
    if not systems:
        return ""

    lines = ["HISTORICAL SYSTEM INTEL (accumulated from prior uploads):"]
    for sys_name, data in sorted(systems.items()):
        ores = data.get("ores", {})
        hostiles = data.get("hostiles", [])
        visits = data.get("visit_count", 0)

        ore_str = ", ".join(f"{m} x{q}" for m, q in sorted(ores.items())) if ores else "none"
        hostile_str = ", ".join(hostiles[:8]) if hostiles else "none"
        lines.append(f"  {sys_name} (visits={visits}): ores=[{ore_str}] hostiles=[{hostile_str}]")

    return "\n".join(lines)
