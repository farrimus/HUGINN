# src/ssu_poller.py
"""
Background polling tasks for the Structure AI.
Polls Sui RPC for SSU state and World API for killmails.
All failures are logged and swallowed — never crash the server.
"""
import os
import asyncio
import logging
from typing import Optional

log = logging.getLogger(__name__)

SSU_POLL_INTERVAL = 60      # seconds
KILLMAIL_POLL_INTERVAL = 300  # 5 minutes
TURRET_POLL_INTERVAL = 60    # seconds (same as SSU poll — spec §background-tasks)

_running = False


async def poll_ssu_state(ssu_object_id: str, structure_id: str, system_id: int):
    """Poll sui_getObject on SSU_OBJECT_ID → append ssu_state event."""
    from src.nova_client import nova_client
    from src.memory_store import get_memory_store

    store = get_memory_store(structure_id)
    try:
        result = await nova_client._rpc("sui_getObject", [
            ssu_object_id,
            {"showContent": True, "showType": True}
        ])
        fields = (
            result.get("result", {})
            .get("data", {})
            .get("content", {})
            .get("fields", {})
        )
        if fields:
            log.debug("SSU object fields: %s", list(fields.keys()))
            data = {
                "fuel_pct": _extract_fuel_pct(fields),
                "anchor_status": fields.get("anchorStatus") or fields.get("anchor_status") or "unknown",
                "services_online": fields.get("servicesOnline") or fields.get("services_online") or 0,
                "services_total": fields.get("servicesTotal") or fields.get("services_total") or 0,
                "raw_fields": list(fields.keys()),
            }
            store.append_event("ssu_state", system_id, data)
            log.info("SSU state polled: fuel=%s anchor=%s", data["fuel_pct"], data["anchor_status"])
        else:
            log.warning("SSU poll: no fields in response for %s", ssu_object_id)
    except Exception as e:
        log.warning("SSU state poll failed: %s", e)


def _extract_fuel_pct(fields: dict) -> float:
    """Best-effort fuel percentage extraction. Returns 100.0 if not determinable."""
    for key in ("fuelAmount", "fuel_amount", "fuel", "fuelPct", "fuel_pct"):
        val = fields.get(key)
        if val is not None:
            try:
                f = float(val)
                if 0 <= f <= 100:
                    return f
                log.debug("SSU fuel raw value: %s=%s (not a percentage)", key, val)
                return 100.0
            except (TypeError, ValueError):
                pass
    return 100.0


async def poll_killmails(structure_id: str, system_id: int):
    """Poll World API killmails → append killmail events."""
    from src.world_api import world_api
    from src.memory_store import get_memory_store
    from datetime import datetime, timezone, timedelta

    store = get_memory_store(structure_id)
    cutoff = datetime.now(timezone.utc) - timedelta(hours=24)

    try:
        kills = await world_api.get_killmails(system_id=system_id)
        new_count = 0
        for kill in kills:
            t = kill.get("time") or kill.get("timestamp") or ""
            try:
                kt = datetime.fromisoformat(t.replace("Z", "+00:00"))
                if kt < cutoff:
                    continue
            except ValueError:
                pass

            data = {
                "kill_id": kill.get("id") or kill.get("killId") or 0,
                "victim_name": (
                    kill.get("victimName") or
                    (kill.get("victim") or {}).get("name", "Unknown")
                ),
                "victim_ship": (
                    kill.get("victimShip") or
                    (kill.get("victim") or {}).get("ship", "Unknown")
                ),
                "attacker_names": [
                    a.get("name", "") for a in (kill.get("attackers") or [])
                ],
                "value_isk": kill.get("totalValue") or kill.get("value") or 0,
            }
            store.append_event("killmail", system_id, data)
            new_count += 1
        if new_count:
            log.info("Killmail poll: %d new kills in system %d", new_count, system_id)
    except Exception as e:
        log.warning("Killmail poll failed: %s", e)


