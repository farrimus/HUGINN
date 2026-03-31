#!/usr/bin/env python3
"""
Quick assembly state query script.
Usage: python query_assembly.py <assembly_id>
"""
import asyncio
import json
import sys
import os
from src.blockchain_queries import nova_client

async def query_assembly(assembly_id: str):
    """Query single assembly state via Sui RPC."""
    print(f"Querying assembly: {assembly_id}\n")

    try:
        resp = await nova_client._rpc("sui_getObject", [
            assembly_id,
            {"showContent": True, "showType": True}
        ])
    except Exception as e:
        print(f"❌ RPC failed: {e}")
        return

    data = resp.get("result", {}).get("data", {})
    if not data:
        print("❌ Assembly not found or no data")
        return

    # Type
    type_str = data.get("type", "")
    type_name = type_str.split("::")[-1] if "::" in type_str else type_str
    print(f"Type: {type_name}")
    print(f"Full type: {type_str}\n")

    # Content fields
    fields = data.get("content", {}).get("fields", {})
    if not fields:
        print("No fields found")
        return

    # Status
    status_val = fields.get("status", {})
    status_str = "UNKNOWN"
    if isinstance(status_val, dict):
        inner = status_val.get("fields", {}).get("status")
        if isinstance(inner, dict):
            status_str = inner.get("variant") or inner.get("name") or "UNKNOWN"
        else:
            status_str = str(inner) if inner else "UNKNOWN"
    else:
        status_str = str(status_val) if status_val else "UNKNOWN"

    print(f"Status: {status_str}")

    # Energy source / fuel
    energy_source_id = fields.get("energy_source_id")
    if isinstance(energy_source_id, dict):
        energy_source_id = (
            energy_source_id.get("fields", {}).get("id")
            or energy_source_id.get("id")
            or energy_source_id.get("Some")
        )

    if energy_source_id:
        print(f"Energy source: {energy_source_id}")
        try:
            node_resp = await nova_client._rpc("sui_getObject", [
                energy_source_id, {"showContent": True}
            ])
            node_fields = (
                node_resp.get("result", {})
                .get("data", {})
                .get("content", {})
                .get("fields", {})
            )
            fuel = node_fields.get("fuel", {})
            if isinstance(fuel, dict):
                fuel = fuel.get("fields", fuel)
            qty = fuel.get("quantity")
            cap = fuel.get("max_capacity")
            if qty is not None and cap is not None and int(cap) > 0:
                fuel_pct = round(int(qty) * 100 / int(cap), 1)
                print(f"Fuel: {fuel_pct}% ({qty}/{cap})")
        except Exception as e:
            print(f"⚠️  Could not fetch fuel: {e}")
    else:
        print("No energy source")

    print(f"\n📋 All fields:")
    for k, v in fields.items():
        if isinstance(v, (dict, list)):
            print(f"  {k}: {json.dumps(str(v)[:80])}")
        else:
            print(f"  {k}: {v}")

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python query_assembly.py <assembly_id>")
        sys.exit(1)

    assembly_id = sys.argv[1]
    asyncio.run(query_assembly(assembly_id))
