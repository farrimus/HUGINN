# UI Components Library Evaluation

**Date:** 2026-04-08
**Source:** `@eveworld/ui-components` + `@evefrontier/dapp-kit` (evefrontier/dapps @ 7404c27)
**Purpose:** Determine what to adopt, copy, or ignore from the official EVE Frontier component library.

---

## Key Strategic Finding

Almost every importable component requires Tailwind CSS. We have no Tailwind. The decision is not "import vs skip" per component — it is a single architectural choice: **add Tailwind or copy/recreate patterns manually.** Until that choice is made, all adoption paths below use our existing vanilla CSS system.

---

## Action Items by Priority

### Immediate — no prerequisites, low effort

| Item | Action | Difficulty |
|------|--------|------------|
| `parseErrorFromMessage` | Import from installed dapp-kit. Classifies tx errors into 24 typed codes (user rejection, insufficient gas, contract revert, etc.). Apply before all `notify()` calls in GateUI and TurretUI. | 1/5 |
| Identicon / `useIdenticon` | Extract the 30-line hook + 16 SVG imports. Assigns random 1-of-16 avatar, persisted to `localStorage["eve-dapp-identicon"]`. Add to BaselinePanel and TurretUI wallet bar. We currently have zero visual identity marker. | 1/5 |
| Disconnect button | `handleDisconnect` is available from `useConnection()` but never surfaced to the user. Add a disconnect link to TurretUI and GateUI. One line of JSX each. | 1/5 |
| Scrollbar CSS | Extract the `.Eve-Scrollbar` CSS rules from `styles-ui.css` (martianred border, custom thumb). Apply globally to `.terminal-output`, `.turret-response`, gate chat. Only TurretUI has custom scrollbar styling today; Terminal and Gate use browser defaults. | 1/5 |
| `SmartAssemblyInfoLine` pattern | Copy the abbreviate-ID + click-to-copy pattern for long Sui object IDs in BaselinePanel. `abbreviateAddress()` is already exported from our installed dapp-kit. | 1/5 |
| Delete `bcs_encoding.py` | Dead code — never imported anywhere. The `hash_input_for_derived_object()` function is explicitly marked "best guess" and is not used in tier resolution (which uses hardcoded IDs from profile JSON). Deleting removes false confidence. | 0/5 |

### Near-term — copy/recreate, no Tailwind

| Item | Action | Difficulty |
|------|--------|------------|
| `EveFeralCodeGen` | Copy the 50-line file. Define one CSS class: `.text-martianred-5 { color: hsla(17, 100%, 50%, 1); }`. Drop into TurretUI loading state and HuginnNewsPanel during streaming. Perfect ambient lore texture. | 1/5 |
| `CopyButton` | Build a `<CopyButton text={string}>` component (~40 lines) using `clickToCopy` from installed dapp-kit (`navigator.clipboard.writeText`). Apply to assembly ID, wallet address, gate destination ID. Add 3-second "COPIED" feedback state. | 2/5 |
| `EveLoadingAnimation` (recreated) | Do not import. Recreate the CSS keyframes (`colorChange`, 3s step animation) + a simple flex wrapper (~40 lines CSS, ~30 lines React). Drop into loading states across TurretUI, GateUI, TerminalUI. | 2/5 |
| In-house toast/alert | `NotificationProvider` from dapp-kit is state-only — it stores notification data but renders no UI. We call `notify()` throughout GateUI and TurretUI but nothing renders. Build a minimal snackbar in vanilla CSS (~60 lines CSS + ~40 lines React) wired to `useNotification()` state. | 2/5 |
| `useCooldown` hook | Copy the cooldown timer mechanic from EveButton. ~30 lines. Apply to BRING ONLINE / BRING OFFLINE buttons in TurretUI — currently they just grey out during txPending with no visual timer. | 2/5 |
| ConfirmDialog for `/unlink` | Build a simple confirm/cancel pair. Gate unlinking is destructive and currently executes on command with no confirmation. | 2/5 |
| `EXCLUDED_TYPEIDS` filter | Add Python constant `EXCLUDED_TYPEIDS = {"87160", "87161", "87162", "87566"}` to backend. Filter portables (refinery, printer, storage, refuge) from assembly list endpoints. These currently return unfiltered alongside network assemblies. | 2/5 |
| Portable structure search | Add optional `?type_ids=` query param to `/entity/assemblies`. Enables searching for portable structures specifically. `type_id` is already available in all assembly responses. | 2/5 |

### Future — requires Tailwind or custom build

