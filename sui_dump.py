#!/usr/bin/env python3
"""
sui_dump.py — Sui object explorer for EVE Frontier.

Queries all known object IDs via Sui JSON-RPC and pretty-prints the full
on-chain state. Also follows energy_source_id hops and dynamic fields.

Usage:
    python sui_dump.py                  # uses .env values
    python sui_dump.py 0xABCD... 0x...  # query specific object IDs
"""

import sys
import json
import os
import asyncio
import httpx
from pathlib import Path
from dotenv import load_dotenv

load_dotenv(Path(__file__).parent / ".env")

RPC_URL = os.environ.get("NOVA_RPC_URL", "https://fullnode.testnet.sui.io")

KNOWN_OBJECTS = {
    "SSU":             os.environ.get("SSU_OBJECT_ID", ""),
    "AccessRegistry":  os.environ.get("NOVA_REGISTRY_OBJECT_ID", ""),
}

# Add any PLAYER_STRUCTURE_IDS and TURRET_OBJECT_IDS from .env
for raw, label in [
    (os.environ.get("PLAYER_STRUCTURE_IDS", ""), "PlayerStructure"),
    (os.environ.get("TURRET_OBJECT_IDS", ""), "Turret"),
]:
    for i, oid in enumerate(filter(None, raw.split(","))):
        KNOWN_OBJECTS[f"{label}[{i}]"] = oid.strip()


# ── ANSI colours ──────────────────────────────────────────────────────────────
RESET  = "\033[0m"
BOLD   = "\033[1m"
CYAN   = "\033[96m"
YELLOW = "\033[93m"
GREEN  = "\033[92m"
RED    = "\033[91m"
DIM    = "\033[2m"


def colour(text: str, code: str) -> str:
    return f"{code}{text}{RESET}"


# ── RPC helpers ───────────────────────────────────────────────────────────────

async def rpc(client: httpx.AsyncClient, method: str, params: list) -> dict:
    payload = {"jsonrpc": "2.0", "id": 1, "method": method, "params": params}
    r = await client.post(RPC_URL, json=payload, timeout=15.0)
    r.raise_for_status()
    return r.json()


async def get_object(client: httpx.AsyncClient, oid: str) -> dict:
    return await rpc(client, "sui_getObject", [
        oid,
        {"showContent": True, "showType": True, "showOwner": True, "showPreviousTransaction": True}
    ])


async def get_dynamic_fields(client: httpx.AsyncClient, oid: str) -> dict:
    return await rpc(client, "suix_getDynamicFields", [oid, None, 50])


# ── Pretty printer ────────────────────────────────────────────────────────────

def _indent(depth: int) -> str:
    return "  " * depth


def pretty(value, depth: int = 0) -> str:
    ind = _indent(depth)
    ind1 = _indent(depth + 1)

    if isinstance(value, dict):
        if not value:
            return colour("{}", DIM)
        lines = [colour("{", DIM)]
        for k, v in value.items():
            key_str = colour(str(k), YELLOW)
            val_str = pretty(v, depth + 1)
            lines.append(f"{ind1}{key_str}: {val_str}")
        lines.append(f"{ind}{colour('}', DIM)}")
        return "\n".join(lines)

    if isinstance(value, list):
        if not value:
            return colour("[]", DIM)
        lines = [colour("[", DIM)]
        for item in value:
            lines.append(f"{ind1}{pretty(item, depth + 1)}")
        lines.append(f"{ind}{colour(']', DIM)}")
        return "\n".join(lines)

    if isinstance(value, str):
        # Sui object IDs / addresses — highlight
        if value.startswith("0x") and len(value) > 10:
            return colour(f'"{value}"', CYAN)
        return colour(f'"{value}"', GREEN)

    if isinstance(value, bool):
        return colour(str(value).lower(), YELLOW)

    if isinstance(value, (int, float)):
        return colour(str(value), YELLOW)

    if value is None:
        return colour("null", DIM)

    return str(value)


def section(title: str) -> None:
    width = 72
    print()
    print(colour("─" * width, DIM))
    print(colour(f"  {title}", BOLD + CYAN))
    print(colour("─" * width, DIM))


def field_table(fields: dict, depth: int = 0) -> None:
    """Print Move struct fields as a compact key: value table."""
    for k, v in fields.items():
        key = colour(f"{_indent(depth)}{k}", YELLOW)
        if isinstance(v, (dict, list)):
            print(f"{key}:")
            print(pretty(v, depth + 1))
        else:
            print(f"{key}: {pretty(v, depth)}")


