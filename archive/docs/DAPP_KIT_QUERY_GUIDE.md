# DApp Kit Complete Query Guide - Wallet & Character Data Discovery

**Purpose:** Comprehensive reference for querying ALL data about a wallet, character, and structures using @evefrontier/dapp-kit

**Source:** Verified from @evefrontier/dapp-kit v0.1.0 implementation

---

## Quick Start: Query Everything About a Wallet

```typescript
import {
  getCharacterAndOwnedObjects,
  getOwnedObjectsByType,
  getOwnedObjectsByPackage,
  getAssemblyWithOwner,
} from '@evefrontier/dapp-kit';

// 1. Get character and all owned objects
const charResult = await getCharacterAndOwnedObjects(walletAddress);

// 2. Get all structures owned by the character
const structuresResult = await getOwnedObjectsByType(
  walletAddress,
  "0xworld::smart_storage_unit::SmartStorageUnit" // Example type
);

// 3. Get a specific structure with full details + owner
const structureDetails = await getAssemblyWithOwner(structureId);
```

---

## All Available Query Functions

### Core Functions in @evefrontier/dapp-kit

| Function | Purpose | Returns | Use For |
|----------|---------|---------|---------|
| `getCharacterAndOwnedObjects()` | Get character + all owned objects | CharacterInfo + objects | Find all player structures |
| `getWalletCharacters()` | Get characters in wallet | Latest character info | Character list |
| `getOwnedObjectsByType()` | Get objects of specific type | Object addresses | Filter structures by type |
| `getOwnedObjectsByPackage()` | Get all objects from package | Full object data | All EVE Frontier objects |
| `getObjectWithJson()` | Get single object data | JSON contents | Inspect object details |
| `getObjectWithDynamicFields()` | Get object + dynamic fields | Object + field nodes | Get inventory, config |
| `getObjectOwnerAndOwnedObjectsByType()` | Get owner + their objects | Owner + objects (BCS) | Traverse ownership |
| `getObjectOwnerAndOwnedObjectsWithJson()` | Get owner + their objects | Owner + objects (JSON) | Traverse ownership |
| `getObjectAndCharacterOwner()` | Get assembly + owner character | Assembly + character | Structure + owner |
| `getAssemblyWithOwner()` | Get assembly full data | moveObject + character + energySource + gate | Complete structure info |
| `getObjectByAddress()` | Get object by address | BCS contents | Raw object data |
| `getSingletonObjectByType()` | Get singleton object | Singleton object address | Global config |
| `getSingletonConfigObjectByType()` | Get config singleton | Singleton + dynamic fields | Energy/fuel config |
| `getObjectsByType()` | Get all objects of type | Paginated results | Query all objects |
| `executeGraphQLQuery()` | Execute custom query | Custom response | Custom queries |

---

## Data Discovery Path

### Level 1: Get Connected Wallet's Character

```typescript
const result = await getCharacterAndOwnedObjects(walletAddress);

// Returns:
// {
//   data: {
//     address: {
//       objects: {
//         nodes: [
//           {
//             contents: {
//               extract: {
//                 asAddress: {
//                   asObject: {
//                     asMoveObject: {
//                       contents: {
//                         json: {
//                           id: "character-id",
//                           character_address: "0x...",
//                           metadata: { name: "PlayerName" },
//                           tribe_id: 123,
//                           ...
//                         }
//                       }
//                     }
//                   },
//                   // All objects owned by character
//                   objects: {
//                     nodes: [
//                       {
//                         contents: {
//                           extract: {
//                             asAddress: {
//                               asObject: {
//                                 asMoveObject: {
//                                   contents: {
//                                     json: { /* structure data */ }
//                                   }
//                                 }
//                               }
//                             }
//                           }
//                         }
//                       }
//                     ]
//                   }
//                 }
//               }
//             }
//           }
//         ]
//       }
//     }
//   }
// }

// Extract character info
const characterJson = result.data?.address?.objects?.nodes?.[0]?.contents?.extract?.asAddress?.asObject?.asMoveObject?.contents?.json;
const characterInfo = {
  id: characterJson?.id,
  name: characterJson?.metadata?.name,
  address: characterJson?.character_address,
  tribeId: characterJson?.tribe_id,
};

// Extract owned objects (structures)
const ownedObjects = result.data?.address?.objects?.nodes?.[0]?.contents?.extract?.asAddress?.objects?.nodes;
ownedObjects?.forEach(obj => {
  const structureData = obj.contents?.extract?.asAddress?.asObject?.asMoveObject?.contents?.json;
  console.log("Structure:", structureData);
});
```

