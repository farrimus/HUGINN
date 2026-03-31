# EVE Frontier — Entity Graph & Schema Linking

**Status:** Active research document. Updated 2026-03-27 after full DApp Kit source audit.
**Purpose:** Define the full entity graph, cross-references, and the traversal system that would make the companion AI situationally aware and the UI navigable.

---

## The Core Idea

EVE Frontier's data model is a graph. Every meaningful object in the game — a structure, a solar system, a character, an item type, a gate — has an identifier. Every identifier is a link to another object. The game client knows this: right-click any item and it opens an info window. That window has links. Every link opens another window.

The in-lore AI companion (HUGINN) should work the same way. Given a structure, it should be able to follow links — to the network this structure belongs to, to connected structures, to their inventories, to the solar systems those gates connect, to the killmail history of those systems. Not because someone asked. Because that is what a structure intelligence that has existed inside these walls would know.

The current companion knows almost nothing. It has an ID and a name. This document is about closing that gap.

---

## The Graph

Every node is an entity. Every edge is a field that references another entity.

```
Character (wallet address)
│
├── PlayerProfile ────────────────→ Character object (character_id, name, tribeId)
│     └── OwnerCap[] ────────────→ Assembly (authorized_object_id per cap)
│
└── CharacterInfo
      ├── name, tribeId
      ├── id (Sui object ID)
      └── characterId (game integer)


Assembly  (SSU / Gate / Turret / NetworkNode / Manufacturing / Refinery)
│
├── type_id ──────────────────────────→ GameType (Datahub API)
│                                         name, description, groupName, categoryName
│                                         mass, volume, iconUrl
│
├── key.item_id ──────────────────────→ game instance ID (u64, unique per object)
├── key.tenant ───────────────────────→ "utopia" | "stillness"
│   └── [item_id + tenant] ──────────→ Sui object ID (via BCS + deriveObjectID)
│
├── metadata.name ────────────────────→ human name ("Markus Outpost")
├── metadata.description
├── metadata.url ─────────────────────→ dApp URL
│
├── status.variant ───────────────────→ "ONLINE" | "OFFLINE" | "ANCHORED" | "UNANCHORED" | "DESTROYED"
│
├── owner_cap_id ─────────────────────→ OwnerCap → Character (name, address, id, tribeId)
│
├── energy_source_id ─────────────────→ Assembly (parent NetworkNode, ONLINE/OFFLINE)
│     [set on all non-NetworkNode assemblies]
│
├── [SSU only]
│     ├── inventory_keys[] ─────────→ dynamic fields (resolved via GraphQL)
│     └── dynamic fields contain:
│           max_capacity, used_capacity
│           items: [{ type_id, quantity, item_id, location, tenant }]
│                         └── type_id → GameType (Datahub)
│
├── [Gate only]
│     └── linked_gate_id ───────────→ Assembly (the other end, raw Sui object)
│                                           └── location → SolarSystem [UNRESOLVED]
│
├── [NetworkNode only]
│     ├── connected_assembly_ids[] ──→ Assembly[]  ← THE MAIN GRAPH EDGE
│     │     [each fetched via getObjectWithJson(id)]
│     ├── fuel.quantity / burn_rate_in_ms / burn_start_time / is_burning
│     │     max_capacity / last_updated / type_id / unit_volume
│     └── energy_source.current_energy_production
│           energy_source.max_energy_production
│           energy_source.total_reserved_energy


SolarSystem   [LOCATION RESOLUTION STILL OPEN]
│
├── id, name
├── constellation_id ─────────────────→ Constellation → region_id → Region
├── location (x, y, z)
│
├── gate_links[] ─────────────────────→ SolarSystem[] (neighbors)
│
└── [live, World API]
      ├── killmails[] ──────────────→ [{ victim_ship, attacker, timestamp }]
      └── security, star type, planets


GameType  (Datahub API — /v2/types/{typeId})
│
├── id (type_id), name, description
├── groupName, groupId
├── categoryName, categoryId
├── mass, radius, volume, portionSize
└── iconUrl


On-chain Singletons
│
├── ObjectRegistry ───────────────────→ item_id + tenant → Sui object ID
│     type: ${packageId}::object_registry::ObjectRegistry
│
├── EnergyConfig ─────────────────────→ type_id → energy_constant (per-assembly cost)
│     type: ${packageId}::energy::EnergyConfig
│
└── FuelConfig ───────────────────────→ type_id → fuel_efficiency (adjusted burn rate)
      type: ${packageId}::fuel::FuelConfig
```

