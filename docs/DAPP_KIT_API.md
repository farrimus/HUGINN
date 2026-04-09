# Complete @evefrontier/dapp-kit API Reference

**Version:** 0.1.7
**Status:** Production-ready

This is the authoritative reference for all methods, hooks, utilities, types, and providers available in the dApp Kit. Use this when building dApps that interact with the builder scaffold.

---

## Table of Contents

1. [Hooks (React)](#hooks) — useConnection, useSmartObject, useNotification, useSponsoredTransaction
2. [Utilities](#utilities) — Formatting, assembly, transaction, transformation, energy, character
3. [GraphQL Queries](#graphql) — Object, character, assembly, singleton data loading
4. [Providers](#providers) — EveFrontierProvider, VaultProvider, SmartObjectProvider, NotificationProvider
5. [Types & Enums](#types) — TypeScript interfaces and discriminated unions
6. [Configuration](#config) — Network setup, constants, tenant configuration
7. [Wallet Features](#wallet) — Sponsored transaction detection and execution
8. [Error Handling](#errors) — Error types and categorization
9. [Common Workflows](#workflows) — Patterns for typical operations
10. [Quick Reference](#quick-ref) — Most-used methods

---

## 1. Hooks {#hooks}

### useConnection()

**Import:** `import { useConnection } from '@evefrontier/dapp-kit'`

Manages wallet connection state and provides connect/disconnect handlers.

**Returns:**
```typescript
{
  currentAccount: WalletAccount | null;           // Current wallet account
  walletAddress: string | undefined;              // Connected wallet address
  isConnected: boolean;                           // Connection status
  hasEveVault: boolean;                           // EVE Vault wallet available
  handleConnect: () => void;                      // Initiate wallet connection
  handleDisconnect: () => void;                   // Disconnect wallet
}
```

**Description:**
- Auto-detects EVE Vault wallet availability
- Opens wallet modal on `handleConnect()`
- Persists connection state in localStorage
- Updates on wallet connection changes

**Example:**
```tsx
function WalletButton() {
  const { isConnected, walletAddress, handleConnect, handleDisconnect } = useConnection();

  if (isConnected) {
    return (
      <div>
        <p>Connected: {walletAddress}</p>
        <button onClick={handleDisconnect}>Disconnect</button>
      </div>
    );
  }

  return <button onClick={handleConnect}>Connect Wallet</button>;
}
```

**Throws:** Error if used outside `EveFrontierProvider`

---

### useSmartObject()

**Import:** `import { useSmartObject } from '@evefrontier/dapp-kit'`

Provides reactive access to smart assembly/structure data from Sui GraphQL.

**Returns:**
```typescript
{
  tenant: string;                                 // Current tenant ID
  assembly: AssemblyType<Assemblies> | null;    // Transformed assembly (typed by enum)
  assemblyOwner: DetailedSmartCharacterResponse | null; // Owner character info
  loading: boolean;                              // Data fetch in progress
  error: string | null;                          // Error message if any
  refetch: () => Promise<void>;                  // Manual refresh
}
```

**How it Works:**
- Resolves assembly ID from URL params (`?itemId=`, `?tenant=`) or environment variable `VITE_OBJECT_ID`
- Automatically polls GraphQL every 10 seconds for updates
- Caches data and only updates state if content changed (hash comparison)
- Fetches datahub game info (metadata, icon, name, description)
- Transforms raw Sui Move objects to typed Assembly objects with module-specific properties

**Assembly Types (Discriminated Union):**
- `SmartStorageUnit` → `.storage.mainInventory` + `.storage.ephemeralInventories`
- `SmartTurret` → `.turret` module
- `SmartGate` → `.gate` module + `.destinationId`
- `NetworkNode` → `.networkNode` module + `.fuel` (burn rate, capacity, quantity)
- `Manufacturing` → `.manufacturing` module
- `Refinery` → `.refinery` module
- `Assembly` → Base type (no module)

**Example:**
```tsx
function AssemblyViewer() {
  const { assembly, assemblyOwner, loading, error } = useSmartObject();

  if (loading) return <div>Loading assembly...</div>;
  if (error) return <div>Error: {error}</div>;
  if (!assembly) return <div>No assembly selected</div>;

  return (
    <div>
      <h2>{assembly.name}</h2>
      <p>Owner: {assemblyOwner?.name}</p>
      <p>State: {assembly.state}</p>
      <p>Energy Usage: {assembly.energyUsage}</p>

      {assembly.type === 'SmartStorageUnit' && (
        <p>Capacity: {assembly.storage.mainInventory.capacity} m³</p>
      )}

      {assembly.type === 'NetworkNode' && (
        <p>Fuel burn: {assembly.fuel.burnTimeInMs}ms</p>
      )}
    </div>
  );
}
```

**Throws:** Error if used outside `EveFrontierProvider`

---

### useNotification()

**Import:** `import { useNotification } from '@evefrontier/dapp-kit'`

Simple in-app notification system for displaying messages to users.

**Returns:**
```typescript
{
  notify: (config: {
    type: Severity;                     // 'success' | 'error' | 'warning' | 'info'
    message?: string;                   // Message text
    txHash?: string;                    // Optional transaction hash for linking
  }) => void;

  notification: {
    isOpen: boolean;
    message: string;
    severity: Severity;
    txHash: string;
    handleClose: () => void;
  };
}
```

**Description:**
- Displays user-facing notifications (success, error, warning, info)
- Optionally links to transaction explorer with txHash
- Auto-formats success messages if txHash provided
- Provides default messages for each severity

**Example:**
```tsx
function SampleComponent() {
  const { notify } = useNotification();

  async function handleTransaction() {
    try {
      const result = await someTransaction();
      notify({
        type: 'success',
        message: 'Transaction successful!',
        txHash: result.digest
      });
    } catch (err) {
      notify({
        type: 'error',
        message: `Failed: ${err.message}`
      });
    }
  }

  return <button onClick={handleTransaction}>Send Tx</button>;
}
```

**Throws:** Error if used outside `EveFrontierProvider`

---

### useSponsoredTransaction()

**Import:** `import { useSponsoredTransaction } from '@evefrontier/dapp-kit'`

React Query mutation hook for executing gas-sponsored transactions on Sui. Only EVE Vault currently supports this.

**Parameters:**
```typescript
useSponsoredTransaction(options?: UseSponsoredTransactionMutationOptions)
```

**Returns (React Query Mutation):**
```typescript
{
  mutate: (args, options?) => void;              // Fire-and-forget
  mutateAsync: (args) => Promise<Output>;        // Promise-based
  isPending: boolean;                            // Transaction in progress
  isError: boolean;                              // Last call failed
  error: UseSponsoredTransactionError | null;   // Error details
  data: SponsoredTransactionOutput | undefined;  // Success result
}
```

**Input Arguments:**
```typescript
{
  txAction: SponsoredTransactionActions;         // Action (online, offline, update-metadata, link-gate, etc.)
  assembly: AssemblyType<Assemblies>;            // Full assembly object (must have type & item_id)
  chain?: string;                                // Optional chain (defaults from env)
  tenant?: string;                               // Optional tenant (defaults from URL param)
  account?: string;                              // Optional signer (defaults to connected wallet)
  metadata?: {
    name?: string;
    description?: string;
    url?: string;
  };
}
```

**Output:**
```typescript
{
  digest: string;                                // Transaction digest (on explorer)
  effects?: string;                              // BCS-encoded effects
  rawEffects?: number[];                         // Raw effect bytes
}
```

**Possible Actions:**
- `BRING_ONLINE` — Bring assembly online
- `BRING_OFFLINE` — Bring assembly offline
- `UPDATE_METADATA` — Update name/description
- `LINK_SMART_GATE` — Link destination gate
- `UNLINK_SMART_GATE` — Unlink gate

**Error Types:**
- `WalletNotConnectedError` — No wallet connected
- `WalletNoAccountSelectedError` — No account selected in wallet
- `WalletSponsoredTransactionNotSupportedError` — Wallet doesn't support feature
- `AssemblyIdRequiredError` — Assembly ID missing or invalid

**Example:**
```tsx
function BringOnlineButton() {
  const { assembly } = useSmartObject();
  const { mutateAsync: sendTx, isPending } = useSponsoredTransaction();

  async function handleBringOnline() {
    try {
      const result = await sendTx({
        txAction: 'online',
        assembly: assembly!,
        chain: 'sui:testnet'
      });
      console.log('Transaction:', result.digest);
    } catch (err) {
      console.error('Failed:', err.message);
    }
  }

  return (
    <button onClick={handleBringOnline} disabled={isPending || !assembly}>
      {isPending ? 'Sending...' : 'Bring Online'}
    </button>
  );
}
```

**Throws:** Error if used outside `EveFrontierProvider`

---

## 2. Utilities {#utilities}

### Formatting Utilities

#### abbreviateAddress(address, precision?, expanded?)
```typescript
abbreviateAddress('0x1234567890abcdef', 5, false)
// → '0x1234...cdef'
```
- **Parameters:** address (string), precision (default: 5), expanded (boolean)
- **Returns:** Abbreviated address string with ellipsis

#### formatM3(quantity)
```typescript
formatM3('1000000000000000000') // → 1 (converts from wei to m³)
```
- **Parameters:** quantity as string or bigint
- **Returns:** Volume in cubic meters

#### formatDuration(seconds)
```typescript
formatDuration(93615) // → '01d 02h 00m 15s'
```
- **Parameters:** Duration in seconds
- **Returns:** Human-readable string (days, hours, minutes, seconds)

#### removeTrailingZeros(number)
```typescript
removeTrailingZeros('1.5000') // → '1.5'
```
- **Returns:** String without trailing zeros after decimal

#### parseURL(url)
```typescript
parseURL('https://example.com/path') // → 'example.com/path'
```
- **Returns:** URL without protocol

#### clickToCopy(text)
```typescript
await clickToCopy('0x123...')
```
- **Returns:** Promise that resolves when copied to clipboard

---

### Assembly Utilities

#### isOwner(assembly, account?)
```typescript
if (isOwner(assembly, walletAddress)) {
  // User owns this assembly
}
```
- **Parameters:** Assembly object, optional account address to check
- **Returns:** Boolean

#### assertAssemblyType(assembly, type)
```typescript
if (assertAssemblyType(assembly, 'SmartStorageUnit')) {
  // TypeScript now knows assembly.storage exists
  console.log(assembly.storage.mainInventory.capacity);
}
```
- **Parameters:** Assembly object, expected type name
- **Returns:** Type guard for TypeScript narrowing

#### getDappUrl(assembly)
```typescript
const url = getDappUrl(assembly); // → 'https://example.com/dapp'
```
- **Returns:** Full dApp URL with https:// prefix

#### findOwnerByAddress(address1, address2)
```typescript
if (findOwnerByAddress(walletA, walletB)) {
  // Addresses match
}
```
- **Returns:** Boolean

#### getCommonItems(array1, array2)
```typescript
const common = getCommonItems([1,2,3], [2,3,4]); // → [2,3]
```
- **Returns:** Intersection of two arrays

---

### Transaction Utilities

#### getTxUrl(suiChain, txHash)
```typescript
const explorerUrl = getTxUrl('testnet', 'ABC123...XYZ');
// → 'https://suiscan.xyz/testnet/tx/ABC123...XYZ'
```
- **Returns:** Suiscan explorer URL for transaction

#### getVolumeM3(quantity, volumePerUnit)
```typescript
const totalVolume = getVolumeM3(100n, 1000000000000000000n); // 100 items × 1 m³
```
- **Parameters:** Quantity (bigint), volume per unit in wei (1e18)
- **Returns:** Total volume in m³

#### getEnv(envKey, fallback)
```typescript
const apiKey = getEnv('VITE_API_KEY', 'default-key');
```
- **Returns:** Environment variable value or fallback

---

### Mapping & Transformation Utilities

#### parseStatus(statusVariant)
```typescript
const state = parseStatus('Online');
// → State.ONLINE
```
- **Returns:** State enum (NULL, UNANCHORED, ANCHORED, ONLINE, DESTROYED)

#### getAssemblyType(moveTypeTag)
```typescript
const type = getAssemblyType('0x123::assembly::SmartStorageUnit');
// → Assemblies.SmartStorageUnit
```
- **Returns:** Assembly type enum

#### getRegistryAddress()
```typescript
const address = await getRegistryAddress(); // Cached
```
- **Returns:** Promise resolving to ObjectRegistry address

#### getObjectId(itemId, tenant)
```typescript
const suiObjectId = await getObjectId('12345', 'testevenet');
```
- **Parameters:** In-game item ID, tenant ID
- **Returns:** Promise resolving to derived Sui object ID

---

### Character Utilities

#### parseCharacterFromJson(json)
```typescript
const character = parseCharacterFromJson(rawGraphQLResponse);
```
- **Returns:** CharacterInfo object with normalized fields
  - `id, address, name, tribeId, characterId, _raw`

#### getCharacterOwnedObjectsJson(data)
```typescript
const objectJsons = getCharacterOwnedObjectsJson(characterData);
```
- **Parameters:** GraphQL response from getCharacterAndOwnedObjects
- **Returns:** Array of object contents.json payloads

#### getCharacterOwnedObjects(address)
```typescript
const objectJsons = await getCharacterOwnedObjects(walletAddress);
```
- **Returns:** Promise resolving to owned objects JSON array

---

### Transform Utilities

#### transformToCharacter(characterInfo)
```typescript
const response = transformToCharacter(rawCharacterInfo);
```
- **Returns:** DetailedSmartCharacterResponse with portrait and assemblies

#### transformToAssembly(objectId, moveObject, options?)
```typescript
const assembly = await transformToAssembly(
  '0x123...abc',
  moveObjectData,
  {
    character: characterInfo,
    datahubInfo: await getDatahubGameInfo(typeId),
    energySource: energySourceObject
  }
);
```
- **Parameters:**
  - `objectId` — Sui object address
  - `moveObject` — Move object data from GraphQL
  - `options`:
    - `character?: CharacterInfo` — Owner info
    - `datahubInfo?: DatahubGameInfo` — Game metadata
    - `energySource?: RawSuiObjectData` — Power source reference
    - `destinationGate?: RawSuiObjectData` — Gate destination
- **Returns:** Promise resolving to typed AssemblyType (or null)
- **Description:** Primary transformation function. Parses dynamic fields, inventory items, fuel stats, and network node linked assemblies.

---

### Energy & Fuel Configuration

#### getEnergyConfig()
```typescript
const config = await getEnergyConfig(); // Cached
// → { 1: 100, 2: 200, ... }
```
- **Returns:** Promise resolving to type_id → energy usage map

#### getEnergyUsageForType(typeId)
```typescript
const usage = await getEnergyUsageForType(1);
// → 100 (energy per tick)
```
- **Returns:** Promise resolving to energy usage value

#### getFuelEfficiencyConfig()
```typescript
const config = await getFuelEfficiencyConfig(); // Cached
// → { 1: 100, 2: 80, ... }
```
- **Returns:** Promise resolving to type_id → fuel efficiency map

#### getFuelEfficiencyForType(typeId)
```typescript
const efficiency = await getFuelEfficiencyForType(1);
// → 100 (0-100 scale)
```
- **Returns:** Promise resolving to efficiency percentage

#### getAdjustedBurnRate(rawBurnTimeMs, efficiencyPercent?)
```typescript
const adjusted = getAdjustedBurnRate(3600000, 80);
// → { burnTimePerUnitMs: 4500, unitsPerHour: 0.8 }
```
- **Parameters:** Burn time at 100% efficiency, efficiency percentage (0-100)
- **Returns:** `{ burnTimePerUnitMs: number, unitsPerHour: number }`
- **Description:** Adjusts burn rate for fuel efficiency

---

### Datahub Utilities

#### getDatahubGameInfo(typeId)
```typescript
const info = await getDatahubGameInfo(77917);
// → { id, name, description, mass, radius, volume, icon, group, category... }
```
- **Parameters:** In-game type ID
- **Returns:** Promise resolving to DatahubGameInfo object
  - `id, name, description, mass, radius, volume, portionSize`
  - `groupName, groupId, categoryName, categoryId`
  - `iconUrl` — Image URL for type icon
- **Description:** Fetches metadata from EVE Frontier Datahub API

---

### Error Handling

#### parseErrorFromMessage(errorMessage)
```typescript
const error = parseErrorFromMessage('Move module error in assembly...');
// → { code: 2001, name: 'ContractCallError', patterns: [...] }
```
- **Returns:** Parsed error object with code and name

**Known Error Codes:**
- 1001: Unknown Error
- 1002: Network Error
- 1003: Invalid Input Error
- 2001-2008: Contract errors
- 3001-3004: Transaction/Gas errors
- 4001-4003: Authorization errors
- 5001: Lens Unavailable

---

## 3. GraphQL Queries {#graphql}

All GraphQL functions are in `@evefrontier/dapp-kit/graphql`. The low-level executor and named query constants are importable from `@evefrontier/dapp-kit` directly.

**Import:** `import { getObjectWithJson, getAssemblyWithOwner, ... } from '@evefrontier/dapp-kit/graphql'`

### Low-Level Executor

#### executeGraphQLQuery(query, variables?)
```typescript
import { executeGraphQLQuery, GET_WALLET_CHARACTERS } from '@evefrontier/dapp-kit';

const result = await executeGraphQLQuery(GET_WALLET_CHARACTERS, {
  owner: walletAddress,
  characterPlayerProfileType: profileType,
});
```
- **Parameters:** A named query constant (e.g. `GET_WALLET_CHARACTERS`) and a variables object
- **Returns:** Raw GraphQL response `{ data, errors }`
- **Use when:** You need direct query execution outside of the React hook lifecycle (e.g. in a `useEffect` or async helper)

#### GET_WALLET_CHARACTERS
```typescript
import { GET_WALLET_CHARACTERS } from '@evefrontier/dapp-kit';
```
- Named query constant for fetching a character by wallet address and character profile type
- Pass to `executeGraphQLQuery()` with `{ owner: walletAddress, characterPlayerProfileType: profileType }`
- Used in `useSession.ts` and `EntityContext.tsx` for tenant-aware character name resolution

---

### Object Queries

#### getObjectByAddress(address)
```typescript
const { data, errors } = await getObjectByAddress('0x123...');
// Raw BCS-encoded data
```
- **Returns:** Object with BCS contents

#### getObjectWithJson(address)
```typescript
const { data } = await getObjectWithJson('0x123...');
// JSON-decoded contents available
```
- **Returns:** Object with JSON-decoded data (most common)

#### getObjectWithDynamicFields(objectId)
```typescript
const { data } = await getObjectWithDynamicFields('0x123...');
// Includes all dynamic field data
```
- **Returns:** Object contents and dynamic fields (inventory, config, etc.)

---

### Ownership Queries

#### getObjectOwnerAndOwnedObjectsByType(objectAddress, ownedObjectType?)
```typescript
const { data } = await getObjectOwnerAndOwnedObjectsByType(
  '0x123...',
  '0x456::item::Item' // optional type filter
);
```
- **Returns:** Owner info and owned objects (BCS format)

#### getObjectOwnerAndOwnedObjectsWithJson(objectAddress, ownedObjectType?)
```typescript
const { data } = await getObjectOwnerAndOwnedObjectsWithJson('0x123...');
```
- **Returns:** Owner info and owned objects (JSON format)

#### getOwnedObjectsByType(owner, objectType?)
```typescript
const { data } = await getOwnedObjectsByType(
  walletAddress,
  '0x123::item::Item'
);
```
- **Returns:** Lightweight list of owned object addresses

#### getOwnedObjectsByPackage(owner, packageId)
```typescript
const { data } = await getOwnedObjectsByPackage(walletAddress, '0x123');
```
- **Returns:** Full object data from specific package

---

### Character Queries

#### getWalletCharacters(wallet)
```typescript
const { data } = await getWalletCharacters(walletAddress);
// Most recent character
```
- **Returns:** Character info for wallet

#### getCharacterAndOwnedObjects(wallet)
```typescript
const { data } = await getCharacterAndOwnedObjects(walletAddress);
// { character, ownedObjects: [...] }
```
- **Returns:** Character and all owned objects in one query

---

### Assembly-Specific Queries

#### getObjectAndCharacterOwner(objectAddress)
```typescript
const { data } = await getObjectAndCharacterOwner(assemblyId);
// { moveObject, assemblyOwner }
```
- **Returns:** Assembly and resolved character owner

#### getAssemblyWithOwner(assemblyId)
```typescript
const { moveObject, assemblyOwner, energySource, destinationGate }
  = await getAssemblyWithOwner(assemblyId);
```
- **Returns:**
  - `moveObject` — Assembly with JSON contents and dynamic fields
  - `assemblyOwner: CharacterInfo | null` — Owner character info
  - `energySource: RawSuiObjectData | null` — Power source
  - `destinationGate: RawSuiObjectData | null` — Gate destination
- **Description:** **PRIMARY function for loading assembly data.** Fetches assembly, resolves owner, and fetches related references in one call. Pairs perfectly with `transformToAssembly()`.

**Typical Workflow:**
```typescript
const { moveObject, assemblyOwner } = await getAssemblyWithOwner(assemblyId);
const typed = await transformToAssembly(assemblyId, moveObject, {
  character: assemblyOwner
});
```

---

### Singleton Queries

#### getSingletonObjectByType(objectType)
```typescript
const { data } = await getSingletonObjectByType('0x123::config::EnergyConfig');
```
- **Returns:** Singleton object address

#### getSingletonConfigObjectByType(objectType, tableName)
```typescript
const { data } = await getSingletonConfigObjectByType(
  getEnergyConfigType(),
  'assembly_energy'
);
```
- **Parameters:**
  - `objectType` — Full Move type (use getter functions)
  - `tableName` — Table path to extract
- **Returns:** Config object with dynamic fields

#### getObjectsByType(objectType, options?)
```typescript
const { data } = await getObjectsByType(
  '0x123::item::Item',
  { first: 50, after: 'cursor' }
);
```
- **Parameters:**
  - `objectType` — Full Move type
  - `options.first` — Results per page (default: 50)
  - `options.after` — Pagination cursor
- **Returns:** Paginated object list

---

## 4. Providers {#providers}

### EveFrontierProvider (Root)

**Import:** `import { EveFrontierProvider } from '@evefrontier/dapp-kit'`

**Props:**
```typescript
{
  children: ReactNode;
  queryClient: QueryClient;  // From @tanstack/react-query
}
```

**Description:** Root provider wrapping your entire app with:
1. QueryClientProvider (React Query)
2. DAppKitProvider (Sui blockchain)
3. VaultProvider (wallet)
4. SmartObjectProvider (assembly data)
5. NotificationProvider (notifications)

**Example:**
```typescript
import { EveFrontierProvider } from '@evefrontier/dapp-kit';
import { QueryClient } from '@tanstack/react-query';

const queryClient = new QueryClient();

function App() {
  return (
    <EveFrontierProvider queryClient={queryClient}>
      <MyDapp />
    </EveFrontierProvider>
  );
}
```

---

### VaultProvider

**Features:**
- Reconnects to wallet persisted in localStorage (`eve-dapp-connected` key)
- EVE Vault wallet detection
- localStorage persistence (`eve-dapp-connected` key)
- Integration with @mysten/dapp-kit-react

---

### SmartObjectProvider

**Features:**
- Fetches assembly and owner character data
- Automatic GraphQL polling (10-second interval)
- Resolves assembly ID from URL params (`?itemId=`, `?tenant=`) or environment
- Data hashing optimization (only updates if content changed)
- Fetches datahub game metadata
- Transforms data to typed Assembly objects

---

### NotificationProvider

**Features:**
- Manages notification state (open, message, severity)
- Transaction hash linking
- Default messages for each severity
- Auto-formats success messages

---

## 5. Types & Enums {#types}

**Import:** `import type { ... } from '@evefrontier/dapp-kit'` or `import { ... } from '@evefrontier/dapp-kit/types'`

### Enums

#### State
```typescript
enum State {
  NULL = 'null',
  UNANCHORED = 'unanchored',
  ANCHORED = 'anchored',
  ONLINE = 'online',
  DESTROYED = 'destroyed'
}
```

#### Assemblies (Assembly Types)
```typescript
type Assemblies =
  | 'SmartStorageUnit'
  | 'SmartTurret'
  | 'SmartGate'
  | 'NetworkNode'
  | 'Manufacturing'
  | 'Refinery'
  | 'Assembly'
```

#### Severity (Notifications)
```typescript
type Severity = 'error' | 'warning' | 'info' | 'success'
```

#### SponsoredTransactionActions
```typescript
enum SponsoredTransactionActions {
  BRING_ONLINE = 'online',
  BRING_OFFLINE = 'offline',
  UPDATE_METADATA = 'update-metadata',
  LINK_SMART_GATE = 'link-smart-gate',
  UNLINK_SMART_GATE = 'unlink-smart-gate'
}
```

---

### Context Types

#### VaultContextType
```typescript
{
  currentAccount: WalletAccount | null;
  walletAddress: string | undefined;
  hasEveVault: boolean;
  isConnected: boolean;
  handleConnect: () => void;
  handleDisconnect: () => void;
}
```

#### SmartObjectContextType
```typescript
{
  tenant: string;
  assembly: AssemblyType<Assemblies> | null;
  assemblyOwner: DetailedSmartCharacterResponse | null;
  loading: boolean;
  error: string | null;
  refetch: () => Promise<void>;
}
```

#### NotificationContextType
```typescript
{
  notify: (config: {
    type: Severity;
    message?: string;
    txHash?: string;
  }) => void;

  notification: {
    isOpen: boolean;
    message: string;
    severity: Severity;
    txHash: string;
    handleClose: () => void;
  };
}
```

---

### Assembly & Character Types

#### DetailedSmartCharacterResponse
```typescript
{
  address: string;
  name: string;
  id: string;
  tribeId: number;
  smartAssemblies: Assemblies[];
  portrait: string;
}
```

#### CharacterInfo
```typescript
{
  id: string;
  address: string;
  name: string;
  tribeId: number;
  characterId: number;
  _raw: RawCharacterData;
}
```

#### SmartAssemblyResponse
```typescript
{
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
}
```

#### AssemblyType<T extends Assemblies> (Discriminated Union)

Each type adds module-specific properties:

**SmartStorageUnit**
```typescript
{
  type: 'SmartStorageUnit';
  storage: {
    mainInventory: {
      capacity: number;
      usedCapacity: number;
      items: InventoryItem[];
    };
    ephemeralInventories: EphemeralInventory[];
  };
  // ... base properties
}
```

**SmartTurret**
```typescript
{
  type: 'SmartTurret';
  turret: TurretModule;
  // ... base properties
}
```

**SmartGate**
```typescript
{
  type: 'SmartGate';
  gate: GateModule;
  destinationId: string;
  destinationGate: RawSuiObjectData | null;
  // ... base properties
}
```

**NetworkNode** (Most Complex)
```typescript
{
  type: 'NetworkNode';
  networkNode: NetworkNodeModule;
  fuel: {
    quantity: number;               // Current fuel
    burnTimeInMs: number;           // Milliseconds to burn 1 unit
    burnStartTime: number;
    isBurning: boolean;
    lastUpdated: number;
    maxCapacity: number;
    previousCycleElapsedTime: number;
    unitVolume: number;             // Volume per unit (wei)
    typeId: number;
  };
  energyProduction: number;         // Energy produced
  energyMaxCapacity: number;        // Max energy capacity
  totalReservedEnergy: number;      // Reserved by linked nodes
  linkedAssemblies: SmartAssemblyResponse[]; // Linked structures
  // ... base properties
}
```

**Manufacturing / Refinery**
```typescript
{
  type: 'Manufacturing' | 'Refinery';
  manufacturing: ManufacturingModule; // or refinery module
  // ... base properties
}
```

**Assembly** (Generic)
```typescript
{
  type: 'Assembly';
  // ... base properties only
}
```

---

#### InventoryItem
```typescript
{
  id: string;
  item_id: string;
  location: { location_hash: string };
  quantity: number;
  tenant: string;
  type_id: number;
  name: string;
}
```

---

#### DatahubGameInfo
```typescript
{
  id: number;                 // Type ID
  name: string;
  description: string;
  mass: number;               // kg
  radius: number;             // meters
  volume: number;             // m³
  portionSize: number;
  groupName: string;          // e.g., "Structures"
  groupId: number;
  categoryName: string;
  categoryId: number;
  iconUrl: string;            // Image URL
}
```

---

## 6. Configuration {#config}

### Constants & Network Configuration

**Import:** `import { ... } from '@evefrontier/dapp-kit'` or subpath imports

#### Network Endpoints

##### getSuiGraphqlEndpoint(env?)
```typescript
const endpoint = getSuiGraphqlEndpoint('testnet');
// → 'https://graphql.testnet.sui.io/graphql'
```
- **Supported networks:** testnet (default), devnet, mainnet

#### Package ID Helpers

##### getEveWorldPackageId()
```typescript
const pkgId = getEveWorldPackageId(); // From VITE_EVE_WORLD_PACKAGE_ID
```
- **Throws:** Error if environment variable not set

##### getCharacterOwnerCapType()
```typescript
const type = getCharacterOwnerCapType();
// → '{pkg}::access::OwnerCap<{pkg}::character::Character>'
```

##### getObjectRegistryType()
```typescript
const type = getObjectRegistryType();
// → '{pkg}::object_registry::ObjectRegistry'
```

##### getEnergyConfigType()
```typescript
const type = getEnergyConfigType();
// → '{pkg}::energy::EnergyConfig'
```

#### Polling & Storage

```typescript
POLLING_INTERVAL = 10000;          // 10 seconds
STORAGE_KEYS.CONNECTED = 'eve-dapp-connected'
```

---

### Tenant Configuration

#### Supported Tenants
```typescript
type TenantId = 'utopia' | 'stillness' | 'testevenet' | 'nebula'
const DEFAULT_TENANT = 'stillness'
```

#### Tenant Config Lookups

```typescript
import { TENANT_CONFIG, DATAHUB_BY_TENANT } from '@evefrontier/dapp-kit';

const config = TENANT_CONFIG['stillness'];
// → { packageId, evePackageId, datahubHost }

const datahubHost = DATAHUB_BY_TENANT['stillness'];
```

#### getEveCoinType(tenantId)
```typescript
const coinType = getEveCoinType('stillness');
// → '{packageId}::EVE::EVE'
```

---

### Game Type IDs

```typescript
import { TYPEIDS } from '@evefrontier/dapp-kit';

TYPEIDS.LENS;                    // 77518
TYPEIDS.SMART_STORAGE_UNIT;      // 77917
TYPEIDS.NETWORK_NODE;            // 88092
TYPEIDS.PORTABLE_REFINERY;       // 87161
TYPEIDS.PROTOCOL_DEPOT;          // 85249
// ... and more

EXCLUDED_TYPEIDS  // Portable items not considered "real" structures
```

---

### Volume Constant

```typescript
ONE_M3 = 1000000000000000000;  // 1e18 (wei to m³ conversion)
```

---

## 7. Wallet Features {#wallet}

**Import:** `import { walletSupportsSponsoredTransaction, ... } from '@evefrontier/dapp-kit'`

### Feature Detection

#### walletSupportsSponsoredTransaction(wallet)
```typescript
if (walletSupportsSponsoredTransaction(currentWallet)) {
  // Show sponsored transaction button
}
```
- **Returns:** Boolean

#### hasSponsoredTransactionFeature(features)
```typescript
if (hasSponsoredTransactionFeature(wallet.features)) {
  // Type-safe access to feature
}
```
- **Returns:** Type guard for TypeScript

#### getSponsoredTransactionFeature(wallet)
```typescript
const method = getSponsoredTransactionFeature(wallet);
if (method) {
  const result = await method(input);
}
```
- **Returns:** `SponsoredTransactionMethod | undefined`

#### getAssemblyTypeApiString(type)
```typescript
const apiSlug = getAssemblyTypeApiString('SmartStorageUnit');
// → 'storage-units'
```
- **Returns:** API-formatted assembly type string

---

## 8. Error Handling {#errors}

### Sponsored Transaction Errors

```typescript
import {
  WalletNotConnectedError,
  WalletNoAccountSelectedError,
  WalletSponsoredTransactionNotSupportedError
} from '@evefrontier/dapp-kit'
```

#### WalletNotConnectedError
```typescript
try {
  // Sponsored tx without connected wallet
} catch (err) {
  if (err instanceof WalletNotConnectedError) {
    console.log('No wallet connected');
  }
}
```

#### WalletNoAccountSelectedError
```typescript
// Thrown when wallet.account is null
```

#### WalletSponsoredTransactionNotSupportedError
```typescript
// Thrown when wallet.features don't include evefrontier:sponsoredTransaction
```

---

## 9. Common Workflows {#workflows}

### Load Assembly with Full Data
```typescript
import { getAssemblyWithOwner, transformToAssembly } from '@evefrontier/dapp-kit/graphql';
import { getDatahubGameInfo } from '@evefrontier/dapp-kit';

const assemblyId = '0x123...';
const { moveObject, assemblyOwner } = await getAssemblyWithOwner(assemblyId);

const datahubInfo = await getDatahubGameInfo(moveObject.data.content.fields.type_id);

const typed = await transformToAssembly(assemblyId, moveObject, {
  character: assemblyOwner,
  datahubInfo
});
```

---

### Type-Safe Assembly Property Access
```typescript
import { assertAssemblyType } from '@evefrontier/dapp-kit';

function displayAssemblyInfo(assembly: AssemblyType<Assemblies>) {
  console.log(`${assembly.name} - State: ${assembly.state}`);

  if (assertAssemblyType(assembly, 'SmartStorageUnit')) {
    const capacity = assembly.storage.mainInventory.capacity;
    console.log(`Storage: ${capacity} m³`);
  }

  if (assertAssemblyType(assembly, 'NetworkNode')) {
    console.log(`Fuel burn: ${assembly.fuel.burnTimeInMs}ms`);
    console.log(`Linked assemblies: ${assembly.linkedAssemblies.length}`);
  }
}
```

---

### Execute Sponsored Transaction
```typescript
function BringOnlineForm() {
  const { assembly, assemblyOwner } = useSmartObject();
  const { notify } = useNotification();
  const { mutateAsync: sendTx, isPending } = useSponsoredTransaction();

  const handleBringOnline = async () => {
    try {
      const result = await sendTx({
        txAction: 'online',
        assembly: assembly!,
        chain: 'sui:testnet',
        metadata: {
          name: `Bringing ${assembly!.name} online`,
        }
      });

      notify({
        type: 'success',
        message: 'Structure brought online!',
        txHash: result.digest
      });
    } catch (err) {
      notify({
        type: 'error',
        message: err instanceof Error ? err.message : 'Transaction failed'
      });
    }
  };

  return (
    <button onClick={handleBringOnline} disabled={isPending || !assembly}>
      {isPending ? 'Sending...' : 'Bring Online'}
    </button>
  );
}
```

---

### Fetch All Character Structures
```typescript
import { getCharacterAndOwnedObjects, getDatahubGameInfo } from '@evefrontier/dapp-kit';

async function loadPlayerStructures(walletAddress: string) {
  const { data } = await getCharacterAndOwnedObjects(walletAddress);

  const structures = data.character.smartAssemblies;

  // Load datahub info for each
  const enriched = await Promise.all(
    structures.map(async (assembly) => ({
      ...assembly,
      datahubInfo: await getDatahubGameInfo(assembly.typeId)
    }))
  );

  return enriched;
}
```

---

### Calculate Adjusted Burn Rate with Efficiency
```typescript
import { getAdjustedBurnRate, getFuelEfficiencyForType } from '@evefrontier/dapp-kit';

async function calculateFuelStats(assembly: NetworkNode) {
  const baseTimeMs = assembly.fuel.burnTimeInMs;
  const efficiency = await getFuelEfficiencyForType(assembly.fuel.typeId);

  const adjusted = getAdjustedBurnRate(baseTimeMs, efficiency);

  console.log(`Fuel burn: ${adjusted.unitsPerHour} units/hour`);
  console.log(`One unit lasts: ${adjusted.burnTimePerUnitMs}ms`);
}
```

---

## 10. Quick Reference {#quick-ref}

### Most-Used Methods for Builder Scaffolds

| Operation | Method | Import |
|-----------|--------|--------|
| **Get assembly data** | `useSmartObject()` | Main |
| **Load assembly + owner** | `getAssemblyWithOwner()` | `/graphql` |
| **Transform to typed assembly** | `transformToAssembly()` | Main |
| **Type-safe narrowing** | `assertAssemblyType()` | Main |
| **Wallet connection** | `useConnection()` | Main |
| **Sponsored transaction** | `useSponsoredTransaction()` | Main |
| **Show notifications** | `useNotification()` | Main |
| **Get energy usage** | `getEnergyUsageForType()` | Main |
| **Get fuel efficiency** | `getFuelEfficiencyForType()` | Main |
| **Calculate burn rate** | `getAdjustedBurnRate()` | Main |
| **Get game metadata** | `getDatahubGameInfo()` | Main |
| **Format display values** | `formatDuration()`, `formatM3()` | Utils |
| **Get explorer link** | `getTxUrl()` | Utils |
| **Parse character** | `parseCharacterFromJson()` | Utils |
| **Get character objects** | `getCharacterAndOwnedObjects()` | `/graphql` |

---

### Common Parameter Values

**Sponsored Transaction Actions:**
```typescript
'online' | 'offline' | 'update-metadata' | 'link-smart-gate' | 'unlink-smart-gate'
```

**Notification Severity:**
```typescript
'success' | 'error' | 'warning' | 'info'
```

**Assembly Types:**
```typescript
'SmartStorageUnit' | 'SmartTurret' | 'SmartGate' | 'NetworkNode' |
'Manufacturing' | 'Refinery' | 'Assembly'
```

**Assembly States:**
```typescript
'null' | 'unanchored' | 'anchored' | 'online' | 'destroyed'
```

---

### Environment Variables

```env
VITE_OBJECT_ID=0x123...          # Optional: Pre-set assembly ID
VITE_EVE_WORLD_PACKAGE_ID=0x456  # Required: EVE World package ID
```

---

## Official Resources

- **TypeDoc API Docs:** http://sui-docs.evefrontier.com/
- **Package:** @evefrontier/dapp-kit (npm)
- **License:** MIT

---

**Status:** Production-ready