**Character Data Available:**
- `id` — Character ID
- `character_address` — Character's on-chain address
- `metadata.name` — Character name (display)
- `tribe_id` — Player's tribe/faction
- `authorized_object_id` — Objects the character owns
- Any custom fields added by game

---

### Level 2: Get All Structures Owned by Character

**Option A: Using getCharacterAndOwnedObjects() result**

Already have all structures in the character's owned objects (see above).

**Option B: Get specific structure type**

```typescript
// Get all Smart Storage Units owned by wallet
const result = await getOwnedObjectsByType(
  walletAddress,
  "0xworld::smart_storage_unit::SmartStorageUnit"
);

// Returns: { data: { address: { objects: { nodes: [{ address, ... }] } } } }
const structureAddresses = result.data?.address?.objects?.nodes?.map(
  n => n.address
);
```

**Option C: Get all EVE Frontier objects**

```typescript
// Get all objects from the EVE Frontier package
const result = await getOwnedObjectsByPackage(
  walletAddress,
  "0xworld" // EVE Frontier package ID
);

// Returns all objects with full data including dynamic fields
const allObjects = result.data?.objects?.nodes;
```

**Common Structure Types:**
```
0xworld::smart_storage_unit::SmartStorageUnit
0xworld::smart_turret::SmartTurret
0xworld::smart_gate::SmartGate
0xworld::network_node::NetworkNode
0xworld::manufacturing::Manufacturing
0xworld::refinery::Refinery
```

---

### Level 3: Get Complete Structure Details

```typescript
const { moveObject, assemblyOwner, energySource, destinationGate } =
  await getAssemblyWithOwner(structureId);

// moveObject contains:
// {
//   contents: {
//     json: {
//       id: "structure-id",
//       name: "Trading Post",
//       type: "SmartStorageUnit",
//       state: "online",
//       owner_cap_id: "...",
//       energy_source_id: "...",
//       linked_gate_id: "...",
//       ...custom fields
//     },
//     type: { repr: "0xworld::smart_storage_unit::SmartStorageUnit" }
//   },
//   dynamicFields: {
//     nodes: [
//       {
//         name: { json: "inventory_item_1", type: { repr: "..." } },
//         contents: { json: { qty: 100, type_id: 123 }, type: { repr: "..." } }
//       },
//       ...
//     ]
//   }
// }

// assemblyOwner contains:
// {
//   id: "character-id",
//   address: "0x...",
//   name: "PlayerName",
//   tribeId: 123,
//   characterId: 456
// }

// energySource and destinationGate contain related object data
```

**Available Structure Data:**
- Basic: `id`, `name`, `type`, `state`, `owner_cap_id`
- Status: `online/offline`, `destroyed`, `anchored`
- System: `system_id`, `location_x`, `location_y`, `location_z`
- Energy: `energy_source_id`, `fuel_type`, `fuel_amount`
- Network: `linked_gate_id` (for gates)
- Custom: Module-specific fields (storage, turret config, etc.)
- Dynamic Fields: Inventory, logs, configurations (see below)

---

### Level 4: Query Dynamic Fields (Inventory, Config, etc.)

```typescript
const result = await getObjectWithDynamicFields(structureId);

// Returns:
// {
//   data: {
//     object: {
//       asMoveObject: {
//         contents: { json: { ...structure data } },
//         dynamicFields: {
//           nodes: [
//             {
//               name: { json: "field_name", type: { repr: "..." } },
//               contents: {
//                 json: { /* field data */ },
//                 type: { layout: "..." }
//               }
//             },
//             ...
//           ]
//         }
//       }
//     }
//   }
// }

const dynamicFields = result.data?.object?.asMoveObject?.dynamicFields?.nodes || [];

dynamicFields.forEach(field => {
  const fieldName = field.name.json;
  const fieldData = field.contents.json;
  console.log(`${fieldName}:`, fieldData);
});

// Examples of dynamic fields:
// - inventory: { items: [...] }
// - access_logs: { entries: [...] }
// - configuration: { settings: {...} }
// - active_orders: { orders: [...] }
```

