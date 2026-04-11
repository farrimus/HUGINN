# dapp-kit Compliance — Audit Findings & Work Items

All identified dapp-kit boundary violations across the frontend and backend, with impact analysis, risk ratings, and a prioritised implementation order. Use this as the complete guide for bringing the codebase into alignment with the data layer boundary defined in `CLAUDE.md`.

`docs/DAPP_KIT_API.md` was also audited against the installed package (v0.1.7). Inaccuracies are in Section 3.

---

## Background: The Boundary

`CLAUDE.md` defines the boundary. In short:

- **dapp-kit owns** — all Sui GraphQL data: assembly state, character resolution, ownership, type metadata, fuel/energy config, inventory dynamic fields.
- **Backend owns** — AI chat, galaxy geography, derived fuel metrics (`hours_remaining`, `burn_rate_units_per_hr`), batch network topology, session management, courier/tribe boards.
- **World API (REST) belongs to the backend** — `/v2/solarsystems`, `/v2/killmails`, `/v2/tribes`, `/v2/smartcharacters` are not Sui GraphQL and are correctly handled server-side.

---

## Section 1 — Backend Violations

### B1 · `src/graphql_queries.py` — Python copy of dapp-kit query layer

**What it is:** A complete copy of dapp-kit's GraphQL query strings (`GET_WALLET_CHARACTERS`, `GET_SINGLETON_CONFIG_OBJECT_BY_TYPE`, `GET_OBJECTS_BY_TYPE`, etc.), the `TENANT_CONFIG` map with package IDs and datahub hostnames, and type string builder functions. Makes direct calls to `https://graphql.testnet.sui.io/graphql`.

**Only consumer:** `entity_resolver.py`. Nothing else imports it.

**Action:** Delete alongside the entity_resolver chain-access methods in Phase 2 (see B2). No standalone migration needed.

---

### B2 · `src/entity_resolver.py` — Backend reimplementation of `useSmartObject` and related GraphQL functions

**What it is:** `EntityResolver` makes direct Sui GraphQL calls for:
- Assembly data (`get_assembly`, `get_assembly_full`) — duplicates `useSmartObject()` / `getAssemblyWithOwner()`
- Character resolution from wallet (`get_character`) — duplicates `getWalletCharacters()`
- EnergyConfig singleton (`get_energy_config`) — duplicates `getEnergyConfig()`
- FuelConfig singleton (`get_fuel_config`) — duplicates `getFuelEfficiencyConfig()`
- SSU inventory via dynamic fields (`get_inventory`) — duplicates dapp-kit dynamic field resolution

**The complication — four active consumers:**

| Consumer | Usage | Removable? |
|---|---|---|
| `endpoints/entity.py` | Powers `/entity/assembly`, `/entity/network`, `/entity/nodes`, `/entity/inventory` | No — frontend calls all four |
| `endpoints/companion.py` | `get_assembly_full` + `get_inventory` on first chat message only | Yes — frontend has this data in EntityContext |
| `ai_tools.py` | `search_types_by_name` (type lookup), `get_inventory` + `get_assembly_full` (build calculator) | Partially — see type cache note below |
| `ssu_watcher_task.py` | `get_inventory` every 60s for all active watch rules | No — background polling has no frontend substitute |

**Parts that are legitimately backend-owned** (do not remove):
- `prewarm_types`, `search_types_by_name`, `get_all_categories`, `get_types_for_category` — pre-warmed Datahub catalog used by the `lookup_item_type` AI tool. dapp-kit's `getDatahubGameInfo()` fetches one type at a time and cannot power fuzzy search. This is a correct backend concern.
- `get_inventory` as used by `ssu_watcher_task.py` — background polling with no connected client.

**Parts that are violations** (target for removal):
- `get_assembly`, `get_assembly_full`, `get_network`, `get_all_network_nodes`, `get_character`, `get_energy_config`, `get_fuel_config`, and the GraphQL client (`_gql()`).

**Migration — two phases:**

**Phase 1 (safe, no endpoint changes):** Eliminate entity_resolver from the companion chat path.

Current architecture: on first chat message, `_preload_context()` in `companion.py` calls `get_assembly_full()` live from Sui GraphQL. The `CompanionChatRequest` body contains `assembly_id`, `assembly_name`, `assembly_type`, `assembly_state` but not inventory, network state, owner character detail, or connected assemblies.

