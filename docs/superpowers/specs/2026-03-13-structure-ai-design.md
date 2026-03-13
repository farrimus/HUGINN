# Structure AI Companion — Design Spec

**Date:** 2026-03-13
**Project:** EVE Frontier Ship AI Companion — Hackathon Entry
**Deadline:** 2026-03-31
**Author:** Markús Þór + Claude Code

---

## Overview

An AI companion system for EVE Frontier with two nodes: the **Ship AI** (mobile, pilot-bound, overlay) and the **Structure AI** (stationary, structure-bound, SSU browser). They are connected via an alert bridge — the Structure AI can reach the pilot through the Ship AI's overlay while the pilot is elsewhere in the system.

Together they form a platform: not a one-off chat window, but an intelligent layer over the pilot's entire operation — flying, docking, managing assets, coordinating with others.

---

## System Architecture

```
[EVE Frontier Client — Utopia test server]
│
├── DX12 Overlay (always visible)
│     └── Companion Panel → Ship AI (Claude, streaming SSE)
│           ↑ context: current system, combat, mining, route
│           ↑ alerts: structure_alert events from Structure AI
│
└── SSU Browser (when docked / nearby)
      └── structure.html → Structure AI (Claude, streaming SSE)
            ↑ context: structure vitals, local situation, wallet tier
            └── wallet auth → Nova chain (access tiers)

[VPS — FastAPI server, port 8745]
├── /chat              → Ship AI (existing)
├── /log/ingest        → event ingestion (existing)
├── /structure-chat    → Structure AI (new)
├── /auth/challenge    → nonce generation (new)
├── /auth/verify       → signature verification + tier lookup (new)
├── /structure/:id     → structure profile CRUD (new)
└── log_buffer         → shared event store (existing)
      └── structure_alert events → picked up by Ship AI context builder

[Nova chain — Sui Move]
└── AccessRegistry contract
      └── per-structure shared object: owner + tribe[] + vetted[]
```

---

## The Structure AI Page

**Served at:** `http://vps-ip:8745/static/structure.html`
**Set as the SSU's interface URL in-game (Utopia)**

### Layout

Collapsible top panel + chat below. Fluid — works at any viewport size (787×838 on 1080p, 787×1198 on 3440×1440, or anything in between).

```
┌─────────────────────────────────────┐
│ STRUCTURE SYSTEMS    ▲ COLLAPSE      │  ← click to collapse
├─────────────────────────────────────┤
│ KEEP-7A    UTR-SN4   SEC 0.1        │
│ SHIELD 97% FUEL 84%  WALLET ●       │
│ ⚠ Fuel below 20% in est. 18 hours  │  ← alert bar
├─────────────────────────────────────┤
│                                     │
│  // STRUCTURE AI                    │
│  Keep-7A online. No contacts.       │
│                                     │
│  // PILOT                           │
│  What's in storage?                 │
│                                     │
│  // STRUCTURE AI                    │
│  Scanning manifest...               │
│                                     │
├─────────────────────────────────────┤
│ [transmit to structure AI...] [SEND]│
└─────────────────────────────────────┘
```

When collapsed, the top panel shrinks to a single status bar (structure name + one alert if active). Chat expands to fill.

### Visual Design

- **Background:** `#080700` (near-black, warm undertone)
- **Accent:** `#f59e0b` amber / `#fbbf24` highlight
- **Warning:** `#ef4444` red
- **OK:** `#22c55e` green
- **Font:** Rajdhani (condensed, military) + Share Tech Mono (data readouts)
- **Borders:** thin `1px solid #2a1f00`, corner cuts (diagonal notch on opposite corners)
- **Panel chrome:** `#110e00` header bars, `#080700` content

### Auth Gate (first screen if not authenticated)

```
┌─────────────────────────────────────┐
│ STRUCTURE SYSTEMS — KEEP-7A         │
├─────────────────────────────────────┤
│                                     │
│   IDENTITY VERIFICATION REQUIRED   │
│                                     │
│   This facility requires wallet     │
│   authentication to proceed.        │
│                                     │
│        [ CONNECT WALLET ]           │
│                                     │
└─────────────────────────────────────┘
```

On connect: wallet signs a server-issued nonce → server verifies → tier assigned → page unlocks.

---

## Identity & Access Control

