"""
src/entity_resolver.py

Core data layer for the Entity Graph. Resolves assembly, character, network,
inventory, and fuel data from Sui GraphQL and Datahub World API.

Instantiated once at server startup (main.py lifespan). Injected via
get_entity_resolver() dependency.

Cache tiers:
  on-chain objects  — 30s TTL   (key: Sui object ID)
  GameTypes         — permanent (key: type_id string)
  singletons        — 5min TTL  (key: type string)
"""

import asyncio
import logging
import time
from typing import Any, Optional

import httpx

from src.graphql_queries import (
    GRAPHQL_ENDPOINT,
    TENANT_CONFIG,
    ENERGY_CONFIG_TABLE,
    FUEL_CONFIG_TABLE,
    character_owner_cap_type,
    character_player_profile_type,
    energy_config_type,
    fuel_config_type,
    smart_storage_unit_type,
    GET_OBJECT_WITH_JSON,
    GET_OBJECT_WITH_DYNAMIC_FIELDS,
    GET_OBJECT_DYNAMICFIELD_CHARACTER_WITH_JSON,
    GET_WALLET_CHARACTERS,
    GET_SINGLETON_CONFIG_OBJECT_BY_TYPE,
    GET_OBJECTS_BY_TYPE,
    GET_OWNED_OBJECTS_BY_TYPE,
)

log = logging.getLogger(__name__)

_ONCHAIN_TTL   = 30.0    # seconds
_SINGLETON_TTL = 300.0   # seconds
_MS_PER_HOUR   = 3_600_000.0


# ---------------------------------------------------------------------------
# Assembly type classification
# ---------------------------------------------------------------------------

def _classify_assembly_type(move_type_repr: str) -> str:
    """Map a Move type repr string to a canonical assembly type name."""
    if "::storage_unit::StorageUnit" in move_type_repr:
        return "SmartStorageUnit"
    if "::turret::Turret" in move_type_repr:
        return "SmartTurret"
    if "::gate::Gate" in move_type_repr:
        return "SmartGate"
    if "::network_node::NetworkNode" in move_type_repr:
        return "NetworkNode"
    if "::manufacturing::Manufacturing" in move_type_repr:
        return "Manufacturing"
    if "::refinery::Refinery" in move_type_repr:
        return "Refinery"
    if "::assembly::Assembly" in move_type_repr:
        return "Assembly"
    return "Unknown"


def _safe_int(val, fallback: int = 0) -> int:
    """Convert u64 string (or int) to int, returning fallback on failure."""
    if val is None:
        return fallback
    try:
        return int(val)
    except (ValueError, TypeError):
        log.warning("entity_resolver: could not convert %r to int", val)
        return fallback


def _unwrap_option(val) -> Optional[str]:
    """Unwrap a Sui Option<address> — may be a bare string or {"Some": "0x..."} or None."""
    if val is None:
        return None
    if isinstance(val, str):
        return val if val.startswith("0x") else None
    if isinstance(val, dict):
        return val.get("Some") or val.get("some")
    return None


# ---------------------------------------------------------------------------
# EntityResolver
# ---------------------------------------------------------------------------