The frontend already has all of this in `EntityContext` (`enrichedAssembly`, `networkData`, `inventoryData`). Add an optional `entity_snapshot` field to `CompanionChatRequest`. When present, `_preload_context()` uses it and skips the chain fetch. The frontend populates it from `EntityContext` state.

Result: removes the Sui GraphQL call from the hot chat path, reduces first-message latency, eliminates `get_assembly_full` and `get_inventory` from `companion.py`.

**Phase 2 (housekeeping, no behavioral change):** Split `entity_resolver.py` into:
- `src/datahub_types.py` — the Datahub type catalog (legitimate backend). Consumed by `ai_tools.py`.
- `src/sui_adapter.py` — the chain-access methods (`get_assembly_full`, `get_network`, `get_inventory`, etc.). Consumed by `endpoints/entity.py` and `ssu_watcher_task.py`. This half remains a known boundary violation that stays until a `/entity/*` endpoint redesign is undertaken.

Delete `graphql_queries.py` as part of Phase 2. `sui_adapter.py` would own its query strings inline.

---

### B3 · `src/ssu_poller.py` — Background polling via `sui_getObject`

**What it is:** Background polling loops using `sui_getObject` (Sui JSON-RPC, not GraphQL). Duplicates `getAssemblyWithOwner()`, `getAssemblyType()`, `parseStatus()` from the frontend side.

- `poll_ssu_state()` — 2-hop `sui_getObject` for assembly data
- `poll_connected_assemblies()` — `sui_getObject` per assembly + manual type repr parsing + manual status parsing
- `poll_ssu_inventory()` — `suix_getDynamicFields` + `sui_getObject` per inventory field

**Action:** Do not remove. Background polling runs with no connected client — it has no frontend substitute (see Section 5). The poller uses the older Sui JSON-RPC path; `ssu_watcher_task.py` uses the newer GraphQL-based path. Consolidating them onto GraphQL is a housekeeping improvement, not a compliance fix, and is not prioritised in Section 4.

---

### B4 · `src/endpoints/game_data.py` — `/sui/object/{object_id}` proxy

`GET /sui/object/{object_id}` proxies `sui_getObject` directly to the frontend. The frontend should use dapp-kit's `executeGraphQLQuery()` with `GET_OBJECT_WITH_JSON` instead.

**Action:** Verify whether the frontend currently calls this endpoint. If it does not, delete it. If it does, replace the frontend call site with `executeGraphQLQuery(GET_OBJECT_WITH_JSON, { address: objectId })` before removing the endpoint.

---

### B5 · Duplicated `parseStatus()` — three implementations

`_parse_status()` in `entity_resolver.py`, `_fmt_status()` in `endpoints/companion.py`, and `_status()` in `endpoints/entity.py` independently parse `{"@variant": "ONLINE"}` style status variants.

**Action:** Consolidate into a single `parse_status(raw)` utility in `src/utils.py`. Replace all three call sites.

---

### B6 · Duplicated `getAssemblyType()` — two implementations

`_classify_assembly_type()` in `entity_resolver.py` and `_assembly_type_label()` in `ssu_poller.py` both parse Move type repr strings to determine assembly kind.

**Action:** Consolidate into a single `classify_assembly_type(type_repr)` function in `src/utils.py`. Replace both call sites.

---

## Section 2 — Frontend Violations

### F1 · `GateUI.tsx` — Duplicate session registration and admin config fetch

**Lines ~131–173.** Two `useEffect` blocks reimplement what `useSession.ts` already provides: `POST /session/register`, `GET /admin/config`, `GET /admin/tool-registry`. GateUI maintains its own `tier`, `featureFlags`, `toolFlags`, `toolRegistry` state in parallel.

**Behavioral difference from `useSession`:**
- GateUI always sends `character_name: walletAddress.slice(0, 10)`. `useSession` resolves the real character name from chain via GraphQL and sends it on a second register call after resolution. GateUI sessions are registered with inferior identity data.
- GateUI never calls tribe presence (`POST /tribe/presence`). If the gate owner is a tribe member, their presence is not reported.
- GateUI does not track `sessionRegistered`. `useSession` returns this flag, which `TerminalUI` uses as a readiness gate.

