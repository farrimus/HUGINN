# @evefrontier/dapp-kit API Reference

**Version:** 0.1.7  
**TypeDoc:** http://sui-docs.evefrontier.com/

**Import paths:**
- Hooks, utilities, types, providers: `@evefrontier/dapp-kit`
- GraphQL functions: `@evefrontier/dapp-kit/graphql`

All hooks throw if used outside `EveFrontierProvider`.

---

## Quick Reference

| Operation | Method | Import |
|-----------|--------|--------|
| Get assembly data | `useSmartObject()` | Main |
| Load assembly + owner | `getAssemblyWithOwner()` | `/graphql` |
| Assembly + resolved character owner | `getObjectAndCharacterOwner()` | `/graphql` |
| Transform to typed assembly | `transformToAssembly()` | Main |
| Type-safe narrowing | `assertAssemblyType()` | Main |
| Wallet connection | `useConnection()` | Main |
| Sponsored transaction | `useSponsoredTransaction()` | Main |
| Show notifications | `useNotification()` | Main |
| Get energy usage | `getEnergyUsageForType()` | Main |
| Get fuel efficiency | `getFuelEfficiencyForType()` | Main |
| Calculate burn rate | `getAdjustedBurnRate()` | Main |
| Get game metadata | `getDatahubGameInfo()` | Main |
| Format display values | `formatDuration()`, `formatM3()` | Main |
| Get explorer link | `getTxUrl()` | Main |
| Get character + objects | `getCharacterAndOwnedObjects()` | `/graphql` |
| Get wallet characters | `getWalletCharacters()` | `/graphql` |
| Resolve object ID from item ID | `getObjectId()` | Main |
| Get registry address | `getRegistryAddress()` | Main |
| Parse error from message | `parseErrorFromMessage()` | Main |
| Check wallet sponsor support | `walletSupportsSponsoredTransaction()` | Main |
| Get assembly API string | `getAssemblyTypeApiString()` | Main |

---

## Hooks

Hooks provide reactive access to wallet state, smart objects, notifications, and sponsored transactions. All hooks must be used within the `EveFrontierProvider`.

### useConnection()

Hook for managing wallet connection state. Auto-detects EVE Vault wallet availability. Persists connection in localStorage (`eve-dapp-connected`).

**Return type:**

```typescript
interface VaultContextType {
  currentAccount: WalletAccount | null;
  walletAddress: string | undefined;
  isConnected: boolean;
  hasEveVault: boolean;
  handleConnect: () => void;
  handleDisconnect: () => void;
}
```

- `currentAccount` — The currently connected wallet account (`null` if not connected)
- `walletAddress` — The connected wallet's address string (`undefined` if not connected)
- `isConnected` — Boolean connection status
- `hasEveVault` — Whether EVE Vault wallet is available
- `handleConnect()` — Opens wallet modal
- `handleDisconnect()` — Disconnects the wallet

---

### useSmartObject()

Hook for accessing smart assembly data from the Sui GraphQL Indexer. Polls for updates automatically.

**Assembly ID resolution:**
1. URL query parameter `?itemId=` (parsed as non-negative integer)
2. Environment variable `VITE_OBJECT_ID` (direct Sui object ID)
3. Fallback: no ID (loading state)

**Tenant resolution:** URL query parameter `?tenant=` with fallback to `DEFAULT_TENANT`.

**Polling:** Runs every `POLLING_INTERVAL` (10s). Only polls when wallet is connected and a valid ID is available. Uses content hash comparison to avoid unnecessary state updates.

**Return type:**

```typescript
interface SmartObjectContextType {
  tenant: string;
  assembly: AssemblyType<Assemblies> | null;
  assemblyOwner: DetailedSmartCharacterResponse | null;
  loading: boolean;
  error: string | null;
  refetch: () => Promise<void>;
}
```

**Assembly module properties by type:**

| Type | Module field | Contents |
|------|-------------|----------|
| `SmartStorageUnit` | `.storage` | `StorageModule` |
| `SmartTurret` | `.turret` | `TurretModule` (empty) |
| `SmartGate` | `.gate` | `GateModule` |
| `NetworkNode` | `.networkNode` | `NetworkNodeModule` |
| `Refinery` | `.refinery` | `RefineryModule` (empty) |
| `Manufacturing` | `.manufacturing` | `ManufacturingModule` (empty) |
| `Assembly` | — | base only |

All assembly types share the `DetailedAssemblyResponse` base (see Types section).

---

### useNotification()

Hook for displaying user notifications.

**Return type:**

```typescript
interface NotificationContextType {
  notify: (notification: {
    type: Severity;
    txHash?: string;
    message?: string;
  }) => void;
  notification: NotificationState;
  handleClose: () => void;
}

interface NotificationState {
  message: string;
  txHash: string;   // empty string when not provided
  severity: Severity;
  handleClose: () => void;
  isOpen: boolean;
}
```

---

### useSponsoredTransaction()

React Query mutation for gas-sponsored transactions. Requires EVE Vault (wallet must support `evefrontier:sponsoredTransaction`).

**Input (passed to `mutate` or `mutateAsync`):**

```typescript
type UseSponsoredTransactionArgs = {
  txAction: SponsoredTransactionActions;
  assembly: AssemblyType<Assemblies>;  // REQUIRED
  tenant?: string;     // Optional: resolved from URL ?tenant= → fallback "testevenet"
  account?: string;
  metadata?: {
    name?: string;
    description?: string;
    url?: string;
  };
}
```

