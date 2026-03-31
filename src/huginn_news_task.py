"""
src/huginn_news_task.py

Background task: generate Huginn's Signal article once per day.
Started from main.py lifespan via asyncio.create_task(run_forever()).
Runs immediately on startup so there is always an article on file.
"""
import asyncio
import json
import logging
import os
from datetime import datetime, timezone
from pathlib import Path

log = logging.getLogger(__name__)

_INTERVAL_SECONDS = 24 * 60 * 60  # 24 hours


async def run_forever() -> None:
    """Generate article on startup, then every 24 hours."""
    log.info("huginn_news_task: started (interval 24h)")
    await asyncio.sleep(30)  # let other startup tasks settle
    while True:
        try:
            await _generate_once()
        except Exception as e:
            log.error("huginn_news_task: generation error: %s", e, exc_info=True)
        await asyncio.sleep(_INTERVAL_SECONDS)


def _build_log_data_block(cutoff_iso: str | None) -> str:
    """
    Aggregate pilot log intel uploaded since last broadcast.

    Iterates all per-wallet log_intel files. For each wallet, includes only
    systems where last_seen > cutoff_iso. Anonymised: no wallet addresses.
    Returns empty string if no new data.
    """
    from src.config import get_data_path

    log_intel_dir = os.path.dirname(get_data_path("log_intel/_known_types.json", env_specific=True))
    if not os.path.isdir(log_intel_dir):
        return ""

    # Aggregate ores and hostiles per system across all new uploads
    systems: dict[str, dict] = {}

    for fname in os.listdir(log_intel_dir):
        if not fname.endswith(".json") or fname.startswith("_"):
            continue
        fpath = os.path.join(log_intel_dir, fname)
        try:
            with open(fpath) as f:
                record = json.load(f)
        except Exception:
            continue

        # Skip wallets with no uploads since last broadcast
        last_upload = record.get("last_upload_at") or ""
        if cutoff_iso and last_upload <= cutoff_iso:
            continue

        for sys_name, data in (record.get("systems") or {}).items():
            # Only include systems touched in new uploads
            last_seen = data.get("last_seen") or ""
            if cutoff_iso and last_seen <= cutoff_iso:
                continue

            entry = systems.setdefault(sys_name, {"ores": {}, "hostiles": set()})
            for mat, qty in (data.get("ores") or {}).items():
                entry["ores"][mat] = entry["ores"].get(mat, 0) + qty
            for h in (data.get("hostiles") or []):
                entry["hostiles"].add(h)

    if not systems:
        return ""

    lines = []
    for sys_name in sorted(systems):
        d = systems[sys_name]
        ore_str = ", ".join(f"{m} x{q}" for m, q in sorted(d["ores"].items())) if d["ores"] else "none"
        hostile_str = ", ".join(sorted(d["hostiles"])) if d["hostiles"] else "none"
        lines.append(f"  {sys_name}: ores=[{ore_str}]  hostiles=[{hostile_str}]")

    return "Shells reported this cycle (anonymised):\n" + "\n".join(lines)


def _build_network_delta_block(cutoff_iso: str | None) -> str:
    """
    List assemblies registered to the network since last broadcast.

    Iterates all structure profile JSON files, includes any where
    created_at > cutoff_iso. Returns empty string if none.
    """
    from src.config import get_data_path

    structures_dir = get_data_path("structures", env_specific=True)
    if not os.path.isdir(structures_dir):
        return ""

    new_structures = []
    for fname in os.listdir(structures_dir):
        if not fname.endswith(".json"):
            continue
        fpath = os.path.join(structures_dir, fname)
        try:
            with open(fpath) as f:
                data = json.load(f)
        except Exception:
            continue

        created_at = data.get("created_at") or ""
        if cutoff_iso and created_at <= cutoff_iso:
            continue

        name = data.get("structure_name") or data.get("assembly_id") or fname
        system = data.get("system_name") or "unknown system"
        new_structures.append((name, system))

    if not new_structures:
        return ""

    new_structures.sort(key=lambda x: x[0])
    lines = [f"  {name} — {system}" for name, system in new_structures]
    header = f"New installations registered this cycle: {len(new_structures)}"
    return header + "\n" + "\n".join(lines)


