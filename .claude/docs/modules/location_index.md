# location_index

## Overview
Indexes Sui blockchain LocationRevealedEvent objects. Maps assembly IDs (player-owned structures) to real-world 3D coordinates and solar system names. Persisted to `data/location_index.json`; rebuilt on-demand via admin endpoint.

## When Should an Agent Use This Module?
- Looking up where a structure is located (assembly_id → system name + coordinates)
- Fetching all nearby structures in a system
- Rebuilding location data from the Sui chain

## Key API
| Symbol | Type | Purpose | Agent Instruction |
|--------|------|---------|------------------|
| `location_index.get(assembly_id)` | method | Fetch structure location by ID | Use to find structure coordinates |
| `location_index.get_all()` | method | Return all indexed structures | Use to list structures in a region |
| `location_index.load()` | method | Load index from disk | Called at module import; no network call |
| `location_index.rebuild()` | async method | Fetch from Sui chain, rebuild index | Admin-only; slow (pages through events) |

### Data Structure
Each location entry:
```json
{
  "assembly_id": "0x...",
  "solarsystem": "system_name",
  "x": 1234567890,
  "y": 2345678901,
  "z": 3456789012,
  "location_hash": "hash_value"
}
```

## Critical Gotchas & Pitfalls for Agents
• **Stale data by design:** `load()` reads from disk only; no network sync on every request. **Call `rebuild()` before gameplay if locations may have changed.**
• **Async only:** `rebuild()` is async and may take minutes (paginates through chain). Do not call mid-session.
• **Partial match:** `get()` returns `None` if assembly_id not found — return gracefully to player.

## Architecture
```
Startup:
  location_index.load() → reads data/location_index.json
  ↓
Runtime:
  get(assembly_id) → returns location dict or None
  get_all() → returns list of all locations
  ↓
Admin path (infrequent):
  rebuild() → paginates suix_queryEvents for LocationRevealedEvent
           → rebuilds index in memory
           → writes to data/location_index.json
```

## Agent Guidance
**Primary Workflow**
1. At startup: index is auto-loaded from disk
2. Fetch structure location: `get(assembly_id)` → returns `{solarsystem, x, y, z, location_hash}`
3. If location is None: structure may not exist or hasn't been revealed yet
4. Admin duty: Call `rebuild()` periodically to sync with chain (slow, but complete)

**Best Practices & Anti-Patterns**
- Always / Check if `get()` returns None before using coordinates
- Always / Call `rebuild()` from a background task, not during chat
- Never / Assume assembly_id exists without checking the result
- Never / Call `rebuild()` on every request (it's paginated and slow)

**Cross-Module Dependencies**
- Depends on: `nova_client` (Sui RPC for rebuild phase)
- Used by: `context_builder` (nearby structures), `structure_profile` (location queries), Structure AI (spatial awareness)

## Progressive Disclosure
**Read this main file by default.**

**Load deeper files ONLY when:**
- You need Sui event schema: read `/docs/ref/structure-ai.md` section on LocationRevealedEvent
- You need rebuild algorithm: read code comments in `location_index.py` for pagination logic