class EntityResolver:
    def __init__(self, tenant: str = "stillness"):
        if tenant not in TENANT_CONFIG:
            raise ValueError(f"Unknown tenant: {tenant}. Known: {list(TENANT_CONFIG.keys())}")
        cfg = TENANT_CONFIG[tenant]
        self.tenant        = tenant
        self.package_id    = cfg["package_id"]
        self.datahub_host  = cfg["datahub_host"]
        self.graphql_url   = GRAPHQL_ENDPOINT
        self._http         = httpx.AsyncClient(timeout=10.0)
        # Cache storage: key -> (data, timestamp)
        self._onchain:   dict[str, tuple[Any, float]] = {}
        self._singleton: dict[str, tuple[Any, float]] = {}
        # Permanent type cache: type_id_str -> dict
        self._types: dict[str, dict] = {}
        # Name index: lowercase_name -> list of type_id_str (built after prewarm)
        self._name_index: dict[str, list[str]] = {}
        # Category index: categoryName -> list of type_id_str (built after prewarm)
        self._category_index: dict[str, list[str]] = {}

    async def close(self) -> None:
        await self._http.aclose()

    # -----------------------------------------------------------------------
    # Internal cache helpers
    # -----------------------------------------------------------------------

    def _cache_get(self, store: dict, key: str, ttl: float) -> Optional[Any]:
        entry = store.get(key)
        if entry is None:
            return None
        data, ts = entry
        if time.monotonic() - ts > ttl:
            del store[key]
            return None
        return data

    def _cache_set(self, store: dict, key: str, data: Any) -> None:
        store[key] = (data, time.monotonic())

    # -----------------------------------------------------------------------
    # Internal network helpers
    # -----------------------------------------------------------------------

    async def _gql(self, query: str, variables: dict) -> Optional[dict]:
        """Run a GraphQL query. Returns result["data"] or None on error."""
        try:
            resp = await self._http.post(
                self.graphql_url,
                json={"query": query, "variables": variables},
                headers={"Content-Type": "application/json"},
                timeout=8.0,
            )
            resp.raise_for_status()
            body = resp.json()
            if "errors" in body:
                log.warning("entity_resolver: GQL errors: %s", body["errors"])
            return body.get("data")
        except Exception as e:
            log.warning("entity_resolver: GQL request failed: %s", e)
            return None

    async def _datahub_get(self, path: str) -> Optional[dict]:
        """GET from Datahub World API. Returns parsed JSON or None on error."""
        url = f"https://{self.datahub_host}{path}"
        try:
            resp = await self._http.get(url, timeout=8.0)
            if resp.status_code == 404:
                return None
            resp.raise_for_status()
            return resp.json()
        except Exception as e:
            log.warning("entity_resolver: datahub request failed %s: %s", path, e)
            return None

    # -----------------------------------------------------------------------
    # Pre-warm GameType cache
    # -----------------------------------------------------------------------

    async def prewarm_types(self) -> None:
        """Fetch all game types from Datahub at startup. Populates permanent type cache."""
        log.info("entity_resolver: pre-warming type cache (tenant=%s)…", self.tenant)
        offset = 0
        limit  = 500
        total  = 0
        while True:
            data = await self._datahub_get(f"/v2/types?limit={limit}&offset={offset}")
            if not data:
                break
            items = data if isinstance(data, list) else data.get("data") or data.get("items") or data.get("types") or []
            if not items:
                break
            for item in items:
                type_id = str(item.get("id", ""))
                if type_id:
                    self._types[type_id] = item
            total += len(items)
            if len(items) < limit:
                break
            offset += limit
        log.info("entity_resolver: type cache pre-warmed (%d types)", total)
        self._build_name_index()
        self._build_category_index()
        try:
            self.write_knowledge_file()
        except Exception as e:
            log.warning("entity_resolver: knowledge file write failed: %s", e)

    def _build_name_index(self) -> None:
        """Build lowercase name → [type_id] reverse index from _types cache."""
        index: dict[str, list[str]] = {}
        for type_id, record in self._types.items():
            name = record.get("name", "")
            if not name:
                continue
            key = name.lower()
            index.setdefault(key, []).append(type_id)
        self._name_index = index
        log.info("entity_resolver: name index built (%d entries)", len(index))

    def _build_category_index(self) -> None:
        """Build categoryName → [type_id] index from _types cache."""
        index: dict[str, list[str]] = {}
        for type_id, record in self._types.items():
            cat = record.get("categoryName") or "Unknown"
            index.setdefault(cat, []).append(type_id)
        self._category_index = index
        log.info("entity_resolver: category index built (%d categories)", len(index))

    def get_all_categories(self) -> dict[str, int]:
        """Return all known categoryNames and the count of types in each."""
        return {cat: len(ids) for cat, ids in self._category_index.items()}

    def get_types_for_category(self, category: str, max_results: int = 50) -> list[dict]:
        """Return up to max_results full type records for a given categoryName."""
        type_ids = self._category_index.get(category, [])[:max_results]
        return [
            self._types[tid]
            for tid in type_ids
            if tid in self._types
        ]

    def get_type_description(self, type_id) -> Optional[str]:
        """Return the description string for a type_id from the cache, or None."""
        record = self._types.get(str(type_id))
        if not record:
            return None
        return record.get("description") or None

    def get_knowledge_block(self, categories: list[str], max_chars: int = 1200) -> str:
        """
        Return a compact 'Name: description.' text block for the given categories.

        Used to auto-inject type knowledge into companion context so HUGINN knows
        what items, ships, and materials are without tool calls.
        """
        lines = []
        for cat in categories:
            type_ids = self._category_index.get(cat, [])
            cat_lines = []
            for tid in type_ids:
                rec = self._types.get(tid, {})
                name = rec.get("name", "")
                desc = (rec.get("description") or "").strip()
                # First sentence only for compactness
                if desc and "." in desc:
                    desc = desc.split(".")[0] + "."
                elif desc and len(desc) > 80:
                    desc = desc[:80] + "…"
                if name:
                    cat_lines.append(f"  {name}: {desc}" if desc else f"  {name}")
            if cat_lines:
                lines.append(f"[{cat}]")
                lines.extend(cat_lines)
        block = "\n".join(lines)
        return block[:max_chars]

    def write_knowledge_file(self, path: str = None) -> None:
        """
        Write all cached types grouped by category to a JSON file.
        Called once after prewarm as a persistent reference.
        """
        import json, os
        if path is None:
            path = f"data/type_knowledge_{self.tenant}.json"
        catalog: dict[str, list[dict]] = {}
        for cat, type_ids in self._category_index.items():
            catalog[cat] = [
                {
                    "id": tid,
                    "name": self._types[tid].get("name", ""),
                    "description": self._types[tid].get("description", ""),
                    "groupName": self._types[tid].get("groupName", ""),
                }
                for tid in type_ids if tid in self._types
            ]
        os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
        with open(path, "w") as f:
            json.dump(catalog, f, indent=2)
        log.info("entity_resolver: type knowledge written to %s (%d categories)", path, len(catalog))

    # -----------------------------------------------------------------------
    # GameType lookup
    # -----------------------------------------------------------------------

    async def get_type(self, type_id) -> Optional[dict]:
        """Fetch a game type by ID (str or int). Returns Datahub /v2/types/{id} dict."""
        key = str(type_id)
        cached = self._types.get(key)
        if cached is not None:
            return cached
        data = await self._datahub_get(f"/v2/types/{key}")
        if data:
            self._types[key] = data
        return data

    def search_types_by_name(self, query: str, max_results: int = 5) -> list[dict]:
        """
        Search game types by name. Returns up to max_results full Datahub records.

        Matches in priority order: exact → prefix → substring (all case-insensitive).
        Each result includes: type_id, name, description, groupName, categoryName,
        mass, volume, iconUrl.
        """
        q = query.lower().strip()
        if not q:
            return []

        exact:    list[str] = []
        prefix:   list[str] = []
        contains: list[str] = []

        for name_lower, type_ids in self._name_index.items():
            if name_lower == q:
                exact.extend(type_ids)
            elif name_lower.startswith(q):
                prefix.extend(type_ids)
            elif q in name_lower:
                contains.extend(type_ids)

        ordered = (exact + prefix + contains)[:max_results]
        results = []
        for type_id in ordered:
            record = self._types.get(type_id)
            if record:
                results.append({
                    "type_id":      type_id,
                    "name":         record.get("name", ""),
                    "description":  record.get("description", ""),
                    "groupName":    record.get("groupName", ""),
                    "categoryName": record.get("categoryName", ""),
                    "mass":         record.get("mass"),
                    "volume":       record.get("volume"),
                    "iconUrl":      record.get("iconUrl", ""),
                })
        return results

    # -----------------------------------------------------------------------
    # Assembly queries
    # -----------------------------------------------------------------------

    async def get_assembly(self, assembly_id: str) -> Optional[dict]:
        """Fetch a single assembly object from Sui. Returns enriched dict with assembly_type."""
        cached = self._cache_get(self._onchain, assembly_id, _ONCHAIN_TTL)
        if cached is not None:
            return cached

        data = await self._gql(GET_OBJECT_WITH_JSON, {"address": assembly_id})
        if not data:
            return None

        obj     = (data.get("object") or {})
        move_obj = (obj.get("asMoveObject") or {})
        contents = (move_obj.get("contents") or {})
        json_data = contents.get("json") or {}
        type_repr = (contents.get("type") or {}).get("repr", "")

        if not json_data:
            return None

        meta_name = (json_data.get("metadata") or {}).get("name") or ""
        raw_name  = json_data.get("name") or ""
        result = {
            **json_data,
            "sui_id":        assembly_id,
            "assembly_type": _classify_assembly_type(type_repr),
            "type_repr":     type_repr,
            "name":          meta_name or raw_name,
        }
        self._cache_set(self._onchain, assembly_id, result)
        return result

    async def get_assembly_full(self, assembly_id: str) -> Optional[dict]:
        """
        Fetch assembly + owner character + energy source + destination gate in one GraphQL call.

        Returns a flat dict:
        {
            "assembly":         {..., assembly_type, sui_id},
            "owner_character":  {...} or None,
            "energy_source":    {..., assembly_type} or None,
            "destination_gate": {..., assembly_type} or None,
        }
        """
        cache_key = f"full:{assembly_id}"
        cached = self._cache_get(self._onchain, cache_key, _ONCHAIN_TTL)
        if cached is not None:
            return cached

        data = await self._gql(
            GET_OBJECT_DYNAMICFIELD_CHARACTER_WITH_JSON,
            {
                "objectId":           assembly_id,
                "characterOwnerType": character_owner_cap_type(self.package_id),
            },
        )
        if not data:
            return None

        obj       = data.get("object") or {}
        move_obj  = obj.get("asMoveObject") or {}
        contents  = move_obj.get("contents") or {}
        json_data = contents.get("json") or {}
        type_repr = (contents.get("type") or {}).get("repr", "")

        if not json_data:
            return None

        meta_name = (json_data.get("metadata") or {}).get("name") or ""
        raw_name  = json_data.get("name") or ""
        assembly = {
            **json_data,
            "sui_id":        assembly_id,
            "assembly_type": _classify_assembly_type(type_repr),
            "type_repr":     type_repr,
            "name":          meta_name or raw_name,
        }

        def _dig(d, *keys):
            """Safely traverse nested dicts, treating None as {}."""
            for k in keys:
                d = (d or {}).get(k)
            return d

        # Owner character — path: extract.asAddress.asObject.asMoveObject.owner.address.objects.nodes[0].contents.authorizedObj.asAddress.asObject.asMoveObject.contents.json
        owner_character = None
        try:
            char_nodes = (
                _dig(contents, "extract", "asAddress", "asObject", "asMoveObject",
                     "owner", "address", "objects", "nodes")
                or []
            )
            if char_nodes:
                char_json = _dig(
                    char_nodes[0],
                    "contents", "authorizedObj", "asAddress", "asObject",
                    "asMoveObject", "contents", "json",
                )
                if char_json:
                    owner_character = char_json
        except Exception as e:
            log.warning("entity_resolver: character parse failed for %s: %s", assembly_id, e)

        # Energy source (NetworkNode)
        energy_source = None
        try:
            es_json = _dig(
                contents,
                "energySource", "asAddress", "asObject", "asMoveObject", "contents", "json",
            )
            if es_json:
                energy_source = {**es_json, "assembly_type": "NetworkNode"}
        except Exception as e:
            log.warning("entity_resolver: energy source parse failed for %s: %s", assembly_id, e)

        # Destination gate
        destination_gate = None
        try:
            dg_json = _dig(
                contents,
                "destinationGate", "asAddress", "asObject", "asMoveObject", "contents", "json",
            )
            if dg_json:
                destination_gate = {**dg_json, "assembly_type": "SmartGate"}
        except Exception as e:
            log.warning("entity_resolver: destination gate parse failed for %s: %s", assembly_id, e)

        result = {
            "assembly":         assembly,
            "owner_character":  owner_character,
            "energy_source":    energy_source,
            "destination_gate": destination_gate,
        }
        self._cache_set(self._onchain, cache_key, result)
        return result

    # -----------------------------------------------------------------------
    # Inventory
    # -----------------------------------------------------------------------

    async def get_inventory(self, assembly_id: str) -> Optional[dict]:
        """
        Fetch SSU inventory via dynamic fields. Returns None if not a SSU or not found.

        Items are resolved against the type cache (pre-warmed at startup).
        """
        cache_key = f"inv:{assembly_id}"
        cached = self._cache_get(self._onchain, cache_key, _ONCHAIN_TTL)
        if cached is not None:
            return cached

        data = await self._gql(GET_OBJECT_WITH_DYNAMIC_FIELDS, {"objectId": assembly_id})
        if not data:
            return None

        obj      = data.get("object") or {}
        move_obj = obj.get("asMoveObject") or {}
        contents = move_obj.get("contents") or {}
        json_data = contents.get("json") or {}
        dyn_fields = (move_obj.get("dynamicFields") or {}).get("nodes", [])

        # Validate it's a SSU via type repr
        assembly = await self.get_assembly(assembly_id)
        if assembly and assembly.get("assembly_type") != "SmartStorageUnit":
            return None

        # Each dynamic field is a Field<ID, Inventory> container.
        # Structure: contents.json = {id, name, value: {max_capacity, used_capacity,
        #   items: {contents: [{key: type_id_str, value: {type_id, quantity, volume, ...}}]}}}
        items: list[dict] = []
        total_max_cap_raw: int = 0
        total_used_cap_raw: int = 0

        for node in dyn_fields:
            try:
                container_json = (node.get("contents") or {}).get("json") or {}
                inv_value = container_json.get("value") or {}

                total_max_cap_raw  += _safe_int(inv_value.get("max_capacity"))
                total_used_cap_raw += _safe_int(inv_value.get("used_capacity"))

                for entry in (inv_value.get("items") or {}).get("contents") or []:
                    try:
                        type_id = str(entry.get("key") or "")
                        item_val = entry.get("value") or {}
                        qty = _safe_int(item_val.get("quantity"))
                        vol_raw = _safe_int(item_val.get("volume"))  # per-unit, game units

                        if not type_id or qty <= 0:
                            continue

                        # Resolve type name from pre-warmed cache
                        game_type = self._types.get(type_id) or {}
                        type_name = game_type.get("name") or f"[TYPE:{type_id}]"
                        category  = game_type.get("categoryName") or ""
                        # Use game type volume if available; fall back to on-chain volume (1/100 m³ unit)
                        vol_unit = float(game_type.get("volume") or (vol_raw / 100.0))

                        items.append({
                            "type_id":         type_id,
                            "type_name":       type_name,
                            "category_name":   category,
                            "quantity":        qty,
                            "volume_per_unit": vol_unit,
                            "total_volume":    round(vol_unit * qty, 4),
                        })
                    except Exception as e:
                        log.warning("entity_resolver: inventory entry parse error: %s", e)
            except Exception as e:
                log.warning("entity_resolver: inventory container parse error: %s", e)

        # Capacity: sum across all containers; raw unit = 1/100 m³
        max_cap: Optional[float] = total_max_cap_raw / 100.0 if total_max_cap_raw else None
        used = sum(i["total_volume"] for i in items)
        cap_pct = round(used * 100 / max_cap, 2) if max_cap and max_cap > 0 else None

        result = {
            "assembly_id":      assembly_id,
            "assembly_name":    (json_data.get("metadata") or {}).get("name") or json_data.get("name") or (assembly or {}).get("name") or assembly_id[:10],
            "used_capacity":    round(used, 4),
            "max_capacity":     max_cap,
            "capacity_percent": cap_pct,
            "items":            sorted(items, key=lambda x: x["quantity"], reverse=True),
        }
        self._cache_set(self._onchain, cache_key, result)
        return result

    # -----------------------------------------------------------------------
    # Network topology
    # -----------------------------------------------------------------------

    async def get_network(self, energy_source_id: str) -> Optional[dict]:
        """
        Fetch NetworkNode and all connected assemblies.

        Caps at 20 connected assemblies fetched in parallel.
        """
        cache_key = f"net:{energy_source_id}"
        cached = self._cache_get(self._onchain, cache_key, _ONCHAIN_TTL)
        if cached is not None:
            return cached

        node_data = await self.get_assembly(energy_source_id)
        if not node_data:
            return None

        # Resolve connected assemblies in parallel (cap 20)
        connected_ids: list = node_data.get("connected_assembly_ids") or []
        connected_ids = [str(c) for c in connected_ids if c][:20]

        results = await asyncio.gather(
            *[self.get_assembly(aid) for aid in connected_ids],
            return_exceptions=True,
        )

        connected = []
        failed    = []
        for aid, res in zip(connected_ids, results):
            if isinstance(res, Exception):
                log.warning("entity_resolver: failed to fetch connected assembly %s: %s", aid, res)
                failed.append(aid)
            elif res:
                atype = res.get("assembly_type", "Unknown")
                display_type = atype
                type_data = await self.get_type(res.get("type_id"))
                if isinstance(type_data, dict):
                    if atype in ("Unknown", "Assembly"):
                        display_type = type_data.get("name") or "Assembly"
                    # For all types: fall back to type name before hex address
                    display_name = res.get("name") or type_data.get("name") or aid[:10]
                    group_name    = type_data.get("groupName") or ""
                    category_name = type_data.get("categoryName") or ""
                else:
                    display_name  = res.get("name") or aid[:10]
                    group_name    = ""
                    category_name = ""
                connected.append({
                    "id":            aid,
                    "name":          display_name,
                    "assembly_type": display_type,
                    "type_repr":     res.get("type_repr", ""),
                    "status":        _parse_status(res.get("status")),
                    "type_id":       str(res.get("type_id") or ""),
                    "key":           res.get("key"),
                    "group_name":    group_name,
                    "category_name": category_name,
                })

        result = {
            "id":                   energy_source_id,
            "name":                 node_data.get("name") or energy_source_id[:10],
            "status":               _parse_status(node_data.get("status")),
            "fuel":                 _extract_fuel(node_data),
            "energy":               _extract_energy(node_data),
            "connected_assemblies": connected,
            "truncated":            len(connected_ids) < len(node_data.get("connected_assembly_ids") or []),
            "failed_ids":           failed,
        }
        self._cache_set(self._onchain, cache_key, result)
        return result

    # -----------------------------------------------------------------------
    # All network nodes
    # -----------------------------------------------------------------------

    async def get_all_network_nodes(self, wallet: Optional[str] = None) -> list[dict]:
        """
        Return a summary list of every NetworkNode on-chain for this tenant.

        Each entry: id, name, status, fuel_percent, hours_remaining,
                    is_burning, connected_count, system_name.

        If wallet is provided, only nodes owned by that address are returned.
        This uses a direct ownership query to avoid iterating all nodes.

        system_name is resolved by cross-referencing connected_assembly_ids
        against saved structure profiles (first match with a non-empty system_name).

        Full list is cached for 60 seconds; wallet filter applied after.
        """
        cache_key = "all_network_nodes"
        cached = self._cache_get(self._singleton, cache_key, 60.0)

        if wallet:
            # Get IDs owned by this wallet, then cross-reference with full list
            move_type = f"{self.package_id}::network_node::NetworkNode"
            owned_data = await self._gql(
                GET_OWNED_OBJECTS_BY_TYPE,
                {"owner": wallet, "object_type": move_type},
            )
            owned_ids: set[str] = set()
            for node in (owned_data or {}).get("address", {}).get("objects", {}).get("nodes") or []:
                addr = node.get("address") or ""
                if addr:
                    owned_ids.add(addr.lower())

            all_nodes = cached if cached is not None else await self._fetch_all_network_nodes()
            if cached is None:
                self._cache_set(self._singleton, cache_key, all_nodes)
            return [n for n in all_nodes if n["id"].lower() in owned_ids]

        if cached is not None:
            return cached

        nodes = await self._fetch_all_network_nodes()
        self._cache_set(self._singleton, cache_key, nodes)
        return nodes

    async def _fetch_all_network_nodes(self) -> list[dict]:
        """Fetch all NetworkNodes from chain. Called by get_all_network_nodes."""
        move_type = f"{self.package_id}::network_node::NetworkNode"
        nodes: list[dict] = []
        cursor = None

        while True:
            data = await self._gql(
                GET_OBJECTS_BY_TYPE,
                {"object_type": move_type, "first": 50, "after": cursor},
            )
            if not data:
                break
            page = data.get("objects") or {}
            for node_obj in page.get("nodes") or []:
                address = node_obj.get("address") or ""
                move_obj = node_obj.get("asMoveObject") or {}
                contents = move_obj.get("contents") or {}
                json_data = contents.get("json") or {}

                raw_fuel   = json_data.get("fuel") or {}
                qty        = _safe_int(raw_fuel.get("quantity"))
                cap        = _safe_int(raw_fuel.get("max_capacity"))
                unit_vol   = _safe_int(raw_fuel.get("unit_volume"))
                burn_ms    = _safe_int(raw_fuel.get("burn_rate_in_ms"))
                is_burning = bool(raw_fuel.get("is_burning", False))

                eff_max  = cap // unit_vol if unit_vol > 0 else cap
                fuel_pct = round(qty * 100.0 / eff_max, 1) if eff_max > 0 else 0.0
                if is_burning and burn_ms > 0:
                    units_per_hr    = _MS_PER_HOUR / burn_ms
                    hours_remaining = qty / units_per_hr if units_per_hr > 0 else 0.0
                else:
                    hours_remaining = 0.0

                connected_ids: list[str] = [
                    str(c) for c in (json_data.get("connected_assembly_ids") or []) if c
                ]

                # Resolve system_name from saved structure profiles
                system_name = ""
                if connected_ids:
                    from src.structure_persistence import load_profile
                    for aid in connected_ids:
                        try:
                            profile = load_profile(aid)
                            if profile and profile.system_name:
                                system_name = profile.system_name
                                break
                        except Exception:
                            pass

                name = json_data.get("name") or address[:10]
                status_raw = json_data.get("online_status") or json_data.get("status") or {}
                status = _parse_status(status_raw)

                nodes.append({
                    "id":              address,
                    "name":            name,
                    "status":          status,
                    "fuel_percent":    fuel_pct,
                    "hours_remaining": round(hours_remaining, 1),
                    "is_burning":      is_burning,
                    "connected_count": len(connected_ids),
                    "system_name":     system_name,
                })

            page_info = page.get("pageInfo") or {}
            if not page_info.get("hasNextPage"):
                break
            cursor = page_info.get("endCursor")

        nodes.sort(key=lambda n: n["connected_count"], reverse=True)
        return nodes

    # -----------------------------------------------------------------------
    # Gate destination
    # -----------------------------------------------------------------------

    async def get_gate_destination(self, linked_gate_id: str) -> Optional[dict]:
        """Fetch a destination gate assembly. Returns None if not found."""
        return await self.get_assembly(linked_gate_id)

    # -----------------------------------------------------------------------
    # Character / wallet queries
    # -----------------------------------------------------------------------

    async def get_character(self, wallet_address: str) -> Optional[dict]:
        """
        Resolve wallet address → Character JSON via PlayerProfile chain.

        Returns character JSON dict or None.
        """
        cache_key = f"char:{wallet_address}"
        cached = self._cache_get(self._onchain, cache_key, _ONCHAIN_TTL)
        if cached is not None:
            return cached

        data = await self._gql(
            GET_WALLET_CHARACTERS,
            {
                "owner": wallet_address,
                "characterPlayerProfileType": character_player_profile_type(self.package_id),
            },
        )
        if not data:
            return None

        try:
            nodes = (
                data
                .get("address", {})
                .get("objects", {})
                .get("nodes", [])
            )
            if not nodes:
                return None
            char_json = (
                nodes[0]
                .get("contents", {})
                .get("extract", {})
                .get("asAddress", {})
                .get("asObject", {})
                .get("asMoveObject", {})
                .get("contents", {})
                .get("json")
            )
            if char_json:
                self._cache_set(self._onchain, cache_key, char_json)
            return char_json
        except Exception as e:
            log.warning("entity_resolver: character resolve failed for %s: %s", wallet_address, e)
            return None

    # -----------------------------------------------------------------------
    # Galaxy (synchronous — no cache needed)
    # -----------------------------------------------------------------------

    def get_system(self, id_or_name) -> Optional[dict]:
        """Synchronous galaxy DB lookup. Returns SolarSystems row dict or None."""
        from src.galaxy_db import galaxy_db
        return galaxy_db.get_system(id_or_name)

    # -----------------------------------------------------------------------
    # Singleton configs
    # -----------------------------------------------------------------------

    async def get_energy_config(self) -> dict[str, int]:
        """
        Fetch EnergyConfig: {type_id_str -> energy_usage_kw}.
        Cached 5 minutes.
        """
        key = f"energy_config:{self.package_id}"
        cached = self._cache_get(self._singleton, key, _SINGLETON_TTL)
        if cached is not None:
            return cached

        data = await self._gql(
            GET_SINGLETON_CONFIG_OBJECT_BY_TYPE,
            {
                "object_type": energy_config_type(self.package_id),
                "table_name":  ENERGY_CONFIG_TABLE,
            },
        )
        result = _parse_config_nodes(data)
        self._cache_set(self._singleton, key, result)
        return result

    async def get_fuel_config(self) -> dict[str, int]:
        """
        Fetch FuelConfig: {type_id_str -> burn_time_per_unit_ms}.
        Cached 5 minutes.
        """
        key = f"fuel_config:{self.package_id}"
        cached = self._cache_get(self._singleton, key, _SINGLETON_TTL)
        if cached is not None:
            return cached

        data = await self._gql(
            GET_SINGLETON_CONFIG_OBJECT_BY_TYPE,
            {
                "object_type": fuel_config_type(self.package_id),
                "table_name":  FUEL_CONFIG_TABLE,
            },
        )
        result = _parse_config_nodes(data)
        self._cache_set(self._singleton, key, result)
        return result

    # -----------------------------------------------------------------------
    # Fuel state calculation (pure)
    # -----------------------------------------------------------------------

    @staticmethod
    def compute_fuel_state(
        node_data: dict,
        burn_time_per_unit_ms: float = 0.0,
        efficiency_pct: float = 100.0,
    ) -> dict:
        """
        Compute fuel state from NetworkNode data.

        Args:
            node_data:              NetworkNode JSON (from get_assembly or get_network)
            burn_time_per_unit_ms:  raw ms per fuel unit. If 0, falls back to
                                    node_data["fuel"]["burn_rate_in_ms"] (on-chain value).
            efficiency_pct:         fuel efficiency % (from EnergyConfig). Default 100.

        Returns dict:
            fuel_quantity, max_capacity, fuel_percent,
            burn_rate_units_per_hr, hours_remaining, is_burning
        """
        fuel     = _extract_fuel(node_data)
        qty      = _safe_int(fuel.get("quantity"))
        cap      = _safe_int(fuel.get("max_capacity"))
        unit_vol = _safe_int(fuel.get("unit_volume"))
        is_burning_raw = fuel.get("is_burning", False)

        eff_max  = cap // unit_vol if unit_vol > 0 else cap
        fuel_pct = round(qty * 100.0 / eff_max, 2) if eff_max > 0 else 0.0

        # Use on-chain burn_rate_in_ms as fallback
        raw_ms = burn_time_per_unit_ms or _safe_int(fuel.get("burn_rate_in_ms"))

        if efficiency_pct > 0 and raw_ms > 0 and is_burning_raw:
            adjusted_ms  = raw_ms * (efficiency_pct / 100.0)
            units_per_hr = _MS_PER_HOUR / adjusted_ms
        else:
            units_per_hr = 0.0

        is_burning      = bool(is_burning_raw) and units_per_hr > 0
        hours_remaining = (qty / units_per_hr) if (is_burning and units_per_hr > 0) else 0.0

        return {
            "fuel_quantity":          qty,
            "max_capacity":           cap,
            "fuel_percent":           fuel_pct,
            "burn_rate_units_per_hr": round(units_per_hr, 4),
            "hours_remaining":        round(hours_remaining, 2),
            "is_burning":             is_burning,
        }