**Tenant resolution (when omitted):**
1. `tenant` parameter
2. URL query parameter `?tenant=`
3. Fallback: `"testevenet"`

**Assembly ID resolution (when `assembly.item_id` is missing):**
1. URL query parameter `?itemId=`
2. Throws `AssemblyIdRequiredError` if neither provides a valid ID

**Returns (React Query mutation result):**

```typescript
{
  mutate: (args: UseSponsoredTransactionArgs, options?) => void;
  mutateAsync: (args: UseSponsoredTransactionArgs) => Promise<SponsoredTransactionOutput>;
  isPending: boolean;
  isError: boolean;
  error: UseSponsoredTransactionError | null;
  data: SponsoredTransactionOutput | undefined;
}
```

**Error classes:**

```typescript
class WalletNotConnectedError extends Error {}
class WalletNoAccountSelectedError extends Error {}
class WalletSponsoredTransactionNotSupportedError extends Error {
  constructor(walletName?: string)
}
class AssemblyIdRequiredError extends Error {
  constructor(reason?: string)
}

type UseSponsoredTransactionError =
  | WalletSponsoredTransactionNotSupportedError
  | WalletNotConnectedError
  | WalletNoAccountSelectedError
  | AssemblyIdRequiredError
  | Error;
```

**Exported types:**

```typescript
type UseSponsoredTransactionArgs = SponsoredTransactionArgs;

type UseSponsoredTransactionMutationOptions = Omit<
  UseMutationOptions<
    SponsoredTransactionOutput,
    UseSponsoredTransactionError,
    UseSponsoredTransactionArgs
  >,
  "mutationFn"
>;
```

---

## Providers

### EveFrontierProvider

Wraps the app with all required providers. Must wrap the entire component tree.

```typescript
import { EveFrontierProvider } from '@evefrontier/dapp-kit';
import { QueryClient } from '@tanstack/react-query';

const queryClient = new QueryClient();

function App() {
  return (
    <EveFrontierProvider queryClient={queryClient}>
      <YourApp />
    </EveFrontierProvider>
  );
}
```

**Provider stack (in order):**
1. `QueryClientProvider` — React Query
2. `DAppKitProvider` — Sui blockchain client
3. `VaultProvider` — EVE Vault wallet + localStorage reconnect
4. `SmartObjectProvider` — GraphQL polling
5. `NotificationProvider` — User notifications

**Props:** `children` (required), `queryClient` (required, `QueryClient` instance)

### Individual providers

All individual providers and contexts are exported for advanced use:

- `VaultProvider` / `VaultContext`
- `SmartObjectProvider` / `SmartObjectContext`
- `NotificationProvider` / `NotificationContext`

---

## GraphQL

Import path: `import { ... } from '@evefrontier/dapp-kit/graphql'`

### Primary Functions

#### executeGraphQLQuery

Low-level executor for custom GraphQL queries.

```typescript
executeGraphQLQuery<T>(
  query: string,
  variables: Record<string, unknown>
): Promise<GraphQLResponse<T>>
```

Throws on HTTP errors. Returns `{ data?, errors? }`.

---

#### getAssemblyWithOwner

Primary function for loading assembly data. Fetches assembly, resolves owner character, and fetches related objects in one call. Pair with `transformToAssembly()`.

```typescript
getAssemblyWithOwner(
  assemblyId: string,
  packageId?: string
): Promise<{
  moveObject: {
    contents: {
      json: Record<string, unknown>;
      type?: { repr: string };
    };
    dynamicFields?: {
      nodes: DynamicFieldNode[];
    };
  } | null;
  assemblyOwner: CharacterInfo | null;
  energySource: RawSuiObjectData | null;
  destinationGate: RawSuiObjectData | null;
}>
```

- `assemblyId` — Sui object ID
- `packageId` — Optional; defaults to configured EVE World package
- `moveObject` — Assembly Move object with JSON contents and dynamic fields
- `assemblyOwner` — Parsed character info
- `energySource` — Energy source object (for network nodes)
- `destinationGate` — Linked gate object (for smart gates)

---

#### getWalletCharacters

Returns the most recent character owned by the wallet.

```typescript
getWalletCharacters(wallet: string): Promise<GraphQLResponse<GetWalletCharactersResponse>>
```

---

#### getCharacterAndOwnedObjects

Returns the wallet's most recent character and all objects owned by that character.

```typescript
getCharacterAndOwnedObjects(wallet: string): Promise<GraphQLResponse<GetCharacterAndOwnedObjectsResponse>>
```

---

### Object / Ownership Queries

| Function | Parameters | Returns |
|----------|-----------|---------|
| `getObjectByAddress(address)` | `address: string` | Object with BCS-encoded contents |
| `getObjectWithJson(address)` | `address: string` | Object with JSON-decoded contents (most common) |
| `getObjectWithDynamicFields(objectId)` | `objectId: string` | Object with dynamic fields as JSON nodes |
| `getObjectOwnerAndOwnedObjectsByType(address, type?)` | `address: string, type?: string` | Owner address + owned objects (BCS) |
| `getObjectOwnerAndOwnedObjectsWithJson(address, type?)` | `address: string, type?: string` | Owner address + owned objects (JSON) |
| `getObjectAndCharacterOwner(address, packageId?)` | `address: string, packageId?: string` | Assembly + resolved character owner chain |
| `getOwnedObjectsByType(owner, type?)` | `owner: string, type?: string` | Lightweight list of owned object addresses |
| `getOwnedObjectsByPackage(owner, packageId)` | `owner: string, packageId: string` | Full object data from specific package |
| `getSingletonObjectByType(objectType)` | `objectType: string` | First object of the type (singleton) |
| `getSingletonConfigObjectByType(objectType, tableName)` | `objectType: string, tableName: string` | Singleton config with dynamic field entries |
| `getObjectsByType(objectType, options?)` | `objectType: string, options?: { first?: number; after?: string }` | Paginated object list with `pageInfo` |

