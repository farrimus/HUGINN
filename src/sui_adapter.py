"""
src/sui_adapter.py

Sui blockchain adapter — GraphQL queries, object parsing, config singletons.

SuiAdapter(DatahubTypeCatalog) owns all on-chain data access:
  - Assembly objects (single + full with owner/energy/gate)
  - Inventory (SSU dynamic fields)
  - Network topology (NetworkNode + connected assemblies)
  - Character / wallet resolution
  - Energy and fuel config singletons

Tenant configuration and GraphQL query strings are defined in this module
(verbatim from @evefrontier/dapp-kit/graphql/queries.ts v0.0.18).

Cache tiers:
  on-chain objects  — 30s TTL   (key: Sui object ID)
  singletons        — 5min TTL  (key: type string)
"""

import asyncio
import logging
import os
import time
from typing import Any, Optional

from src.datahub_types import DatahubTypeCatalog
from src.utils import classify_assembly_type as _classify_assembly_type
from src.utils import parse_status as _parse_status

log = logging.getLogger(__name__)

_ONCHAIN_TTL   = 30.0    # seconds
_SINGLETON_TTL = 300.0   # seconds
_MS_PER_HOUR   = 3_600_000.0


# ---------------------------------------------------------------------------
# Tenant Configuration
# (from @evefrontier/dapp-kit/utils/constants.ts TENANT_CONFIG v0.0.18)
# ---------------------------------------------------------------------------

GRAPHQL_ENDPOINT = "https://graphql.testnet.sui.io/graphql"

TENANT_CONFIG: dict[str, dict] = {
    "stillness": {
        "package_id":   "0x28b497559d65ab320d9da4613bf2498d5946b2c0ae3597ccfda3072ce127448c",
        "datahub_host": "world-api-stillness.live.tech.evefrontier.com",
    },
    "utopia": {
        "package_id":   "0xd12a70c74c1e759445d6f209b01d43d860e97fcf2ef72ccbbd00afd828043f75",
        "datahub_host": "world-api-utopia.uat.pub.evefrontier.com",
    },
    "nebula": {
        "package_id":   "0x353988e063b4683580e3603dbe9e91fefd8f6a06263a646d43fd3a2f3ef6b8c1",
        "datahub_host": "world-api-nebula.test.evefrontier.tech",
    },
}

DEFAULT_TENANT = os.getenv("DEPLOYMENT_ENV", "utopia")

# Table names for config singleton queries
ENERGY_CONFIG_TABLE = "assembly_energy"
FUEL_CONFIG_TABLE   = "fuel_efficiency"


# ---------------------------------------------------------------------------
# Type string builders
# (mirror @evefrontier/dapp-kit/utils/constants.ts helper functions)
# ---------------------------------------------------------------------------

def character_player_profile_type(pkg: str) -> str:
    return f"{pkg}::character::PlayerProfile"


def character_owner_cap_type(pkg: str) -> str:
    return f"{pkg}::access::OwnerCap<{pkg}::character::Character>"


def energy_config_type(pkg: str) -> str:
    return f"{pkg}::energy::EnergyConfig"


def fuel_config_type(pkg: str) -> str:
    return f"{pkg}::fuel::FuelConfig"


# ---------------------------------------------------------------------------
# GraphQL query string constants
# (verbatim from @evefrontier/dapp-kit/graphql/queries.ts)
# ---------------------------------------------------------------------------

_GET_OBJECT_WITH_JSON = '''
query GetObjectWithJson($address: SuiAddress!) {
    object(address: $address) {
      address
      version
      digest
      asMoveObject {
        contents {
          type {
            repr
          }
          json
          bcs
        }
      }
    }
  }
'''

_GET_OBJECT_WITH_DYNAMIC_FIELDS = '''
query GetObjectWithDynamicFields($objectId: SuiAddress!) {
    object(address: $objectId) {
      asMoveObject {
        contents {
          json
        }
        dynamicFields {
          nodes {
            contents {
              json
              type {
                layout
              }
            }
            name {
              json
              type {
                repr
              }
            }
          }
        }
      }
    }
  }
'''

