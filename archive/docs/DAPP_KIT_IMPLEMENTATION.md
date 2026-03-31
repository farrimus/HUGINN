# Implementing DApp Kit Queries in Your App

**Goal:** Replace backend `/structures` endpoint with direct blockchain queries using DApp Kit

**Time to implement:** 30 minutes for basic version, 1-2 hours for full featured

---

## What We're Doing

**Current Flow:**
```
User connects wallet → Backend `/structures` endpoint → Get structures → Display
```

**New Flow:**
```
User connects wallet → DApp Kit getCharacterAndOwnedObjects() → Direct blockchain → Display
```

**Benefits:**
- No backend latency
- Real-time data from blockchain
- More data available (inventory, dynamic fields, etc.)
- Decentralized (trust blockchain, not server)

---

## Step 1: Create a Custom Hook

**File:** `frontend/src/hooks/useWalletStructures.ts`

```typescript
import { useState, useEffect } from 'react';
import {
  getCharacterAndOwnedObjects,
  getAssemblyWithOwner,
} from '@evefrontier/dapp-kit';

export interface CharacterInfo {
  id: string;
  name: string;
  address: string;
  tribeId: number;
  characterId?: number;
}

export interface StructureBasic {
  id: string;
  name: string;
  type: string;
  state: string;
  system_name?: string;
  owner_address: string;
}

export interface StructureDetailed extends StructureBasic {
  location_x?: number;
  location_y?: number;
  location_z?: number;
  energy_source_id?: string;
  fuel_amount?: number;
  linked_gate_id?: string;
  dynamicFields?: Array<{
    name: string;
    data: Record<string, unknown>;
  }>;
  _raw?: Record<string, unknown>;
}

interface UseWalletStructuresReturn {
  character: CharacterInfo | null;
  structures: StructureBasic[];
  loading: boolean;
  error: string | null;
  refetch: () => Promise<void>;
}

/**
 * Hook to query all structures owned by a wallet's character
 * Uses DApp Kit to query blockchain directly (no backend needed)
 */
export function useWalletStructures(
  walletAddress: string | null | undefined
): UseWalletStructuresReturn {
  const [character, setCharacter] = useState<CharacterInfo | null>(null);
  const [structures, setStructures] = useState<StructureBasic[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const fetchStructures = async () => {
    if (!walletAddress) {
      setCharacter(null);
      setStructures([]);
      return;
    }

    setLoading(true);
    setError(null);

    try {
      // Query blockchain directly
      const result = await getCharacterAndOwnedObjects(walletAddress);

      if (result.errors) {
        throw new Error(`GraphQL error: ${result.errors[0]?.message}`);
      }

      if (!result.data?.address?.objects?.nodes?.[0]) {
        throw new Error('No character found for this wallet');
      }

      // Extract character from result
      const characterNode = result.data.address.objects.nodes[0];
      const characterJson = characterNode.contents?.extract?.asAddress?.asObject
        ?.asMoveObject?.contents?.json as Record<string, unknown>;

      if (!characterJson) {
        throw new Error('Could not parse character data');
      }

      const characterInfo: CharacterInfo = {
        id: (characterJson.id as string) || '',
        name: ((characterJson.metadata as Record<string, unknown>)?.name as string) || 'Unknown',
        address: (characterJson.character_address as string) || '',
        tribeId: (characterJson.tribe_id as number) || 0,
        characterId: (characterJson.character_id as number),
      };

      setCharacter(characterInfo);

      // Extract structures from owned objects
      const ownedObjectsNodes =
        characterNode.contents?.extract?.asAddress?.objects?.nodes || [];

      const structures: StructureBasic[] = ownedObjectsNodes
        .map((node: Record<string, unknown>) => {
          try {
            const structureJson = (node as any).contents?.extract?.asAddress
              ?.asObject?.asMoveObject?.contents?.json as Record<string, unknown>;

            if (!structureJson) return null;

            return {
              id: (structureJson.id as string) || '',
              name: (structureJson.name as string) || 'Unknown',
              type: (structureJson.type as string) || 'Unknown',
              state: (structureJson.state as string) || 'unknown',
              system_name: (structureJson.system_name as string),
              owner_address: characterInfo.address,
            };
          } catch (e) {
            console.warn('Failed to parse structure:', e);
            return null;
          }
        })
        .filter((s): s is StructureBasic => s !== null);

      setStructures(structures);
    } catch (err) {
      const errorMsg = err instanceof Error ? err.message : 'Unknown error';
      setError(errorMsg);
      console.error('Failed to fetch structures:', err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchStructures();
  }, [walletAddress]);

  return {
    character,
    structures,
    loading,
    error,
    refetch: fetchStructures,
  };
}
```