---

### Query Constants

All exported query string constants from `graphql/queries.ts`:

| Constant | Purpose |
|----------|---------|
| `GET_OBJECT_BY_ADDRESS` | Object with BCS-encoded contents |
| `GET_OBJECT_WITH_JSON` | Object with JSON-decoded contents |
| `GET_OBJECT_WITH_DYNAMIC_FIELDS` | Object with dynamic fields in JSON format |
| `GET_OBJECT_DYNAMICFIELD_CHARACTER_WITH_JSON` | Assembly with owner chain + character resolution — **internal, not a public export** |
| `GET_OBJECT_OWNER_AND_OWNED_OBJECTS_BY_TYPE` | Owner + owned objects (BCS) |
| `GET_OBJECT_OWNER_AND_OWNED_OBJECTS_WITH_JSON` | Owner + owned objects (JSON) |
| `GET_OWNED_OBJECTS_BY_TYPE` | Objects by address filtered by type |
| `GET_OWNED_OBJECTS_BY_PACKAGE` | Objects by address filtered by package |
| `GET_WALLET_CHARACTERS` | Most recent character owned by wallet |
| `GET_CHARACTER_AND_OWNED_OBJECTS` | Character + objects owned by character |
| `GET_SINGLETON_OBJECT_BY_TYPE` | First object of type |
| `GET_SINGLETON_CONFIG_OBJECT_BY_TYPE` | Singleton config with dynamic field table |
| `GET_OBJECTS_BY_TYPE` | All objects of type with pagination |

---

### GraphQL Response Types

#### GraphQLResponse

```typescript
interface GraphQLResponse<T = unknown> {
  data?: T;
  errors?: Array<{ message: string }>;
}
```

#### PageInfo

```typescript
interface PageInfo {
  hasNextPage: boolean;
  endCursor: string | null;
}
```

#### DynamicFieldNode

```typescript
interface DynamicFieldNode {
  contents: {
    json: Record<string, unknown>;
    type: { layout: string };
  };
  name: {
    json: unknown;
    type: { repr: string };
  };
}
```

#### RawSuiObjectData

Raw Sui object data for EVE Frontier objects (assemblies, network nodes, gates).

```typescript
interface RawSuiObjectData {
  id: string;
  type_id: string;
  extension: unknown;
  inventory_keys?: string[];
  linked_gate_id?: string;
  energy_source_id?: string;
  key?: { item_id: string; tenant: string };
  location?: { location_hash: string; structure_id: string };
  metadata?: { assembly_id: string; description: string; name: string; url: string };
  owner_cap_id?: string;
  status?: {
    assembly_id?: string;
    item_id?: string;
    status: { "@variant": string };
    type_id?: string;
  };
  fuel?: {
    max_capacity: string;
    burn_rate_in_ms: string;
    type_id: string;
    unit_volume: string;
    quantity: string;
    is_burning: boolean;
    previous_cycle_elapsed_time: string;
    burn_start_time: string;
    last_updated: string;
  };
  energy_source?: {
    max_energy_production: string;
    current_energy_production: string;
    total_reserved_energy: string;
  };
  connected_assembly_ids?: string[];
}
```

#### RawCharacterData

```typescript
interface RawCharacterData {
  id: `0x${string}`;
  key: { item_id: string; tenant: string };
  tribe_id: number;
  character_address: `0x${string}`;
  metadata: { assembly_id: `0x${string}`; name: string; description: string; url: string };
  owner_cap_id: `0x${string}`;
  [key: string]: unknown;
}
```

#### OwnerCapData

```typescript
interface OwnerCapData {
  authorized_object_id: string;
  id: string;
}
```

---

## Utilities

### Transformation

#### transformToAssembly

```typescript
async function transformToAssembly(
  objectId: string,
  moveObject: MoveObjectData,
  options?: TransformOptions
): Promise<AssemblyType<Assemblies> | null>
```

Transforms raw Sui Move object data to a typed assembly. Parses dynamic fields, inventory, fuel stats, and linked assemblies. Returns `null` if raw data is missing.

```typescript
interface TransformOptions {
  character?: CharacterInfo | null;
  datahubInfo?: DatahubGameInfo | null;
  energySource?: RawSuiObjectData | null;
  destinationGate?: RawSuiObjectData | null;
}
```

#### parseStatus

```typescript
function parseStatus(statusVariant: string | undefined): State
```

Converts raw status variant string to `State` enum. Maps `"ONLINE"`, `"OFFLINE"`/`"ANCHORED"`, `"UNANCHORED"`, `"DESTROYED"` to enum values; defaults to `State.NULL`.

#### getAssemblyType

```typescript
function getAssemblyType(typeRepr: string): Assemblies
```