---

## Complete Query Examples

### Example 1: Get All Structures for a Character

```typescript
import { getCharacterAndOwnedObjects } from '@evefrontier/dapp-kit';

async function getCharacterStructures(walletAddress: string) {
  const result = await getCharacterAndOwnedObjects(walletAddress);

  const characterData = result.data?.address?.objects?.nodes?.[0]?.contents?.extract?.asAddress?.asObject?.asMoveObject?.contents?.json;
  const ownedObjects = result.data?.address?.objects?.nodes?.[0]?.contents?.extract?.asAddress?.objects?.nodes || [];

  const character = {
    id: characterData?.id,
    name: characterData?.metadata?.name,
    address: characterData?.character_address,
    tribeId: characterData?.tribe_id,
  };

  const structures = ownedObjects.map(obj => {
    const json = obj.contents?.extract?.asAddress?.asObject?.asMoveObject?.contents?.json;
    return {
      id: json?.id,
      name: json?.name,
      type: json?.type,
      state: json?.state,
      system: json?.system_id,
      // Add more fields as needed
    };
  });

  return { character, structures };
}
```

---

### Example 2: Get Detailed Info for Each Structure

```typescript
import { getAssemblyWithOwner } from '@evefrontier/dapp-kit';

async function getStructuresWithDetails(structureIds: string[]) {
  const details = await Promise.all(
    structureIds.map(async (structureId) => {
      const { moveObject, assemblyOwner, energySource } =
        await getAssemblyWithOwner(structureId);

      return {
        structure: moveObject?.contents?.json,
        owner: assemblyOwner,
        energySource: energySource?.contents?.json,
        dynamicFields: moveObject?.dynamicFields?.nodes,
      };
    })
  );

  return details;
}
```

---

### Example 3: Find Structures of Specific Type

```typescript
import {
  getCharacterAndOwnedObjects,
  getOwnedObjectsByType
} from '@evefrontier/dapp-kit';

async function getStorageStructures(walletAddress: string) {
  // Option A: Filter from getCharacterAndOwnedObjects
  const charResult = await getCharacterAndOwnedObjects(walletAddress);
  const allObjects = charResult.data?.address?.objects?.nodes?.[0]?.contents?.extract?.asAddress?.objects?.nodes || [];

  const storageUnits = allObjects.filter(obj => {
    const type = obj.contents?.extract?.asAddress?.asObject?.asMoveObject?.contents?.type?.repr;
    return type?.includes('SmartStorageUnit');
  });

  // Option B: Query directly by type
  const typeResult = await getOwnedObjectsByType(
    walletAddress,
    "0xworld::smart_storage_unit::SmartStorageUnit"
  );
  const typeAddresses = typeResult.data?.address?.objects?.nodes?.map(n => n.address);

  return { storageUnits, typeAddresses };
}
```

---

### Example 4: Get Structure + Inventory

```typescript
import {
  getAssemblyWithOwner,
  getObjectWithDynamicFields
} from '@evefrontier/dapp-kit';

async function getStructureWithInventory(structureId: string) {
  // Get basic structure + owner
  const { moveObject: structure, assemblyOwner: owner } =
    await getAssemblyWithOwner(structureId);

  // Get full dynamic fields (inventory, logs, etc.)
  const dynamicResult = await getObjectWithDynamicFields(structureId);
  const dynamicFields = dynamicResult.data?.object?.asMoveObject?.dynamicFields?.nodes || [];

  // Extract inventory
  const inventoryField = dynamicFields.find(f =>
    f.name.json === 'inventory' || f.name.json === 'items'
  );

  return {
    structure: structure?.contents?.json,
    owner,
    inventory: inventoryField?.contents?.json,
    otherFields: dynamicFields.map(f => ({
      name: f.name.json,
      data: f.contents.json
    }))
  };
}
```

