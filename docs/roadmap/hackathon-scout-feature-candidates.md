# Hackathon Scout — Feature Candidates

Scouted from the EVE Frontier × Sui Hackathon 2026 submission pool and the EF WebCore external toolset. Seven items assessed for integration into HUGINN.

**Context:** Voting ran April 1–15. Winners announced April 24, 2026. Projects submitted to [DeepSurge](https://www.deepsurge.xyz/projects?hackathon=122cbb25-ab13-484d-82d8-fc1831bfe3df&stage=submitted) (requires login). Public list at [vote.deepsurge.xyz](https://vote.deepsurge.xyz/).

---

## Decision Summary

| # | Item | Verdict | Effort | Files |
|---|------|---------|--------|-------|
| 6 | Lore Core | **USE** | Low | `prompts/lore.md` (new) |
| 5 | Tribe Awareness | **USE** | Low | `src/world_api.py`, `src/ai_tools.py` |
| 3 | Ship Hull Stats | **USE** | Low | `src/companion.py`, `src/context_builder.py` |
| 1 | Character Session Enrichment | **USE** | Medium | `src/endpoints/session.py`, `src/companion.py`, frontend register |
| 2 | Gate Access Awareness | **DEFER** | High | — |
| 4 | KARUM Marketplace | **SKIP** | — | — |
| 7 | Dev Core | **Reference** | None | `docs/DATA_REFERENCE.md` |

---

## USE Items

### 6. Lore Core (EF WebCore)

**Status:** Not yet started

**What it is:** efwebcore.com/lore — structured lore sourced from EVE Frontier Whitepaper v0.7.5 and evefrontier.wiki. Contains:
- 5 setting entries: The Frontier, The Collapse, Rogue Drones, Riders, Digital Physics & Energy
- 4 factions: Tribes, Syndicates, Exclave Ventures (NPC / Orphan Geist), Ophidia Operations (NPC / Ophidian Sensor Cloak / Askur)
- 5 game pillars: Realism, Cruel survival, Broken world, Forever game, Co-Created Universe
- 40 glossary terms: all fuel types (D1/D2/SOF-40/SOF-80/EU-40/EU-90), Crude Matter, Rifts, Still Knot, Salt, $EVE, EVE Points, Fossilized Exotronics, Feral Echo, Rogue Drones, Riders, Tribes, Syndicates, Askur, Ophidian Sensor Cloak, and more

**Gap:** `prompts/companion.md` has no faction descriptions, no world history, no glossary. HUGINN cannot speak to any of these topics with authority.

**Implementation:** Create `prompts/lore.md` with the lore content. Inject it into the prompt build alongside `companion.md`. No code changes. Estimated token cost: ~2,000 tokens.

---

### 5. Tribe Awareness (EF WebCore — Tribe Core)

**Status:** Not yet started

**What it is:** Live tribe directory from `GET /v2/tribes` — organizations, tax rates, and identity data.

**Confirmed fields:** `id`, `name`, `nameShort`, `description`, `taxRate`, `tribeUrl`.

**Gap:** `WorldAPIClient.get_tribe()` in `src/world_api.py` exists but discards all fields except `name`. The list endpoint `GET /v2/tribes` is never called. The `manage_tribe` tool only tracks pilot presence (who's online), not tribe directory data. Tribe membership per character is available only as a `tribeId` integer via dapp-kit `CharacterInfo` — no member roster is exposed by the World API.

**Implementation:**
- Add `get_tribes()` to `WorldAPIClient` in `src/world_api.py` — one method, same `_cached_fetch` pattern as existing calls
- Fix `get_tribe(tribe_id)` in `src/world_api.py` to return the full object (name, nameShort, description, taxRate, tribeUrl) instead of only name
- Add `get_tribe_info` tool in `src/ai_tools.py` — live fetch per request, no DB storage

---

### 3. Ship Hull Stats (EF WebCore — Ship Core)

**Status:** Not yet started

**What it is:** Hull database with slot counts, CPU/powergrid output, and ship class stats.

**Gap:** `src/ship_profile.py` already contains the full hull catalog for all current hulls (Wend, Reflex, Recurve, Reiver, USV, Lorha, MCF, HAF, Tades, Maul, Chumaq, Carom) with `slots` (high/mid/low), `cpu_output`, `powergrid_output`, `fuel_capacity`, and `structure_hp`. HUGINN's context block currently sends only hull name, fuel type, fuel quantity, jump range, and jump budget — slots, CPU, and powergrid are in the catalog but not forwarded to the AI.

**Implementation:** Add `slots`, `cpu_output`, and `powergrid_output` to the ship context block in `src/companion.py` or `src/context_builder.py`. No new data sources, no new API calls.

**Out of scope:** Full fit analysis (which modules are in fitted slots) requires `GET /v2/characters/me/` endpoints that need an in-game Bearer JWT. The backend cannot hold this token. Defer until the game client exposes a solution.

---

### 1. Character Session Enrichment (EF WebCore — Character Core)

**Status:** Not yet started

**What it is:** Pilot identity enrichment at session registration — character ID and tribe ID from on-chain data.

**Gap:** `CharacterSession` in `src/endpoints/session.py` already defines `character_id` and `tribe_id` fields. Neither is populated automatically — they default to `None` in all active sessions. The frontend `RegisterRequest` does not send them. `tribe_id` is absent from `tool_context`, so the AI cannot use it for tribe-aware decisions without asking the pilot directly.

**Implementation:**
- Frontend: send `character_id` and `tribe_id` in the `/session/register` POST (dapp-kit `CharacterInfo` returns both at wallet connect time)
- `src/endpoints/session.py`: accept `character_id` and `tribe_id` in `RegisterRequest` and store them on the session
- `src/companion.py`: thread `tribe_id` into `tool_context` so it is available to tribe-aware tools

**Out of scope:**
- Owned assemblies (ships/structures): dapp-kit returns these client-side; no server relay mechanism exists
- Jump history: `GET /v2/characters/me/jumps` requires an in-game Bearer JWT; the backend cannot call it

---

## DEFER

### 2. Gate Access Awareness (Open Borders Protocol + world-contracts)

**What it is:** On-chain gate extension contracts that control jump permit issuance. Two confirmed patterns:
- `tribe_permit.move` — gate allows only pilots whose `tribe` field matches a configured `u32` tribe ID. Issues a timed `JumpPermit`.
- `corpse_gate_bounty.move` — gate requires deposit of a specific item type as toll payment.

Open Borders Protocol (hackathon submission) reportedly adds four access modes: open, tribe-only, bounty/toll, blacklist.

**Gate struct fields** (from `gate.move`): `id`, `owner_cap_id`, `linked_gate_id` (bidirectional), `AssemblyStatus`, hashed `Location`, optional `network_node`, `extension: Option<TypeName>`

**Why deferred:**

The gate's `extension: Option<TypeName>` field is readable via a single Sui RPC call — sufficient to detect locked vs. open. Everything beyond that is blocked:

- `ExtensionConfig` (the object holding tribe ID or bounty type) is a separate Sui shared object with no pointer in the Gate struct. Discovery requires per-extension lookup chains that are not self-describing from the gate alone.
- Open Borders Protocol package ID is unknown — their `ExtensionConfig` schema cannot be queried.
- Bounty gate access requires completing a transaction; it cannot be answered by a static read.
- Player-deployed SmartGates are absent from `systems.json`. The route engine in `src/route_engine.py` uses a static gate graph and has no concept of dynamically access-filtered edges.

Full access-aware routing requires: OBP package ID, per-extension `ExtensionConfig` discovery, and structural changes to `src/route_engine.py`. Unblock when OBP publishes their package ID and player SmartGates are indexed.

---

## SKIP

### 4. Marketplace and SSU Discovery (KARUM)

**What it is:** An on-chain marketplace for EVE Frontier — SSU owners register shops, players browse listings and buy resources with SUI.

**Status:** karum.space serves a JavaScript SPA. No public REST API, no Sui package ID, no on-chain registry object ID is discoverable. Nothing to integrate against.

Revisit if KARUM publishes a REST API or on-chain registry object ID. Integration pattern would be: new `find_marketplace` tool in `src/ai_tools.py`, same shape as `manage_courier`.

---

## Reference

### 7. Dev Core (EF WebCore)

**What it is:** Developer diagnostics at `https://www.efwebcore.com/debug` — endpoint health probes, GraphQL query presets, and environment package IDs.

**Package IDs recovered:**

| Object | Utopia | Stillness |
|--------|--------|-----------|
| worldPackage | `0xd12a70c74c1e759445d6f209b01d43d860e97fcf2ef72ccbbd00afd828043f75` | `0x28b497559d65ab320d9da4613bf2498d5946b2c0ae3597ccfda3072ce127448c` |
| objectRegistry | `0xc2b969a72046c47e24991d69472afb2216af9e91caf802684514f39706d7dc57` | `0x454a9aa3d37e1d08d3c9181239c1b683781e4087fbbbd48c935d54b6736fd05c` |
| killmailRegistry | `0xa92de75fde403a6ccfcb1d5a380f79befaed9f1a2210e10f1c5867a4cd82b84e` | `0x7fd9a32d0bbe7b1cfbb7140b1dd4312f54897de946c399edb21c3a12e52ce283` |
| serverAddressRegistry | `0x9a9f2f7d1b8cf100feb532223aa6c38451edb05406323af5054f9d974555708b` | `0xeb97b81668699672b1147c28dacb3d595534c48f4e177d3d80337dbde464f05f` |
| locationRegistry | `0x62e6ec4caea639e21e4b8c3cf0104bace244b3f1760abed340cc3285905651cf` | `0xc87dca9c6b2c95e4a0cbe1f8f9eeff50171123f176fbfdc7b49eef4824fc596b` |
| energyConfig | `0x9285364e8104c04380d9cc4a001bbdfc81a554aad441c2909c2d3bd52a0c9c62` | `0xd77693d0df5656d68b1b833e2a23cc81eb3875d8d767e7bd249adde82bdbc952` |
| fuelConfig | `0x0f354c803af170ac0d1ac9068625c6321996b3013dc67bdaf14d06f93fa1671f` | `0x4fcf28a9be750d242bc5d2f324429e31176faecb5b84f0af7dff3a2a6e243550` |
| gateConfig | `0x69a392c514c4ca6d771d8aa8bf296d4d7a021e244e792eb6cd7a0c61047fc62b` | `0xd6d9230faec0230c839a534843396e97f5f79bdbd884d6d5103d0125dc135827` |
| adminACL | `0xa8655c6721967e631d8fd157bc88f7943c5e1263335c4ab553247cd3177d4e86` | `0x8ca0e61465f94e60f9c2dadf9566edfe17aa272215d9c924793d2721b3477f93` |

Cross-reference these against the package IDs in `data/` config files. File any discrepancies in `docs/DATA_REFERENCE.md`.

**GraphQL patterns not in dapp-kit:** `NetworkNode` objects query (`::network_node::NetworkNode`) and `JumpEvent` filter (`::smartgate::JumpEvent`). Relevant for future network topology or gate jump feed features.

**World API:** No new `/v2/` endpoints discovered beyond those already in `docs/DATA_REFERENCE.md`.
