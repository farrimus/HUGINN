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

# Module-level imports for testability (can be patched in tests).
# nova_client and structure_profile helpers are imported lazily at first use to
# avoid circular imports at module load time.
try:
    from src.nova_client import nova_client
except Exception:  # pragma: no cover
    nova_client = None  # type: ignore[assignment]

try:
    from src.structure_profile import load_profile, save_profile
except Exception:  # pragma: no cover
    load_profile = None  # type: ignore[assignment]
    save_profile = None  # type: ignore[assignment]

SSU_POLL_INTERVAL = 60      # seconds
KILLMAIL_POLL_INTERVAL = 300  # 5 minutes
TURRET_POLL_INTERVAL = 60    # seconds (same as SSU poll — spec §background-tasks)

_running = False


async def poll_ssu_state(structure_id: str, ssu_object_id: str) -> None:
    """Poll SSU on-chain state. Two hops: StorageUnit → NetworkNode for fuel.

    Hop 1 fetches the StorageUnit object for status and energy_source_id.
    Hop 2 fetches the NetworkNode (energy_source_id) for fuel quantity/capacity
    and connected_assembly_ids (proxy for services_online).

    shield_pct is NOT polled — SSUs have no on-chain shield field.
    docked_count is NOT polled — no on-chain field exists; manual-override only.
    """
    # Hop 1: fetch StorageUnit
    try:
        ssu_data = await nova_client._rpc("sui_getObject", [
            ssu_object_id,
            {"showContent": True, "showType": True}
        ])
    except Exception as e:
        log.warning("poll_ssu_state: RPC hop 1 failed for %s: %s", ssu_object_id, e)
        return

    fields = (
        ssu_data.get("result", {})
        .get("data", {})
        .get("content", {})
        .get("fields", {})
    )
    if not fields:
        log.warning("poll_ssu_state: no fields in StorageUnit object %s", ssu_object_id)
        return

    profile = load_profile(structure_id)
    if not profile:
        log.warning("poll_ssu_state: no profile found for structure_id %s", structure_id)
        return

    # Status: ONLINE / OFFLINE / NULL from AssemblyStatus enum
    status_val = fields.get("status", {})
    if isinstance(status_val, dict):
        inner = status_val.get("fields", {}).get("status")
        if isinstance(inner, dict):
            # Sui Move enum variant: {"variant": "ONLINE"} or {"name": "ONLINE"}
            status_str = inner.get("variant") or inner.get("name") or str(inner)
        else:
            status_str = str(inner) if inner is not None else None
    else:
        status_str = str(status_val) if status_val is not None else None

    # Hop 2: fetch NetworkNode for fuel and connected assemblies
    energy_source_id = fields.get("energy_source_id")
    # energy_source_id may be nested: {"fields": {"id": "0x..."}} or a bare string or None/Some
    if isinstance(energy_source_id, dict):
        energy_source_id = (
            energy_source_id.get("fields", {}).get("id")
            or energy_source_id.get("id")
            or energy_source_id.get("Some")
        )

    fuel_pct = None
    services_online = None
    if energy_source_id:
        try:
            node_data = await nova_client._rpc("sui_getObject", [
                energy_source_id,
                {"showContent": True, "showType": True}
            ])
        except Exception as e:
            log.warning("poll_ssu_state: RPC hop 2 failed for NetworkNode %s: %s",
                        energy_source_id, e)
            node_data = {}

        node_fields = (
            node_data.get("result", {})
            .get("data", {})
            .get("content", {})
            .get("fields", {})
        )
        if node_fields:
            fuel = node_fields.get("fuel", {})
            if isinstance(fuel, dict):
                fuel = fuel.get("fields", fuel)
            qty = fuel.get("quantity")
            cap = fuel.get("max_capacity")
            if qty is not None and cap is not None and int(cap) > 0:
                fuel_pct = round(int(qty) * 100 / int(cap), 1)

            # connected_assembly_ids length → proxy for services_online
            connected = node_fields.get("connected_assembly_ids") or []
            services_online = len(connected)
    else:
        log.debug("poll_ssu_state: no energy_source_id on SSU %s, skipping hop 2", ssu_object_id)

    changed = False
    if fuel_pct is not None and profile.fuel_pct != fuel_pct:
        profile.fuel_pct = fuel_pct
        changed = True
    if services_online is not None and profile.services_online != services_online:
        profile.services_online = services_online
        changed = True
    # shield_pct NOT polled — SSUs have no on-chain shield field
    # docked_count NOT polled — no on-chain field; manual-override only

    if status_str:
        log.info("SSU %s status: %s  fuel: %s%%  services: %s",
                 structure_id, status_str, fuel_pct, services_online)

    if changed:
        save_profile(profile)
        log.info("poll_ssu_state: updated profile for %s", structure_id)


def _extract_fuel_pct(fields: dict) -> float:
    """Deprecated — fuel extraction is now inline in poll_ssu_state (two-hop RPC).

    Retained to avoid breaking any direct callers outside this module, but no
    longer called internally. Will be removed in a future cleanup pass.
    """
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
        await poll_ssu_state(structure_id, ssu_object_id)
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
