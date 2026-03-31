# EVE Frontier Data Schemas

Reference mapping every game data type to its authoritative source.

**Backend:** `src/eve_types.py` — Pydantic models
**Frontend:** `frontend/src/types/eve.ts` — TypeScript interfaces
**dapp-kit GraphQL types:** `@evefrontier/dapp-kit/graphql/types.ts` — raw query response shapes

---

## Sources

| Source | Base URL / Location | Auth |
|--------|---------------------|------|
| World API (utopia) | `https://world-api-utopia.uat.pub.evefrontier.com` | None (most), Bearer JWT (jumps) |
| World API (stillness) | `https://world-api-stillness.live.tech.evefrontier.com` | Same |
| Sui GraphQL | `https://graphql.testnet.sui.io/graphql` | None |
| Sui JSON-RPC | `https://fullnode.testnet.sui.io` | None |
| dapp-kit | `@evefrontier/dapp-kit` npm package | SDK-managed |

---

## World API Types

### SolarSystem
**Endpoint:** `GET /v2/solarsystems`, `GET /v2/solarsystems/{id}`
**Auth:** None
**Fields:** `id`, `name`, `constellationId`, `regionId`, `location {x,y,z}`
**Extended (detailed):** + `gateLinks [{id, name, location, destination: SolarSystem}]`

### GameType
**Endpoint:** `GET /v2/types`, `GET /v2/types/{id}`
**Auth:** None
**Total types:** 392+ (as of 2026-03-27)
**Known categories:** Deployable, Ship, Module, Charge, Material, Asteroid, Commodity
**Known groups (Deployable):** Storage, ... (check API for full list)
**Fields:** `id`, `name`, `description`, `mass`, `radius`, `volume`, `portionSize`, `groupName`, `groupId`, `categoryName`, `categoryId`, `iconUrl`, `attributes`

### Ship
**Endpoint:** `GET /v2/ships`, `GET /v2/ships/{id}`
**Auth:** None
**Fields:** `id`, `name`, `classId`, `className`, `description`, `slots {high,medium,low}`, `health {shield,armor,structure}`, `physics {mass,maximumVelocity,inertiaModifier,heat{heatCapacity,conductance}}`, `damageResistances {shield,armor,structure}` (each with `emDamage,thermalDamage,kineticDamage,explosiveDamage`), `fuelCapacity`, `cpuOutput`, `powergridOutput`, `capacitor {capacity,rechargeRate}`

### Jump
**Endpoint:** `GET /v2/characters/me/jumps`
**Auth:** Bearer JWT (player token — in-game browser only)
**Fields:** `id` (UNIX ms timestamp), `time` (ISO string), `origin: SolarSystem`, `destination: SolarSystem`, `ship {instanceId, typeId}`
**Usage:** Latest jump's `destination` = player's current system.

### Tribe
**Endpoint:** `GET /v2/tribes`, `GET /v2/tribes/{id}`
**Auth:** None
**Fields:** `id`, `name`, `nameShort`, `description`, `taxRate`, `tribeUrl`
**Notes:** IDs 1000044–1000172 = NPC corps; 98000001+ = player corps

### Constellation
**Endpoint:** `GET /v2/constellations`, `GET /v2/constellations/{id}`
**Auth:** None
**Fields:** `id`, `name`, `regionId`, `location`, `solarSystems: [SolarSystem]`

### POD (Provable Object Datatype)
**Endpoint:** `GET /v2/characters/me/jumps/{id}?format=pod`, `POST /v2/pod/verify`
**Fields:** `entries {key: {valueType, stringVal|boolVal|bytesVal|bigVal|timeVal}}`, `signature`, `signerPublicKey`
**valueType enum:** `null`, `string`, `bytes`, `cryptographic`, `int`, `boolean`, `eddsa_pubkey`, `date`

---

## Blockchain Types (Move structs via Sui GraphQL)

### TenantItemId
**Where used:** `key` field on Assembly, Character
**Fields:** `item_id: string` (game integer as string), `tenant: string` ("utopia" | "stillness")

### Assembly (StorageUnit / Gate / Turret / NetworkNode)
**Source:** Sui GraphQL `getAssemblyWithOwner()` → `RawSuiObjectData`
**Core fields (all assembly types):**
- `id` — Sui object ID (0x...)
- `type_id` — u64 game type as string
- `key: TenantItemId`
- `metadata {assembly_id, name, description, url}`
- `owner_cap_id`
- `status {status: {"@variant": "ONLINE"|"OFFLINE"}}`
- `location {location_hash, structure_id}` — hashed, not raw coordinates

**SmartGate-specific:** `linked_gate_id`
**StorageUnit-specific:** `inventory_keys: string[]`
**NetworkNode-specific:** `energy_source_id`, `fuel {max_capacity, burn_rate_in_ms, type_id, unit_volume, quantity, is_burning, ...}`, `energy_source {max_energy_production, current_energy_production, total_reserved_energy}`, `connected_assembly_ids`

**Move events (on creation):**
```
AssemblyCreatedEvent:   assembly_id, assembly_key, owner_cap_id, type_id
GateCreatedEvent:       + location_hash, status
StorageUnitCreatedEvent: + max_capacity, location_hash, status
TurretCreatedEvent:     (same as Assembly)
NetworkNodeCreatedEvent: + fuel_max_capacity, fuel_burn_rate_in_ms, max_energy_production
```

### Character
**Source:** Sui GraphQL `getWalletCharacters()` → `RawCharacterData`
**Fields:** `id`, `key: TenantItemId`, `tribe_id`, `character_address`, `metadata`, `owner_cap_id`
**Processed form (CharacterInfo):** `id`, `address`, `name`, `tribeId`, `characterId` (integer)

### OwnerCap
**Source:** `suix_getOwnedObjects` filtered by `{StructType: "pkg::assembly::OwnerCap<...>"}`
**Fields:** `id`, `authorized_object_id` (= Assembly's Sui object ID)
**Ownership chain:** wallet → OwnerCap → Assembly

### AccessRegistry (our extension)
**Source:** `sui_getObject` on the AccessRegistry shared object
**Fields:** `owner: string`, `tribe: string[]`, `vetted: string[]`
**Tiers:** OWNER > TRIBE > VETTED > NONE

---

## Probe Results (Known IDs)

| ID | Type | Notes |
|----|------|-------|
| `1000000019552` | item_id | SSU in utopia tenant (World API returns 404 — not exposed via REST) |
| `0x3b2ac50f0da15672de1b876b4b674d2dd591b325758f8f7fb2151e63bd72ba20` | assembly_id | On-chain object; query via Sui GraphQL |
| `utopia` | tenant | UAT environment (testnet) |
| `stillness` | tenant | Live production environment |

---

## API Discovery Notes

- `/v2/smartassemblies/{item_id}` returns 404 — assemblies are queried via Sui GraphQL, not World API REST
- Solar systems: 24,502 total (paginated, limit 1000 per page)
- Types: 392 total (as of discovery date)
- Tribes: 20 total (11 NPC + 9 player corps)
- Jumps endpoint is the only authenticated World API endpoint in scope

---

## dapp-kit Integration

The official `@evefrontier/dapp-kit` package provides:
- `useSmartObject()` — loads `Assembly` data automatically (via URL params `?itemId=&tenant=`)
- `getAssemblyWithOwner()` — GraphQL query returning assembly + owner character
- `transformToAssembly()` — converts `RawSuiObjectData` → usable assembly object
- `transformToCharacter()` — converts `RawCharacterData` → `CharacterInfo`

See `frontend/node_modules/@evefrontier/dapp-kit/graphql/` for GraphQL query strings and raw response types.