# ---------------------------------------------------------------------------
# Shared helpers for field extraction
# ---------------------------------------------------------------------------

def _parse_status(status_val, _depth: int = 0) -> str:
    """Extract status string from various representations (handles nesting up to 3 levels)."""
    if status_val is None:
        return "UNKNOWN"
    if isinstance(status_val, str):
        return status_val
    if isinstance(status_val, dict) and _depth < 3:
        # Try direct string keys first
        for key in ("@variant", "variant", "name"):
            v = status_val.get(key)
            if isinstance(v, str):
                return v
        # Then recurse for nested dicts (e.g. {"status": {"@variant": "ONLINE"}})
        for key in ("status",):
            v = status_val.get(key)
            if v is not None:
                return _parse_status(v, _depth + 1)
    return str(status_val)


def _extract_fuel(node_data: dict) -> dict:
    """Extract fuel sub-dict from NetworkNode JSON. Handles nested or flat."""
    fuel = node_data.get("fuel") or {}
    if isinstance(fuel, dict):
        # GraphQL JSON may flatten or nest — handle both
        return fuel.get("fields") or fuel
    return {}


def _extract_energy(node_data: dict) -> dict:
    """Extract energy fields from NetworkNode JSON."""
    current = _safe_int(node_data.get("current_energy_production"))
    maximum = _safe_int(node_data.get("max_energy_production"))
    reserved = _safe_int(node_data.get("total_reserved_energy"))
    pct = round(current * 100.0 / maximum, 2) if maximum > 0 else 0.0
    return {
        "current_energy_production": current,
        "max_energy_production":     maximum,
        "total_reserved_energy":     reserved,
        "energy_percent":            pct,
    }