| Item | Decision |
|------|----------|
| `GateView` / `GateCard` | Type mismatch with our data shape + Tailwind-heavy. Build a custom `GateStatusCard.tsx` using our CSS variable system when gate visualization becomes a priority. |
| `TurretView` | 31 lines, one non-functional radio option ("All in range"), no tx wiring, requires Tailwind + MUI. Build custom `TargetingModeSelector` using `.turret-btn` button group pattern when contract targeting API exists. |
| `AssemblyInfo` | Requires Tailwind + dapp-kit discriminated union types incompatible with our flat `enrichedAssembly`. Extract `SmartAssemblyInfoLine` pattern only (see immediate actions). |
| `EveContainer` | SVG corner decorations + statusText slots. Good concept, fits our aesthetic. Implement as custom `<PanelFrame>` component in a future visual refresh pass. |
| Full `Header` component | Requires Tailwind. Extract identicon only (see immediate actions). |
| `EveButton` (import) | Not worth importing — our custom CSS is lighter and already EVE-themed. Adopt cooldown mechanic only (see near-term). |

### Skip entirely

| Item | Reason |
|------|--------|
| `EveLinearBar` | Does not exist in the repository at this commit. Text-based capacity/fuel displays are also superior for our terminal aesthetic. |
| `InventoryView` | Our text-mode InventoryPanel is intentionally terminal-style. The official component uses a grid/card layout that breaks our aesthetic. |
| `ConnectWallet` / `EveConnectWallet` | Handled by dapp-kit's `useConnection()` already. |
| Skeleton loaders | Would require retrofitting our panel structure. Not justified. |

---

## Component Reference

### Components inspected

| Component | Source retrievable | Tailwind required | Verdict |
|-----------|-------------------|-------------------|---------|
| `EveFeralCodeGen` | Yes | One class only | Copy |
| `EveLoadingAnimation` | Yes | Heavy | Recreate CSS pattern |
| `EveButton` | No (404) | Yes (inferred) | Copy cooldown hook only |
| `EveAlert` | No (404) | Likely | Build in-house |
| `EveScroll` | No (404) | Unknown | Extract CSS rules |
| `EveLinearBar` | No (404, doesn't exist) | N/A | Skip |
| `EveContainer` | No (404) | Yes | Future custom build |
| `AssemblyInfo` | Yes | Yes | Pattern only |
| `GateView` / `GateCard` | Yes | Heavy | Custom build later |
| `TurretView` | Yes | Yes + MUI | Custom build later |
| `Header` | Yes | Yes | Extract identicon only |
| `ClickToCopy` | Partial | No | Build with dapp-kit util |

### dapp-kit utilities already available in our install

These are exported from `@evefrontier/dapp-kit` and can be imported today:

- `parseErrorFromMessage` — error code classification
- `clickToCopy` — clipboard write utility (`navigator.clipboard.writeText`)
- `abbreviateAddress` — shortens 66-char Sui addresses to first N chars
- `TYPEIDS` enum — all 13 game type IDs (SMART_STORAGE_UNIT=77917, NETWORK_NODE=88092, etc.)
- `EXCLUDED_TYPEIDS` — the four portable structure type IDs + REFUGE

---

## TYPEIDS Reference

From `@evefrontier/dapp-kit/utils/constants.ts`:

```
LENS = 77518
TRANSACTION_CHIP = 79193
COMMON_ORE = 77800
METAL_RICH_ORE = 77810
SMART_STORAGE_UNIT = 77917
PROTOCOL_DEPOT = 85249
GATEKEEPER = 83907
SALT = 83839
NETWORK_NODE = 88092
PORTABLE_REFINERY = 87161
PORTABLE_PRINTER = 87162
PORTABLE_STORAGE = 87566
REFUGE = 87160
```

`EXCLUDED_TYPEIDS = [87161, 87162, 87566, 87160]`

Tenant IDs: `"utopia" | "stillness" | "testevenet" | "nebula"`
(We only handle utopia and stillness — testevenet and nebula are unknown tenants worth accounting for.)

---

## BCS / Object ID Derivation Notes

The official TypeScript pattern for deriving a Sui object ID:

```ts
import { bcs } from "@mysten/sui/bcs";
import { deriveObjectID } from "@mysten/sui/utils";

const key = bcs.struct("TenantItemId", {
  item_id: bcs.u64(),
  tenant: bcs.string(),
}).serialize({ item_id: itemId, tenant }).toBytes();

const objectId = deriveObjectID(registryAddress, key, fullTypePath);
```

Known test vector: `itemId=691735, tenant="test"` → `0xccee853995609e171763798b6faaf635793a9a88d79211d6486bfdd268d3fd73`

Our Python `bcs_encoding.py` is unused dead code. Tier resolution uses hardcoded `tier_registry_object_id` from profile JSON files — no derivation involved. If runtime derivation is ever needed, use a TypeScript sidecar; do not attempt to replicate Sui's `hash_type_and_key` in Python.
