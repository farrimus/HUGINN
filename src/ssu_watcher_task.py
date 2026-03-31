"""
src/ssu_watcher_task.py

Background task: poll SSU inventories every 60s, push SSE alerts to connected clients.

Started from main.py lifespan via asyncio.create_task(run_forever()).
"""

import asyncio
import datetime
import logging
import os

log = logging.getLogger(__name__)

_POLL_INTERVAL = 60  # seconds


async def run_forever() -> None:
    """Background loop. Started from main.py lifespan after EntityResolver is ready."""
    log.info("watcher_task: started (poll interval %ds)", _POLL_INTERVAL)
    # Brief delay so the resolver finishes pre-warming before first poll
    await asyncio.sleep(10)
    while True:
        try:
            await _poll_once()
        except Exception as e:
            log.error("watcher_task: poll error: %s", e, exc_info=True)
        await asyncio.sleep(_POLL_INTERVAL)


async def _poll_once() -> None:
    from src.config import get_data_path
    from src.session_store import load_session, save_session
    from src.entity_resolver import get_entity_resolver
    from src.endpoints.watcher import push_alert

    resolver = get_entity_resolver()

    # Scan data/{tenant}/sessions/ for all tenants
    data_base = os.path.dirname(get_data_path("_", env_specific=False))
    session_files: list[tuple[str, str]] = []  # (wallet_address, sessions_dir)
    try:
        for tenant_entry in os.scandir(data_base):
            if not tenant_entry.is_dir():
                continue
            sessions_dir = os.path.join(tenant_entry.path, "sessions")
            if not os.path.isdir(sessions_dir):
                continue
            for f in os.scandir(sessions_dir):
                if f.name.endswith(".json"):
                    wallet = "0x" + f.name[:-5]
                    session_files.append((wallet, sessions_dir))
    except Exception as e:
        log.warning("watcher_task: session scan failed: %s", e)
        return

    if not session_files:
        return

    now = datetime.datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")

    for wallet, base_dir in session_files:
        session = load_session(wallet, base_dir=base_dir)
        if not session or not session.watch_list:
            continue

        changed = False
        for rule in session.watch_list:
            if not rule.get("active"):
                continue

            ssu_id = rule.get("ssu_id", "")
            if not ssu_id:
                continue

            try:
                inv = await asyncio.wait_for(resolver.get_inventory(ssu_id), timeout=10.0)
            except asyncio.TimeoutError:
                log.warning("watcher_task: timeout fetching inventory %s", ssu_id[:12])
                continue
            except Exception as e:
                log.warning("watcher_task: error fetching inventory %s: %s", ssu_id[:12], e)
                continue

            if inv is None:
                # SSU not found or not a SSU — deactivate to stop polling
                log.info("watcher_task: deactivating rule %s — SSU %s not found",
                         rule["id"][:8], ssu_id[:12])
                rule["active"] = False
                changed = True
                continue

            rule["last_checked"] = now
            changed = True

            items = inv.get("items", [])
            item_filter = rule.get("item_filter")
            threshold = int(rule.get("threshold", 0))

            if item_filter:
                count = sum(
                    item.get("quantity", 0)
                    for item in items
                    if item_filter.lower() in item.get("type_name", "").lower()
                )
            else:
                count = sum(item.get("quantity", 0) for item in items)

            if count < threshold:
                rule["last_alert"] = now
                alert = {
                    "rule_id": rule["id"],
                    "ssu_id": ssu_id,
                    "ssu_name": rule.get("ssu_name") or ssu_id[:16],
                    "item_filter": item_filter,
                    "threshold": threshold,
                    "current_count": count,
                    "timestamp": now,
                }
                log.info("watcher_task: ALERT %s — %s count=%d threshold=%d",
                         wallet[:12], ssu_id[:12], count, threshold)
                push_alert(wallet, alert)

        if changed:
            save_session(session, base_dir=base_dir)