Determines assembly type from Move object type tag (e.g. `'0x123::storage_unit::StorageUnit'` → `Assemblies.SmartStorageUnit`).

#### assertAssemblyType

```typescript
function assertAssemblyType(
  assembly: AssemblyType<Assemblies> | null,
  assemblyType: Assemblies
): assembly is AssemblyType<Assemblies>
```

Type guard for TypeScript narrowing to type-safe property access.

```typescript
if (assertAssemblyType(assembly, 'NetworkNode')) {
  assembly.networkNode.fuel  // TypeScript narrows here
}
```

#### getObjectId

```typescript
async function getObjectId(
  itemId: string,
  selectedTenant: string
): Promise<string>
```

Converts in-game item ID + tenant to Sui object ID via the AssemblyRegistry.

---

### Character

#### parseCharacterFromJson

```typescript
function parseCharacterFromJson(json: unknown): CharacterInfo | null
```

Normalizes raw character JSON into `CharacterInfo`. Returns `null` when input is not a usable object.

#### transformToCharacter

```typescript
function transformToCharacter(characterInfo: CharacterInfo): DetailedSmartCharacterResponse
```

Transforms `CharacterInfo` to `DetailedSmartCharacterResponse` with empty `smartAssemblies` and blank `portrait`.

#### getCharacterOwnedObjectsJson

```typescript
function getCharacterOwnedObjectsJson(
  data: GetCharacterAndOwnedObjectsResponse | undefined
): Record<string, unknown>[] | undefined
```

Extracts JSON payloads from the first character's owned objects. Returns `undefined` if missing or empty.

#### getCharacterOwnedObjects

```typescript
async function getCharacterOwnedObjects(
  address: string
): Promise<Record<string, unknown>[] | undefined>
```

Fetches character and owned objects via GraphQL, returns JSON payload array. Returns `undefined` if not found.

#### findOwnerByAddress

```typescript
function findOwnerByAddress(
  address1: string | undefined,
  address2: string | undefined
): boolean
```

Checks if two addresses match. Returns `false` if either is undefined or empty.

---

### Fuel & Energy

#### getEnergyUsageForType

```typescript
async function getEnergyUsageForType(typeId: number): Promise<number>
```

Returns energy usage per tick for assembly type. Cached after first fetch. Returns `0` if not found.

#### getFuelEfficiencyForType

```typescript
async function getFuelEfficiencyForType(typeId: number): Promise<number>
```

Returns fuel efficiency percentage (0–100) for fuel type. Cached after first fetch. Returns `0` if not found.

#### getAdjustedBurnRate

```typescript
function getAdjustedBurnRate(
  rawBurnTimeMs: number,
  efficiencyPercent: number | null | undefined
): AdjustedBurnRate
```

Returns efficiency-adjusted burn time per unit and units per hour. Treats invalid efficiency values (`null`, `undefined`, non-finite, ≤0, >100) as 100%.

```typescript
interface AdjustedBurnRate {
  burnTimePerUnitMs: number;
  unitsPerHour: number;
}
```

#### getEnergyConfig

```typescript
async function getEnergyConfig(): Promise<Record<number, number>>
```

Fetches EnergyConfig singleton from chain. Returns `typeId → energyUsage` map. Cached after first fetch.

#### getFuelEfficiencyConfig

```typescript
async function getFuelEfficiencyConfig(): Promise<Record<number, number>>
```

Fetches Fuel Efficiency Config singleton from chain. Returns `typeId → efficiency` map. Cached after first fetch.

---

### Datahub

#### getDatahubGameInfo

```typescript
async function getDatahubGameInfo(typeId: number): Promise<DatahubGameInfo>
```

Fetches game type metadata (name, description, icon, physical properties) from EVE Frontier Datahub by type ID. Resolves tenant from `window.location.search`.

---

### Formatting

| Function | Signature | Description |
|----------|-----------|-------------|
| `abbreviateAddress` | `(addr?: string, precision?: number, expanded?: boolean): string` | Shortens address to first/last N chars (e.g. `"0x123...abc"`). Pass `expanded: true` for full string. |
| `formatM3` | `(quantity: string \| bigint): number` | Converts wei-like volume (10^18) to m³. |
| `formatDuration` | `(seconds: number): string` | Duration to human-readable string (e.g. `"01d 02h 00m 15s"`). |
| `removeTrailingZeros` | `(number: string): string` | Trims trailing decimal zeros (e.g. `"1.5000"` → `"1.5"`). |
| `parseURL` | `(url: string): string` | Strips protocol prefix (`https://`, `http://`, `ftp://`). |
| `clickToCopy` | `(text: string): Promise<void>` | Copies text to clipboard. |
| `getVolumeM3` | `(quantity: bigint, volumePerUnit: bigint): number` | Total volume from quantity × unit volume (wei). |
| `getCommonItems` | `<T>(array1: T[], array2: T[]): T[]` | Returns elements present in both arrays. |

---

### Transaction & Misc

#### getTxUrl

```typescript
function getTxUrl(suiChain: string, txHash: string): string
```

Returns Suiscan explorer URL: `https://suiscan.xyz/{chain}/tx/{hash}`.

#### isOwner

```typescript
function isOwner(
  assembly: DetailedAssemblyResponse | SmartAssemblyResponse | null,
  account?: string
): boolean
```

Returns `true` if the account address matches the assembly's owner. Returns `false` if either is missing.

#### getDappUrl

