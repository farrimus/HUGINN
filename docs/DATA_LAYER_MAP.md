# EVE Frontier Data Layer Map

**Produced:** 2026-03-29
**Method:** Full read of dapp-kit source (transforms.ts, types.ts, worldApiReturnTypes.ts, graphql/queries.ts, graphql/client.ts, utils/datahub.ts, utils/config.ts, utils/constants.ts), backend source (entity_resolver.py, endpoints/entity.py, eve_types.py, graphql_queries.py), and frontend context (EntityContext.tsx, types/terminal.ts).
**Status:** Authoritative as of the above date. Re-verify if dapp-kit package is upgraded.

For the actionable decision reference (where does X belong?), see `docs/DAPP_KIT_BOUNDARY.md`.

---

## A. Per-Assembly-Type Data Map

### Base Fields (all 7 types, from transforms.ts)

Every assembly type carries these fields regardless of kind:

`id`, `item_id`, `type`, `typeDetails`, `name`, `state`, `character`, `solarSystem`, `isParentNodeOnline`, `energySourceId`, `energyUsage`, `typeId`, `_raw`, `_options`, `description`, `dappURL`

### SmartStorageUnit

**dapp-kit transforms.ts fields:**
- All base fields
- `storage.mainInventory.capacity` (string)
- `storage.mainInventory.usedCapacity` (string)
- `storage.mainInventory.items` (InventoryItem[])
- `storage.ephemeralInventories` (EphemeralInventory[])

**Raw on-chain fields (_raw.contents.json):**
- `inventory_keys?: string[]` — keys for dynamic field inventory containers
- `key?: {item_id: string, tenant: string}`
- `metadata?: {assembly_id, name, description, url}`
- `status?: {assembly_id?, item_id?, status: {"@variant": string}, type_id?}`
- `owner_cap_id?: string`
- `location?: {location_hash, structure_id}`
- `extension: unknown` — present, never parsed

**Backend-computed fields (entity_resolver.py):**
- `sui_id`, `assembly_type: "SmartStorageUnit"`, `type_repr`, `name` (prioritized from metadata)
- Inventory: `assembly_id, assembly_name, used_capacity (m³), max_capacity (m³), capacity_percent`
- Each item: `type_id, type_name (Datahub), category_name, quantity, volume_per_unit, total_volume`

**Currently displayed in UI:** `id, assembly_type, type_id, name, status`, owner `(character_name, tribe_id, character_id)`, full InventoryData

---

### SmartGate

**dapp-kit transforms.ts fields:**
- All base fields
- `gate.destinationId` (string | undefined)
- `gate.destinationGate` (RawSuiObjectData | null)

**Raw on-chain fields:**
- `linked_gate_id?: string` — destination gate Sui object ID (SmartGate only)
- Standard: `key, metadata, status, owner_cap_id, location`
- `extension: unknown` — present, never parsed

**Backend-computed fields:**
- `sui_id`, `assembly_type: "SmartGate"`, `name`
- `destination_gate: {id, name, status}`

**Currently displayed in UI:** `id, assembly_type, name, status`, destination gate info, owner info

---

### SmartTurret

**dapp-kit transforms.ts fields:**
- All base fields
- `turret: {}` — **empty object, no fields**

**Raw on-chain fields:**
- Standard: `key, metadata, status, owner_cap_id, location`
- `extension: unknown` — present, never parsed

**Backend-computed fields:**
- `sui_id`, `assembly_type: "SmartTurret"`, `name`

**Currently displayed in UI:** `id, assembly_type, name, status`, owner info. No turret-specific rendering.

---

### NetworkNode

**dapp-kit transforms.ts fields:**
- All base fields (note: `energySourceId` is `undefined` — NetworkNode IS the source)
- `networkNode.fuel` (FuelResponse)
- `networkNode.energyProduction`
- `networkNode.energyMaxCapacity`
- `networkNode.totalReservedEnergy`
- `networkNode.linkedAssemblies` (SmartAssemblyResponse[])

**FuelResponse fields:** `quantity, burnTimeInMs, burnStartTime, isBurning, lastUpdated, maxCapacity, previousCycleElapsedTime, unitVolume, typeId`

