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


def _store_path(wallet: str, env: str | None = None) -> str:
    from src.config import get_data_path
    return get_data_path(f"log_intel/{wallet.lower()}.json", env_specific=True, env_override=env)


def _known_types_path(env: str | None = None) -> str:
    from src.config import get_data_path
    return get_data_path("log_intel/_known_types.json", env_specific=True, env_override=env)


def load_known_types(env: str | None = None) -> dict:
    """Return global registry of all ore, hostile, and item names seen across the network."""
    path = _known_types_path(env=env)
    if not os.path.exists(path):
        return {"ores": [], "hostiles": [], "items": []}
    try:
        data = json.load(open(path))
        data.setdefault("items", [])
        return data
    except Exception as e:
        log.warning("log_intel_store: load_known_types failed: %s", e)
        return {"ores": [], "hostiles": [], "items": []}


def register_items(names: list) -> int:
    """Add item names seen in any structure's inventory to the global registry. Returns new count."""
    path = _known_types_path()
    registry = load_known_types()
    known: set = set(registry["items"])
    new_count = sum(1 for n in names if n and n not in known)
    for n in names:
        if n:
            known.add(n)
    if new_count == 0:
        return 0
    registry["items"] = sorted(known)
    try:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w") as f:
            json.dump(registry, f, indent=2)
    except Exception as e:
        log.warning("log_intel_store: register_items save failed: %s", e)
    return new_count


def _update_known_types(gamelog_events: list[dict], env: str | None = None) -> None:
    """Add any new ore or hostile names from this upload to the global registry."""
    path = _known_types_path(env=env)
    registry = load_known_types(env=env)
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


def load(wallet: str, env: str | None = None) -> dict:
    """Load intel record for wallet. Returns empty record if not found."""
    if not _wallet_safe(wallet):
        return _empty(wallet)
    path = _store_path(wallet, env=env)
    if not os.path.exists(path):
        return _empty(wallet)
    try:
        with open(path) as f:
            return json.load(f)
    except Exception as e:
        log.warning("log_intel_store: load failed for %s: %s", wallet, e)
        return _empty(wallet)


def save(wallet: str, record: dict, env: str | None = None) -> None:
    if not _wallet_safe(wallet):
        log.warning("log_intel_store: invalid wallet, not saving: %s", wallet)
        return
    path = _store_path(wallet, env=env)
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


def get_last_processed_date(wallet: str, env: str | None = None) -> str | None:
    """Return YYYYMMDD of the most recent file date processed, or None."""
    return load(wallet, env=env).get("last_processed_date")


def merge_upload(
    wallet: str,
    gamelog_events: list[dict],
    ts_list: list[str],
    sys_list: list[str],
    newest_file_date: str | None,
    env: str | None = None,
) -> dict:
    """
    Merge new upload results into the existing intel record and return the updated record.
    - Mining events accumulate ore quantities per system.
    - Combat events accumulate unique hostile names per system.
    - System visit counts are incremented from the timeline.
    - last_processed_date is advanced to newest_file_date if it's later.
    """
    record = load(wallet, env=env)
    record = _migrate(record)
    systems: dict = record.setdefault("systems", {})
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    # System visit counts from timeline
    seen_in_this_upload: set[str] = set()
    for sys_name in sys_list:
        if sys_name not in seen_in_this_upload:
            entry = systems.setdefault(sys_name, _empty_system())
            entry["visit_count"] = entry.get("visit_count", 0) + 1
            entry["last_seen"] = now
            if entry.get("first_seen") is None:
                entry["first_seen"] = now
            seen_in_this_upload.add(sys_name)

    # Mining
    for ev in gamelog_events:
        if ev.get("type") != "mining":
            continue
        sys_name = ev.get("system", "unknown")
        material = ev.get("material", "unknown")
        qty = ev.get("quantity", 0)
        entry = systems.setdefault(sys_name, _empty_system())
        ores: dict = entry.setdefault("ores", {})
        if material not in ores:
            ores[material] = {"qty": qty, "first_seen": now, "last_seen": now}
        else:
            ores[material]["qty"] = ores[material].get("qty", 0) + qty
            ores[material]["last_seen"] = now

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
        hostiles: dict = entry.setdefault("hostiles", {})
        if hostile not in hostiles:
            hostiles[hostile] = {"count": 1, "first_seen": now, "last_seen": now}
        else:
            hostiles[hostile]["count"] = hostiles[hostile].get("count", 0) + 1
            hostiles[hostile]["last_seen"] = now

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

    save(wallet, record, env=env)
    _update_known_types(gamelog_events, env=env)

    from src import system_knowledge
    system_knowledge.record_from_upload(systems, reported_by=wallet, env=env)

    return record


def _empty_system() -> dict:
    return {
        "visit_count": 0,
        "first_seen": None,
        "last_seen": None,
        "ores": {},      # {name: {"qty": int, "first_seen": ts, "last_seen": ts}}
        "hostiles": {},  # {name: {"count": int, "first_seen": ts, "last_seen": ts}}
    }


def _migrate(record: dict) -> dict:
    """Upgrade old schema (int ores, list hostiles, no first_seen) to current format in-place."""
    for entry in record.get("systems", {}).values():
        if "first_seen" not in entry:
            entry["first_seen"] = entry.get("last_seen")

        # ores: {name: int} → {name: {qty, first_seen, last_seen}}
        ores = entry.get("ores", {})
        if ores:
            sample = next(iter(ores.values()))
            if isinstance(sample, (int, float)):
                ts = entry.get("last_seen")
                entry["ores"] = {
                    name: {"qty": int(qty), "first_seen": ts, "last_seen": ts}
                    for name, qty in ores.items()
                }

        # hostiles: [name] → {name: {count, first_seen, last_seen}}
        hostiles = entry.get("hostiles", [])
        if isinstance(hostiles, list):
            ts = entry.get("last_seen")
            entry["hostiles"] = {
                name: {"count": 1, "first_seen": ts, "last_seen": ts}
                for name in hostiles
            }
    return record


def format_for_huginn(wallet: str, env: str | None = None) -> str:
    """
    Return a compact historical context block for HUGINN's prompt.
    Only included if the wallet has prior upload history.
    """
    record = load(wallet, env=env)
    record = _migrate(record)
    systems: dict = record.get("systems", {})
    if not systems:
        return ""

    lines = ["HISTORICAL SYSTEM INTEL (accumulated from prior uploads):"]
    for sys_name, data in sorted(systems.items()):
        ores: dict = data.get("ores", {})
        hostiles: dict = data.get("hostiles", {})
        visits = data.get("visit_count", 0)
        last_seen = (data.get("last_seen") or "")[:10]

        ore_str = ", ".join(
            f"{n} x{v['qty']}" for n, v in sorted(ores.items())
        ) if ores else "none"
        hostile_str = ", ".join(list(hostiles.keys())[:8]) if hostiles else "none"
        lines.append(
            f"  {sys_name} (visits={visits}, last={last_seen}): "
            f"ores=[{ore_str}] hostiles=[{hostile_str}]"
        )

    return "\n".join(lines)