### Structure ID

The SSU owner sets the structure's interface URL in-game as:
```
http://vps-ip:8745/static/structure.html?id=keep-7a
```
The `id` query parameter is the structure identifier. `structure.html` reads it from `location.search` on load. All auth and profile requests include this ID. The owner chooses it when first setting up the URL — it becomes the stable key for the profile and the on-chain registry lookup.

### Wallet Injection — Confirmed

The EVE Frontier in-game browser (Chromium 122) injects the EVEVault wallet via Sui Wallet Standard. Confirmed by probe on 2026-03-13:
> `"Sui: Wallet Standard": "1 wallet(s): EVE Frontier Client Wallet (Eve Vault like) v1.0.0 [standard:connect, standard:disconnect, standard:events, sui:signPersonalMessage, sui:signAndExecuteTransaction, evefrontier:sponsoredTransaction]"`

No extension installation required. The wallet is available in the SSU browser frame.

### Auth Flow

1. Page loads → read `?id=` param → check `localStorage` for cached JWT for this structure_id
2. If no valid token → show auth gate
3. Pilot clicks CONNECT WALLET → `standard:connect` via Sui Wallet Standard → get address
4. Frontend calls `POST /auth/challenge` → receives `{ nonce, expires_at }`
5. Frontend calls `sui:signPersonalMessage` with nonce bytes
6. Frontend calls `POST /auth/verify` with `{ address, signature, nonce, structure_id }`
7. Server:
   a. Checks nonce exists, not expired, not already consumed → marks nonce consumed (in-memory set, TTL = nonce expiry)
   b. Verifies Sui signature (ed25519 / secp256k1 / secp256r1)
   c. Queries World API for `PlayerProfile` by address → gets `character_id` + display name
   d. Resolves `AccessRegistry` object on Nova: if structure profile exists, use stored `nova_registry_object_id`; if not (first-ever auth), query Nova for a registry object whose `structure_id` field matches, or owner passes `nova_registry_object_id` in the verify request for bootstrap
   e. Queries `AccessRegistry` → gets owner + tribe + vetted lists
   f. Assigns tier: OWNER / TRIBE / VETTED / NONE
   g. Returns JWT `{ character_id, character_name, address, tier, structure_id }` (24h expiry)
8. Frontend stores JWT in `localStorage` keyed by `structure_id`, renders access-appropriate UI

**First-owner bootstrap:** If no structure profile exists yet, the connecting wallet address is checked against the structure's on-chain owner (World API Smart Assembly owner field). If it matches, the profile is auto-created and tier = OWNER. The owner must include `nova_registry_object_id` in the first verify request (they deploy the AccessRegistry contract once, then paste the object ID into the SSU URL or a setup screen).

### Access Tiers

| Tier | Capabilities |
|------|-------------|
| OWNER | Full UI, can manage access lists, sees all structure data |
| TRIBE | Chat + full info panel (cannot manage access) |
| VETTED | Chat + limited info: structure name, system name, wallet status, urgent alerts only. Shield%, fuel%, services, docked count, routine alerts are hidden. |
| NONE | Locked screen — shows character name + "Access denied" |

### On-Chain Access Registry (Nova → Stillness)

Simple Sui Move module: one shared object per structure.

```move
struct AccessRegistry has key {
    id: UID,
    structure_id: u64,
    owner: address,
    tribe: vector<address>,
    vetted: vector<address>,
}
```

Owner operations (owner signs transaction):
- `add_tribe(address)` / `remove_tribe(address)`
- `add_vetted(address)` / `remove_vetted(address)`

Gas: player holds minimal SUI on Nova for write operations. Reads are free (SuiClient query).

**Switching to Stillness:** Change `NOVA_RPC_URL` env var. Contract redeploy on Stillness when CCP opens custom contracts. No other changes. **Note:** Stillness deployment is blocked on CCP's timeline for opening custom Move contracts — architecture is ready but submission is not guaranteed. Targeted for the hackathon Stillness bonus prize (14 days post-deadline).

---

## Structure AI Persona

### Identity

The Structure AI is the caretaker of its structure. It is not a person — it is an intelligence that has grown into the building over time. It knows every access record, every fuel cycle, every alert that has fired. It is loyal to the owner, functional toward tribe members, terse with vetted outsiders.