---

## Data Sources

Each entity lives in exactly one authoritative source. Some entities are enriched from multiple sources.

| Entity | Authoritative Source | Access Method | Speed |
|---|---|---|---|
| Assembly (state, links) | Blockchain (Sui) | Sui GraphQL RPC | ~200ms |
| Assembly inventory | Blockchain (Sui) | GraphQL dynamic fields | ~200ms |
| Character (identity, caps) | Blockchain (Sui) | Sui GraphQL RPC | ~200ms |
| GameType (name, stats) | Datahub API | `/v2/types/{typeId}` | ~100ms |
| EnergyConfig (per-type) | Blockchain (Sui) | GraphQL singleton | ~200ms (cached) |
| FuelConfig (per-type) | Blockchain (Sui) | GraphQL singleton | ~200ms (cached) |
| SolarSystem (static) | Local DB | galaxy_db SQLite | instant |
| SolarSystem (live) | World API | `/v2/solarsystems/{id}` | ~100ms |
| Killmails | World API | `/v2/killmails?solarSystemId=` | ~100ms |
| Gate links (static) | Local file | gate_graph.json in-memory | instant |
| StructureProfile (derived) | Our disk | structures/{id}.json | instant |
| Memory/events | Our disk | memory_store per structure | instant |

**Datahub hosts by tenant:**
- `utopia` → `world-api-utopia.uat.pub.evefrontier.com`
- `stillness` → `world-api-stillness.live.tech.evefrontier.com` ← **live game**
- `nebula` / `testevenet` → `world-api-nebula.test.evefrontier.tech`

**DEFAULT_TENANT = "stillness"** (live game). Default Sui network = testnet.

---

## Sui GraphQL Endpoint

All blockchain queries go through Sui GraphQL RPC:
- testnet: `https://graphql.testnet.sui.io/graphql`
- devnet: `https://graphql.devnet.sui.io/graphql`

The EVE World package IDs per tenant (from DApp Kit constants, v0.0.18):
- `utopia`: `0xd12a70c74c1e759445d6f209b01d43d860e97fcf2ef72ccbbd00afd828043f75`
- `stillness`: `0x28b497559d65ab320d9da4613bf2498d5946b2c0ae3597ccfda3072ce127448c`

---

## Assembly Type Classification

Assembly type is determined by the **Move type repr string** in the GraphQL response, NOT by numeric type_id range.

| Move type contains | Assembly enum |
|---|---|
| `::storage_unit::StorageUnit` | SmartStorageUnit |
| `::turret::Turret` | SmartTurret |
| `::gate::Gate` | SmartGate |
| `::network_node::NetworkNode` | NetworkNode |
| `::manufacturing::Manufacturing` | Manufacturing |
| `::refinery::Refinery` | Refinery |

The `type_id` field is a **game item type** (like an EVE item type — it tells you what item this is, e.g., "Smart Storage Unit Mk1"). Known type IDs from DApp Kit constants:

| type_id | Item |
|---|---|
| 77917 | Smart Storage Unit |
| 88092 | Network Node |
| 85249 | Protocol Depot |
| 83907 | Gatekeeper |
| 87161 | Portable Refinery |
| 87162 | Portable Printer |
| 87566 | Portable Storage |
| 87160 | Refuge |
| 77518 | Lens |
| 77800 | Common Ore |
| 77810 | Metal-Rich Ore |
| 79193 | Transaction Chip |
| 83839 | Salt |

Portable types (87161, 87162, 87566, 87160) are excluded from assembly listings in the DApp Kit.

---

## GraphQL Queries Available (from DApp Kit)

These queries are ready to use directly against the Sui GraphQL endpoint. The Python backend can call them directly with `httpx` or `requests`.