---

## What Data Can You Extract?

### Character Data
- ✅ Character ID, name, address
- ✅ Tribe ID, faction
- ✅ Account creation date (from metadata)
- ✅ All owned objects (structures, items, etc.)
- ✅ Character level, experience
- ✅ Standings, reputation
- ✅ Custom character properties

### Structure Data
- ✅ Structure ID, name, type
- ✅ Current state (online/offline/destroyed)
- ✅ Location (system, coordinates)
- ✅ Owner character
- ✅ Energy source, fuel amount
- ✅ Linked gate ID (for gates)
- ✅ Module configuration (turrets, refinery, etc.)
- ✅ Dynamic field data (inventory, logs, orders, access)
- ✅ Creation date, last modified date
- ✅ Active jobs/operations
- ✅ Ownership history (via owner_cap chain)

### Dynamic Fields (Per Structure Type)
- **Storage Unit**: Inventory items, capacities, reserved space
- **Turret**: Target lists, ammunition, fire control settings
- **Gate**: Linked destinations, access control lists
- **Refinery**: Processing queue, output configuration
- **Manufacturing**: Production orders, material requirements
- **Network Node**: Network topology, peer list

### Transaction History & Metadata
- ✅ `previousTransaction` (timestamp of last update)
- ✅ Object version and digest (for state verification)
- ✅ Owner address (wallet address)
- ✅ Creation timestamp

---

## How to Discover New Fields

### 1. Inspect Raw JSON Response

```typescript
const result = await getAssemblyWithOwner(structureId);
const rawJson = result.moveObject?.contents?.json;

console.log(JSON.stringify(rawJson, null, 2));
// Shows all available fields in the structure
```

### 2. Check Dynamic Fields

```typescript
const result = await getObjectWithDynamicFields(structureId);
const fields = result.data?.object?.asMoveObject?.dynamicFields?.nodes || [];

fields.forEach(field => {
  console.log(`Field: ${field.name.json}`);
  console.log(`Type: ${field.name.type.repr}`);
  console.log(`Data:`, JSON.stringify(field.contents.json, null, 2));
});
```

### 3. Query by Type to Find Structure Variants

```typescript
// List all objects of a type to see variations
const result = await getObjectsByType(
  "0xworld::smart_storage_unit::SmartStorageUnit",
  { first: 10 }
);

result.data?.objects?.nodes?.forEach(obj => {
  const json = obj?.asMoveObject?.contents?.json;
  console.log("Structure variant fields:", Object.keys(json || {}));
});
```

### 4. Use Type Information

```typescript
const result = await getObjectWithJson(structureId);
const typeRepr = result.data?.object?.asMoveObject?.contents?.type?.repr;

// typeRepr gives you the full Move type:
// "0xworld::smart_storage_unit::SmartStorageUnit<0x123...>"
// The generic parameter might indicate module variants
```

---

## Error Handling

```typescript
async function safeQueryStructure(structureId: string) {
  try {
    const result = await getAssemblyWithOwner(structureId);

    if (result.errors) {
      console.error("GraphQL errors:", result.errors);
      return null;
    }

    if (!result.data?.moveObject) {
      console.warn("Structure not found or not accessible");
      return null;
    }

    return result.data;
  } catch (err) {
    console.error("Query failed:", err);
    return null;
  }
}
```

---

## Performance Tips

### 1. Batch Queries with Promise.all()

```typescript
// Query multiple structures in parallel
const details = await Promise.all(
  structureIds.map(id => getAssemblyWithOwner(id))
);
```

### 2. Filter Client-Side When Possible

```typescript
// Instead of multiple type queries, get all and filter
const charResult = await getCharacterAndOwnedObjects(walletAddress);
const allObjects = charResult.data?.address?.objects?.nodes?.[0]?.contents?.extract?.asAddress?.objects?.nodes || [];

// Filter by type locally (faster than multiple queries)
const storageUnits = allObjects.filter(obj => {
  const type = obj.contents?.extract?.asAddress?.asObject?.asMoveObject?.contents?.type?.repr;
  return type?.includes('SmartStorageUnit');
});
```