```typescript
function getDappUrl(assembly: AssemblyType<Assemblies>): string
```

Returns the dApp URL for an assembly, ensuring `https://` prefix. Returns empty string if no `dappURL` is set.

#### getEnv

```typescript
function getEnv(env: string, fallback: string): string
```

Returns the env value or fallback if empty.

---

### Errors

#### ERRORS

```typescript
type ErrorType = {
  code: number;
  name: string;
  patterns: string[];
  message: string;
};

const ERRORS: Record<number | string, ErrorType>
```

Predefined error codes and string aliases:

| Code | Alias | Message |
|------|-------|---------|
| 1001 | `UNKNOWN_ERROR` | "Unknown error" |
| 1002 | — | "Network error" |
| 1003 | — | "Invalid input error" |
| 2001 | `CONTRACT_CALL` | "Contract call error" |
| 2002 | — | "Contract deployment error" |
| 2003 | — | "World resource not found" |
| 2004 | `ABI_FUNCTION_NOT_FOUND` | "ABI function not found" |
| 2005 | `FORWARDER_NOT_FOUND` | "ERC2771 Forwarder contract not found" |
| 2006 | `CALLFROM_NOT_FOUND` | "callFrom function not found" |
| 2007 | — | "ABI encoding bytes size mismatch" |
| 2008 | — | "Contract revert error" |
| 3001 | — | "Insufficient gas" |
| 3002 | `INSUFFICIENT_EVE` | "Insufficient EVE" |
| 3003 | — | "User denied transaction" |
| 3004 | — | "Transaction timeout" |
| 4001 | — | "Unauthorized access" |
| 4002 | — | "User not logged in" |
| 4003 | — | "Chain mismatch" |
| 5001 | `LENS_UNAVAILABLE` | "No lenses available" |

#### ERROR_MESSAGES

```typescript
const ERROR_MESSAGES: Record<number, string>
```

Lookup table of error code → message string (derived from `ERRORS`).

#### parseErrorFromMessage

```typescript
function parseErrorFromMessage(errorMessage: string): {
  code: number;
  name: string;
  patterns: string[];
}
```

Matches an error message against known patterns. Defaults to code 1001 (Unknown Error) if no pattern matches.

---

### Configuration Helpers

Functions returning fully-qualified Move type strings from the EVE World package, or other on-chain/env config.

| Function | Returns |
|----------|---------|
| `getEveWorldPackageId()` | Package ID from `VITE_EVE_WORLD_PACKAGE_ID` (throws if unset) |
| `getCharacterOwnerCapType()` | `'{pkg}::access::OwnerCap<{pkg}::character::Character>'` |
| `getObjectRegistryType()` | `'{pkg}::object_registry::ObjectRegistry'` |
| `getEnergyConfigType()` | `'{pkg}::energy::EnergyConfig'` |
| `getFuelEfficiencyConfigType()` | `'{pkg}::fuel::FuelConfig'` |
| `getCharacterPlayerProfileType()` | `'{pkg}::character::PlayerProfile'` |
| `getSuiGraphqlEndpoint(env?)` | GraphQL URL for `testnet`/`devnet`/`mainnet`; unknown → testnet |
| `getEveCoinType(tenantId)` | `'{evePackageId}::EVE::EVE'` |

#### getRegistryAddress

```typescript
async function getRegistryAddress(packageId?: string): Promise<string>
```

Fetches the AssemblyRegistry singleton address for the given package ID. Cached per package to support multiple tenants in the same session. Uses `getEveWorldPackageId()` if `packageId` is not provided.

---

### Constants

#### ONE_M3

```typescript
const ONE_M3 = 1000000000000000000  // 1e18 — wei to m³ conversion
```

#### POLLING_INTERVAL

```typescript
const POLLING_INTERVAL = 10000  // 10 seconds
```

#### STORAGE_KEYS

```typescript
const STORAGE_KEYS = { CONNECTED: "eve-dapp-connected" }
```

#### SUI_GRAPHQL_NETWORKS / GRAPHQL_ENDPOINTS

```typescript
const SUI_GRAPHQL_NETWORKS = ["testnet", "devnet", "mainnet"] as const;
type SuiGraphqlNetwork = "testnet" | "devnet" | "mainnet";
const DEFAULT_GRAPHQL_NETWORK: SuiGraphqlNetwork = "testnet";

const GRAPHQL_ENDPOINTS: Record<SuiGraphqlNetwork, string> = {
  testnet: "https://graphql.testnet.sui.io/graphql",
  devnet: "https://graphql.devnet.sui.io/graphql",
  mainnet: "https://graphql.mainnet.sui.io/graphql",
};
```

#### TYPEIDS

```typescript
enum TYPEIDS {
  LENS             = 77518,
  TRANSACTION_CHIP = 79193,
  COMMON_ORE       = 77800,
  METAL_RICH_ORE   = 77810,
  SMART_STORAGE_UNIT = 77917,
  PROTOCOL_DEPOT   = 85249,
  GATEKEEPER       = 83907,
  SALT             = 83839,
  NETWORK_NODE     = 88092,
  PORTABLE_REFINERY = 87161,
  PORTABLE_PRINTER = 87162,
  PORTABLE_STORAGE = 87566,
  REFUGE           = 87160,
}
```

#### EXCLUDED_TYPEIDS