| Function | Query | What it fetches |
|---|---|---|
| `getObjectByAddress(addr)` | `GET_OBJECT_BY_ADDRESS` | Object with BCS contents |
| `getObjectWithJson(addr)` | `GET_OBJECT_WITH_JSON` | Object with JSON fields |
| `getObjectWithDynamicFields(id)` | `GET_OBJECT_WITH_DYNAMIC_FIELDS` | Object + all dynamic fields (inventory) |
| `getObjectAndCharacterOwner(addr)` | `GET_OBJECT_DYNAMICFIELD_CHARACTER_WITH_JSON` | Assembly + owner char + energy source + dest gate |
| `getAssemblyWithOwner(id)` | (wraps above) | Full assembly with character, energy source, destination gate |
| `getObjectOwnerAndOwnedObjectsByType(addr, type)` | `GET_OBJECT_OWNER_AND_OWNED_OBJECTS_BY_TYPE` | Owner's objects of a given type |
| `getOwnedObjectsByType(owner, type)` | `GET_OWNED_OBJECTS_BY_TYPE` | All objects of type owned by address |
| `getOwnedObjectsByPackage(owner, pkgId)` | `GET_OWNED_OBJECTS_BY_PACKAGE` | All objects from a package owned by address |
| `getWalletCharacters(wallet)` | `GET_WALLET_CHARACTERS` | Characters owned by wallet |
| `getCharacterAndOwnedObjects(wallet)` | `GET_CHARACTER_AND_OWNED_OBJECTS` | Character + all OwnerCap assemblies |
| `getSingletonObjectByType(type)` | `GET_SINGLETON_OBJECT_BY_TYPE` | First object of given type (singletons) |
| `getSingletonConfigObjectByType(type, table)` | `GET_SINGLETON_CONFIG_OBJECT_BY_TYPE` | Config singleton with dynamic field table |
| `getObjectsByType(type, {first, after})` | `GET_OBJECTS_BY_TYPE` | Paginated all objects of a type |

**The power query** — `GET_OBJECT_DYNAMICFIELD_CHARACTER_WITH_JSON` — fetches in a single GraphQL call:
1. Assembly JSON contents + dynamic fields (inventory)
2. Owner chain: `owner_cap_id → OwnerCap → Character address → PlayerProfile → Character`
3. Energy source: `energy_source_id → NetworkNode object`
4. Destination gate: `linked_gate_id → Gate object`

This is a 4-hop traversal in a single network round trip.

---

## Item ID → Sui Object ID Derivation

To go from in-game item ID to Sui object address:

```python
# Python equivalent of the DApp Kit BCS encoding
import struct

# 1. Fetch ObjectRegistry singleton address
registry_address = await get_singleton_object_by_type(
    f"{package_id}::object_registry::ObjectRegistry"
)

# 2. BCS-encode {id: u64, tenant: string}
# key = bcs.struct("TenantItemId", {id: u64, tenant: string}).serialize({id: item_id, tenant: tenant})

# 3. deriveObjectID(registry_address, type_tag, key)
# object_id = deriveObjectID(registry_address, f"{package_id}::in_game_id::TenantItemId", key)
```

The Sui Python SDK has BCS encoding. The `deriveObjectID` function uses Sui's object derivation.

---

## Fuel State Calculation

NetworkNode fuel data from blockchain:

| Field | Description |
|---|---|
| `fuel.quantity` | Current fuel units (u64 string) |
| `fuel.max_capacity` | Max fuel capacity (u64 string) |
| `fuel.burn_rate_in_ms` | Milliseconds to burn one unit at 100% efficiency |
| `fuel.burn_start_time` | Unix timestamp (ms) when burning started |
| `fuel.is_burning` | Whether actively burning |
| `fuel.last_updated` | Last state update timestamp |
| `fuel.type_id` | Fuel item type_id |
| `fuel.unit_volume` | Volume per unit |

**Adjusted burn rate calculation:**
```python
# From DApp Kit getAdjustedBurnRate()
def get_adjusted_burn_rate(raw_burn_time_ms: int, efficiency_percent: float | None):
    if efficiency_percent and 0 < efficiency_percent <= 100:
        burn_time_per_unit_ms = raw_burn_time_ms * (efficiency_percent / 100)
    else:
        burn_time_per_unit_ms = raw_burn_time_ms

    units_per_hour = (3_600_000 / burn_time_per_unit_ms) if burn_time_per_unit_ms > 0 else 0
    return burn_time_per_unit_ms, units_per_hour

# Hours of fuel remaining:
elapsed_ms = current_time_ms - burn_start_time_ms
remaining_units = quantity - (elapsed_ms / burn_time_per_unit_ms)
hours_remaining = remaining_units * burn_time_per_unit_ms / 3_600_000
```