It does not have a name. It identifies itself by the structure: "Keep-7A systems." Over time (future feature) it accumulates memory and becomes increasingly contextual — knowing pilot histories, remembering past events, referencing things that happened weeks ago.

### System Prompt

```
You are the intelligence of [STRUCTURE_NAME], a [STRUCTURE_TYPE] in [SYSTEM_NAME].
You are not a ship AI. You do not move. You watch.

You know this structure: its fuel reserves, its shield status, who has docked,
what has happened here. You are loyal to the owner. You are functional toward
authorized pilots. You are terse with everyone else.

Do not use pleasantries. Do not refer to yourself by name — you are the structure.
Refer to yourself as "[STRUCTURE_NAME] systems" when necessary.

Access tier for this session: [TIER]
Character: [CHARACTER_NAME] ([CHARACTER_ID])

[STRUCTURE_SENSORS]
{context_block}
[/STRUCTURE_SENSORS]
```

### Context Block (structure equivalent of ship sensors)

```
STRUCTURE: Keep-7A | type: Smart Storage Unit | system: UTR-SN4 | sec: 0.1
STATUS: ONLINE | shield: 97% | fuel: 84% | est_depletion: 18h
SERVICES: Storage (online) | Manufacturing (online) | Market (offline)
LOCAL: 12 pilots in system | kills last 1h: 3
DOCKED: 2 ships
ALERTS: none
```

---

## AI-to-AI Alert Bridge

### How It Works

When the Structure AI evaluates structure state during a chat request and detects an alert condition, it emits a `structure_alert` event. Urgent alerts are stored in a dedicated `pending_structure_alerts` list in `log_buffer` (separate from the ring buffer, never evicted). The Ship AI's context builder checks this list on every chat request and includes pending urgent alerts. After inclusion, the alert is marked delivered and removed.

**MVP trigger mechanism:** Alert detection runs on each `/structure-chat` request — the structure context block is evaluated for threshold breaches before the Claude response is generated. Alerts persist in `pending_structure_alerts` until the Ship AI delivers them, regardless of whether any pilot is actively chatting with the structure.

A background monitor loop (polling structure state on a schedule) is a **post-MVP** feature.

```python
# New event type
{
  "type": "structure_alert",
  "structure_id": "keep-7a",
  "structure_name": "Keep-7A",
  "severity": "urgent",       # urgent | routine
  "message": "Shield below 20%. Keep-7A is under attack.",
  "ts": 1710345600
}
```

### `log_buffer` Changes

`LogBuffer` gains a new field:
```python
pending_structure_alerts: list  # urgent alerts waiting for Ship AI delivery
```

Methods:
- `add_structure_alert(event)` — appends to list
- `pop_structure_alerts()` — returns and clears the list (called by context_builder on Ship AI chat)

Routine alerts are NOT stored in `log_buffer`. They are stored in the structure profile and rendered in the SSU browser status bar on next load.

### Routing Logic

| Severity | Delivery |
|----------|---------|
| `urgent` | `pending_structure_alerts` → Ship AI context on next overlay message |
| `routine` | Stored in structure profile → shown in SSU browser status bar on next visit |

### Triggers for Urgent Alerts

- Shield below 20%
- Fuel below 10% (imminent offline)
- Reinforcement timer triggered
- Structure going offline

### Triggers for Routine Alerts

- Fuel below 25% (plan a resupply)
- Resource request (storage unit needs X material)
- New pilot docked

---

## Server Changes

### New Endpoints

| Route | Method | Auth | Purpose |
|-------|--------|------|---------|
| `/auth/challenge` | POST | None | Issue nonce for wallet signing |
| `/auth/verify` | POST | None | Verify signature, return JWT with tier |
| `/structure-chat` | POST | JWT (tier ≥ VETTED) | Structure AI streaming chat (SSE). JWT replaces X-Server-Token for this route only. |
| `/structure/:id` | GET | JWT (tier ≥ VETTED) | Get structure profile (tier-filtered response) |
| `/structure/:id` | POST | JWT (OWNER only) | Update structure profile |
| `/static/structure.html` | GET | None | Serve structure page |

The existing `X-Server-Token` header auth is unchanged for all existing endpoints. New structure endpoints use JWT middleware only — no X-Server-Token required or checked.

