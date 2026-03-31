# src/blockchain_killmails.py
"""
Blockchain-based killmail querying via Sui RPC.

Queries KillmailCreatedEvent from EVE Frontier world contracts on Sui.
Converts blockchain events to World API killmail format for consistency.
"""

import os
import json
import logging
from pathlib import Path
from typing import Optional, List
from datetime import datetime, timezone

log = logging.getLogger(__name__)

KILLMAIL_REFRESH_INTERVAL = 3600  # 1 hour


async def refresh_killmails_incremental(env: str = None) -> int:
    """Fetch only new killmails from blockchain and append to local JSONL.

    Loads existing killmail keys, fetches newest-first from chain, stops
    when hitting already-known events, appends new ones.

    Args:
        env: Deployment env (defaults to DEPLOYMENT_ENV)

    Returns:
        Number of new killmails appended (0 if nothing new or on error)
    """
    env = env or os.getenv("DEPLOYMENT_ENV", "stillness")

    from src.config import get_network_config
    network = get_network_config(env)
    package_id = network["eve_frontier_package"]
    rpc_url = network["nova_rpc_url"]

    data_dir = Path(__file__).parent.parent / "data" / env
    jsonl_path = data_dir / "killmails.jsonl"

    # Load existing keys for dedup
    existing_keys: set = set()
    if jsonl_path.exists():
        with open(jsonl_path) as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    event = json.loads(line)
                    key = _extract_tenant_item_id(event.get("key", {}))
                    if key:
                        existing_keys.add(key)
                except Exception:
                    pass

    event_type = f"{package_id}::killmail::KillmailCreatedEvent"
    new_events = []
    cursor = None
    done = False

    import httpx
    async with httpx.AsyncClient(timeout=30.0) as client:
        while not done:
            payload = {
                "jsonrpc": "2.0",
                "id": 1,
                "method": "suix_queryEvents",
                "params": [{"MoveEventType": event_type}, cursor, 1000, False],
            }
            try:
                resp = await client.post(rpc_url, json=payload)
                resp.raise_for_status()
                result = resp.json().get("result", {})
            except Exception as e:
                log.warning("refresh_killmails_incremental: RPC error: %s", e)
                return 0

            events = result.get("data", [])
            for event in events:
                parsed = event.get("parsedJson", {})
                key = _extract_tenant_item_id(parsed.get("key", {}))
                if key in existing_keys:
                    done = True
                    break
                new_events.append(parsed)

            if not result.get("hasNextPage") or not result.get("nextCursor"):
                break
            cursor = result["nextCursor"]

    if not new_events:
        log.debug("refresh_killmails_incremental: no new killmails")
        return 0

    data_dir.mkdir(parents=True, exist_ok=True)
    with open(jsonl_path, "a") as f:
        for event in new_events:
            f.write(json.dumps(event) + "\n")

    log.info("refresh_killmails_incremental: appended %d new killmails to %s", len(new_events), jsonl_path)
    return len(new_events)


async def killmail_refresh_loop():
    """Background task: refresh killmails every hour."""
    import asyncio
    while True:
        await asyncio.sleep(KILLMAIL_REFRESH_INTERVAL)
        try:
            added = await refresh_killmails_incremental()
            if added:
                log.info("killmail_refresh_loop: +%d new killmails", added)
        except Exception as e:
            log.warning("killmail_refresh_loop: error: %s", e)