Fuel efficiency per assembly type comes from the `FuelConfig` on-chain singleton.

---

## What We Can Traverse Now vs. What Needs Research

### Confirmed traversable (DApp Kit source confirms)

- **Assembly → GameType**: Datahub API `/v2/types/{typeId}` returns full type info (name, description, groupName, categoryName, mass, volume, iconUrl). Call it from Python.
- **Assembly → Character (owner)**: Single GraphQL call (`GET_OBJECT_DYNAMICFIELD_CHARACTER_WITH_JSON`) follows `owner_cap_id → OwnerCap → PlayerProfile → Character`.
- **Assembly → Parent NetworkNode**: Same single GraphQL call follows `energy_source_id` and returns the NetworkNode's full JSON. Every non-NetworkNode assembly knows its parent.
- **NetworkNode → connected assemblies**: `connected_assembly_ids[]` on the blockchain object. Each ID fetched via `getObjectWithJson(id)`. Name, state, type, typeDetails per connected assembly.
- **NetworkNode → fuel state**: All fuel fields are on the blockchain object as u64 strings. Calculation confirmed.
- **NetworkNode → energy state**: `energy_source.current_energy_production`, `max_energy_production`, `total_reserved_energy`.
- **SmartGate → destination gate raw object**: Same single GraphQL call follows `linked_gate_id`. Returns the gate's JSON. Gate's location is still needed for system resolution.
- **SSU → inventory**: Dynamic fields on the blockchain object. `GET_OBJECT_WITH_DYNAMIC_FIELDS` fetches them. Contents: `max_capacity`, `used_capacity`, `items[{type_id, quantity, item_id, location_hash, tenant}]`.
- **Character → assemblies**: `getCharacterAndOwnedObjects(wallet)` returns character + all OwnerCap `authorized_object_id` entries.
- **SolarSystem → neighbors**: `gate_graph.json` loaded. Instant traversal.
- **SolarSystem → killmails**: `world_api.get_killmails(system_id)` works.
- **Assembly type classification**: Move type repr string, not type_id range.
- **Item ID → Sui object ID**: BCS encoding + deriveObjectID via ObjectRegistry singleton.

### Unknown — still needs investigation

- **Assembly → SolarSystem**: The `solarSystem` field exists in `SmartAssemblyResponse` (DApp Kit type) but `transformToAssembly` does NOT populate it from the blockchain data. The `location_hash` / `structure_id` question remains open. Possible sources: World API `/v2/assemblies/{id}` (if such endpoint exists), or a separate Sui query, or the location is only known to the game server.

- **Gate → destination system**: Follows from the above. If destination gate's location resolves to a system, gates become navigable.

- **Inventory item location**: Each `InventoryItem` has a `location: { location_hash: string }`. This location_hash is the same unresolved field.

---

## What the Companion Gains

Today HUGINN starts every conversation knowing:

```
STRUCTURE ID: 0xabc...
STRUCTURE NAME: "Warkus Outpost
TYPE: Smart Storage Unit
SYSTEM: AUDN
RIDER: Warkus
```

With entity graph traversal at connection time, HUGINN would start knowing:

```
STRUCTURE: Warkus Outpost (SSU, ONLINE)
TYPE: Heavy Storage Unit — Storage category, 50,000 m³
OWNER: Warkus (tribeId: 3, characterId: 1234567)
SYSTEM: AUDN | 3 gates | 2 kills (24h)
REGION: XYZ | CONSTELLATION: B-12

NETWORK NODE: Node-7 (ONLINE)
  FUEL: 68% — approx 14 days remaining (burn rate: 1.2 units/hr)
  ENERGY: 4,200 / 6,000 kW (70%)
  CONNECTED STRUCTURES (4):
    - Markus Outpost [this] (SSU, ONLINE) — 900 kW
    - Gate-Alpha (SmartGate, ONLINE → BD-H5T) — 800 kW
    - Turret-1 (SmartTurret, OFFLINE) — 600 kW
    - Refinery-2 (Refinery, ONLINE) — 1,100 kW

INVENTORY (SSU):
  500x Tritanium (Mineral, 0.01 m³ each)
  120x Fuel Block (Fuel)
  3x Civilian Shield Booster (Module)
  CAPACITY: 3,420 / 50,000 m³

GATE: Gate-Alpha → destination gate [system TBD — location resolution pending]
```

