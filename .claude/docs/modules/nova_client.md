# nova_client

## Overview
Sui JSON-RPC client for Nova chain (EVE Frontier builder sandbox). Wraps `sui_getObject` and `suix_queryEvents` for on-chain structure data. Provides typed access to AccessRegistry objects and generic RPC methods. Resolves wallet addresses to access tiers (OWNER, TRIBE, VETTED, NONE).

## When Should an Agent Use This Module?
- Fetching AccessRegistry shared objects for structure access tier resolution
- Resolving a pilot's wallet address to access tier (OWNER/TRIBE/VETTED/NONE)
- Making raw Sui JSON-RPC calls when no typed client exists

## Key API
| Symbol | Type | Purpose | Agent Instruction |
|--------|------|---------|------------------|
| `nova_client.get_access_registry(object_id)` | async method | Fetch an AccessRegistry object by Sui object ID | Use to retrieve tier lists for a structure |
| `nova_client.resolve_tier(address, registry)` | method | Resolve wallet address to access tier | After fetching registry, call with pilot address to get tier |
| `nova_client._rpc(method, params)` | async method | Generic Sui JSON-RPC call | Advanced: use only for custom RPC calls not covered by typed methods |

### Data Structures
**AccessRegistry**
```python
@dataclass
class AccessRegistry:
    owner: str        # Wallet address of structure owner
    tribe: list       # Authorized tribe member addresses
    vetted: list      # Vetted outsider addresses
```

## Critical Gotchas & Pitfalls for Agents
• **get_access_registry is async:** Use `await` and call from async context.
• **resolve_tier is NOT async:** Takes an AccessRegistry object (already fetched), returns tier string immediately.
• **RPC endpoint configurable:** Set `NOVA_RPC_URL` env var to switch from Testnet to Stillness or custom node.
• **Timeout 10 seconds:** All RPC calls have 10s timeout; slow chain responses fail gracefully and return `None` or raise.
• **Address comparison is case-insensitive:** `resolve_tier()` lowercases both address and registry entries before comparing.
• **No error details returned:** `get_access_registry()` returns `None` on any RPC error — caller must handle gracefully.

## Architecture
```
Fetch AccessRegistry:
  Input: object_id (Sui object ID)
  ↓
  Build JSON-RPC payload {"jsonrpc": "2.0", "id": 1, "method": "sui_getObject", "params": [object_id, ...]}
  ↓
  POST to NOVA_RPC_URL with 10s timeout
  ↓
  Extract fields (owner, tribe, vetted)
  ↓
  Return AccessRegistry or None

Resolve Tier:
  Input: address (wallet address), registry (AccessRegistry)
  ↓
  Lowercase address
  ↓
  Check if address == registry.owner.lower() → return "OWNER"
  Check if address in [t.lower() for t in registry.tribe] → return "TRIBE"
  Check if address in [v.lower() for v in registry.vetted] → return "VETTED"
  Otherwise → return "NONE"
```

## Agent Guidance
**Primary Workflow**
1. To resolve structure access: `access_reg = await nova_client.get_access_registry(object_id)`
2. Fetch pilot address from request headers/session
3. Resolve tier: `tier = nova_client.resolve_tier(pilot_address, access_reg)`
4. Handle `None` return from get_access_registry: structure may not have AccessRegistry object, fall back to server-side tier

**Best Practices & Anti-Patterns**
- Always / Use `get_access_registry()` then `resolve_tier()` for access control flow
- Always / Lowercase pilot addresses before passing to `resolve_tier()`
- Always / Call from async functions; wrap in `asyncio.run()` if needed from sync code
- Always / Handle `None` gracefully — assume tier=NONE if registry not found
- Never / Poll the same object repeatedly in quick succession (cache results)

**Cross-Module Dependencies**
- Depends on: `httpx` (async HTTP), Sui chain RPC endpoint (Nova or Stillness)
- Used by: `location_index` (rebuild), `structure_auth` (tier resolution), `ssu_poller` (SSU state)

## Progressive Disclosure
**Read this main file by default.**

**Load deeper files ONLY when:**
- You need Sui RPC docs: see https://docs.sui.io/sui-api-ref
- You need to add new RPC methods: read `nova_client.py` for pattern
- You need structure auth flow: read `/docs/ref/structure-ai.md` section on access tiers
