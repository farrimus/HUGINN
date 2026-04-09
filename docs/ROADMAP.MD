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
| Intel stores | No temporal metadata (`first_seen_at`, `last_seen_at`) — stale and fresh records indistinguishable |
| Claude model selection | `claude-sonnet-4-6` everywhere — log summarization and Signal don't need it |
| Log parser | Drops unknown entity types (players, ships, player structures) |
| UI | TerminalUI, GateUI, TurretUI — functional but unfinished |
| Rate limiting | None on `/companion/stream` or `/logs/upload` — tokens exposed |

---

## What to Work on Next

### Delete dead code — `bcs_encoding.py`

`src/bcs_encoding.py` is never imported anywhere. The `hash_input_for_derived_object()` function is marked "best guess" in comments and is not used in tier resolution (which uses hardcoded IDs from profile JSON). Delete it. It creates false confidence that Python-side BCS derivation works. If runtime object ID derivation is ever needed, use a TypeScript sidecar — do not replicate Sui's `hash_type_and_key` in Python.

### UI quick wins — EVE component library evaluation

A full evaluation of `@eveworld/ui-components` and `@evefrontier/dapp-kit` was done on 2026-04-08. Several low-effort improvements fall out of it. All of the immediate items are difficulty 1/5. Full list with exact copy/recreation instructions in `docs/roadmap/eval-ui-components-library.md`.

**Immediate (no prerequisites):**
- `parseErrorFromMessage` — import from installed dapp-kit, apply before all `notify()` calls in GateUI and TurretUI. Classifies tx errors into 24 typed codes.
- Identicon / `useIdenticon` — 30-line hook + 16 SVG imports. Adds visual identity marker to BaselinePanel and TurretUI wallet bar. Currently zero visual identity exists.
- Disconnect button — `handleDisconnect` from `useConnection()` is available but never surfaced. Add to TurretUI and GateUI.
- Scrollbar CSS — extract `.Eve-Scrollbar` rules from dapp-kit `styles-ui.css`. Apply to `.terminal-output`, gate chat. Only TurretUI has custom scrollbar styling today.
- `EXCLUDED_TYPEIDS` backend filter — add `EXCLUDED_TYPEIDS = {"87160", "87161", "87162", "87566"}` to backend and filter portables (refinery, printer, storage, refuge) from assembly list endpoints. These currently return unfiltered.

**Near-term (copy/recreate, no Tailwind required):**
- `EveFeralCodeGen` — copy 50-line file + one CSS class. Ambient lore texture for loading states.
- In-house toast/notification snackbar — `notify()` is called throughout GateUI and TurretUI but nothing renders. Build minimal snackbar wired to `useNotification()` state.
- `CopyButton` — clipboard copy for assembly IDs and wallet addresses using `clickToCopy` from dapp-kit.
- `EveLoadingAnimation` — recreate CSS keyframes, apply across TurretUI, GateUI, TerminalUI loading states.
- ConfirmDialog for `/unlink` — gate unlinking is destructive, currently executes immediately with no confirmation.
- `useCooldown` hook — copy cooldown mechanic for BRING ONLINE/OFFLINE buttons in TurretUI (currently just grey out).

### BYOK — Bring Your Own API Key

Allow users to supply their own Claude API key. Key stored in browser `localStorage`, sent as `X-User-Api-Key` header, used per-request and discarded — never written to server disk. Server key remains fallback. Full design in `docs/roadmap/byok-api-keys.md`.

Three files, ~70 lines total:
- `src/endpoints/companion.py` — read header, pass to `AsyncAnthropic` instantiation (~15 lines)
- `frontend/src/hooks/useCompanionStream.ts` — inject header from localStorage (~5 lines)
- `frontend/src/components/TerminalUI.tsx` — `/apikey` slash command + inline settings panel (~50 lines)

**Open decisions before implementing:**
- Tier policy for BYOK users — does tier still apply, or do BYOK users get a VETTED floor?
- Logging hygiene — confirm FastAPI middleware does not log `X-User-Api-Key` header before shipping.

### Add temporal metadata to intel stores

No intel record currently carries `first_seen_at`, `last_seen_at`, or `observation_count`. Stale data is indistinguishable from current data. This must be added before more records accumulate — records written without timestamps cannot be backdated.

| Task | Files |
|------|-------|
| Add `first_seen_at`, `last_seen_at`, `observation_count` to `log_intel_store.py` | `log_intel_store.py`, `system_knowledge.py` |
| Audit `query_intel` scope — cross-pilot or personal only? | `ai_tools.py`, `intel_store.py` |
| Audit `memory_store.py` → `context_builder.py` connection | `memory_store.py`, `context_builder.py` |

### Verified player location (`/provemylocation`)

Players currently self-report their system via `/system <name>`. A verified path exists using player-exported PODs from `evefrontier.com/account` — no CCP cooperation or auth tokens required. The backend verifies the cryptographic signature, resolves the system name via a public World API endpoint, and marks the location as confirmed.

Full investigation and both implementation paths in `docs/roadmap/verified-location-rpc-investigation.md`.

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

**Contribution → VETTED tier pathway** — after there are enough users to make the flywheel worth incentivizing.

**UI revision** — TerminalUI, GateUI, TurretUI sizes, layout, and visual design are all in scope. After the intelligence layer has substance.

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
- `log-parser-intelligence-evolution.md` — quarantine store, candidate hostile extraction, entity category tagging
- `model-routing.md` — full routing decision table, rollout sequence, prompt engineering rules
- `strategic-priorities.md` — ranked priority list with sequencing waves
- `verified-location-rpc-investigation.md` — World API auth investigation, POD export path, zkLogin path
- `warehouse-receipts-item-custody.md` — Loash Industries contract integration plan

**Stale** (describe problems now resolved — kept for historical context):
- `data-layer-architecture.md` — store structural problems; most are fixed. Watch items: session read-modify-write race under concurrent load, `memory_store/` summarization divergence risk, dead session accumulation.
- `intelligence-pipeline-analysis.md` — written when log intel and system_knowledge were unwired. Both are now operational.
