"""
src/endpoints/entity.py

Entity REST endpoints — read-only, no auth required.

GET /entity/assembly/{sui_object_id}
GET /entity/network/{network_node_id}
GET /entity/inventory/{assembly_id}
GET /entity/nodes
"""

import asyncio
import logging
import os
import re
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query

from src.entity_resolver import EntityResolver, get_entity_resolver

_DEFAULT_TENANT = os.getenv("DEPLOYMENT_ENV", "utopia")

log = logging.getLogger(__name__)
entity_router = APIRouter()

_SUI_ID_RE = re.compile(r"^0x[0-9a-fA-F]{1,64}$")


def _validate_sui_id(obj_id: str) -> None:
    if not _SUI_ID_RE.match(obj_id):
        raise HTTPException(status_code=400, detail="Invalid Sui object ID format")


async def _resolve_with_timeout(coro, timeout: float = 10.0):
    try:
        return await asyncio.wait_for(coro, timeout=timeout)
    except asyncio.TimeoutError:
        raise HTTPException(status_code=504, detail="Entity resolver timed out")


# ---------------------------------------------------------------------------
# GET /entity/assembly/{sui_object_id}
# ---------------------------------------------------------------------------

@entity_router.get("/entity/assembly/{sui_object_id}")
async def get_assembly_entity(
    sui_object_id: str,
    tenant: str = Query(default=_DEFAULT_TENANT),
    resolver: EntityResolver = Depends(get_entity_resolver),
):
    """
    Fetch enriched assembly data.

    Returns: id, assembly_type, type_id, name, status, key,
             owner (character_name, tribe_id, character_id),
             network_node (id, name, status, fuel_percent, fuel_hours_remaining,
                           energy_used, energy_max),
             destination_gate (id, name, status)
    """
    _validate_sui_id(sui_object_id)

    full = await _resolve_with_timeout(resolver.get_assembly_full(sui_object_id))
    if not full:
        raise HTTPException(status_code=404, detail="Assembly not found")

    asm  = full.get("assembly") or {}
    char = full.get("owner_character")
    es   = full.get("energy_source")
    dg   = full.get("destination_gate")

    # Owner
    owner = None
    if char:
        owner = {
            "character_name": char.get("name") or char.get("metadata", {}).get("name") or "",
            "tribe_id":       char.get("tribe_id") or 0,
            "character_id":   char.get("id") or char.get("character_id") or "",
        }

    # Network node summary
    network_node = None
    if es:
        fuel = es.get("fuel") or {}
        if isinstance(fuel, dict):
            fuel = fuel.get("fields") or fuel
        qty        = int(fuel.get("quantity") or 0)
        cap        = int(fuel.get("max_capacity") or 0)
        unit_vol   = int(fuel.get("unit_volume") or 0)
        # max_capacity is in m3; unit_volume is m3/unit → effective max in units
        eff_max    = cap // unit_vol if unit_vol > 0 else cap
        fuel_pct   = round(qty * 100.0 / eff_max, 2) if eff_max > 0 else 0.0

        # Fuel hours remaining using on-chain burn_rate_in_ms
        burn_ms  = int(fuel.get("burn_rate_in_ms") or 0)
        is_burning = fuel.get("is_burning", False)
        if is_burning and burn_ms > 0:
            units_per_hr = 3_600_000.0 / burn_ms
            hours_remaining = qty / units_per_hr if units_per_hr > 0 else 0.0
        else:
            hours_remaining = 0.0

        network_node = {
            "id":                   es.get("id") or "",
            "name":                 es.get("name") or "",
            "status":               _status(es.get("status")),
            "fuel_percent":         fuel_pct,
            "fuel_quantity":        qty,
            "fuel_effective_max":   eff_max,
            "fuel_hours_remaining": round(hours_remaining, 2),
            "energy_used":          str(es.get("current_energy_production") or "0"),
            "energy_max":           str(es.get("max_energy_production") or "0"),
        }

    # Destination gate summary
    destination_gate = None
    if dg:
        destination_gate = {
            "id":     dg.get("id") or "",
            "name":   dg.get("name"),
            "status": _status(dg.get("status")),
        }

    return {
        "id":               sui_object_id,
        "assembly_type":    asm.get("assembly_type", "Unknown"),
        "type_id":          str(asm.get("type_id") or ""),
        "name":             asm.get("name") or "",
        "status":           _status(asm.get("status")),
        "key":              asm.get("key"),
        "owner":            owner,
        "network_node":     network_node,
        "destination_gate": destination_gate,
    }


# ---------------------------------------------------------------------------
# GET /entity/network/{network_node_id}
# ---------------------------------------------------------------------------

