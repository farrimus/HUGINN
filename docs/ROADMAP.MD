# HUGINN Development Roadmap — Post-Hackathon

This is a pre-alpha hobby project. One developer. One real tester. The hackathon MVP shipped every planned feature — AI chat, on-chain access control, route planning, log upload, kill feed, SSU watcher, courier board, tribe presence — across two environments (utopia/stillness). Nothing is finished.

The supporting analysis in `docs/roadmap/` explains why things are structured the way they are. Read those when working on the relevant area.

---

## Current State

### What is functional

| Feature | Status | Key files |
|---------|--------|-----------|
| AI companion chat (SSE streaming) | Functional | `endpoints/companion.py`, `ai_tools.py`, `context_builder.py` |
| On-chain access control | Functional — per-request Sui RPC | `session_store.py`, `endpoints/session.py` |
| Route planner | Most complete feature | `route_engine.py` + `data/gate_graph.json` |
| Recon (system intel) | Functional | World API + Galaxy DB; kill context via `context_builder.py` |
| Kill feed sync | Functional | Hourly from Sui events; `blockchain_killmails.py` |
| Log upload | Functional end-to-end | Parse + summarize + store + feeds `system_knowledge.db` |
| SSU watcher | Functional | `ssu_watcher_task.py` SSE alert streams |
| Courier board | Functional | `endpoints/courier.py` |
| Tribe presence board | Functional | `endpoints/tribe.py`, `endpoints/tribe_posts.py` |
| Huginn Signal | Functional — KILL FEED + NETWORK DELTA | `huginn_news_task.py`, `huginn_news.py` |
| Global knowledge graph | Functional — fed by log uploads | `system_knowledge.py`, `endpoints/system_knowledge.py` |
| Multi-tenant (utopia/stillness) | Functional | `config.py`; dapp-kit patch for dual-registry cache |
| AccessRegistry Move contract | Deployed | Testnet; `move/access_registry/` |

### Intelligence pipeline

| Store | AI read path | Compounds? |
|-------|-------------|-----------|
| `intel_store.py` field reports | Yes (`query_intel`) | Per-structure only |
| `log_intel_store.py` log uploads | Yes (feeds `system_knowledge.db` on upload) | Cross-pilot, global |
| `killmails.jsonl` | Partial (`context_builder.py`) | Yes — automated |
| `memory_store/` event memory | Unconfirmed | Unknown |
| `system_knowledge.db` | Yes (`query_system_knowledge`, `record_field_observation`) | Wired — grows with every upload |

### Known areas in scope for change

| Area | Current state |
|------|--------------|
| Access tier | Per-request Sui RPC — 100–400ms per chat turn; Testnet degradation = hard failure |
| Intel stores | `log_intel_store.py` has `first_seen`/`last_seen` per ore and hostile. `intel_store.py` field report scope (cross-pilot vs. personal) unaudited. |
| Claude model selection | `claude-sonnet-4-6` everywhere — log summarization and Signal don't need it |
| Log parser | Drops unknown entity types (players, ships, player structures) |
| UI | TerminalUI, GateUI, TurretUI — functional but unfinished |
| Rate limiting | None on `/companion/stream` or `/logs/upload` — tokens exposed |

---

## What to Work on Next

Items are ordered: no-blockers with no open decisions first, sorted by effort ascending; then items with soft dependencies; then items with open decisions or significant scope.

### Lore Core

- `prompts/companion.md` contains no faction descriptions, world history, or glossary. HUGINN cannot speak to these topics with authority.
- Create `prompts/lore.md` with content from the EVE Frontier Whitepaper v0.7.5: 5 setting entries (The Frontier, The Collapse, Rogue Drones, Riders, Digital Physics & Energy), 4 factions (Tribes, Syndicates, Exclave Ventures, Ophidia Operations), 5 game pillars, and 40+ glossary terms (all fuel types, Crude Matter, Rifts, Still Knot, Salt, $EVE, EVE Points, Fossilized Exotronics, and more).
- Inject `lore.md` into the prompt build alongside `companion.md`. No changes to any other file.
- Estimated token cost: ~2,000 tokens per chat turn.
- Full content specification: `docs/roadmap/hackathon-scout-feature-candidates.md` — Lore Core section.

### Ship Hull Stats

- `src/ship_profile.py` contains the full hull catalog for all current hulls with `slots` (high/mid/low), `cpu_output`, and `powergrid_output`. The ship context block in `src/context_builder.py` does not forward these fields — the AI receives hull name, class, fuel type, fuel quantity, jump range, jump budget, and adaptive level only.
- Add `slots`, `cpu_output`, and `powergrid_output` to the ship context block in `src/context_builder.py`. No new data sources, no new API calls.
- Out of scope: full fit analysis (which modules are in fitted slots) requires an in-game Bearer JWT. Defer until the game client exposes a solution.