```typescript
const EXCLUDED_TYPEIDS = [
  TYPEIDS.PORTABLE_REFINERY,
  TYPEIDS.PORTABLE_PRINTER,
  TYPEIDS.PORTABLE_STORAGE,
  TYPEIDS.REFUGE,
]
```

Portable items not considered "real" structures — excluded from certain assembly operations.

#### Tenant constants

```typescript
type TenantId = "utopia" | "stillness" | "testevenet" | "nebula";
const DEFAULT_TENANT = "stillness";

interface TenantConfig {
  packageId: string;
  evePackageId: string;
  datahubHost: string;
}

const TENANT_CONFIG: Record<TenantId, TenantConfig> = {
  nebula: {
    packageId:    "0x353988e063b4683580e3603dbe9e91fefd8f6a06263a646d43fd3a2f3ef6b8c1",
    evePackageId: "0x6407060579895a8b30f7d30d2447046eb80ecc23f0c9acde09222b2a505583c9",
    datahubHost:  "world-api-nebula.test.evefrontier.tech",
  },
  testevenet: {
    packageId:    "0x353988e063b4683580e3603dbe9e91fefd8f6a06263a646d43fd3a2f3ef6b8c1",
    evePackageId: "0x6407060579895a8b30f7d30d2447046eb80ecc23f0c9acde09222b2a505583c9",
    datahubHost:  "world-api-testevenet.test.evefrontier.tech",
  },
  utopia: {
    packageId:    "0xd12a70c74c1e759445d6f209b01d43d860e97fcf2ef72ccbbd00afd828043f75",
    evePackageId: "0xf0446b93345c1118f21239d7ac58fb82d005219b2016e100f074e4d17162a465",
    datahubHost:  "world-api-utopia.uat.pub.evefrontier.com",
  },
  stillness: {
    packageId:    "0x28b497559d65ab320d9da4613bf2498d5946b2c0ae3597ccfda3072ce127448c",
    evePackageId: "0x2a66a89b5a735738ffa4423ac024d23571326163f324f9051557617319e59d60",
    datahubHost:  "world-api-stillness.live.tech.evefrontier.com",
  },
};

const DATAHUB_BY_TENANT:       Record<TenantId, string>   // datahubHost per tenant
const EVE_PACKAGE_ID_BY_TENANT: Record<TenantId, string>  // evePackageId per tenant
const KNOWN_EVE_COIN_TYPES:    Set<string>                 // all valid "{evePackageId}::EVE::EVE" values
```

---

## Types & Enums

### Enums

```typescript
// Assembly lifecycle states — NOTE: NULL and UNANCHORED are uppercase
enum State {
  NULL       = "NULL",
  UNANCHORED = "UNANCHORED",
  ANCHORED   = "anchored",
  ONLINE     = "online",
  DESTROYED  = "destroyed",
}

// Available operations on assemblies
enum ActionTypes {
  UNANCHOR     = "Unanchor",
  ANCHOR       = "Anchor",
  BRING_ONLINE = "Online unit",
  BRING_OFFLINE = "Offline unit",
  DESTROY      = "Destroy",
}

// Assembly type discriminator
enum Assemblies {
  SmartStorageUnit = "SmartStorageUnit",
  SmartTurret      = "SmartTurret",
  SmartGate        = "SmartGate",
  NetworkNode      = "NetworkNode",
  Manufacturing    = "Manufacturing",
  Refinery         = "Refinery",
  Assembly         = "Assembly",
}

// Notification severity
enum Severity {
  Error   = "error",
  Warning = "warning",
  Info    = "info",
  Success = "success",
}

// URL query parameter keys
enum QueryParams {
  ITEM_ID = "itemId",
  TENANT  = "tenant",
}

// Supported wallet names
enum SupportedWallets {
  EVE_VAULT                 = "Eve Vault",
  EVE_FRONTIER_CLIENT_WALLET = "EVE Frontier Client Wallet",
}

// Sponsored transaction action strings
enum SponsoredTransactionActions {
  BRING_ONLINE     = "online",
  BRING_OFFLINE    = "offline",
  /** @deprecated Use UPDATE_METADATA instead */
  EDIT_UNIT        = "edit-unit",
  UPDATE_METADATA  = "update-metadata",
  LINK_SMART_GATE  = "link-smart-gate",
  UNLINK_SMART_GATE = "unlink-smart-gate",
}
```

---

### Assembly Types

```typescript
// Base assembly properties (all types)
interface SmartAssemblyResponse {
  id: string;
  item_id: number;
  type: Assemblies;
  typeDetails?: DatahubGameInfo;
  name: string;
  state: State;
  character?: SmartCharacterResponse;
  solarSystem?: SolarSystem;
  isParentNodeOnline?: boolean;
  energySourceId?: string;
  energyUsage: number;
  typeId: number;
  _raw?: MoveObjectData;
  _options?: TransformOptions;      // stored transform context
}

// Adds description and dapp URL
interface DetailedAssemblyResponse extends SmartAssemblyResponse {
  description: string;
  dappURL: string;
}

// Generic type mapping assembly kind to its module shape
type AssemblyType<T extends Assemblies> = {
  [K in T]:
    K extends Assemblies.SmartStorageUnit ? AssemblyProperties<K> & { storage: StorageModule }
    : K extends Assemblies.SmartTurret    ? AssemblyProperties<K> & { turret: TurretModule }
    : K extends Assemblies.SmartGate      ? AssemblyProperties<K> & { gate: GateModule }
    : K extends Assemblies.NetworkNode    ? AssemblyProperties<K> & { networkNode: NetworkNodeModule }
    : K extends Assemblies.Refinery       ? AssemblyProperties<K> & { refinery: RefineryModule }
    : K extends Assemblies.Manufacturing  ? AssemblyProperties<K> & { manufacturing: ManufacturingModule }
    : K extends Assemblies.Assembly       ? AssemblyProperties<K>
    : never;
}[T];
```