async def get_all_killmails(package_id: str = None, rpc_url: str = None) -> Optional[List[dict]]:
    """Fetch ALL KillmailCreatedEvents from Sui blockchain with cursor pagination.

    No system filter — returns every killmail ever recorded for the given package.

    Args:
        package_id: Sui package ID (defaults to WORLD_CONTRACTS_PACKAGE_ID env var)
        rpc_url: Sui RPC URL (defaults to nova_rpc_url from config)

    Returns:
        List of killmail dicts (raw blockchain format), or None on failure
    """
    pkg = package_id or os.getenv("WORLD_CONTRACTS_PACKAGE_ID")
    if not pkg:
        log.warning("get_all_killmails: no package_id configured")
        return None

    if rpc_url is None:
        from src.config import load_config_from_env
        rpc_url = load_config_from_env()["nova_rpc_url"]

    event_type = f"{pkg}::killmail::KillmailCreatedEvent"
    all_events = []
    cursor = None
    page = 0

    log.info("get_all_killmails: starting full fetch from %s", rpc_url)

    import httpx
    async with httpx.AsyncClient(timeout=30.0) as client:
        while True:
            payload = {
                "jsonrpc": "2.0",
                "id": 1,
                "method": "suix_queryEvents",
                "params": [
                    {"MoveEventType": event_type},
                    cursor,
                    1000,
                    False,  # descending (newest first)
                ],
            }
            try:
                resp = await client.post(rpc_url, json=payload)
                resp.raise_for_status()
                result = resp.json().get("result", {})
            except Exception as e:
                log.warning("get_all_killmails: RPC error on page %d: %s", page, e)
                return None

            events = result.get("data", [])
            all_events.extend(events)
            page += 1

            has_next = result.get("hasNextPage", False)
            cursor = result.get("nextCursor")

            log.debug("get_all_killmails: page %d → %d events (total %d)", page, len(events), len(all_events))

            if not has_next or not cursor:
                break

    log.info("get_all_killmails: fetched %d total events across %d pages", len(all_events), page)
    return [e.get("parsedJson", {}) for e in all_events if e.get("parsedJson")]


def load_killmails_for_system(system_id: int, env: str = None) -> List[dict]:
    """Load killmails for a system from the local JSONL file.

    Reads data/{env}/killmails.jsonl, converts raw blockchain events to
    World API format, and filters by system_id.

    Args:
        system_id: Solar system ID to filter for
        env: Deployment env (defaults to DEPLOYMENT_ENV env var)

    Returns:
        List of killmail dicts in World API format (empty list if file missing)
    """
    import os as _os
    from pathlib import Path

    env = env or _os.getenv("DEPLOYMENT_ENV", "stillness")
    data_dir = Path(__file__).parent.parent / "data" / env
    jsonl_path = data_dir / "killmails.jsonl"

    if not jsonl_path.exists():
        log.debug("load_killmails_for_system: %s not found", jsonl_path)
        return []

    results = []
    system_id_str = str(system_id)

    with open(jsonl_path) as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                import json as _json
                event = _json.loads(line)
            except Exception:
                continue

            # Fast filter before conversion
            raw_sys = event.get("solar_system_id", {})
            if isinstance(raw_sys, dict):
                if str(raw_sys.get("item_id", "")) != system_id_str:
                    continue
            else:
                if str(raw_sys) != system_id_str:
                    continue

            km = _event_to_killmail(event)
            if km:
                results.append(km)

    return results


async def get_killmails_from_blockchain(system_id: int) -> Optional[List[dict]]:
    """Query KillmailCreatedEvent from Sui blockchain for a system.

    Args:
        system_id: Solar system ID to filter killmails for

    Returns:
        List of killmail dicts (World API format) if successful,
        None if blockchain querying is unavailable or fails
    """
    package_id = os.getenv("WORLD_CONTRACTS_PACKAGE_ID")
    if not package_id:
        log.debug("get_killmails_from_blockchain: WORLD_CONTRACTS_PACKAGE_ID not configured")
        return None

    try:
        from src.blockchain_queries import nova_client
    except ImportError:
        log.debug("get_killmails_from_blockchain: blockchain_queries not available")
        return None

    try:
        # Query KillmailCreatedEvent from blockchain
        event_type = f"{package_id}::killmail::KillmailCreatedEvent"

        result = await nova_client._rpc("suix_queryEvents", [
            {"MoveEventType": event_type},  # Correct filter format: MoveEventType, not EventType
            None,                           # cursor (None = start from latest)
            1000,                           # limit: fetch up to 1000 events
            False,                          # ascending=False → newest first
        ])

        events_data = result.get("result", {})
        events = events_data.get("data", [])

        if not events:
            log.debug("No killmail events found on blockchain")
            return []

        # Convert Sui events to World API killmail format
        killmails = []
        for event in events:
            parsed = event.get("parsedJson", {})

            # Filter by system_id (extract from TenantItemId)
            event_system_id = _extract_tenant_item_id(parsed.get("solar_system_id", {}))
            try:
                if not event_system_id or int(event_system_id) != system_id:
                    continue
            except (ValueError, TypeError):
                continue

            killmail = _event_to_killmail(parsed)
            if killmail:
                killmails.append(killmail)

        if killmails:
            log.info("blockchain_killmails: %d events for system %d", len(killmails), system_id)

        return killmails

    except Exception as e:
        log.warning("get_killmails_from_blockchain failed: %s", e, exc_info=True)
        return None