---

## Step 2: Use the Hook in TerminalUI

**File:** `frontend/src/components/TerminalUI.tsx`

Replace the current `fetchStructures()` function:

```typescript
import { useWalletStructures } from '../hooks/useWalletStructures';

export function TerminalUI() {
  const { isConnected, walletAddress } = useConnection();

  // Replace old useState for structures with new hook
  const { character, structures, loading, error, refetch } =
    useWalletStructures(isConnected ? walletAddress : null);

  // Rest of your component...
  const [selectedStructure, setSelectedStructure] = useState<Structure | null>(null);
  const [logs, setLogs] = useState<TerminalLog[]>([...]);

  const addLog = (text: string, type: TerminalLog['type'] = 'info') => {
    setLogs((prev) => [...prev, { text, type, timestamp: Date.now() }]);
  };

  // Update /list command to use new data
  const handleCommand = async (input: string) => {
    const trimmed = input.trim();
    const parts = trimmed.split(' ');
    const command = parts[0].toLowerCase();

    if (command === '/connect') {
      if (isConnected) {
        addLog('Wallet already connected', 'warning');
      } else {
        handleConnect();
        addLog('Initiating wallet connection...', 'command');
      }
    } else if (command === '/disconnect') {
      if (!isConnected) {
        addLog('Wallet not connected', 'warning');
      } else {
        handleDisconnect();
        addLog('Wallet disconnected', 'info');
      }
    } else if (command === '/list') {
      if (!isConnected) {
        addLog('Connect wallet first with /connect', 'warning');
      } else if (loading) {
        addLog('Loading structures...', 'info');
      } else if (error) {
        addLog(`Error loading structures: ${error}`, 'error');
      } else if (structures.length === 0) {
        addLog('No structures available', 'info');
      } else {
        addLog(
          `${character?.name} has ${structures.length} structures:`,
          'info'
        );
        structures.forEach((s) => {
          addLog(
            `  [${s.id}] ${s.name} (${s.type}) - ${s.state}`,
            'info'
          );
        });
      }
    } else if (command === '/select') {
      if (!isConnected) {
        addLog('Connect wallet first with /connect', 'warning');
      } else if (parts.length < 2) {
        addLog('Usage: /select <structure-id>', 'warning');
      } else {
        const structureId = parts[1];
        const structure = structures.find((s) => s.id === structureId);
        if (!structure) {
          addLog(`Structure '${structureId}' not found`, 'error');
        } else {
          setSelectedStructure(structure);
          addLog(
            `Selected structure: ${structure.name} (${structure.state})`,
            'info'
          );
          addLog('Ready to chat. Send a message to begin.', 'info');
        }
      }
    } else if (command === '/help') {
      addLog('Available commands:', 'info');
      addLog('  /connect - Connect wallet', 'info');
      addLog('  /disconnect - Disconnect wallet', 'info');
      addLog('  /list - List available structures', 'info');
      addLog('  /select <id> - Select a structure', 'info');
      addLog('  /help - Show this message', 'info');
      addLog('Regular text is sent to AI chat', 'info');
    } else {
      addLog(`Unknown command: ${command}`, 'error');
      addLog('Type /help for available commands', 'warning');
    }
  };

  // Auto-list structures when wallet connects
  useEffect(() => {
    if (isConnected && structures.length > 0) {
      addLog(
        `${character?.name} connected with ${structures.length} structures`,
        'info'
      );
    }
  }, [isConnected]);

  // ... rest of component
}
```