**Raw on-chain fields:**
- `fuel?: {max_capacity, burn_rate_in_ms, type_id, unit_volume, quantity, is_burning, previous_cycle_elapsed_time, burn_start_time, last_updated}` — all strings (u64)
- `energy_source?: {max_energy_production, current_energy_production, total_reserved_energy}` — all strings
- `connected_assembly_ids?: string[]`
- Standard: `key, metadata, status, owner_cap_id, location`
- `extension: unknown` — present, never parsed

**Backend-computed fields:**
- `sui_id`, `assembly_type: "NetworkNode"`, `name`
- `fuel: {quantity, max_capacity, fuel_percent, burn_rate_units_per_hr, hours_remaining, is_burning}`
- `energy: {current_energy_production, max_energy_production, total_reserved_energy, energy_percent}`
- `connected_assemblies[]` (capped at 20): `{id, name, assembly_type, status, type_id, key, group_name, category_name}`
- `truncated: bool` — true if >20 assemblies were connected

**Currently displayed in UI:** All fuel + energy fields, connected assemblies list

---

### Manufacturing

**dapp-kit transforms.ts fields:**
- All base fields
- `manufacturing: {isParentNodeOnline: state === State.ONLINE}` — **computed from the assembly's own state, NOT the parent NetworkNode's state. Likely a bug.**

**Raw on-chain fields:**
- Standard: `key, metadata, status, owner_cap_id, location, energy_source_id`
- `extension: unknown` — present, never parsed

**Backend-computed fields:**
- `sui_id`, `assembly_type: "Manufacturing"`, `name`
- Parent node: `{id, name, status, fuel_percent, fuel_hours_remaining, energy_used, energy_max}`

**Currently displayed in UI:** `id, assembly_type, name, status`, owner info, parent network node reference

---

### Refinery

**dapp-kit transforms.ts fields:**
- All base fields
- `refinery: {isParentNodeOnline: state === State.ONLINE}` — same caveat as Manufacturing above

**Raw on-chain fields:**
- Standard: `key, metadata, status, owner_cap_id, location, energy_source_id`
- `extension: unknown` — present, never parsed

**Backend-computed fields:**
- `sui_id`, `assembly_type: "Refinery"`, `name`
- Parent node reference (same as Manufacturing)

**Currently displayed in UI:** `id, assembly_type, name, status`, owner info, parent network node reference

---

### Assembly (generic)

**dapp-kit transforms.ts fields:**
- Base fields only. No module-specific block.

**Raw on-chain fields:**
- Standard: `key, metadata, status, owner_cap_id, location, energy_source_id` (optional)
- `extension: unknown` — present, never parsed

**Backend-computed fields:**
- `sui_id`, `assembly_type: "Assembly" | "Unknown"`, `name`

---

### Field Availability Matrix

| Field | Storage | Gate | Turret | NetworkNode | Mfg | Refinery |
|-------|---------|------|--------|-------------|-----|----------|
| id, type_id, key, metadata, status | YES | YES | YES | YES | YES | YES |
| inventory_keys | YES | — | — | — | — | — |
| linked_gate_id | — | YES | — | — | — | — |
| energy_source_id | — | — | — | — (self) | YES | YES |
| fuel | — | — | — | YES | — | — |
| energy_source | — | — | — | YES | — | — |
| connected_assembly_ids | — | — | — | YES | — | — |
| `.storage` module | YES | — | — | — | — | — |
| `.gate` module | — | YES | — | — | — | — |
| `.turret` module (empty {}) | — | — | YES | — | — | — |
| `.networkNode` module | — | — | — | YES | — | — |
| `.manufacturing` module | — | — | — | — | YES | YES |
| `.refinery` module | — | — | — | — | — | YES |
| Backend enrichment available | YES (inventory) | YES (dest gate) | NO | YES (network topo) | YES (parent node) | YES (parent node) |

---

## B. Complete dapp-kit Function Reference