**Migration:**
1. Remove the two `useEffect` blocks (lines ~130–173) and the four local state declarations.
2. Call `useSession(walletAddress, assemblyId, tenant, assembly?.solarSystem?.name || '')`.
3. Destructure `{ tier, featureFlags, setFeatureFlags, toolFlags, setToolFlags, toolRegistry }` — all are returned by `useSession` and already consumed by GateUI's AdminPanel.

**Risk: MED.** `useSession` returns a `sessionRegistered` flag that `TerminalUI` uses as a readiness gate. GateUI does not currently gate on this. If the swap is done and GateUI does not adopt the gate, there is no timing regression — the chat input remains available immediately. If GateUI does adopt the gate, the chat input is disabled for one HTTP round-trip on first load; `useSession` sets `sessionRegistered = true` in its catch handler, so a backend failure does not blank the UI permanently. No extension to `useSession` is required — it returns all fields GateUI needs and sends a strict superset of the inline version's request payload.

---

### F2 · `GateUI.tsx` and `TurretUI.tsx` — `chain` parameter in `useSponsoredTransaction`

**This is not a bug.** The `chain` field appears in the dapp-kit JSDoc but does NOT exist in the actual `SponsoredTransactionArgs` type or the `mutationFn` implementation. TypeScript enforces required fields — both files compile. Transactions are working correctly. No code change needed. The documentation in `DAPP_KIT_API.md` should be corrected to remove `chain` from the type description.

---

### F3 · `main.tsx` — Redundant outer `QueryClientProvider`

`main.tsx` wraps with both `<QueryClientProvider client={queryClient}>` and `<EveFrontierProvider queryClient={queryClient}>`. `EveFrontierProvider` internally wraps `QueryClientProvider` as its first layer. Both wrappers reference the same `QueryClient` instance.

**Impact:** None. React Query v5 resolves hooks to the nearest context. No hooks in `frontend/src/` are positioned outside `EveFrontierProvider`. The outer wrapper is unreachable dead weight.

**Action:** Remove the outer `<QueryClientProvider>` wrapper and the `QueryClientProvider` import from `@tanstack/react-query` in `main.tsx`.

**Risk: LOW.**

---

### F4 · Multiple files — Manual wallet address truncation instead of `abbreviateAddress()`

**Locations:** `TurretUI.tsx:152`, `GateUI.tsx:61`, `GateUI.tsx:135`, `useSession.ts:96`, `useSession.ts:132`, `useSession.ts:136`, `TerminalUI.tsx:280`.

`abbreviateAddress(addr, precision?)` outputs `${addr.slice(0, precision)}...${addr.slice(-precision)}` (default `precision=5`, producing a 13-char string). Current code produces 8- or 10-char strings with no trailing context or different ellipsis style.

**Two distinct use sites:**

1. **Display only** (`TurretUI.tsx:152`, `GateUI.tsx:61`, `TerminalUI.tsx:280`): Visual change only. Use `abbreviateAddress(addr, 8)` to stay close to the current display length.

2. **POST body `character_name` fallback** (`GateUI.tsx:135`, `useSession.ts:96`, `useSession.ts:132/136`): This changes the stored session `character_name` for wallets without a resolved real name. Verify the backend is fine with the new format before changing these sites.

**Risk: LOW–MED.** Visual-only sites are safe. POST body sites require backend verification.

---

### F5 · Multiple files — Manual status string comparison instead of `parseStatus()` + `State` enum

**Locations:** `EntityContext.tsx:349`, `TurretUI.tsx:45–46`, `GateUI.tsx:99`, `GateUI.tsx:446–451`.

**Critical implementation detail:** `State.ONLINE` equals the string `"online"` (lowercase). Backend strings are uppercase (`"ONLINE"`, `"ANCHORED"`). A naive `rawStatus === State.ONLINE` comparison silently breaks — always false.

**Required pattern:** `parseStatus(rawStatus) === State.ONLINE` — parse first, then compare to the enum.

**ANCHORED normalization:** `parseStatus('ANCHORED')` returns `State.ANCHORED`, not `State.ONLINE`. The current `TurretUI.tsx` isOnline check correctly handles both: `state.toLowerCase() === 'online' || state.toLowerCase() === 'anchored'`. Any replacement must preserve the `|| State.ANCHORED` branch, or anchored turrets will display and behave as offline.