---

## Step 3: Optional - Get Detailed Structure Info

**File:** `frontend/src/hooks/useStructureDetails.ts`

```typescript
import { useState } from 'react';
import { getAssemblyWithOwner, getObjectWithDynamicFields } from '@evefrontier/dapp-kit';

export interface StructureDetails {
  json: Record<string, unknown>;
  dynamicFields?: Array<{
    name: string;
    data: Record<string, unknown>;
  }>;
}

interface UseStructureDetailsReturn {
  details: StructureDetails | null;
  loading: boolean;
  error: string | null;
}

export function useStructureDetails(
  structureId: string | null
): UseStructureDetailsReturn {
  const [details, setDetails] = useState<StructureDetails | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const fetchDetails = async () => {
    if (!structureId) {
      setDetails(null);
      return;
    }

    setLoading(true);
    setError(null);

    try {
      // Get full details with owner and dynamic fields
      const result = await getAssemblyWithOwner(structureId);

      if (!result.moveObject) {
        throw new Error('Structure not found');
      }

      const dynamicFields = result.moveObject.dynamicFields?.nodes?.map(
        (node) => ({
          name: node.name.json as string,
          data: node.contents.json,
        })
      ) || [];

      setDetails({
        json: result.moveObject.contents.json,
        dynamicFields,
      });
    } catch (err) {
      const errorMsg = err instanceof Error ? err.message : 'Unknown error';
      setError(errorMsg);
      console.error('Failed to fetch structure details:', err);
    } finally {
      setLoading(false);
    }
  };

  // Auto-fetch when structure ID changes
  if (structureId) {
    fetchDetails();
  }

  return { details, loading, error };
}
```

---

## Step 4: Query Multiple Structures at Once

```typescript
import { getAssemblyWithOwner } from '@evefrontier/dapp-kit';

async function getStructuresDetails(
  structureIds: string[]
): Promise<Record<string, StructureDetailed>> {
  const results = await Promise.all(
    structureIds.map(async (id) => {
      try {
        const result = await getAssemblyWithOwner(id);
        return {
          id,
          data: {
            json: result.moveObject?.contents.json,
            dynamicFields: result.moveObject?.dynamicFields?.nodes?.map(
              (node) => ({
                name: node.name.json as string,
                data: node.contents.json,
              })
            ),
          },
        };
      } catch (e) {
        console.error(`Failed to get details for ${id}:`, e);
        return { id, data: null };
      }
    })
  );

  const details: Record<string, StructureDetailed> = {};
  results.forEach(({ id, data }) => {
    if (data) {
      details[id] = {
        ...(data.json as StructureDetailed),
        dynamicFields: data.dynamicFields,
      };
    }
  });

  return details;
}
```

---

## Step 5: Add Refresh Command

**In TerminalUI handleCommand():**

```typescript
} else if (command === '/refresh') {
  addLog('Refreshing structure list...', 'command');
  await refetch();
  addLog('Structure list refreshed', 'info');
} else if (command === '/info') {
  if (!selectedStructure) {
    addLog('Select a structure first with /select <id>', 'warning');
  } else {
    addLog(`Structure: ${selectedStructure.name}`, 'info');
    addLog(`  ID: ${selectedStructure.id}`, 'info');
    addLog(`  Type: ${selectedStructure.type}`, 'info');
    addLog(`  State: ${selectedStructure.state}`, 'info');
    if (selectedStructure.system_name) {
      addLog(`  System: ${selectedStructure.system_name}`, 'info');
    }
  }
}
```

---

## Before and After Comparison

### Before (Using Backend)