| Function | Returns | Data Source | Used in App |
|----------|---------|-------------|-------------|
| `useConnection()` | `{currentAccount, walletAddress, isConnected, hasEveVault, handleConnect, handleDisconnect}` | Wallet state | YES |
| `useSmartObject()` | `{tenant, assembly, assemblyOwner, loading, error, refetch}` | World API + Sui GraphQL | YES |
| `useNotification()` | `{notify(), notification}` | In-memory | YES |
| `useSponsoredTransaction()` | React Query mutation `{mutate, mutateAsync, isPending, isError, error, data}` | EVE Vault RPC | NO |
| `getAssemblyWithOwner(assemblyId)` | `{moveObject, assemblyOwner, energySource, destinationGate}` | Sui GraphQL | NO |
| `getObjectWithJson(address)` | Object + JSON contents | Sui GraphQL | NO (backend uses internally) |
| `getObjectWithDynamicFields(objectId)` | Object + dynamic fields array | Sui GraphQL | NO |
| `getOwnedObjectsByType(owner, objectType)` | Object addresses | Sui GraphQL | NO |
| `getOwnedObjectsByPackage(owner, packageId)` | Objects with full data | Sui GraphQL | NO |
| `getWalletCharacters(wallet)` | Character objects owned by wallet | Sui GraphQL | NO (backend reimplements) |
| `getCharacterAndOwnedObjects(wallet)` | Character + OwnerCap assemblies | Sui GraphQL | NO (backend reimplements) |
| `getObjectsByType(objectType, options)` | Paginated object list | Sui GraphQL | NO |
| `getSingletonObjectByType(objectType)` | Singleton address | Sui GraphQL | NO (backend uses internally) |
| `getSingletonConfigObjectByType(objectType, tableName)` | Config singleton with dynamic fields | Sui GraphQL | NO (backend uses internally) |
| `transformToAssembly(objectId, moveObject, options)` | Typed `AssemblyType<Assemblies>` | Move JSON | NO |
| `transformToCharacter(characterInfo)` | `DetailedSmartCharacterResponse` | Character JSON | NO |
| `getDatahubGameInfo(typeId)` | `DatahubGameInfo` (name, description, icon, groupName, categoryName, volume) | Datahub REST | NO |
| `getEnergyConfig()` | `Record<typeId_str, energy_usage_kw>` | Sui GraphQL singleton | NO (backend reimplements) |
| `getFuelEfficiencyConfig()` | `Record<typeId_str, burn_ms_per_unit>` | Sui GraphQL singleton | NO (backend reimplements) |
| `getEnergyUsageForType(typeId)` | number | Cached EnergyConfig | NO |
| `getFuelEfficiencyForType(typeId)` | number | Cached FuelConfig | NO |
| `getAdjustedBurnRate(typeId, quantity)` | Adjusted burn rate | Fuel + efficiency config | NO |
| `parseStatus(statusVariant)` | `State` enum value | Status object | NO (backend reimplements) |
| `getAssemblyType(moveTypeRepr)` | `Assemblies` enum value | Move type string | NO (backend reimplements) |
| `parseCharacterFromJson(json)` | `CharacterInfo` | Character JSON | NO |
| `abbreviateAddress(address, precision, expanded)` | Abbreviated address string | Address string | NO |
| `formatDuration(ms)` | Human-readable duration | Milliseconds | NO |
| `formatM3(volume)` | Human-readable volume | Cubic meters | NO |
| `executeGraphQLQuery<T>(query, variables)` | `GraphQLResponse<T>` | Sui GraphQL | NO |

**Summary:** 3 of 29 dapp-kit functions are currently used in the frontend (`useConnection`, `useSmartObject`, `useNotification`).

---

## C. Complete GraphQL Query Reference

All queries are defined in `frontend/node_modules/@evefrontier/dapp-kit/graphql/queries.ts`.