def _event_to_killmail(event_data: dict) -> Optional[dict]:
    """Convert a KillmailCreatedEvent to World API killmail format.

    Args:
        event_data: Parsed JSON from Sui KillmailCreatedEvent

    Returns:
        Killmail dict or None if conversion fails
    """
    try:
        # Extract timestamp (u64 seconds from blockchain)
        kill_timestamp = event_data.get("kill_timestamp", 0)
        ts_str = _format_timestamp(kill_timestamp)

        # Extract TenantItemId values (they have item_id and tenant fields)
        key = event_data.get("key", {})
        key_id = _extract_tenant_item_id(key)

        solar_system = event_data.get("solar_system_id", {})
        system_id = _extract_tenant_item_id(solar_system)

        victim = event_data.get("victim_id", {})
        victim_id = _extract_tenant_item_id(victim)

        killer = event_data.get("killer_id", {})
        killer_id = _extract_tenant_item_id(killer)

        # Extract loss_type variant (SHIP or STRUCTURE)
        loss_type_data = event_data.get("loss_type", {})
        if isinstance(loss_type_data, dict):
            loss_type = loss_type_data.get("variant", "UNKNOWN")
        else:
            loss_type = str(loss_type_data)

        killmail = {
            # Identifiers
            "id": key_id,
            "killId": key_id,

            # Timestamp (dual format for compatibility)
            "time": ts_str,
            "timestamp": ts_str,

            # System
            "solarSystemId": system_id,

            # Parties involved
            "victim_id": victim_id,
            "killer_id": killer_id,
            "reported_by": _extract_tenant_item_id(event_data.get("reported_by_character_id", {})),

            # Classification
            "loss_type": loss_type,

            # Optional fields (not in blockchain event)
            # TODO: Enrich with character names/ships once lookup available
            "victimName": f"Character {victim_id}",
            "victimShip": "Unknown",
            "totalValue": 0,

            # Attackers list (minimal format)
            "attackers": [
                {
                    "name": f"Character {killer_id}",
                    "corp": "",
                }
            ],
        }
        return killmail

    except Exception as e:
        log.warning("Failed to convert killmail event: %s", e)
        return None


def _extract_tenant_item_id(tenant_item_id_data) -> str:
    """Extract item_id from TenantItemId struct.

    TenantItemId has fields: item_id (u64), tenant (String).
    Returns the item_id as string, or empty string if not found.
    """
    if not tenant_item_id_data:
        return ""

    if isinstance(tenant_item_id_data, dict):
        return str(tenant_item_id_data.get("item_id", ""))
    else:
        return str(tenant_item_id_data)


def _format_timestamp(ts_u64) -> str:
    """Convert Sui u64 timestamp (seconds) to ISO 8601 string.

    Args:
        ts_u64: Unix timestamp in seconds (u64 from blockchain)

    Returns:
        ISO 8601 formatted timestamp string or empty string on error
    """
    if not ts_u64:
        return ""

    try:
        ts_sec = int(ts_u64)
        dt = datetime.fromtimestamp(ts_sec, tz=timezone.utc)
        # Format as ISO 8601 with 'Z' suffix for UTC
        return dt.isoformat().replace("+00:00", "Z")
    except (ValueError, TypeError, OSError):
        return ""