def _build_kill_feed_block(cutoff_iso: str | None) -> str:
    """
    Summarise killmails recorded since last broadcast.

    Reads data/{env}/killmails.jsonl, filters by kill timestamp > cutoff_iso,
    groups by solar system. Resolves system names via galaxy DB where possible.
    Returns empty string if no kills in this cycle.
    """
    from src.config import get_data_path

    env = os.getenv("DEPLOYMENT_ENV", "stillness")
    jsonl_path = Path(os.path.dirname(os.path.dirname(__file__))) / "data" / env / "killmails.jsonl"
    if not jsonl_path.exists():
        return ""

    # Try to load galaxy DB for system name resolution
    galaxy = None
    try:
        from src.galaxy_db import GalaxyDB
        galaxy = GalaxyDB()
    except Exception:
        pass

    # Convert cutoff ISO to unix seconds for comparison against kill_timestamp
    cutoff_ts: int | None = None
    if cutoff_iso:
        try:
            from datetime import datetime, timezone
            dt = datetime.fromisoformat(cutoff_iso.replace("Z", "+00:00"))
            cutoff_ts = int(dt.timestamp())
        except Exception:
            pass

    kills_by_system: dict[str, list[dict]] = {}

    with open(jsonl_path) as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                event = json.loads(line)
            except Exception:
                continue

            # Raw JSONL format: kill_timestamp is unix seconds as string
            try:
                kill_ts = int(event.get("kill_timestamp") or 0)
            except (ValueError, TypeError):
                kill_ts = 0
            if cutoff_ts and kill_ts <= cutoff_ts:
                continue

            # solar_system_id is a TenantItemId struct {item_id, tenant}
            raw_sys = event.get("solar_system_id") or {}
            sys_id = str(raw_sys.get("item_id") or "") if isinstance(raw_sys, dict) else str(raw_sys)
            if not sys_id:
                continue

            # Resolve system name
            sys_label = sys_id
            if galaxy:
                try:
                    row = galaxy.get_system(int(sys_id))
                    if row:
                        sys_label = row.get("name") or sys_id
                except Exception:
                    pass

            # loss_type is {variant: "SHIP"|"STRUCTURE", fields: {}}
            loss_raw = event.get("loss_type") or {}
            loss_type = loss_raw.get("variant", "") if isinstance(loss_raw, dict) else str(loss_raw)
            kills_by_system.setdefault(sys_label, []).append({"loss_type": loss_type})

    if not kills_by_system:
        return ""

    lines = []
    total = 0
    for sys_label in sorted(kills_by_system):
        events = kills_by_system[sys_label]
        total += len(events)
        ship_kills = sum(1 for e in events if e.get("loss_type") == "SHIP")
        struct_kills = sum(1 for e in events if e.get("loss_type") == "STRUCTURE")
        parts = []
        if ship_kills:
            parts.append(f"{ship_kills} ship{'s' if ship_kills != 1 else ''}")
        if struct_kills:
            parts.append(f"{struct_kills} structure{'s' if struct_kills != 1 else ''}")
        lines.append(f"  {sys_label}: {', '.join(parts)} destroyed")

    header = f"Kill activity this cycle ({total} total):"
    return header + "\n" + "\n".join(lines)


async def _generate_once() -> None:
    from src.structure_persistence import load_profile
    from src.structure_loader import load_structures_from_directory
    from src.intel_store import IntelStore
    from src.huginn_news import generate_article, save_article, load_article

    # Use last broadcast time as cutoff so only new data is included
    existing = load_article()
    cutoff_iso: str | None = existing.get("generated_at") if existing else None
    log.info("huginn_news_task: cutoff=%s", cutoff_iso or "none (first run)")

    structures_data = load_structures_from_directory("data/structures")
    contexts = []
    for s in structures_data:
        assembly_id = s["id"]
        profile = load_profile(assembly_id)
        if not profile:
            continue
        try:
            store = IntelStore(assembly_id)
            intel = store._entries
        except Exception:
            intel = []
        contexts.append({"profile": profile, "intel": intel})

    log_block = _build_log_data_block(cutoff_iso)
    kill_feed_block = _build_kill_feed_block(cutoff_iso)
    network_delta_block = _build_network_delta_block(cutoff_iso)

    log.info(
        "huginn_news_task: generating from %d structures | log_data=%s | kills=%s | network_delta=%s",
        len(contexts),
        "yes" if log_block else "none",
        "yes" if kill_feed_block else "none",
        "yes" if network_delta_block else "none",
    )
    text = await generate_article(
        contexts,
        log_block=log_block,
        kill_feed_block=kill_feed_block,
        network_delta_block=network_delta_block,
    )
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    save_article(text, now)
    log.info("huginn_news_task: article saved (%d chars)", len(text))