None of this requires Claude to ask. It is pre-loaded context.

---

## What the UI Gains

| Panel | Current | With Entity Graph |
|---|---|---|
| `baseline` | Structure ID, wallet, state | Name, type, owner name, network node fuel %, connected count |
| `system_intel` | Security, star, planet count, kills | + Gate destinations, distance to known structures |
| `threat_assessment` | Kill count, aggressor, ship class | + Ship type resolved to full GameType (mass, class, iconUrl) |
| `network_map` | Does not exist | Network node + all connected assemblies, state, energy usage per node |
| `inventory` | Does not exist | SSU contents with resolved item names, quantities, m³ used |
| `gate_info` | Does not exist | Gate link → raw destination gate (system pending location resolution) |
| `asset_map` | Does not exist | All structures owned by character, states |

---

## The Resolver Architecture

A single Python class — `EntityResolver` — owns all traversal. It takes any ID, determines its type, fetches from the right source, and returns a typed result. It caches aggressively since blockchain data changes slowly.

```python
resolver = EntityResolver(tenant="stillness", package_id=STILLNESS_PACKAGE_ID)

# Any of these work:
assembly  = await resolver.get_assembly("0xabc...")        # GraphQL
game_type = await resolver.get_type(77917)                 # Datahub API (cached)
system    = resolver.get_system("Heimatar IV")             # instant, local
character = await resolver.get_character("0xwallet...")    # GraphQL

# Traversal:
network   = await resolver.get_network(assembly)           # follows connected_assembly_ids
inventory = await resolver.get_inventory(assembly)         # reads dynamic fields
gate_dest = await resolver.get_gate_destination(assembly)  # follows linked_gate_id
fuel_hrs  = resolver.compute_fuel_hours(network_node)      # pure calculation

# Character's assets:
assemblies = await resolver.get_character_assemblies("0xwallet...")
```

The resolver feeds two consumers:
- **Claude tools** — `get_connected_assemblies`, `get_inventory`, `get_gate_info`
- **Context builder** — pre-traverse the graph before Claude's first response

---

## Implementation Plan

In order of impact and feasibility. All are now confirmed implementable.

**1. EntityResolver class** (`src/entity_resolver.py`)
Foundation. Wraps Sui GraphQL queries + Datahub API calls. Caches with TTL (blockchain = 30s, types = forever, singletons = 5min). Uses the confirmed GraphQL queries from DApp Kit.

**2. Network context pre-load**
On every `/companion/stream`, if the assembly has a known NetworkNode (`energy_source_id`), traverse its `connected_assembly_ids` and inject into HUGINN's context. Highest-value single change.

**3. Tool: `get_connected_assemblies`**
Returns structured network data. Maps to `network_map` UI panel.

**4. Tool: `get_inventory`**
Reads SSU dynamic fields. Returns item list with type names from Datahub. Maps to `inventory` panel.

**5. Tool: `get_gate_info`**
Follows `linked_gate_id`. Returns destination gate object. System resolution pending.

**6. `network_map` panel (frontend)**
Visual connected assembly graph. Status, type, name, energy draw per node. Clickable.

**7. `inventory` panel (frontend)**
Item list with resolved names, volume, categories.

---

## Open Questions

1. **Does `location_hash` map to a solar system ID?** The DApp Kit defines `solarSystem: { id, name, location: {x,y,z} }` in `SmartAssemblyResponse` but never populates it in `transformToAssembly`. The field exists — suggesting the data is accessible somewhere. Candidates: a World API endpoint like `/v2/assemblies/{assemblyId}`, or the location hash itself encodes the system ID via a known derivation. **This is the single most important open question.** Unlocking it removes the `/system` command entirely.

2. **What World API endpoints exist beyond `/v2/types/` and `/v2/solarsystems/`?** The Datahub host serves more than just types. Checking the full route listing at `world-api-stillness.live.tech.evefrontier.com` may reveal an assemblies or structures endpoint that returns location.

---

## Summary

The DApp Kit source code answers most of our open questions. Inventory is readable via GraphQL dynamic fields. Assembly type classification uses Move type strings not type_id ranges. The entire owner → character → assemblies chain is traversable in one GraphQL call. The parent NetworkNode is fetched automatically with every assembly. Fuel state is fully computable from on-chain data.

The one remaining gap is `location_hash` → solar system. Everything else is ready to build.