_GET_OBJECT_DYNAMICFIELD_CHARACTER_WITH_JSON = '''
query GetObjectOwnerCharacterOwnerAndInventory(
  $objectId: SuiAddress!
  $characterOwnerType: String!
) {
  object(address: $objectId) {
    asMoveObject {
      contents {
        json
        type { repr }
        bcs
        extract(path: "owner_cap_id") {
          asAddress {
            asObject {
              asMoveObject {
                owner {
                  ... on AddressOwner {
                    address {
                      objects(filter: { type: $characterOwnerType }, last: 1) {
                        nodes {
                          contents {
                            authorizedObj: extract(path: "authorized_object_id") {
                              asAddress {
                                asObject {
                                  asMoveObject {
                                    contents { bcs json }
                                  }
                                }
                              }
                            }
                          }
                        }
                      }
                    }
                  }
                }
              }
            }
          }
        }
       energySource: extract(path: "energy_source_id") {
          asAddress {
            asObject {
              asMoveObject {
                contents { bcs json }
              }
            }
          }
        }
        destinationGate: extract(path: "linked_gate_id") {
          asAddress {
            asObject {
              asMoveObject {
                contents { bcs json }
              }
            }
          }
        }
      }
      dynamicFields {
          nodes {
            contents {
              json
              extract(path: "id") {
              asAddress {
                asObject {
                    asMoveObject {
                    contents { bcs json }
                    }
                }
                }
              }
            }
            name {
              json
              type {
                repr
              }
            }
          }
        }
    }
  }
}
'''

_GET_WALLET_CHARACTERS = '''
query GetWalletCharacters($owner: SuiAddress!, $characterPlayerProfileType: String!) {
    address(
        address: $owner
    ) {
        objects(
            last: 1
            filter: {
                type: $characterPlayerProfileType
            }
        ) {
            nodes {
                contents {
                    extract(path: "character_id") {
                        asAddress {
                            asObject {
                                asMoveObject {
                                    contents {
                                        type {
                                            repr
                                        }
                                        json
                                    }
                                }
                            }
                        }
                    }
                }
            }
        }
    }
}
'''

_GET_SINGLETON_CONFIG_OBJECT_BY_TYPE = '''
query GetSingletonConfigObjectByType($object_type: String!, $table_name: String!) {
    objects(filter: { type: $object_type }, first: 1) {
        nodes {
            address
            asMoveObject {
                contents {
                    extract(path: $table_name) {
                        extract(path: "id") {
                            asAddress {
                                addressAt {
                                    dynamicFields {
                                        pageInfo {
                                            hasNextPage
                                            endCursor
                                        }
                                        nodes {
                                            key: name {
                                                json
                                            }
                                            value: value {
                                                ... on MoveValue {
                                                    json
                                                }
                                            }
                                        }
                                    }
                                }
                            }
                        }
                    }
                }
            }
        }
    }
}
'''

_GET_OBJECTS_BY_TYPE = '''
query GetObjectsByType($object_type: String, $first: Int, $after: String) {
    objects(
      filter: {
        type: $object_type
      }
      first: $first
      after: $after
    ) {
      nodes {
        address
        version
        asMoveObject {
          contents {
            json
            type {
              repr
            }
          }
        }
      }
      pageInfo {
        hasNextPage
        endCursor
      }
    }
  }
'''

_GET_OWNED_OBJECTS_BY_TYPE = '''
query GetOwnedObjectsByType($owner: SuiAddress!, $object_type: String) {
    address(address: $owner) {
      objects(
        filter: {
          type: $object_type
        }
      ) {
        nodes {
          address
        }
      }
    }
  }
'''


# ---------------------------------------------------------------------------
# Shared field-extraction helpers
# ---------------------------------------------------------------------------

def _safe_int(val, fallback: int = 0) -> int:
    """Convert u64 string (or int) to int, returning fallback on failure."""
    if val is None:
        return fallback
    try:
        return int(val)
    except (ValueError, TypeError):
        log.warning("sui_adapter: could not convert %r to int", val)
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