**Risk: MED.** Correct in principle. Silent breakage risk if the enum-vs-uppercase trap is missed or the ANCHORED branch is dropped.

---

### F6 · `EntityContext.tsx` — Manual GraphQL response traversal instead of `getCharacterOwnedObjects()`

**Lines ~291–356.** After calling `getCharacterAndOwnedObjects(walletAddress)`, the code manually walks `result.data?.address?.objects?.nodes?.[0]?.contents?....`. dapp-kit exports `getCharacterOwnedObjects(address)` which performs this traversal and returns `Record<string, unknown>[] | undefined`.

**Action:** Replace the manual traversal with `getCharacterOwnedObjects(walletAddress!)`.

**Risk: LOW.**

---

### F7 · `EntityContext.tsx` + `useSession.ts` — Duplicate `GET_WALLET_CHARACTERS` call

Both make independent `executeGraphQLQuery(GET_WALLET_CHARACTERS, ...)` calls with the same wallet address to fetch the character name. `useSession` populates `visitorName` for the terminal display; `EntityContext` populates `characterAssemblies.character_name` for the asset map. `TerminalUI` could read `characterAssemblies?.character_name` from `useEntityContext()` instead of having `useSession` re-fetch it independently.

**Risk: LOW.** Not a correctness issue — an efficiency issue. Consolidate after F1 (GateUI session fix) to avoid coordinating changes across multiple files at once.

---

### F8 · `BaselinePanel` — `gameTypeName` slot unpopulated; `getDatahubGameInfo()` never called

`BaselinePanel` renders a TYPE / CATEGORY section conditioned on `data.gameTypeName || data.enrichmentLoading`. Neither field is ever populated. `getDatahubGameInfo(typeId)` would provide it. The `type_id` field is present on `EnrichedAssembly` as a `string`.

**Implementation requirements:**
- `getDatahubGameInfo` is async and makes a live HTTP fetch to Datahub. It has no internal cache and no error handling — a non-OK response causes an uncaught throw.
- `type_id` on `EnrichedAssembly` is a `string`; `getDatahubGameInfo` expects a `number`. Requires `Number(type_id)` conversion.
- Must be wrapped in a `useQuery` keyed on `['datahub-type', type_id]` with a `staleTime` (type data is static). Pass `enrichmentLoading: true` while pending.

**Risk: MED.** No regression for existing behavior (section is always hidden until populated). The risk is entirely in the implementation — `getDatahubGameInfo` needs a try/catch wrapper, the type conversion, and a `useQuery` wrapper, not a bare `useEffect`.

---

### F9 · `GateUI.tsx:66` — Unsafe type cast instead of `assertAssemblyType()`

`const gateAssembly = assembly as AssemblyType<Assemblies.SmartGate> | null` is an unsafe TypeScript cast. The correct pattern is `assertAssemblyType(assembly, Assemblies.SmartGate)` which narrows the type safely.

**Risk: LOW.** Works at runtime. TypeScript-only correctness issue.

---

### F10 · `GateUI.tsx` and `TurretUI.tsx` — Truncated tx digest instead of `getTxUrl()`

Both display `result.digest.slice(0, 12)` after a transaction. dapp-kit exports `getTxUrl(chain, txHash)` returning a full Suiscan explorer URL. The `useNotification` `txHash` param accepts this URL directly.

**Risk: LOW.**

---

## Section 3 — `DAPP_KIT_API.md` Inaccuracies

### D1 · `executeGraphQLQuery` — `variables` marked optional, is required

Doc shows `variables?: Record<string, unknown>`. Actual package signature: `variables: Record<string, unknown>` (required, no `?`). Callers must always pass an object; use `{}` for variable-free queries.

**Fix:** Remove the `?`.

---

### D2 · `GET_OBJECT_DYNAMICFIELD_CHARACTER_WITH_JSON` listed as public export

This constant is defined in `graphql/queries.ts` and used internally by `getObjectAndCharacterOwner()` (marked `@internal`), but is not re-exported from `graphql/index.ts`. Importing it from `@evefrontier/dapp-kit/graphql` fails. It is not imported anywhere in `frontend/src/`.

**Fix:** Remove from the Query Constants table, or add an explicit note that it is internal.

---

