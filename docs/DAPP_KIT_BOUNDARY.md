# dapp-kit Boundary — Decision Reference

**Purpose:** Before writing any data-layer code, answer "where does this belong?" using this table.
This is the authoritative boundary. There is no need to consult any other document first.

**Full technical record** (per-type field maps, all GraphQL queries, raw on-chain schema): `docs/DATA_LAYER_MAP.md`

---

## The Boundary in One Sentence

**dapp-kit owns all game data access. The Python backend owns AI, social infrastructure, and derived metrics.**

---

## Decision Table — "I need to..."

| Task | Owner | Exact Call |
|------|-------|------------|
| Get assembly data (any type) | dapp-kit | `useSmartObject(assemblyId)` or `getAssemblyWithOwner(assemblyId)` |
| Transform raw Move object → typed assembly | dapp-kit | `transformToAssembly(objectId, moveObject, options)` |
| Get character owned by a wallet | dapp-kit | `getWalletCharacters(wallet)` |
| Get character + all assemblies it owns | dapp-kit | `getCharacterAndOwnedObjects(wallet)` |
| Transform raw character JSON → typed character | dapp-kit | `transformToCharacter(characterInfo)` |
| Get type name, groupName, category, icon, volume | dapp-kit | `getDatahubGameInfo(typeId)` |
| Parse assembly status string → State enum | dapp-kit | `parseStatus(statusVariant)` |
| Classify Move type repr → assembly kind | dapp-kit | `getAssemblyType(moveTypeRepr)` |
| Get energy usage constants (all types) | dapp-kit | `getEnergyConfig()` → `getEnergyUsageForType(typeId)` |
| Get fuel efficiency constants (all types) | dapp-kit | `getFuelEfficiencyConfig()` → `getFuelEfficiencyForType(typeId)` |
| Get adjusted burn rate with efficiency | dapp-kit | `getAdjustedBurnRate(typeId, quantity)` |
| Format a duration in ms → human string | dapp-kit | `formatDuration(ms)` |
| Format a volume in m³ → human string | dapp-kit | `formatM3(volume)` |
| Abbreviate a Sui address | dapp-kit | `abbreviateAddress(address, precision, expanded)` |
| Execute a sponsored transaction | dapp-kit | `useSponsoredTransaction()` |
| Run any Sui GraphQL query | dapp-kit | `executeGraphQLQuery(query, variables)` — or use a named query from `graphql/queries.ts` |
| AI companion chat | Backend only | Python + Claude API |
| Solar system / galaxy geography lookup | Backend only | Galaxy DB (Python) |
| Fuel hours remaining, burn rate derived metrics | Backend (adds value) | `compute_fuel_state()` — dapp-kit returns raw fuel data, not derived hours |
| Network topology (20 connected assemblies, parallel) | Backend (adds value) | `get_network()` — dapp-kit has no batch fetch |
| Courier board contracts | Backend only | Session + DB (Python) |
| Tribe board / presence roster | Backend only | Session + DB (Python) |
| Server-side session management | Backend only | Python session store |
| Startup type cache prewarm | Backend only | Python startup task |

---

## What dapp-kit Does NOT Cover

These are the only things the Python backend legitimately owns that dapp-kit cannot provide:

1. **AI reasoning** — Claude API calls, prompt construction, lore context injection
2. **Galaxy DB** — solar system topology, jump routes, geographic context
3. **Derived fuel metrics** — hours_remaining, burn_rate_units_per_hr (dapp-kit returns raw FuelResponse, not computed state)
4. **Batch network topology** — fetching 20 connected assemblies in parallel; dapp-kit has no batch primitive
5. **Social boards** — courier contracts, tribe presence, server-side state
6. **Session management** — player sessions, auth state across requests

If your task is not on this list, check whether dapp-kit covers it before writing Python.

---

## The 9 Known Backend Duplications (as of 2026-03-29)

These exist in the backend and duplicate dapp-kit. They work, so do not delete them mid-project.
But do not add more. And when refactoring, move these toward dapp-kit equivalents.

| Python Function | Duplicates |
|----------------|------------|
| `_classify_assembly_type()` | `getAssemblyType()` |
| `_parse_status()` | `parseStatus()` |
| `get_character()` | `getWalletCharacters()` |
| `get_character_assemblies()` | `getCharacterAndOwnedObjects()` |
| `get_energy_config()` | `getEnergyConfig()` |
| `get_fuel_config()` | `getFuelEfficiencyConfig()` |
| `_parse_config_nodes()` | `parseConfig()` in dapp-kit config.ts |
| `_extract_fuel()` | inline logic in dapp-kit transforms.ts |
| `_extract_energy()` | inline logic in dapp-kit transforms.ts |

---

## Known Gaps in the Data (as of 2026-03-29)

These cannot be resolved without inspecting live on-chain data:

- `extension: unknown` — present on every assembly object, never parsed. Purpose unknown.
- `dynamicFields` content — only documented for SmartStorageUnit (inventory). Unknown for Gate, Turret, NetworkNode, Manufacturing, Refinery.
- `manufacturing.isParentNodeOnline` — dapp-kit computes this from the assembly's own state, not the parent node's state. May be a bug.