### Character Session Enrichment

- `CharacterSession` defines `character_id` and `tribe_id` as `Optional[int]`. Both default to `None` in all active sessions — `RegisterRequest` does not include them, so they are never populated. `tribe_id` is absent from `tool_context`, so the AI cannot use it for tribe-aware decisions.
- Three files:
  - Frontend: send `character_id` and `tribe_id` in the `/session/register` POST. dapp-kit `CharacterInfo` returns both at wallet connect time.
  - `src/endpoints/session.py`: add `character_id` and `tribe_id` to `RegisterRequest`; store on the session.
  - `src/companion.py`: thread `tribe_id` into `tool_context`.
- Out of scope: owned assemblies (dapp-kit client-side only, no server relay mechanism) and jump history (`GET /v2/characters/me/jumps` requires in-game Bearer JWT).

### Tribe Awareness

- `WorldAPIClient.get_tribe(tribe_id)` discards all fields except `name`. The list endpoint `GET /v2/tribes` is never called. Tribe directory data (description, tax rate, short name, tribe URL) is unavailable to the AI.
- Three changes, all in `src/world_api.py` and `src/ai_tools.py`:
  - Add `get_tribes()` to `WorldAPIClient` — one method, same `_cached_fetch` pattern as existing calls.
  - Fix `get_tribe(tribe_id)` to return the full object: `name`, `nameShort`, `description`, `taxRate`, `tribeUrl`.
  - Add `get_tribe_info` tool in `src/ai_tools.py` — live fetch per request, no DB storage.
- Note: works standalone. More useful after Character Session Enrichment — when `tribe_id` is populated in the session, the AI can look up the pilot's own tribe without asking.

### Audit intel stores

| Task | Files |
|------|-------|
| Audit `query_intel` scope — cross-pilot or personal only? | `ai_tools.py`, `intel_store.py` |
| Audit `memory_store.py` → `context_builder.py` connection | `memory_store.py`, `context_builder.py` |

### Verified player location (`/provemylocation`)

Players currently self-report their system via `/system <name>`. A verified path exists using player-exported PODs from `evefrontier.com/account` — no CCP cooperation or auth tokens required. The backend verifies the cryptographic signature, resolves the system name via a public World API endpoint, and marks the location as confirmed.

Full investigation and both implementation paths in `docs/roadmap/verified-location-rpc-investigation.md`.

### BYOK — Bring Your Own API Key

Allow users to supply their own Claude API key. Key stored in browser `localStorage`, sent as `X-User-Api-Key` header, used per-request and discarded — never written to server disk. Server key remains fallback. Full design in `docs/roadmap/byok-api-keys.md`.

Three files, ~70 lines total:
- `src/endpoints/companion.py` — read header, pass to `AsyncAnthropic` instantiation (~15 lines)
- `frontend/src/hooks/useCompanionStream.ts` — inject header from localStorage (~5 lines)
- `frontend/src/components/TerminalUI.tsx` — `/apikey` slash command + inline settings panel (~50 lines)

**Open decisions before implementing:**
- Tier policy for BYOK users — does tier still apply, or do BYOK users get a VETTED floor?
- Logging hygiene — confirm FastAPI middleware does not log `X-User-Api-Key` header before shipping.

### Warehouse receipts — on-chain item custody

Loash Industries (fellow hackathon participants) have deployed Sui Move contracts on both testnets that lock items into SSU vaults and issue bearer receipt tokens in return. Contracts require no deployment work. HUGINN needs PTB builders, vault state query endpoints, frontend panels, and AI tools.

This is the only path to real courier contracts — items locked in vault, receipt is the cargo claim. Text-only courier posts become enforceable.

Full integration plan in `docs/roadmap/warehouse-receipts-item-custody.md`.

---

## Things That Matter Later

These are real concerns. None of them matter right now with one tester and near-zero traffic. Revisit when the trigger applies.

**Access tier caching** — when Sui Testnet degradation actually causes problems or when 100–400ms per chat turn becomes noticeable. Resolve tier once at `/session/register`, cache in session, lazy TTL refresh. Full design: `docs/roadmap/access-tier-caching.md`.

**Rate limiting on `/companion/stream` and `/logs/upload`** — before sharing the URL publicly with people you don't know.

**Claude model routing** — when the monthly Claude bill is high enough to care. Haiku for log summarization and Huginn Signal; sonnet for companion chat. Hard rule: haiku never writes to `system_knowledge.db` or `log_intel_store.py` without schema validation at the write path. Full decision table: `docs/roadmap/model-routing.md`.