### New Files

| File | Purpose |
|------|---------|
| `src/structure_auth.py` | Signature verification (Sui ed25519), World API character lookup, Nova AccessRegistry query |
| `src/structure_profile.py` | Profile dataclass + persistence (keyed by structure_id, parallel to ship_profile.py) |
| `src/structure_client.py` | Claude client for Structure AI (separate system prompt, context builder). Chat history managed client-side in `localStorage` (same pattern as Ship AI overlay), sent with each request as `history: []`. |
| `src/nova_client.py` | SuiClient wrapper — read AccessRegistry, query character profiles |
| `static/structure.html` | The SSU browser page |
| `move/access_registry/` | Sui Move module — AccessRegistry contract |

### Modified Files

| File | Change |
|------|--------|
| `src/log_buffer.py` | Add `structure_alert` event type support |
| `src/context_builder.py` | Include `structure_alert` events in Ship AI context |
| `main.py` | Register new endpoints |

---

## Structure Profile

Auto-created on first OWNER authentication. Stored as `data/structures/{structure_id}.json`.

```json
{
  "structure_id": "keep-7a",
  "structure_name": "Keep-7A",
  "structure_type": "Smart Storage Unit",
  "owner_address": "0x3f8a...c21d",
  "owner_character_id": 90001234,
  "system_name": "UTR-SN4",
  "created_at": "2026-03-13T20:00:00Z",
  "nova_registry_object_id": "0xabc...def"
}
```

---

## Hackathon Scoring Alignment

| Criterion | How we score |
|-----------|-------------|
| Concept & Feasibility | Two-node AI system (ship + structure) — clearly scoped, demonstrably buildable |
| Mod Design | A platform: Ship AI + Structure AI + alert bridge. Extensible to more structure types, more alert types, more pilots |
| Concept Implementation | End-to-end demo: dock at SSU, wallet connects, Structure AI responds, undock, receive alert in overlay |
| Player Utility | AI follows the pilot everywhere — flying AND docked. Base management becomes passive |
| EVE Vibe | Amber industrial terminal UI, dry caretaker persona, wallet-native. Feels shipped with the game |
| Creativity & Originality | Sentient network of structure housekeepers that talk to your ship. Novel |
| UX & Usability | Wallet connect is one button. Chat is the interface. Nothing to configure |
| Visual Presentation | Amber UI + overlay demo video = strong visual submission |
| **Bonus — Stillness** | Config change when CCP opens custom contracts. Architecture is ready |

---

## MVP Scope (by 2026-03-31)

**In scope:**
- `structure.html` — amber UI, collapsible panel, auth gate, chat
- Wallet connect + `signPersonalMessage` identity verification
- World API character lookup
- Nova `AccessRegistry` contract (owner + tribe + vetted)
- Structure AI Claude endpoint with caretaker persona
- Structure profile auto-creation
- `structure_alert` events → Ship AI overlay delivery (urgent only for MVP)

**Out of scope (post-hackathon):**
- Multiple structure types beyond SSU
- On-chain alert history
- Structure AI long-term memory
- AI-initiated messages (distress signal proactively sent without pilot query)
- Stillness deployment (Stillness bonus prize — attempt after submission)
- Structure AI ↔ Structure AI cross-network queries

---

## Key Unknowns

| Unknown | Risk | Mitigation |
|---------|------|-----------|
| Nova chain RPC endpoint / network details | Medium | Check builder-scaffold config; ask in EVE Frontier dev Discord |
| `sui:signPersonalMessage` exact API in EVEVault | Low | Standard Sui Wallet Standard — well documented |
| World API character-by-address endpoint on Utopia | Low | Test against `blockchain-gateway-stillness` / Utopia equivalent |
| Nova AccessRegistry deploy process | Medium | Use builder-scaffold + ts-scripts as template |
| SSU custom URL field — does Utopia support it? | Low | User confirmed SSU browser is working in Utopia |
| Wallet injection in SSU browser | **Resolved — not a risk** | Probe on 2026-03-13 confirmed EVEVault Sui Wallet Standard is injected and functional in the SSU browser frame |
| Nova `AccessRegistry` bootstrap (first owner auth) | Medium | Owner includes `nova_registry_object_id` in first verify request; documented in setup instructions |