---

### Module Types

```typescript
interface StorageModule {
  mainInventory: {
    capacity: string;        // string, not number
    usedCapacity: string;    // string, not number
    items: InventoryItem[];
  };
  ephemeralInventories: EphemeralInventory[];
}

interface GateModule {
  destinationId: string | undefined;
  destinationGate: RawSuiObjectData | null;
}

interface NetworkNodeModule {
  fuel: FuelResponse;
  energyProduction: number;
  energyMaxCapacity: number;
  totalReservedEnergy: number;
  linkedAssemblies: SmartAssemblyResponse[];
}

interface TurretModule {}       // reserved
interface ManufacturingModule {}// reserved
interface RefineryModule {}     // reserved
```

---

### Fuel & Burn Types

```typescript
interface FuelResponse {
  quantity: number;
  burnTimeInMs: number;
  burnStartTime: number;
  isBurning: boolean;
  lastUpdated: number;
  maxCapacity: number;
  previousCycleElapsedTime: number;
  unitVolume: number;
  typeId: number;
}

interface BurnResponse {
  isBurning: boolean;
  startTime: string;
}
```

---

### Character Types

```typescript
// Raw character from World API (used in SmartAssemblyResponse.character)
interface SmartCharacterResponse {
  address: string;
  id: string;
  name: string;
  tribeId: number;
  characterId: number;
}

// Parsed character info returned by GraphQL ownership functions
interface CharacterInfo {
  address: string;
  id: string;
  name: string;
  tribeId: number;
  characterId: number;
  _raw?: RawCharacterData;
}

// Enriched character with assembly list (returned by transformToCharacter)
interface DetailedSmartCharacterResponse {
  address: string;
  name: string;
  id: string;
  tribeId: number;
  smartAssemblies: Assemblies[];
  portrait: string;
}
```

---

### Inventory Types

```typescript
interface InventoryItem {
  id: string;
  item_id: string;
  location: { location_hash: string };
  quantity: number;
  tenant: string;
  type_id: number;
  name: string;
}

interface EphemeralInventory {
  ownerId: string;
  ownerName: string;
  storageCapacity: bigint;
  usedCapacity: bigint;
  ephemeralInventoryItems: InventoryItem[];
}
```

---

### Location & Game Data

```typescript
interface SolarSystem {
  id: number;
  name: string;
  location: { x: number; y: number; z: number };
}

interface DatahubGameInfo {
  id: number;
  name: string;
  description: string;
  mass: number;
  radius: number;
  volume: number;
  portionSize: number;
  groupName: string;
  groupId: number;
  categoryName: string;
  categoryId: number;
  iconUrl: string;
}
```

---

### Sponsored Transaction Types

```typescript
// Low-level input used by the wallet feature
interface SponsoredTransactionInput {
  txAction: SponsoredTransactionActions;
  assembly: AssemblyType<Assemblies>["item_id"];  // item_id number
  tenant: string;
  assemblyType: SponsoredTransactionAssemblyType;
  metadata?: SponsoredTransactionMetadata;
}

// Higher-level args used by useSponsoredTransaction hook
type SponsoredTransactionArgs = Omit<
  SponsoredTransactionInput,
  "assembly" | "assemblyType" | "account" | "tenant"
> & {
  assembly: AssemblyType<Assemblies>;  // full assembly object
  account?: string;
  tenant?: string;
  txAction: SponsoredTransactionActions;
  metadata?: SponsoredTransactionMetadata;
};

interface SponsoredTransactionMetadata {
  name?: string;
  description?: string;
  url?: string;
}

interface SponsoredTransactionOutput {
  digest: string;
  effects?: string;
  rawEffects?: number[];
}

type SponsoredTransactionMethod = (
  input: SponsoredTransactionInput
) => Promise<SponsoredTransactionOutput>;

// Hook-level type aliases
type UseSponsoredTransactionArgs = SponsoredTransactionArgs;
type UseSponsoredTransactionError =
  | WalletSponsoredTransactionNotSupportedError
  | WalletNotConnectedError
  | WalletNoAccountSelectedError
  | AssemblyIdRequiredError
  | Error;
type UseSponsoredTransactionMutationOptions = Omit<
  UseMutationOptions<SponsoredTransactionOutput, UseSponsoredTransactionError, UseSponsoredTransactionArgs>,
  "mutationFn"
>;
```

---

### Context Types

```typescript
interface VaultContextType {
  currentAccount: WalletAccount | null;
  walletAddress: string | undefined;
  hasEveVault: boolean;
  isConnected: boolean;
  handleConnect: () => void;
  handleDisconnect: () => void;
}

interface SmartObjectContextType {
  tenant: string;
  assembly: AssemblyType<Assemblies> | null;
  assemblyOwner: DetailedSmartCharacterResponse | null;
  loading: boolean;
  error: string | null;
  refetch: () => Promise<void>;
}

interface NotificationContextType {
  notify: (notification: { type: Severity; txHash?: string; message?: string }) => void;
  notification: NotificationState;
  handleClose: () => void;
}

interface NotificationState {
  message: string;
  txHash: string;
  severity: Severity;
  handleClose: () => void;
  isOpen: boolean;
}
```