# ── Object display ────────────────────────────────────────────────────────────

def display_object(label: str, oid: str, data: dict) -> None:
    section(f"{label}  {colour(oid, DIM)}")

    if "error" in data.get("result", {}):
        err = data["result"]["error"]
        print(colour(f"  ERROR: {err}", RED))
        return

    result = data.get("result", {}).get("data")
    if not result:
        print(colour("  (no data returned)", DIM))
        return

    obj_type = result.get("type", "unknown type")
    print(f"  {colour('type', DIM)}: {colour(obj_type, GREEN)}")

    owner = result.get("owner")
    if owner:
        print(f"  {colour('owner', DIM)}: {pretty(owner)}")

    prev_tx = result.get("previousTransaction")
    if prev_tx:
        print(f"  {colour('previousTransaction', DIM)}: {colour(prev_tx, CYAN)}")

    content = result.get("content", {})
    fields = content.get("fields", {})
    if fields:
        print(f"\n  {colour('fields:', BOLD)}")
        for k, v in fields.items():
            key = colour(f"    {k}", YELLOW)
            if isinstance(v, (dict, list)):
                print(f"{key}:")
                # indent each line of pretty output
                for line in pretty(v, 3).splitlines():
                    print(f"    {line}")
            else:
                print(f"{key}: {pretty(v)}")
    else:
        print(colour("  (no content fields)", DIM))
        if content:
            print(pretty(content, 1))


def display_dynamic_fields(parent_label: str, oid: str, dyn_data: dict) -> None:
    section(f"Dynamic fields of {parent_label}  {colour(oid, DIM)}")

    if "error" in dyn_data.get("result", {}):
        print(colour(f"  ERROR: {dyn_data['result']['error']}", RED))
        return

    items = dyn_data.get("result", {}).get("data", [])
    if not items:
        print(colour("  (no dynamic fields)", DIM))
        return

    print(f"  {colour(str(len(items)), YELLOW)} dynamic field(s) found:\n")
    for item in items:
        name = item.get("name", {})
        obj_type = item.get("type", "")
        obj_id = item.get("objectId", "")
        print(f"  {colour('objectId', DIM)}: {colour(obj_id, CYAN)}")
        print(f"  {colour('name', DIM)}: {pretty(name)}")
        print(f"  {colour('type', DIM)}: {colour(obj_type, GREEN)}")
        print()


# ── Main ──────────────────────────────────────────────────────────────────────

async def main(extra_ids: list[str]) -> None:
    targets = dict(KNOWN_OBJECTS)  # label → oid

    for oid in extra_ids:
        targets[f"CLI:{oid[:10]}…"] = oid

    # Remove empty entries
    targets = {k: v for k, v in targets.items() if v}

    if not targets:
        print(colour("No object IDs found. Check .env or pass IDs as arguments.", RED))
        sys.exit(1)

    print(colour(f"\nSui Object Dumper", BOLD))
    print(colour(f"RPC: {RPC_URL}", DIM))
    print(colour(f"Objects to query: {len(targets)}", DIM))

    async with httpx.AsyncClient() as client:
        for label, oid in targets.items():
            data = await get_object(client, oid)
            display_object(label, oid, data)

            # If this object has an energy_source_id, follow it
            fields = (
                data.get("result", {})
                .get("data", {})
                .get("content", {})
                .get("fields", {})
            )
            energy_id = fields.get("energy_source_id")
            if isinstance(energy_id, dict):
                energy_id = (
                    energy_id.get("fields", {}).get("id")
                    or energy_id.get("id")
                    or energy_id.get("Some")
                )
            if energy_id and isinstance(energy_id, str) and energy_id.startswith("0x"):
                hop_data = await get_object(client, energy_id)
                display_object(f"{label} → NetworkNode", energy_id, hop_data)

            # Fetch dynamic fields for every object
            dyn = await get_dynamic_fields(client, oid)
            dyn_items = dyn.get("result", {}).get("data", [])
            if dyn_items:
                display_dynamic_fields(label, oid, dyn)
                # Fetch each dynamic field object for its content
                for item in dyn_items:
                    child_id = item.get("objectId", "")
                    if child_id:
                        child_data = await get_object(client, child_id)
                        child_label = f"{label}.dynfield[{item.get('name', {}).get('value', '?')}]"
                        display_object(child_label, child_id, child_data)

    print()
    print(colour("─" * 72, DIM))
    print(colour("  Done.", BOLD))
    print()


if __name__ == "__main__":
    extra = sys.argv[1:]
    asyncio.run(main(extra))
