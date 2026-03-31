#!/usr/bin/env python3
"""
fetch_killmails.py — Fetch all killmails from Sui blockchain and store to JSONL.

Usage:
    python3 scripts/fetch_killmails.py [--env stillness|utopia] [--out PATH]

Defaults to DEPLOYMENT_ENV from environment (or stillness if unset).
Output: data/{env}/killmails.jsonl (one raw killmail per line).
"""

import asyncio
import json
import os
import sys
from collections import defaultdict
from pathlib import Path

# Allow imports from project root
sys.path.insert(0, str(Path(__file__).parent.parent))


async def main():
    import argparse

    parser = argparse.ArgumentParser(description="Fetch all killmails from Sui blockchain")
    parser.add_argument("--env", default=None, help="Deployment env: stillness or utopia")
    parser.add_argument("--out", default=None, help="Output JSONL path (overrides default)")
    args = parser.parse_args()

    env = args.env or os.getenv("DEPLOYMENT_ENV", "stillness")
    os.environ["DEPLOYMENT_ENV"] = env

    from src.config import load_config_from_env, get_network_config
    from src.blockchain_killmails import get_all_killmails, _event_to_killmail, _extract_tenant_item_id

    network = get_network_config(env)
    package_id = network["eve_frontier_package"]
    rpc_url = network["nova_rpc_url"]

    print(f"env:     {env}")
    print(f"package: {package_id}")
    print(f"rpc:     {rpc_url}")
    print("fetching...")

    events = await get_all_killmails(package_id=package_id, rpc_url=rpc_url)

    if events is None:
        print("ERROR: fetch failed — check logs")
        sys.exit(1)

    if not events:
        print("No killmail events found on chain.")
        sys.exit(0)

    # Determine output path
    if args.out:
        out_path = Path(args.out)
    else:
        out_path = Path(__file__).parent.parent / "data" / env / "killmails.jsonl"

    out_path.parent.mkdir(parents=True, exist_ok=True)

    # Write JSONL — each line is the raw parsedJson event
    with open(out_path, "w") as f:
        for event in events:
            f.write(json.dumps(event) + "\n")

    # Stats
    systems = defaultdict(int)
    timestamps = []
    for event in events:
        sys_id = _extract_tenant_item_id(event.get("solar_system_id", {}))
        if sys_id:
            systems[sys_id] += 1
        ts = event.get("kill_timestamp")
        if ts:
            try:
                timestamps.append(int(ts))
            except (ValueError, TypeError):
                pass

    print(f"\nresults:")
    print(f"  total killmails : {len(events)}")
    print(f"  unique systems  : {len(systems)}")
    print(f"  written to      : {out_path}")

    if timestamps:
        from datetime import datetime, timezone
        earliest = datetime.fromtimestamp(min(timestamps), tz=timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
        latest = datetime.fromtimestamp(max(timestamps), tz=timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
        print(f"  date range      : {earliest} → {latest}")

    # Top 5 systems by kill count
    top = sorted(systems.items(), key=lambda x: x[1], reverse=True)[:5]
    if top:
        print(f"\n  top systems by kills:")
        for sys_id, count in top:
            print(f"    system {sys_id:>15} : {count} kills")


if __name__ == "__main__":
    asyncio.run(main())
