# Assembly Data Flow - Official DApp Kit Implementation

**Date:** 2026-03-27
**Status:** Production - Verified against @evefrontier/dapp-kit source code
**Source:** SmartObjectProvider.tsx, useSmartObject.ts

---

## The Correct Architecture

Use **ONLY** `useSmartObject()` from DApp Kit. No custom hooks needed.

```typescript
import { useSmartObject } from '@evefrontier/dapp-kit';

export function TerminalUI() {
  const { assembly, assemblyOwner, loading, error, refetch } = useSmartObject();
  // That's it.
}
```

---

## What The Game Sends

When a player opens an assembly in-game, the browser navigates to your dApp with:

```
https://yoursite.com/?itemId=2112000113&tenant=utopia
```

**Parameters:**
- `itemId` — in-game item ID (serial number)
- `tenant` — network/realm (e.g., "utopia", "stillness")

---

## What SmartObjectProvider Does (Automatic)

SmartObjectProvider (part of EveFrontierProvider) automatically:

1. **Reads URL parameters**
   ```typescript
   const itemId = new URLSearchParams(window.location.search).get("itemId");
   const tenant = new URLSearchParams(window.location.search).get("tenant");
   ```

2. **Converts itemId+tenant to Sui Object ID**
   ```typescript
   const objectId = await getObjectId(itemId, tenant);
   // Uses BCS encoding and Sui's deriveObjectID()
   ```

3. **Fetches assembly + owner character in ONE call**
   ```typescript
   const { moveObject, assemblyOwner } = await getAssemblyWithOwner(objectId);
   ```

4. **Polls for updates** (every 5 seconds by default)

5. **Provides data via context**
   ```typescript
   SmartObjectContext.Provider value={{
     assembly,        // Assembly object with id, name, type, state, etc.
     assemblyOwner,   // Character who owns this assembly
     loading,
     error,
     refetch,
     tenant
   }}
   ```

---

## What useSmartObject() Returns

```typescript
interface SmartObjectContextType {
  assembly: {
    id: string;              // Sui object ID
    name: string;            // Assembly name
    type: Assemblies;        // Type enum (StorageUnit, Turret, Gate, etc.)
    state: State;            // ONLINE, OFFLINE, DESTROYED, etc.
    [other fields...]        // Various assembly-specific data
  } | null;

  assemblyOwner: {           // The CHARACTER who owns this assembly
    name: string;
    id: string;
    address: string;
    [other fields...]
  } | null;

  loading: boolean;          // Fetching in progress
  error: string | null;      // Error message if fetch failed
  refetch: () => Promise<void>;  // Manual refresh
  tenant: string;            // Current tenant
}
```

---

## Flow Diagram

```
Game Opens Assembly
    ↓
Browser sends: ?itemId=2112000113&tenant=utopia
    ↓
EveFrontierProvider wraps your app
    ↓
SmartObjectProvider reads URL params
    ↓
Calls getObjectId(itemId, tenant)
    ↓
Derives Sui object ID
    ↓
Calls getAssemblyWithOwner(objectId)
    ↓
Queries Sui blockchain
    ↓
Returns assembly + owner character
    ↓
Sets up polling (refreshes every 5s)
    ↓
Provides via SmartObjectContext
    ↓
useSmartObject() hook reads context
    ↓
Your component accesses { assembly, assemblyOwner }
    ↓
Display baseline panel with data
```

---

## Baseline Panel Data Mapping

```typescript
const { assembly, assemblyOwner, loading, error } = useSmartObject();

displayToolOutput('baseline', {
  crudVersion: 'HUGINN - Version',
  signature: walletAddress,           // From useConnection()
  shellName: assemblyOwner?.name,     // From useSmartObject() ← CHARACTER
  accessLevel: '[REDACTED]',          // TODO: Define source
  assemblySignature: assembly?.id,    // From useSmartObject() ← ASSEMBLY
  location: '[REDACTED]',             // TODO: Define source
});
```

---

## Configuration Options

### Option 1: URL Parameters (Recommended)

Game sends: `?itemId=2112000113&tenant=utopia`

SmartObjectProvider automatically uses these.

### Option 2: Environment Variable

Set in `.env`:
```
VITE_OBJECT_ID=0x3b2ac50f0da15672de1b876b4b674d2dd591b325758f8f7fb2151e63bd72ba20
```

SmartObjectProvider uses this if found (takes priority over URL params).

⚠️ **Not recommended for dynamic data** — only for static testing.

---

## Critical Implementation Details

### Setup Required

**In `main.tsx`:**
```typescript
import { EveFrontierProvider } from '@evefrontier/dapp-kit';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';

const queryClient = new QueryClient();

createRoot(document.getElementById('root')!).render(
  <QueryClientProvider client={queryClient}>
    <EveFrontierProvider queryClient={queryClient}>
      <App />
    </EveFrontierProvider>
  </QueryClientProvider>,
);
```

### What NOT to Do

❌ Don't create custom `useCharacterData()` hook
❌ Don't create custom `useAssemblyData()` hook
❌ Don't manually parse `?objectId=` from URL
❌ Don't call `getWalletCharacters()` separately
❌ Don't call `getObjectWithJson()` directly

✅ **Just use `useSmartObject()`**

---

## Why This Works

1. **Single source of truth** — All assembly + owner data comes from SmartObjectProvider
2. **Automatic polling** — Data stays fresh without manual refresh
3. **Type-safe** — Full TypeScript support
4. **Battle-tested** — Official DApp Kit implementation
5. **No custom logic** — Follows the framework's conventions

---

## Error Handling

```typescript
const { assembly, assemblyOwner, error, loading } = useSmartObject();

if (loading) return <div>Loading assembly...</div>;
if (error) return <div>Error: {error}</div>;
if (!assembly) return <div>No assembly found</div>;

// Safe to use now
return <div>{assembly.name}</div>;
```

---

## Debugging

SmartObjectProvider logs to console:

```
[DappKit] SmartObjectProvider: Checking for item ID
[DappKit] SmartObjectProvider: Fetching object: { itemId, selectedTenant }
[DappKit] SmartObjectProvider: Object data updated
[DappKit] SmartObjectProvider: Started polling for object: 0x...
```

Enable browser DevTools console to see flow.

---

## Related Documentation

- **Official DApp Kit:** https://docs.evefrontier.com/tools/dapp-kit
- **Sui Docs:** https://sui-docs.evefrontier.com/
- **SmartObjectProvider Source:** `@evefrontier/dapp-kit/providers/SmartObjectProvider.tsx`
- **useSmartObject Source:** `@evefrontier/dapp-kit/hooks/useSmartObject.ts`

---

## Version Info

- **@evefrontier/dapp-kit:** 0.1.7
- **React:** 19.2.4
- **@tanstack/react-query:** 5.0.0
- **TypeScript:** 5.9.3

---

## Summary

✅ **Do this:**
```typescript
const { assembly, assemblyOwner } = useSmartObject();
```

❌ **Don't do this:**
```typescript
const characterData = useCharacterData(walletAddress);
const assemblyData = useAssemblyData();
```

One hook. One source. Everything you need.
