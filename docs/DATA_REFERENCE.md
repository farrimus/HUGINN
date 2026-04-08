# Data Reference

All data sources available to the backend and frontend.

---

## World API

Two tenants:

| Tenant | Base URL | Environment |
|--------|----------|-------------|
| `utopia` | `https://world-api-utopia.uat.pub.evefrontier.com` | UAT / testnet |
| `stillness` | `https://world-api-stillness.live.tech.evefrontier.com` | Live production |

Authentication: none required for most endpoints. `GET /v2/characters/me/jumps` requires a Bearer JWT from the in-game browser.

### Endpoints

**Solar Systems**
- `GET /v2/solarsystems` — paginated list, limit 1000 per page (24,502 total)
- `GET /v2/solarsystems/{id}`
- Fields: `id`, `name`, `constellationId`, `regionId`, `location {x,y,z}`
- Extended (detail): + `gateLinks [{id, name, location, destination: SolarSystem}]`

**Game Types**
- `GET /v2/types`, `GET /v2/types/{id}`
- Fields: `id`, `name`, `description`, `mass`, `radius`, `volume`, `portionSize`, `groupName`, `groupId`, `categoryName`, `categoryId`, `iconUrl`, `attributes`
- Total: 392 types. Categories: Deployable, Ship, Module, Charge, Material, Asteroid, Commodity

**Ships**
- `GET /v2/ships`, `GET /v2/ships/{id}`
- Fields: `id`, `name`, `classId`, `className`, `description`, `slots {high,medium,low}`, `health {shield,armor,structure}`, `physics {mass,maximumVelocity,...}`, `fuelCapacity`, `cpuOutput`, `powergridOutput`, `capacitor {capacity,rechargeRate}`

**Player Jumps** (authenticated)
- `GET /v2/characters/me/jumps` — requires Bearer JWT (available from in-game browser only)
- Fields: `id` (UNIX ms), `time` (ISO string), `origin: SolarSystem`, `destination: SolarSystem`, `ship {instanceId, typeId}`
- Latest jump's `destination` = player's current system

**Tribes**
- `GET /v2/tribes`, `GET /v2/tribes/{id}`
- Fields: `id`, `name`, `nameShort`, `description`, `taxRate`, `tribeUrl`
- IDs 1000044–1000172 = NPC corps; 98000001+ = player corps (20 total: 11 NPC + 9 player)

**Constellations**
- `GET /v2/constellations`, `GET /v2/constellations/{id}`
- Fields: `id`, `name`, `regionId`, `location`, `solarSystems: [SolarSystem]`

**Notes:**
- `/v2/smartassemblies/{item_id}` returns 404 — assemblies are on-chain, not World API
- Assembly data comes from Sui GraphQL via `@evefrontier/dapp-kit`

---

## Blockchain Types (Sui / Move)

Queried via `@evefrontier/dapp-kit` or raw Sui GraphQL.

**Sui GraphQL endpoints:**
- Testnet: `https://graphql.testnet.sui.io/graphql`
- JSON-RPC: `https://fullnode.testnet.sui.io`

### Assembly

All assembly types share these core fields:
- `id` — Sui object ID (0x...)
- `type_id` — u64 game type as string
- `key: TenantItemId {item_id, tenant}`
- `metadata {assembly_id, name, description, url}`
- `owner_cap_id`
- `status {"@variant": "ONLINE" | "OFFLINE"}`
- `location {location_hash, structure_id}`

Type-specific fields:
- **SmartGate:** + `linked_gate_id`
- **StorageUnit:** + `inventory_keys: string[]`
- **NetworkNode:** + `energy_source_id`, `fuel {max_capacity, burn_rate_in_ms, type_id, quantity, is_burning, ...}`, `connected_assembly_ids`

### Character
- `id`, `key: TenantItemId`, `tribe_id`, `character_address`, `metadata`, `owner_cap_id`

### AccessRegistry
- `owner: string`, `tribe: string[]`, `vetted: string[]`
- Access tiers: OWNER > TRIBE > VETTED > NONE

---

## Galaxy Database (SQLite)

**File:** `data/eve_universe.db`
**Build:** `python build_universe.py` (one-time, from World API)
**Python interface:** `src/galaxy_db.py` → `GalaxyDB` class

The database is gitignored and must be built locally. It contains all solar systems, celestials, and gate connections from CCP's public data.

### ID Ranges