| Query Constant | What It Fetches | Fields Traversed |
|----------------|----------------|-----------------|
| `GET_OBJECT_BY_ADDRESS` | Single object, BCS only (no JSON) | `object(address).asMoveObject.contents.{type.repr, bcs}` |
| `GET_OBJECT_WITH_JSON` | Single object, JSON + BCS | `object(address).asMoveObject.contents.{type.repr, json, bcs}` |
| `GET_OBJECT_WITH_DYNAMIC_FIELDS` | Object JSON + all dynamic fields | `object.contents.json` + `dynamicFields.nodes[].{contents.json, name.json, type}` |
| `GET_OBJECT_DYNAMICFIELD_CHARACTER_WITH_JSON` | Assembly + owner character + energy source + destination gate in one query | `object → owner_cap_id → OwnerCap<Character> → authorized_object_id → Character JSON; also energySource JSON; also destinationGate JSON` |
| `GET_OBJECT_OWNER_AND_OWNED_OBJECTS_BY_TYPE` | Object + owner's objects of a specific type (BCS) | `object.owner.address.objects(filter: type).nodes[].contents.bcs` |
| `GET_OBJECT_OWNER_AND_OWNED_OBJECTS_WITH_JSON` | Object + owner's objects of a specific type (JSON) | Same as above but with JSON + address |
| `GET_OWNED_OBJECTS_BY_TYPE` | Addresses of objects owned by a wallet, filtered by type | `address(owner).objects(filter: type).nodes[].address` |
| `GET_OWNED_OBJECTS_BY_PACKAGE` | Full objects owned by address filtered by package | `objects(filter: {owner, package}).nodes[].{address, version, asMoveObject.{contents.json, dynamicFields}}` |
| `GET_WALLET_CHARACTERS` | Most recent character owned by wallet | `address → PlayerProfile → character_id → Character JSON` |
| `GET_CHARACTER_AND_OWNED_OBJECTS` | Character + all OwnerCap assemblies it owns | `address → PlayerProfile → Character JSON; OwnerCap[] → authorized_object_ids → assembly JSONs` |
| `GET_SINGLETON_OBJECT_BY_TYPE` | Address of a singleton object by type | `objects(filter: type).nodes[0].address` |
| `GET_SINGLETON_CONFIG_OBJECT_BY_TYPE` | Config singleton with its dynamic field table | Deep extract: config object → table address → `dynamicFields.nodes[].{key.json, value.json}` |
| `GET_OBJECTS_BY_TYPE` | Paginated list of all objects of a specific type | `objects(filter, first, after).nodes[].{address, version, contents.{json, type.repr}}, pageInfo` |

---

## D. Unknowns

Things that cannot be determined without querying live on-chain data.

1. **`extension: unknown` on every assembly object**
   - Typed as `unknown` in graphql/types.ts. Never parsed or used anywhere in dapp-kit or the backend.
   - Likely a future extensibility hook in the Move contract.
   - **Resolution:** Inspect live on-chain object JSON for each assembly type. Check EVE Frontier Move contract source.

2. **`dynamicFields` content for SmartGate, SmartTurret, NetworkNode, Manufacturing, Refinery**
   - Only SmartStorageUnit dynamic fields are documented (inventory containers with capacity + items).
   - Whether other types have dynamic fields and what they contain is unknown.
   - **Resolution:** Query each type via `GET_OBJECT_WITH_DYNAMIC_FIELDS` on a live object of each type.

3. **`manufacturing.isParentNodeOnline` correctness**
   - dapp-kit transforms.ts line 242 computes `isParentNodeOnline: state === State.ONLINE` using the manufacturing assembly's own state — not the parent NetworkNode's state.
   - This appears to be a bug: you could have an online manufacturing unit whose parent node is offline.
   - **Resolution:** Check Move contract definition; test with an online manufacturing assembly connected to an offline NetworkNode.

4. **Inventory volume conversion factor**
   - Backend divides raw on-chain volume by 100.0 to get m³.
   - The 100x factor is used but not documented against any spec.
   - **Resolution:** Cross-check against Datahub `/v2/types/{typeId}` volume values for known item types.

5. **OwnerCap resolution failure modes**
   - `GET_OBJECT_DYNAMICFIELD_CHARACTER_WITH_JSON` chains multiple extract calls. Silent nulls can occur at any step.
   - Behavior with wallets that have multiple characters, or no characters, is untested.
   - **Resolution:** Test with edge-case wallets (no character, multiple characters).

6. **Connected assemblies beyond 20**
   - Backend caps `get_network()` at 20 connected assemblies and sets `truncated: true` for the rest.
   - Whether any NetworkNode in the live game exceeds 20 connections is unknown.
   - **Resolution:** Query live NetworkNodes; implement cursor pagination if needed.

7. **Fuel burn timing drift**
   - `burn_start_time` and `previous_cycle_elapsed_time` are raw u64 strings from on-chain.
   - The backend computes `hours_remaining` from these, but the precision of the timing drift across block boundaries is unknown.
   - **Resolution:** Compare computed vs observed depletion over time in a running system.

8. **`_parse_status()` recursion depth**
   - Backend stops recursing into nested status objects at depth 3. The limit appears arbitrary.
   - Whether any Move struct nests status deeper than 3 levels is unknown.
   - **Resolution:** Inspect actual status objects on-chain across all assembly types.

---

## E. Backend Functions That Duplicate dapp-kit

