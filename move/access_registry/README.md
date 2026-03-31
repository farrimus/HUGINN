# AccessRegistry — Sui Move Contract

Per-structure on-chain access control for EVE Frontier Companion.

## Deployment

**Network:** Nova testnet (chain-id `4c78adac`)
**Package ID:** `0xf33568afc1a24e7b5de4db95d01b5db1d0ef6a99269251fb9a355dde844255b9`
**Status:** Live and in use.

## What It Does

Structure owners create an `AccessRegistry` shared object that defines who can access their
installation's AI companion. The Python backend queries this object on every pilot interaction
to resolve the access tier (OWNER / TRIBE / VETTED / NONE). That tier gates the companion's
available tools, response depth, and news access in real time via Sui JSON-RPC.

## Access Tiers

| Tier | Who | Access |
|------|-----|--------|
| OWNER | Structure owner wallet | Full — all tools, admin, Huginn Signal |
| TRIBE | Corp/tribe member addresses | Read — chat, structure state |
| VETTED | Explicitly approved outsiders | Read — limited data |
| NONE | Everyone else | Minimal public info only |

## Entry Points

| Function | Who can call | Effect |
|----------|-------------|--------|
| `create(structure_id)` | Anyone | Creates new registry, caller becomes owner |
| `add_tribe(addr)` | Owner | Adds address to tribe (corp member) list |
| `remove_tribe(addr)` | Owner | Removes address from tribe list |
| `add_vetted(addr)` | Owner | Adds address to vetted outsider list |
| `remove_vetted(addr)` | Owner | Removes address |
| `transfer_ownership(new_owner)` | Owner | Transfers ownership |

## Source

- Contract: `sources/access_registry.move`
- Tests: `tests/access_registry_tests.move`
- Published metadata: `Published.toml`