**Complete the knowledge graph** — wire killmail system visit counts and `intel_store.py` field reports into `system_knowledge.db`. Inject per-system summaries proactively into `context_builder.py`. Enrich Huginn Signal from the graph. Not worth doing while pilot count is low and the stores are thin.

**Parser coverage** — when there are enough real log uploads to have a meaningful signal on what's being dropped. Build the quarantine store, candidate hostile extraction, and developer CLI then. Full design: `docs/roadmap/log-parser-intelligence-evolution.md`.

**Self-service structure registration** — when someone other than the developer wants to add a structure. Move `structures/*.json` to a SQLite table; add registration flow in the admin panel.

**Backup** — before sharing with anyone who'd care about losing their data.

**HTTPS / TLS** — before any public URL shared beyond current testers.

**Contribution → VETTED tier pathway** — after there are enough users to make the flywheel worth incentivizing. The BYOK tier policy decision (whether BYOK users receive a VETTED floor) should be resolved before the BYOK item ships.

**UI revision** — TerminalUI, GateUI, TurretUI sizes, layout, and visual design are all in scope. After the intelligence layer has substance.

---

## Deferred / Blocked

These items have been evaluated and have known integration patterns. Work cannot start due to external dependencies outside this project's control.

### Gate Access Awareness

- On-chain gate extension contracts control jump permit issuance. Two confirmed patterns: `tribe_permit.move` (gates allowing only pilots whose tribe ID matches a configured u32) and `corpse_gate_bounty.move` (gates requiring deposit of a specific item type as toll).
- The gate's `extension: Option<TypeName>` field is readable via a single Sui RPC call — sufficient to detect locked vs. open.
- Blocked by:
  - Open Borders Protocol (OBP) package ID is unknown. `ExtensionConfig` (the object holding tribe ID or bounty type) is a separate Sui shared object with no pointer in the Gate struct — discovery requires per-extension lookup chains not self-describing from the gate alone.
  - OBP's `ExtensionConfig` schema cannot be queried without the package ID.
  - Bounty gate access requires completing a transaction; it cannot be answered by a static read.
  - Player-deployed SmartGates are absent from `systems.json`. `src/route_engine.py` uses a static gate graph with no concept of access-filtered edges.
- Unblock when: OBP publishes their package ID AND player SmartGates are indexed in `systems.json`.
- Full blocker analysis: `docs/roadmap/hackathon-scout-feature-candidates.md` — Gate Access Awareness section.

---

## Skipped

These items were evaluated and will not be integrated in their current state.

### KARUM Marketplace

- An on-chain marketplace for EVE Frontier resources. `karum.space` serves a JavaScript SPA. No public REST API, no Sui package ID, no on-chain registry object ID is discoverable. Nothing to integrate against.
- Revisit if KARUM publishes a REST API or on-chain registry object ID. Integration pattern: new `find_marketplace` tool in `src/ai_tools.py`, same shape as `manage_courier`.

---

## Hard Rules

These apply now, not later.

1. **No haiku writes to `system_knowledge.db` or `log_intel_store.py` without schema validation at the write path.** Misattributed intelligence is permanent and cited by every future pilot.

2. **Temporal columns from the start.** Any new intel record without `first_seen_at`, `last_seen_at`, `observation_count` at write time is permanently undateable.

3. **`gamelog_raw` text has no path to any Claude-facing function. Inviolable.** Raw log text is attacker-controlled.

4. **Before writing any new data access code, check the dapp-kit boundary in `CLAUDE.md`.** Nine known boundary violations exist.

As the knowledge layer deepens, HUGINN risks sounding like a database. Confidence scores, observation counts, and temporal metadata feed the prompt — they never appear verbatim in responses. Every data enrichment must be paired with a corresponding update to `prompts/companion.md`.

---

## Supporting Documents

The `docs/roadmap/` directory contains detailed analysis written post-hackathon. Read the relevant doc when working on that area.

- `access-tier-caching.md` — full design for resolving tier at registration, TTL strategy, consistency window
- `byok-api-keys.md` — BYOK design, exact file changes, open decisions
- `eval-ui-components-library.md` — EVE component library evaluation, full quick-win list with difficulty ratings
- `hackathon-scout-feature-candidates.md` — post-hackathon scout evaluation: Lore Core, Ship Hull Stats, Session Enrichment, Tribe Awareness (USE); Gate Access Awareness (DEFER/blocked); KARUM Marketplace (SKIP)
- `log-parser-intelligence-evolution.md` — quarantine store, candidate hostile extraction, entity category tagging
- `model-routing.md` — full routing decision table, rollout sequence, prompt engineering rules
- `strategic-priorities.md` — ranked priority list with sequencing waves
- `verified-location-rpc-investigation.md` — World API auth investigation, POD export path, zkLogin path
- `warehouse-receipts-item-custody.md` — Loash Industries contract integration plan