See `docs/DAPP_KIT_BOUNDARY.md` for the full table and context. Summary:

| Python Function | dapp-kit Equivalent |
|----------------|---------------------|
| `_classify_assembly_type()` | `getAssemblyType()` |
| `_parse_status()` | `parseStatus()` |
| `get_character()` | `getWalletCharacters()` |
| `get_character_assemblies()` | `getCharacterAndOwnedObjects()` |
| `get_energy_config()` | `getEnergyConfig()` |
| `get_fuel_config()` | `getFuelEfficiencyConfig()` |
| `_parse_config_nodes()` | `parseConfig()` in dapp-kit config.ts |
| `_extract_fuel()` | inline in transforms.ts |
| `_extract_energy()` | inline in transforms.ts |

These duplications exist because the backend is Python and cannot import dapp-kit (Node.js/TypeScript). They work. Do not delete them mid-project. Do not add more.

`compute_fuel_state()` is NOT a duplication — it computes derived metrics (`hours_remaining`, `burn_rate_units_per_hr`) that dapp-kit does not expose.

---

## F. Raw On-Chain Data Schema (RawSuiObjectData)

**Source:** `frontend/node_modules/@evefrontier/dapp-kit/graphql/types.ts` lines 367–419

### Top-Level Fields

| Field | Type | Present On | Notes |
|-------|------|------------|-------|
| `id` | string | All | Sui object ID (0x...) |
| `type_id` | string | All | Game type ID (u64 as string) |
| `extension` | unknown | All | Never parsed. Purpose UNKNOWN. |
| `inventory_keys` | string[] \| undefined | SmartStorageUnit | Keys for inventory dynamic field containers |
| `linked_gate_id` | string \| undefined | SmartGate | Destination gate Sui object ID |
| `energy_source_id` | string \| undefined | Non-NetworkNode types | Parent NetworkNode Sui object ID |
| `key` | `{item_id: string, tenant: string}` \| undefined | All | Deterministic game key |
| `location` | `{location_hash: string, structure_id: string}` \| undefined | All | Hashed location — not raw coordinates |
| `metadata` | `{assembly_id, description, name, url}` \| undefined | All | User-set name/description/dapp URL |
| `owner_cap_id` | string \| undefined | All | OwnerCap object ID |
| `status` | `{assembly_id?, item_id?, status: {"@variant": string}, type_id?}` \| undefined | All | State enum wrapper |
| `fuel` | `{max_capacity, burn_rate_in_ms, type_id, unit_volume, quantity, is_burning, previous_cycle_elapsed_time, burn_start_time, last_updated}` | NetworkNode | All values are strings (u64 on-chain) |
| `energy_source` | `{max_energy_production, current_energy_production, total_reserved_energy}` | NetworkNode | All values are strings |
| `connected_assembly_ids` | string[] \| undefined | NetworkNode | Sui IDs of assemblies powered by this node |

### dynamicFields Structure

All types share the same container shape:

```
dynamicFields?: {
  nodes: Array<{
    contents: {
      json: Record<string, unknown>;
      type: { layout: string };
    };
    name: {
      json: unknown;
      type: { repr: string };
    };
  }>
}
```

### dynamicFields Content by Type

| Type | Contents | Structure |
|------|----------|-----------|
| SmartStorageUnit | Inventory Field containers | `{id, name, value: {max_capacity, used_capacity, items: {contents: [{key: type_id_str, value: {type_id, quantity, volume, ...}}]}}}` |
| SmartGate | UNKNOWN | May be empty |
| SmartTurret | UNKNOWN | May be empty |
| NetworkNode | UNKNOWN | May store fuel burn history |
| Manufacturing | UNKNOWN | May store production queue or recipes |
| Refinery | UNKNOWN | May store processing state |

### Datahub API

**Base URL:** `https://datahub.evefrontier.com` (from constants.ts)

**Endpoint:** `GET /v2/types/{typeId}`

**Returns (DatahubGameInfo):** `typeId, name, description, groupName, groupId, categoryName, categoryId, volume, iconUrl, mass`

**TYPEIDS constants** (from constants.ts — exact values verified):
- Used as lookup keys for known assembly type IDs
- Map game type IDs to human-readable assembly kind names

**EXCLUDED_TYPEIDS:** A set of type IDs excluded from certain listings (exact values in constants.ts — typically internal/system types not shown to players).