---

## Wallet Feature Detection

### Check Wallet Support

```typescript
// Check if a Wallet object supports sponsored transactions (object feature format)
function walletSupportsSponsoredTransaction(wallet: Wallet): boolean

// Type guard: narrows features record to include EveFrontierSponsoredTransactionFeature
function hasSponsoredTransactionFeature(
  features: Record<string, unknown>
): features is Record<string, unknown> & EveFrontierSponsoredTransactionFeature

// Flexible check — supports both object and array feature formats
// Object form: features = { 'evefrontier:sponsoredTransaction': {...} }
// Array form:  features = ['evefrontier:sponsoredTransaction']
function supportsSponsoredTransaction(features: unknown): boolean
```

### Get Sponsored Transaction Method

```typescript
// Get method from a Wallet object (object feature format only)
function getSponsoredTransactionFeature(
  wallet: Wallet
): SponsoredTransactionMethod | undefined

// Get method with legacy and v2 wallet support
function getSponsoredTransactionMethod(
  wallet: Wallet | { features: unknown; name?: string; version?: string }
): SponsoredTransactionMethod | undefined
```

### EveFrontierSponsoredTransactionFeature

```typescript
const EVEFRONTIER_SPONSORED_TRANSACTION = "evefrontier:sponsoredTransaction";

interface EveFrontierSponsoredTransactionFeature {
  readonly "evefrontier:sponsoredTransaction": {
    readonly version: "1.0.0";
    signSponsoredTransaction: SponsoredTransactionMethod;
  };
}
```

### getAssemblyTypeApiString

```typescript
function getAssemblyTypeApiString(type: Assemblies): SponsoredTransactionAssemblyType
```

| Assembly Type | API String |
|---|---|
| `Assemblies.SmartStorageUnit` | `"storage-units"` |
| `Assemblies.SmartTurret` | `"turrets"` |
| `Assemblies.SmartGate` | `"gates"` |
| `Assemblies.NetworkNode` | `"network-nodes"` |
| `Assemblies.Manufacturing` | `"manufacturing"` |
| `Assemblies.Refinery` | `"refineries"` |
| `Assemblies.Assembly` | `"assemblies"` |

```typescript
const ASSEMBLY_TYPE_API_STRING: Record<Assemblies, string>
type SponsoredTransactionAssemblyType = (typeof ASSEMBLY_TYPE_API_STRING)[Assemblies];
```

---

## Configuration

### dAppKit

```typescript
import { dAppKit } from '@evefrontier/dapp-kit';
```

A configured Sui gRPC client instance (`createDAppKit()`). Used internally by the provider stack for network connectivity.

Supports:
- `testnet`: https://fullnode.testnet.sui.io:443
- `devnet`: https://fullnode.devnet.sui.io:443

### Environment Variables

```env
VITE_EVE_WORLD_PACKAGE_ID=0x...   # Required: EVE World package ID
VITE_OBJECT_ID=0x...              # Optional: Pre-set assembly Sui object ID
VITE_SUI_GRAPHQL_ENDPOINT=https:// # Optional: Override GraphQL endpoint
```

---

## Common Workflows

### Load and Type an Assembly

```typescript
import { getAssemblyWithOwner } from '@evefrontier/dapp-kit/graphql';
import { getDatahubGameInfo, transformToAssembly, assertAssemblyType } from '@evefrontier/dapp-kit';

const { moveObject, assemblyOwner, energySource, destinationGate }
  = await getAssemblyWithOwner(assemblyId);

const typeId = (moveObject.contents?.json as any)?.type_id;
const datahubInfo = await getDatahubGameInfo(parseInt(typeId, 10));

const assembly = await transformToAssembly(assemblyId, moveObject, {
  character: assemblyOwner, datahubInfo, energySource, destinationGate
});

if (assertAssemblyType(assembly, 'NetworkNode')) {
  const { quantity, burnTimeInMs } = assembly.networkNode.fuel;
  const { unitsPerHour } = getAdjustedBurnRate(burnTimeInMs, 80);
}
```

### Execute Sponsored Transaction

```typescript
function BringOnlineForm() {
  const { assembly } = useSmartObject();
  const { notify } = useNotification();
  const { mutateAsync: sendTx, isPending } = useSponsoredTransaction();

  const handleBringOnline = async () => {
    try {
      const result = await sendTx({
        txAction: SponsoredTransactionActions.BRING_ONLINE,
        assembly: assembly!,
      });
      notify({ type: Severity.Success, message: 'Online!', txHash: result.digest });
    } catch (err) {
      notify({ type: Severity.Error, message: err instanceof Error ? err.message : 'Failed' });
    }
  };

  return (
    <button onClick={handleBringOnline} disabled={isPending || !assembly}>
      {isPending ? 'Sending...' : 'Bring Online'}
    </button>
  );
}
```

### Execute Custom GraphQL Query

```typescript
import { executeGraphQLQuery, GET_WALLET_CHARACTERS } from '@evefrontier/dapp-kit/graphql';

const result = await executeGraphQLQuery(GET_WALLET_CHARACTERS, {
  owner: walletAddress,
  characterPlayerProfileType: getCharacterPlayerProfileType(),
});

if (result.data) {
  // process result.data
}
```