@entity_router.get("/entity/network/{network_node_id}")
async def get_network_entity(
    network_node_id: str,
    tenant: str = Query(default=_DEFAULT_TENANT),
    resolver: EntityResolver = Depends(get_entity_resolver),
):
    """
    Fetch NetworkNode topology: fuel, energy, connected assemblies.
    """
    _validate_sui_id(network_node_id)

    net = await _resolve_with_timeout(resolver.get_network(network_node_id))
    if not net:
        raise HTTPException(status_code=404, detail="Network node not found")

    raw_fuel   = net.get("fuel") or {}
    qty        = int(raw_fuel.get("quantity") or 0)
    cap        = int(raw_fuel.get("max_capacity") or 0)
    unit_vol   = int(raw_fuel.get("unit_volume") or 0)
    burn_ms    = int(raw_fuel.get("burn_rate_in_ms") or 0)
    is_burning = bool(raw_fuel.get("is_burning", False))

    eff_max  = cap // unit_vol if unit_vol > 0 else cap
    fuel_pct = round(qty * 100.0 / eff_max, 2) if eff_max > 0 else 0.0
    if is_burning and burn_ms > 0:
        units_per_hr    = 3_600_000.0 / burn_ms
        hours_remaining = qty / units_per_hr if units_per_hr > 0 else 0.0
    else:
        units_per_hr    = 0.0
        hours_remaining = 0.0

    energy = net.get("energy") or {}

    return {
        "id":     network_node_id,
        "name":   net.get("name") or "",
        "status": net.get("status") or "UNKNOWN",
        "fuel": {
            "quantity":               str(qty),
            "max_capacity":           str(cap),
            "fuel_percent":           fuel_pct,
            "hours_remaining":        round(hours_remaining, 2),
            "burn_rate_units_per_hr": round(units_per_hr, 4),
            "is_burning":             is_burning,
        },
        "energy": {
            "current_energy_production": str(energy.get("current_energy_production") or 0),
            "max_energy_production":     str(energy.get("max_energy_production") or 0),
            "total_reserved_energy":     str(energy.get("total_reserved_energy") or 0),
            "energy_percent":            energy.get("energy_percent") or 0.0,
        },
        "connected_assemblies": net.get("connected_assemblies") or [],
        "truncated":            net.get("truncated", False),
    }


# ---------------------------------------------------------------------------
# GET /entity/nodes
# ---------------------------------------------------------------------------

@entity_router.get("/entity/nodes")
async def get_all_nodes(
    tenant: str = Query(default=_DEFAULT_TENANT),
    wallet: Optional[str] = Query(default=None),
    resolver: EntityResolver = Depends(get_entity_resolver),
):
    """
    Return summary list of NetworkNodes for this tenant.
    If wallet is provided, only nodes owned by that address are returned.
    Sorted by connected structure count descending.
    """
    nodes = await _resolve_with_timeout(resolver.get_all_network_nodes(wallet=wallet), timeout=30.0)
    return {"nodes": nodes, "count": len(nodes)}


# ---------------------------------------------------------------------------
# GET /entity/inventory/{assembly_id}
# ---------------------------------------------------------------------------

@entity_router.get("/entity/inventory/{assembly_id}")
async def get_inventory_entity(
    assembly_id: str,
    tenant: str = Query(default=_DEFAULT_TENANT),
    resolver: EntityResolver = Depends(get_entity_resolver),
):
    """
    Fetch SSU inventory. Returns 404 for non-SSU assemblies.
    """
    _validate_sui_id(assembly_id)

    # Check assembly type first
    asm = await _resolve_with_timeout(resolver.get_assembly(assembly_id))
    if not asm:
        raise HTTPException(status_code=404, detail="Assembly not found")
    if asm.get("assembly_type") != "SmartStorageUnit":
        raise HTTPException(status_code=404, detail="Assembly is not a StorageUnit")

    inv = await _resolve_with_timeout(resolver.get_inventory(assembly_id))
    if not inv:
        raise HTTPException(status_code=404, detail="Inventory not found")

    return inv


# ---------------------------------------------------------------------------
# GET /entity/types/categories
# ---------------------------------------------------------------------------

@entity_router.get("/entity/types/categories")
async def get_type_categories(
    resolver: EntityResolver = Depends(get_entity_resolver),
):
    """
    Return all Datahub type categories and the count of types in each.
    Useful for discovering category names (e.g. what NPCs/enemies are called).
    """
    cats = resolver.get_all_categories()
    sorted_cats = dict(sorted(cats.items(), key=lambda x: x[1], reverse=True))
    return {"categories": sorted_cats, "total_types": sum(cats.values())}


@entity_router.get("/entity/types/by-category/{category}")
async def get_types_by_category(
    category: str,
    max_results: int = Query(default=50, le=500),
    resolver: EntityResolver = Depends(get_entity_resolver),
):
    """
    Return all types in a given category with full Datahub records.
    Use /entity/types/categories first to discover valid category names.
    """
    types = resolver.get_types_for_category(category, max_results=max_results)
    if not types:
        raise HTTPException(status_code=404, detail=f"No types found for category '{category}'")
    return {"category": category, "count": len(types), "types": types}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _status(val, _depth: int = 0) -> str:
    if val is None:
        return "UNKNOWN"
    if isinstance(val, str):
        return val
    if isinstance(val, dict) and _depth < 3:
        for key in ("@variant", "variant", "name"):
            v = val.get(key)
            if isinstance(v, str):
                return v
        for key in ("status",):
            v = val.get(key)
            if v is not None:
                return _status(v, _depth + 1)
    return str(val)