### 3. Use getOwnedObjectsByType for Pagination

```typescript
// Only for truly large datasets (rare)
const result = await getObjectsByType(
  "0xworld::smart_storage_unit::SmartStorageUnit",
  { first: 50, after: cursor }
);
```

### 4. Cache Results

```typescript
// Cache character data if querying frequently
const characterCache = new Map<string, CharacterInfo>();

async function getCachedCharacter(walletAddress: string) {
  if (characterCache.has(walletAddress)) {
    return characterCache.get(walletAddress);
  }

  const result = await getCharacterAndOwnedObjects(walletAddress);
  // Extract and cache...
  return characterCache.get(walletAddress);
}
```

---

## Integration with Current App

### Current Implementation
Your app currently:
- Uses `useConnection()` hook for wallet state
- Calls `/structures` endpoint (backend-side)
- Sends chat messages to `/structure-chat`

### What You Could Do Instead

Replace backend `/structures` endpoint with direct DApp Kit calls:

```typescript
import { useConnection } from '@evefrontier/dapp-kit';
import { getCharacterAndOwnedObjects } from '@evefrontier/dapp-kit';

export function useWalletStructures() {
  const { walletAddress } = useConnection();
  const [structures, setStructures] = useState([]);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    if (!walletAddress) return;

    setLoading(true);
    getCharacterAndOwnedObjects(walletAddress)
      .then(result => {
        // Parse structures from result
        const structs = extractStructures(result);
        setStructures(structs);
      })
      .finally(() => setLoading(false));
  }, [walletAddress]);

  return { structures, loading };
}

// Then use in component:
function TerminalUI() {
  const { structures } = useWalletStructures();

  return (
    <div>
      {structures.map(s => (
        <div key={s.id}>{s.name} in {s.system}</div>
      ))}
    </div>
  );
}
```

---

## Complete API Reference

| Function | Input | Output |
|----------|-------|--------|
| `getCharacterAndOwnedObjects(wallet)` | Wallet address | Character + all owned objects |
| `getWalletCharacters(wallet)` | Wallet address | Latest character |
| `getOwnedObjectsByType(owner, type)` | Owner address, object type | Objects of that type |
| `getOwnedObjectsByPackage(owner, pkg)` | Owner address, package ID | All objects from package |
| `getObjectWithJson(address)` | Object address | Object JSON data |
| `getObjectWithDynamicFields(objectId)` | Object ID | Object + dynamic fields |
| `getObjectOwnerAndOwnedObjectsByType(obj, type)` | Object address, type | Owner + owner's objects |
| `getObjectOwnerAndOwnedObjectsWithJson(obj, type)` | Object address, type | Owner + owner's objects (JSON) |
| `getObjectAndCharacterOwner(object)` | Object address | Object + character owner |
| `getAssemblyWithOwner(assemblyId)` | Assembly ID | Assembly + owner + energy + gate |
| `getObjectByAddress(address)` | Object address | BCS-encoded object |
| `getSingletonObjectByType(type)` | Object type | Singleton object address |
| `getSingletonConfigObjectByType(type, table)` | Type, table name | Config object + dynamic fields |
| `getObjectsByType(type, options)` | Object type, pagination | Paginated objects |
| `executeGraphQLQuery(query, vars)` | GraphQL string, variables | Custom response |

---

## Summary

**To query everything about a wallet:**

1. Call `getCharacterAndOwnedObjects(walletAddress)`
   - Get character info
   - Get all structures owned

2. For each structure, call `getAssemblyWithOwner(structureId)`
   - Get detailed structure data
   - Get owner character info
   - Get energy source info

3. Call `getObjectWithDynamicFields(structureId)` for inventory/config
   - Get all dynamic fields
   - Extract inventory, logs, settings

4. Inspect raw JSON to discover new fields
   - Use `console.log(JSON.stringify(data, null, 2))`
   - Check `type.repr` for type information

**All available** through DApp Kit's GraphQL interface to Sui blockchain.