```typescript
const [structures, setStructures] = useState<Structure[]>([]);
const [loadingStructures, setLoadingStructures] = useState(false);

const fetchStructures = async (): Promise<void> => {
  setLoadingStructures(true);
  try {
    const response = await fetch(`${API_BASE_URL}/structures`);
    if (!response.ok) {
      throw new Error(`HTTP ${response.status}`);
    }
    const data = await response.json();
    setStructures(data.structures || []);
  } catch (err) {
    addLog(`Error loading structures: ${err}`, 'error');
  } finally {
    setLoadingStructures(false);
  }
};

useEffect(() => {
  if (isConnected && walletAddress) {
    fetchStructures();
  }
}, [isConnected, walletAddress]);
```

### After (Using DApp Kit)

```typescript
const { character, structures, loading, error, refetch } =
  useWalletStructures(isConnected ? walletAddress : null);

// That's it! The hook handles everything
```

---

## Debugging

### Check if Data is Being Fetched

```typescript
useEffect(() => {
  console.log('Structures loaded:', structures);
  console.log('Character:', character);
  console.log('Loading:', loading);
  console.log('Error:', error);
}, [structures, character, loading, error]);
```

### Inspect Raw Response

```typescript
const result = await getCharacterAndOwnedObjects(walletAddress);
console.log('Full response:', JSON.stringify(result, null, 2));
```

### Check DApp Kit Errors

```typescript
if (result.errors) {
  console.error('GraphQL Errors:', result.errors);
  result.errors.forEach(err => console.error(err.message));
}
```

---

## Common Pitfalls

### 1. Null Safety

```typescript
// ❌ WRONG - Will crash if path doesn't exist
const name = result.data.address.objects.nodes[0].contents.json.name;

// ✅ RIGHT - Safe navigation
const name = result.data?.address?.objects?.nodes?.[0]?.contents?.json?.name;
```

### 2. Type Safety

```typescript
// ❌ WRONG
const structures = ownedObjects.map(obj => obj.contents.extract...);

// ✅ RIGHT - Type-safe with try/catch
const structures = ownedObjects
  .map(node => {
    try {
      const json = (node as any).contents?.extract?.asAddress?.asObject?.asMoveObject?.contents?.json;
      return json ? parseStructure(json) : null;
    } catch (e) {
      return null;
    }
  })
  .filter((s): s is Structure => s !== null);
```

### 3. Performance

```typescript
// ❌ WRONG - Queries in a loop
for (const id of structureIds) {
  await getAssemblyWithOwner(id); // One by one
}

// ✅ RIGHT - Parallel queries
await Promise.all(
  structureIds.map(id => getAssemblyWithOwner(id))
);
```

### 4. Dependency Management

```typescript
// ❌ WRONG - Hook called conditionally
if (isConnected) {
  const { structures } = useWalletStructures(walletAddress);
}

// ✅ RIGHT - Always call, pass null if not needed
const { structures } = useWalletStructures(
  isConnected ? walletAddress : null
);
```

---

## Testing Locally

```bash
# 1. Make sure hook is exported
grep "export function useWalletStructures" src/hooks/useWalletStructures.ts

# 2. Start dev server
npm run dev

# 3. In browser console
localStorage.setItem('test-wallet', '0x...')

# 4. Connect wallet and run /list
```

---

## Rollout Plan

### Phase 1: Development (1-2 hours)
- [ ] Create `useWalletStructures.ts` hook
- [ ] Create `useStructureDetails.ts` hook
- [ ] Update TerminalUI to use hooks
- [ ] Test locally with `npm run dev`

### Phase 2: Testing (30 min)
- [ ] Test wallet connection
- [ ] Test /list command
- [ ] Test /select command
- [ ] Test error handling
- [ ] Test with different wallet addresses

### Phase 3: Deployment (10 min)
- [ ] Run `npm run build`
- [ ] Copy to `/static/companion/`
- [ ] Test in production
- [ ] Monitor for errors

### Phase 4: Cleanup (optional)
- [ ] Remove `/structures` endpoint from backend if unused
- [ ] Update documentation

---

## What Works Without Changes

The following will work as-is with the new structure data:
- Chat messages (still use backend `/structure-chat`)
- Server token authentication (if needed)
- Terminal display and commands
- Tool output and animations

---

## Full Example: Production-Ready Hook