def _extract_fuel(node_data: dict) -> dict:
    """Extract fuel sub-dict from NetworkNode JSON. Handles nested or flat."""
    fuel = node_data.get("fuel") or {}
    if isinstance(fuel, dict):
        return fuel.get("fields") or fuel
    return {}


def _extract_energy(node_data: dict) -> dict:
    """Extract energy fields from NetworkNode JSON."""
    current  = _safe_int(node_data.get("current_energy_production"))
    maximum  = _safe_int(node_data.get("max_energy_production"))
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
        log.warning("sui_adapter: config parse failed: %s", e)
        return {}


# ---------------------------------------------------------------------------
# SuiAdapter
# ---------------------------------------------------------------------------

class SuiAdapter(DatahubTypeCatalog):
    """
    On-chain data access layer. Inherits DatahubTypeCatalog for type metadata.

    Instantiated once per tenant at server startup (main.py lifespan).
    Injected via get_entity_resolver() / get_resolver_for_tenant().
    """

    def __init__(self, tenant: str = "stillness") -> None:
        if tenant not in TENANT_CONFIG:
            raise ValueError(f"Unknown tenant: {tenant}. Known: {list(TENANT_CONFIG.keys())}")
        cfg = TENANT_CONFIG[tenant]
        super().__init__(datahub_host=cfg["datahub_host"])
        self.tenant      = tenant
        self.package_id  = cfg["package_id"]
        self.graphql_url = GRAPHQL_ENDPOINT
        # TTL caches: key -> (data, timestamp)
        self._onchain:   dict[str, tuple[Any, float]] = {}
        self._singleton: dict[str, tuple[Any, float]] = {}

    # -----------------------------------------------------------------------
    # Cache helpers
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
    # GraphQL helper
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
                log.warning("sui_adapter: GQL errors: %s", body["errors"])
            return body.get("data")
        except Exception as e:
            log.warning("sui_adapter: GQL request failed: %s", e)
            return None

    # -----------------------------------------------------------------------
    # Assembly queries
    # -----------------------------------------------------------------------

    async def get_assembly(self, assembly_id: str) -> Optional[dict]:
        """Fetch a single assembly object from Sui. Returns enriched dict with assembly_type."""
        cached = self._cache_get(self._onchain, assembly_id, _ONCHAIN_TTL)
        if cached is not None:
            return cached

        data = await self._gql(_GET_OBJECT_WITH_JSON, {"address": assembly_id})
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

        Returns:
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
            _GET_OBJECT_DYNAMICFIELD_CHARACTER_WITH_JSON,
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
            for k in keys:
                d = (d or {}).get(k)
            return d

        # Owner character
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
            log.warning("sui_adapter: character parse failed for %s: %s", assembly_id, e)

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
            log.warning("sui_adapter: energy source parse failed for %s: %s", assembly_id, e)

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
            log.warning("sui_adapter: destination gate parse failed for %s: %s", assembly_id, e)

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

        data = await self._gql(_GET_OBJECT_WITH_DYNAMIC_FIELDS, {"objectId": assembly_id})
        if not data:
            return None

        obj        = data.get("object") or {}
        move_obj   = obj.get("asMoveObject") or {}
        contents   = move_obj.get("contents") or {}
        json_data  = contents.get("json") or {}
        dyn_fields = (move_obj.get("dynamicFields") or {}).get("nodes", [])

        # Validate it's a SSU via type repr
        assembly = await self.get_assembly(assembly_id)
        if assembly and assembly.get("assembly_type") != "SmartStorageUnit":
            return None

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
                        qty     = _safe_int(item_val.get("quantity"))
                        vol_raw = _safe_int(item_val.get("volume"))

                        if not type_id or qty <= 0:
                            continue

                        game_type = self._types.get(type_id) or {}
                        type_name = game_type.get("name") or f"[TYPE:{type_id}]"
                        category  = game_type.get("categoryName") or ""
                        vol_unit  = float(game_type.get("volume") or (vol_raw / 100.0))

                        items.append({
                            "type_id":         type_id,
                            "type_name":       type_name,
                            "category_name":   category,
                            "quantity":        qty,
                            "volume_per_unit": vol_unit,
                            "total_volume":    round(vol_unit * qty, 4),
                        })
                    except Exception as e:
                        log.warning("sui_adapter: inventory entry parse error: %s", e)
            except Exception as e:
                log.warning("sui_adapter: inventory container parse error: %s", e)

        max_cap: Optional[float] = total_max_cap_raw / 100.0 if total_max_cap_raw else None
        used    = sum(i["total_volume"] for i in items)
        cap_pct = round(used * 100 / max_cap, 2) if max_cap and max_cap > 0 else None

        result = {
            "assembly_id":      assembly_id,
            "assembly_name":    (
                (json_data.get("metadata") or {}).get("name")
                or json_data.get("name")
                or (assembly or {}).get("name")
                or assembly_id[:10]
            ),
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
                log.warning("sui_adapter: failed to fetch connected assembly %s: %s", aid, res)
                failed.append(aid)
            elif res:
                atype = res.get("assembly_type", "Unknown")
                display_type = atype
                type_data = await self.get_type(res.get("type_id"))
                if isinstance(type_data, dict):
                    if atype in ("Unknown", "Assembly"):
                        display_type = type_data.get("name") or "Assembly"
                    display_name  = res.get("name") or type_data.get("name") or aid[:10]
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

    async def get_all_network_nodes(self, wallet: Optional[str] = None) -> list[dict]:
        """
        Return a summary list of every NetworkNode on-chain for this tenant.

        Each entry: id, name, status, fuel_percent, hours_remaining,
                    is_burning, connected_count, system_name.

        If wallet is provided, only nodes owned by that address are returned.
        Full list is cached for 60 seconds; wallet filter applied after.
        """
        cache_key = "all_network_nodes"
        cached = self._cache_get(self._singleton, cache_key, 60.0)

        if wallet:
            move_type  = f"{self.package_id}::network_node::NetworkNode"
            owned_data = await self._gql(
                _GET_OWNED_OBJECTS_BY_TYPE,
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
                _GET_OBJECTS_BY_TYPE,
                {"object_type": move_type, "first": 50, "after": cursor},
            )
            if not data:
                break
            page = data.get("objects") or {}
            for node_obj in page.get("nodes") or []:
                address  = node_obj.get("address") or ""
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

                name       = json_data.get("name") or address[:10]
                status_raw = json_data.get("online_status") or json_data.get("status") or {}
                status     = _parse_status(status_raw)

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
            _GET_WALLET_CHARACTERS,
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
            log.warning("sui_adapter: character resolve failed for %s: %s", wallet_address, e)
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
        """Fetch EnergyConfig: {type_id_str -> energy_usage_kw}. Cached 5 minutes."""
        key    = f"energy_config:{self.package_id}"
        cached = self._cache_get(self._singleton, key, _SINGLETON_TTL)
        if cached is not None:
            return cached

        data = await self._gql(
            _GET_SINGLETON_CONFIG_OBJECT_BY_TYPE,
            {
                "object_type": energy_config_type(self.package_id),
                "table_name":  ENERGY_CONFIG_TABLE,
            },
        )
        result = _parse_config_nodes(data)
        self._cache_set(self._singleton, key, result)
        return result

    async def get_fuel_config(self) -> dict[str, int]:
        """Fetch FuelConfig: {type_id_str -> burn_time_per_unit_ms}. Cached 5 minutes."""
        key    = f"fuel_config:{self.package_id}"
        cached = self._cache_get(self._singleton, key, _SINGLETON_TTL)
        if cached is not None:
            return cached

        data = await self._gql(
            _GET_SINGLETON_CONFIG_OBJECT_BY_TYPE,
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
        fuel           = _extract_fuel(node_data)
        qty            = _safe_int(fuel.get("quantity"))
        cap            = _safe_int(fuel.get("max_capacity"))
        unit_vol       = _safe_int(fuel.get("unit_volume"))
        is_burning_raw = fuel.get("is_burning", False)

        eff_max  = cap // unit_vol if unit_vol > 0 else cap
        fuel_pct = round(qty * 100.0 / eff_max, 2) if eff_max > 0 else 0.0

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