| Level | ID range | Primary key |
|-------|----------|-------------|
| Region | 10xxxxxx | regionId |
| Constellation | 20xxxxxx | constellationId |
| Solar System | 30xxxxxx | solarSystemId |
| Planet / Moon / Station | 40xxxxxx | planetId / moonId / stationId |

### Tables

| Table | Key columns |
|-------|-------------|
| Regions | regionId, name, centerX/Y/Z |
| Constellations | constellationId, name, regionId, centerX/Y/Z |
| SolarSystems | solarSystemId, name, constellationId, regionId, centerX/Y/Z, star_* (age, mass, temp, spectral_class, etc.) |
| Planets | planetId, name, solarSystemId, celestialIndex, typeId, centerX/Y/Z, radius, density, temperature, orbitRadius, ... |
| Moons | moonId, name, planetId, solarSystemId, typeId, centerX/Y/Z, radius, + physical/orbital cols |
| NpcStations | stationId, name, solarSystemId, planetId, typeId, centerX/Y/Z, operationId, isConquerable, reprocessingEfficiency, reprocessingStationsTake, ownerId, lagrangePoint, orbitId |
| LagrangePoints | id, solarSystemId, planetId, pointType (L1–L5), centerX/Y/Z |
| Jumps | fromSystemId, toSystemId, fromCenterX/Y/Z, toCenterX/Y/Z, jumpType |
| Types | typeId, typeName, groupId, description, published, mass, volume, capacity, portionSize, basePrice, marketGroupId, iconId, soundId, graphicId |

IDs are INTEGER. Coordinates and physical values are REAL (often NULL). Use `IS NULL`, not `= 0`, for missing foreign keys.

### GalaxyDB Methods

```python
db = GalaxyDB("data/eve_universe.db")

db.get_system(name_or_id)              # By name (str) or solarSystemId (int)
db.get_region(id)
db.get_constellation(id)
db.get_planet(id)
db.get_moon(id)
db.get_station(id)
db.get_celestials_in_system(system_id) # → {planets, moons, stations, lagrange_points}
db.search_systems(pattern)             # LIKE search on name
db.get_jumps_from_system(system_id)    # → list of dicts; extract toSystemId for adjacent IDs
db.run_sql(sql, params)                # → list of dicts

# Module-level utility functions (also importable from galaxy_db):
spectral_label(code: str) -> str       # "G2" → "G2 (Yellow Dwarf)"
count_planets(planets: list) -> dict   # list of planet dicts → {"Barren": 3, "Temperate": 1, ...}
```

### Common Queries

```sql
-- System with region and constellation names
SELECT s.solarSystemId, s.name, c.name AS constellationName, r.name AS regionName
FROM SolarSystems s
LEFT JOIN Constellations c ON s.constellationId = c.constellationId
LEFT JOIN Regions r ON s.regionId = r.regionId
WHERE s.solarSystemId = ?;

-- All celestials in a system
SELECT planetId AS id, name, 'planet' AS kind, centerX, centerY, centerZ FROM Planets WHERE solarSystemId = ?
UNION ALL SELECT moonId, name, 'moon', centerX, centerY, centerZ FROM Moons WHERE solarSystemId = ?
UNION ALL SELECT stationId, name, 'station', centerX, centerY, centerZ FROM NpcStations WHERE solarSystemId = ?;

-- One-jump neighbors
SELECT toSystemId FROM Jumps WHERE fromSystemId = ?
UNION SELECT fromSystemId FROM Jumps WHERE toSystemId = ?;
```

---

## dapp-kit Integration

`@evefrontier/dapp-kit` v0.1.7 provides React hooks and utilities for all game data access on the frontend.

Key functions:
- `useSmartObject()` — loads assembly + owner automatically from URL params
- `getAssemblyWithOwner(objectId)` — GraphQL query: assembly + owner character
- `transformToAssembly(objectId, moveObject, options?)` — converts raw Sui object → typed assembly
- `useConnection()` — wallet connect/disconnect, current account

See `docs/DAPP_KIT_API.md` for the complete API reference.

---

## Known IDs

| ID | Type | Notes |
|----|------|-------|
| `1000000019552` | item_id | SSU in utopia tenant |
| `0x3b2ac50f0da15672de1b876b4b674d2dd591b325758f8f7fb2151e63bd72ba20` | assembly_id | On-chain Sui object |
| `utopia` | tenant | UAT environment |
| `stillness` | tenant | Live production |