```typescript
// frontend/src/hooks/useWalletStructures.ts
import { useState, useEffect, useCallback } from 'react';
import { getCharacterAndOwnedObjects } from '@evefrontier/dapp-kit';

export interface Structure {
  id: string;
  name: string;
  type: string;
  state: string;
  system_name?: string;
  owner_address: string;
}

export interface Character {
  id: string;
  name: string;
  address: string;
  tribeId: number;
}

interface UseWalletStructuresReturn {
  character: Character | null;
  structures: Structure[];
  loading: boolean;
  error: string | null;
  refetch: () => Promise<void>;
}

const QUERY_TIMEOUT = 10000; // 10 second timeout

export function useWalletStructures(
  walletAddress: string | null | undefined,
  autoRefetch = true
): UseWalletStructuresReturn {
  const [character, setCharacter] = useState<Character | null>(null);
  const [structures, setStructures] = useState<Structure[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const fetchStructures = useCallback(async () => {
    if (!walletAddress) {
      setCharacter(null);
      setStructures([]);
      return;
    }

    setLoading(true);
    setError(null);

    try {
      // Set timeout for query
      const controller = new AbortController();
      const timeoutId = setTimeout(() => controller.abort(), QUERY_TIMEOUT);

      const result = await Promise.race([
        getCharacterAndOwnedObjects(walletAddress),
        new Promise((_, reject) =>
          setTimeout(
            () => reject(new Error('Query timeout')),
            QUERY_TIMEOUT
          )
        ),
      ]);

      clearTimeout(timeoutId);

      if (!result || typeof result !== 'object') {
        throw new Error('Invalid response from blockchain');
      }

      const typedResult = result as any;

      if (typedResult.errors) {
        throw new Error(
          `Blockchain error: ${typedResult.errors[0]?.message || 'Unknown'}`
        );
      }

      const characterNode = typedResult.data?.address?.objects?.nodes?.[0];
      if (!characterNode) {
        throw new Error('No character found for this wallet');
      }

      const characterJson = characterNode.contents?.extract?.asAddress?.asObject
        ?.asMoveObject?.contents?.json;

      if (!characterJson || typeof characterJson !== 'object') {
        throw new Error('Could not parse character data');
      }

      setCharacter({
        id: (characterJson as any).id || '',
        name: (characterJson as any).metadata?.name || 'Unknown',
        address: (characterJson as any).character_address || '',
        tribeId: (characterJson as any).tribe_id || 0,
      });

      const ownedObjects =
        characterNode.contents?.extract?.asAddress?.objects?.nodes || [];

      const parsedStructures: Structure[] = [];

      for (const obj of ownedObjects) {
        try {
          const structureJson = (obj as any).contents?.extract?.asAddress
            ?.asObject?.asMoveObject?.contents?.json;

          if (structureJson && typeof structureJson === 'object') {
            parsedStructures.push({
              id: (structureJson as any).id || '',
              name: (structureJson as any).name || 'Unknown',
              type: (structureJson as any).type || 'Unknown',
              state: (structureJson as any).state || 'unknown',
              system_name: (structureJson as any).system_name,
              owner_address: (characterJson as any).character_address || '',
            });
          }
        } catch (e) {
          console.warn('Could not parse structure:', e);
        }
      }

      setStructures(parsedStructures);
    } catch (err) {
      const errorMsg = err instanceof Error ? err.message : 'Unknown error';
      setError(errorMsg);
      console.error('[useWalletStructures] Error:', err);
    } finally {
      setLoading(false);
    }
  }, [walletAddress]);

  useEffect(() => {
    if (autoRefetch) {
      fetchStructures();
    }
  }, [walletAddress, fetchStructures, autoRefetch]);

  return {
    character,
    structures,
    loading,
    error,
    refetch: fetchStructures,
  };
}
```

---

## Summary

1. Copy `useWalletStructures` hook into your project
2. Replace `useState` calls in TerminalUI with the hook
3. Update `/list` command to use new data
4. Test with `npm run dev`
5. Build and deploy

**Result:** Structures loaded directly from blockchain, no backend endpoint needed.