def _parse_config_nodes(data: Optional[dict]) -> dict[str, int]:
    """
    Parse GET_SINGLETON_CONFIG_OBJECT_BY_TYPE response.

    Response path:
      data.objects.nodes[0].asMoveObject.contents.extract.extract
          .asAddress.addressAt.dynamicFields.nodes
      Each node: {key: {json: type_id_str}, value: {json: value_str}}
    """
    if not data:
        return {}
    try:
        nodes = (
            data
            .get("objects", {})
            .get("nodes", [{}])[0]
            .get("asMoveObject", {})
            .get("contents", {})
            .get("extract", {})
            .get("extract", {})
            .get("asAddress", {})
            .get("addressAt", {})
            .get("dynamicFields", {})
            .get("nodes", [])
        )
        result: dict[str, int] = {}
        for node in nodes:
            k = (node.get("key") or {}).get("json")
            v = (node.get("value") or {}).get("json")
            if k is not None and v is not None:
                result[str(k)] = _safe_int(v)
        return result
    except Exception as e:
        log.warning("entity_resolver: config parse failed: %s", e)
        return {}


# ---------------------------------------------------------------------------
# Resolver registry (one instance per tenant, injected in lifespan)
# ---------------------------------------------------------------------------

_resolvers: dict[str, EntityResolver] = {}
_default_tenant: str = "utopia"


def get_resolver_for_tenant(tenant: str) -> EntityResolver:
    """Return the EntityResolver for the given tenant.

    Falls back to the default tenant if the requested tenant is unknown.
    Raises RuntimeError if no resolvers have been registered yet (lifespan not run).
    """
    if not _resolvers:
        raise RuntimeError("EntityResolver not initialized — lifespan not run")
    if tenant in _resolvers:
        return _resolvers[tenant]
    log.warning("entity_resolver: unknown tenant %r, falling back to %s", tenant, _default_tenant)
    return _resolvers[_default_tenant]


def get_entity_resolver() -> EntityResolver:
    """Backward-compatible: returns the default-tenant resolver."""
    return get_resolver_for_tenant(_default_tenant)