async def poll_sui_events(ssu_object_id: str, structure_id: str, system_id: int):
    """Poll suix_queryEvents on SSU object → append events."""
    from src.nova_client import nova_client
    from src.memory_store import get_memory_store

    store = get_memory_store(structure_id)
    cursor = getattr(poll_sui_events, "_cursor", None)

    try:
        result = await nova_client._rpc("suix_queryEvents", [
            {"Sender": ssu_object_id},
            cursor,
            50,
            False,  # ascending order (oldest-first); cursor advances forward so each poll returns only events newer than the last seen
        ])
        data = result.get("result", {})
        events = data.get("data", [])
        next_cursor = data.get("nextCursor")
        if next_cursor:
            poll_sui_events._cursor = next_cursor

        for event in events:
            parsed = event.get("parsedJson", {})
            event_type_str = event.get("type", "")
            if "FuelDelivered" in event_type_str or "fuel" in event_type_str.lower():
                store.append_event("ssu_state", system_id, {"raw": parsed})
            elif "AccessList" in event_type_str or "access" in event_type_str.lower():
                store.append_event("access_change", system_id, {"raw": parsed})
            else:
                log.debug("Unhandled Sui event type: %s", event_type_str)

        if events:
            log.info("Sui events poll: %d events processed", len(events))
    except Exception as e:
        log.warning("Sui events poll failed: %s", e)


async def poll_turret(turret_object_id: str, structure_id: str, system_id: int):
    """Poll a single turret object state via sui_getObject → append turret_state event."""
    from src.nova_client import nova_client
    from src.memory_store import get_memory_store

    store = get_memory_store(structure_id)
    try:
        result = await nova_client._rpc("sui_getObject", [
            turret_object_id,
            {"showContent": True, "showType": True}
        ])
        fields = (
            result.get("result", {})
            .get("data", {})
            .get("content", {})
            .get("fields", {})
        )
        if fields:
            data = {
                "turret_id": turret_object_id,
                "active": fields.get("active") or fields.get("isActive") or False,
                "ammo": fields.get("ammo") or fields.get("ammoCount") or 0,
                "raw_fields": list(fields.keys()),
            }
            store.append_event("turret_state", system_id, data)
            log.debug("Turret polled: %s active=%s", turret_object_id[:12], data["active"])
    except Exception as e:
        log.warning("Turret poll failed (%s): %s", turret_object_id[:12], e)


async def _ssu_loop(ssu_object_id: str, structure_id: str, system_id: int):
    """Run SSU + Sui events polling every 60s."""
    while True:
        await poll_ssu_state(ssu_object_id, structure_id, system_id)
        await poll_sui_events(ssu_object_id, structure_id, system_id)
        await asyncio.sleep(SSU_POLL_INTERVAL)


async def _killmail_loop(structure_id: str, system_id: int):
    """Run killmail polling every 5 minutes."""
    while True:
        await poll_killmails(structure_id, system_id)
        await asyncio.sleep(KILLMAIL_POLL_INTERVAL)


async def _turret_loop(turret_ids: list[str], structure_id: str, system_id: int):
    """Poll all configured turrets every 60 seconds."""
    while True:
        for tid in turret_ids:
            await poll_turret(tid, structure_id, system_id)
        await asyncio.sleep(TURRET_POLL_INTERVAL)


def start_background_tasks(structure_id: str, ssu_object_id: str, system_id: int):
    """
    Launch polling tasks via asyncio. Call from FastAPI lifespan.
    Silently skips if required IDs are missing.

    Turret object IDs are read from TURRET_OBJECT_IDS env var (comma-separated list
    of Sui object IDs). If unset, turret polling is disabled.

    WatchTower webhook (POST to external endpoint on state change) is not implemented
    in this plan — deferred post-hackathon. Requires a stable webhook URL and
    contractual event schema, neither of which is confirmed yet.
    """
    if not structure_id:
        log.warning("SSU poller: no structure_id configured, skipping all polling")
        return

    if system_id and system_id > 0:
        asyncio.create_task(_killmail_loop(structure_id, system_id))
        log.info("Killmail poller started (system_id=%d, interval=%ds)",
                 system_id, KILLMAIL_POLL_INTERVAL)
    else:
        log.info("SSU poller: system_id not set, killmail polling disabled")

    if ssu_object_id:
        asyncio.create_task(_ssu_loop(ssu_object_id, structure_id, system_id))
        log.info("SSU poller started (object_id=%s, interval=%ds)",
                 ssu_object_id[:12] + "...", SSU_POLL_INTERVAL)
    else:
        log.info("SSU poller: SSU_OBJECT_ID not set, SSU polling disabled")

    turret_ids_raw = os.environ.get("TURRET_OBJECT_IDS", "")
    turret_ids = [t.strip() for t in turret_ids_raw.split(",") if t.strip()]
    if turret_ids:
        asyncio.create_task(_turret_loop(turret_ids, structure_id, system_id))
        log.info("Turret poller started (%d turrets, interval=%ds)",
                 len(turret_ids), TURRET_POLL_INTERVAL)
    else:
        log.info("SSU poller: TURRET_OBJECT_IDS not set, turret polling disabled")
