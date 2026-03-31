#!/usr/bin/env python3
"""
Utility to discover EVE Frontier world contracts package ID from Sui blockchain.

Queries the Sui RPC to find recent KillmailCreatedEvent events and extracts
the package ID from the event type string.

Usage:
    python3 src/discover_package_id.py

Environment:
    DEPLOYMENT_ENV: 'utopia' or 'stillness' (default: stillness)
"""

import os
import sys
import asyncio
import logging
from typing import Optional

log = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO, format='%(message)s')


async def discover_package_id() -> Optional[str]:
    """Query Sui blockchain for KillmailCreatedEvent and extract package ID.

    Returns:
        Package ID string (0x...) or None if not found
    """
    try:
        from src.blockchain_queries import nova_client
    except Exception as e:
        log.error(f"Failed to import blockchain_queries: {e}")
        return None

    try:
        log.info("Querying Sui blockchain for KillmailCreatedEvent...")
        log.info("(Scanning recent blocks...)\n")

        # Query for events with 'killmail' in the type
        result = await nova_client._rpc("suix_queryEvents", [
            {"EventType": "*killmail*"},  # Wildcard filter
            None,                          # start from latest
            100,                           # get last 100 events
            False,                         # reverse order (newest first)
        ])

        events_data = result.get("result", {})
        events = events_data.get("data", [])

        if not events:
            log.warning("No killmail events found in recent blocks.\n")
            log.info("Possible causes:")
            log.info("  1. No kills have been recorded on this network yet")
            log.info("  2. World contracts not deployed to this network")
            log.info("  3. Event naming differs from expected pattern\n")
            log.info("Alternative methods to find package ID:")
            log.info("  1. Sui Testnet Explorer: https://testnet.suivision.xyz/")
            log.info("     Search for 'world' or 'killmail'")
            log.info("  2. World-contracts deployment logs")
            log.info("  3. EVE Frontier Builder Discord")
            return None

        # Extract package ID from first event
        for event in events:
            event_type = event.get("type", "")
            if not event_type:
                continue

            log.info(f"Found event: {event_type}\n")

            # Parse event type: 0x<package>::module::EventName
            if "::" in event_type:
                parts = event_type.split("::")
                package_id = parts[0]

                if package_id.startswith("0x"):
                    log.info(f"✓ Package ID discovered: {package_id}\n")
                    log.info("To use this, update .env:")
                    log.info(f"  WORLD_CONTRACTS_PACKAGE_ID={package_id}\n")

                    if "Killmail" in event_type:
                        log.info(f"Event type verified: {event_type}\n")

                    return package_id

        log.warning("Could not extract package ID from event types")
        return None

    except Exception as e:
        log.error(f"Discovery query failed: {e}\n")
        log.info("Make sure:")
        log.info("  1. DEPLOYMENT_ENV=stillness is set in .env")
        log.info("  2. RPC endpoint is reachable")
        log.info("  3. Some kills have been recorded on the network")
        return None


async def main():
    """Main entry point."""
    from src.config import load_config_from_env

    log.info("=" * 60)
    log.info("EVE Frontier Package ID Discovery")
    log.info("=" * 60 + "\n")

    config = load_config_from_env()
    env = config["deployment_env"]
    log.info(f"Network: {env}\n")

    package_id = await discover_package_id()
    return 0 if package_id else 1


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