### D3 · `chain` in `UseSponsoredTransactionArgs` — not a real field

The doc shows `chain: string` as a required field in `UseSponsoredTransactionArgs`. This field does not exist in the actual type definition or the `mutationFn` implementation. It is JSDoc-only.

**Fix:** Remove `chain` from the `UseSponsoredTransactionArgs` type block in the doc.

---

## Section 4 — Work Item Priority Order

Items are ordered by: risk of the current state causing production bugs first, then data quality improvements, then housekeeping.

| # | Area | Item | Risk | Effort |
|---|------|------|------|--------|
| 1 | Backend | B2 Phase 1: Add `entity_snapshot` to `CompanionChatRequest`, remove Sui GraphQL calls from chat path | MED | Medium |
| 2 | Frontend | F1: Replace GateUI inline session block with `useSession` | MED | Small |
| 3 | Doc | D3: Remove `chain` from `UseSponsoredTransactionArgs` in `DAPP_KIT_API.md` | LOW | Trivial |
| 4 | Doc | D1: Fix `executeGraphQLQuery` `variables` — remove `?` | LOW | Trivial |
| 5 | Doc | D2: Remove `GET_OBJECT_DYNAMICFIELD_CHARACTER_WITH_JSON` from public table | LOW | Trivial |
| 6 | Frontend | F3: Remove outer `QueryClientProvider` from `main.tsx` | LOW | Trivial |
| 7 | Frontend | F6: Replace manual GraphQL response traversal with `getCharacterOwnedObjects()` | LOW | Small |
| 8 | Frontend | F5: Use `parseStatus()` + `State` enum (careful with case — use `parseStatus(raw) === State.X` pattern) | MED | Small |
| 9 | Frontend | F4: Replace `walletAddress.slice(0, N)` with `abbreviateAddress()` — display sites first, POST body sites after backend verification | LOW–MED | Small |
| 10 | Frontend | F8: Populate `gameTypeName` via `getDatahubGameInfo()` using `useQuery` + error handling | MED | Medium |
| 11 | Backend | B5: Consolidate three `parse_status()` reimplementations into `src/utils.py` | LOW | Small |
| 12 | Backend | B6: Consolidate two `getAssemblyType()` reimplementations into `src/utils.py` | LOW | Small |
| 13 | Backend | B4: Verify `/sui/object/{object_id}` proxy endpoint is unused; delete if so | LOW | Trivial |
| 14 | Backend | B2 Phase 2: Split `entity_resolver.py` into `datahub_types.py` + `sui_adapter.py` | LOW | Medium |
| 15 | Frontend | F7: Consolidate duplicate `GET_WALLET_CHARACTERS` call after F1 is done | LOW | Small |
| 16 | Frontend | F9: Replace unsafe type cast with `assertAssemblyType()` | LOW | Trivial |
| 17 | Frontend | F10: Use `getTxUrl()` for transaction digest links | LOW | Small |

---

## Section 5 — What Not To Change

These items appear to be violations but should not be changed:

**`/entity/assembly`, `/entity/network`, `/entity/nodes`, `/entity/inventory` endpoints** — the frontend calls all four actively from `EntityContext.tsx`. These are the primary data pipeline for all UI panels. Removing them without replacing the entire `EntityContext` data flow breaks the UI.

**`ssu_watcher_task.py` + `ssu_poller.py` chain access** — background polling with no connected client cannot be replaced by frontend-driven data pushes. Server-side chain access is correct here.

**`entity_resolver.py` Datahub type cache** (`prewarm_types`, `search_types_by_name`) — the `lookup_item_type` AI tool uses fuzzy search across the full type catalog. dapp-kit's `getDatahubGameInfo()` is a per-type point lookup; it cannot replace this. This is legitimately backend-owned.

**`blockchain_queries.py` `get_access_registry()`** — reads the `AccessRegistry` shared object for OWNER/TRIBE/VETTED tier resolution. This is server-side auth logic with no dapp-kit equivalent.

**`blockchain_killmails.py`** — uses `suix_queryEvents` for `KillmailCreatedEvent` ingestion. No dapp-kit primitive covers bulk historical killmail fetching for AI context.

**`location_index.py`** — indexes `LocationRevealedEvent` on-chain events into a local file. No dapp-kit equivalent for historical event indexing.
