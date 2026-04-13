# move/ -- Sui Move Smart Contracts

## AccessRegistry Contract

Per-structure on-chain access control for the EVE Frontier Companion.

**Source:** `access_registry/sources/access_registry.move`
**Tests:** `access_registry/tests/access_registry_tests.move`
**Network:** Nova testnet (chain-id `4c78adac`)
**Package ID:** `0xf33568afc1a24e7b5de4db95d01b5db1d0ef6a99269251fb9a355dde844255b9`

### Access Tiers

| Tier | Who | Access |
|------|-----|--------|
| OWNER | Structure owner wallet | Full -- all tools, admin, Huginn Signal |
| TRIBE | Corp/tribe member addresses | Read -- chat, structure state |
| VETTED | Explicitly approved outsiders | Read -- limited data |
| NONE | Everyone else | Minimal public info only |

### Entry Points

| Function | Who can call | Effect |
|----------|-------------|--------|
| `create(structure_id)` | Anyone | Creates registry, caller becomes owner |
| `add_tribe(addr)` / `remove_tribe(addr)` | Owner | Manage tribe list |
| `add_vetted(addr)` / `remove_vetted(addr)` | Owner | Manage vetted list |
| `transfer_ownership(new_owner)` | Owner | Transfer ownership |

The Python backend reads this contract on every request via `src/blockchain_queries.py` to resolve pilot access tier.
