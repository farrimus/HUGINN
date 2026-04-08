# Warehouse Receipts: On-Chain Item Custody

**Status:** Contracts deployed on both testnets. No deployment work required. Integration is backend PTB builders + frontend panels.
**Goal:** Replace text-only courier contracts with actual on-chain item custody. Make inventory interactive instead of read-only.

---

## What This Is

A community-built Sui Move extension for SSUs by Loash Industries (hackathon participants, not CCP Games). Players deposit items into an SSU vault and receive a `multicoin::Balance` bearer token in return. The token can be split, transferred, or traded. Anyone holding it can redeem it for the underlying items. Custody is fully decoupled from ownership.

Repo: `https://github.com/loash-industries/warehouse-receipts`

Deployed addresses:
- `utopia` testnet: `0xcaefce5e087e4ace962a2964f8df4df3fc33600171d5402574ea5ec38f9f46ce`
- `stillness` testnet: `0xc7c9d06e5825ba99d6ad49cdf2c62c4574daa82cba8675b354b94bca56cd32cc`

Dependencies:
- `evefrontier/world-contracts` — official EVE Frontier Move framework
- `Algorithmic-Warfare/multicoin` — custom Sui Move package providing `Collection`, `CollectionCap`, and `Balance`

---

## The Authorization Model

Extensions are **permissionless at the blockchain level, owner-gated at the SSU level**. Anyone can call the extension functions — but only after the SSU owner has completed a one-time vault setup.

```
Step 1 (SSU owner, one-time):
  initialize_vault(storage_unit, owner_cap)
  → requires OwnerCap<StorageUnit>
  → creates VaultConfig + MultiCoin Collection, shares both on-chain

Step 2 (SSU owner, one-time):
  authorize_extension<VaultAuth> on the StorageUnit
  → tells the SSU to accept the VaultAuth witness type

Step 3 (any player):
  deposit_for_receipt(storage_unit, character, owner_cap, vault_config, collection, type_id, quantity)
  → moves items from player's owned inventory → extension-controlled open inventory
  → mints a multicoin::Balance receipt, returns it to the caller

Step 4 (anyone holding the receipt):
  redeem_receipt(receipt, storage_unit, character, vault_config, collection, to_ssu_owner)
  → burns the Balance
  → withdraws items from open inventory to redeemer (or SSU owner, configurable)
```

HUGINN is a companion app, not an SSU owner. We guide owners through the one-time setup via a PTB signing flow. After that, any visitor can deposit and redeem without further owner action.

Batch variants exist for both operations: `batch_deposit_for_receipt` and `batch_redeem_receipt`.

---

## What MultiCoin Actually Is

`multicoin::Balance` is **not** a standard Sui `Coin<T>`. It does not use `0x2::coin`. It is a custom Sui object with:
- `asset_id` — maps to EVE Frontier `type_id` (the item type, e.g. Tritanium)
- quantity — u64 amount

Receipts support split, join, and transfer like a coin. They cannot be traded on a standard Sui DEX without an adapter. Peer-to-peer transfer works today; DEX composability is possible in the future if a MultiCoin-aware pool exists.

---

## What This Closes For Us

| Capability | Current state | With receipts |
|---|---|---|
| Inventory | Read-only display, polled every 5 min | Same read, plus deposit + redeem operations |
| Courier contracts | Text-only — items described, never moved | Items locked in vault, receipt is the cargo claim |
| P2P item trading | Not possible | Receipt transfer = atomic handover |
| AI knowledge | Knows item counts, not commitments | Can report unclaimed receipts, suggest deposits |
| Watcher alerts | Fires when item count drops below threshold | Can additionally watch receipt balances |

The courier board is the biggest win. Today a pilot posts "haul 200 Tritanium for 500 ISK" as text. With receipts: depositor locks items in the SSU vault, gets a receipt, hands it to the hauler as the cargo claim ticket. Delivery = redemption. No trust required between strangers.

---

## What It Does Not Do

- **No currency or ISK.** `asset_id` maps to item types, not fungible money. The reward side of a courier contract still has no on-chain mechanism.
- **No DEX.** Receipts are composable inputs to one, but no live MultiCoin DEX exists yet.
- **No automated pricing.** No oracle, no price discovery.
- **No cross-SSU transfers.** A receipt is bound to the SSU vault it was minted from. Redemption must happen at the same SSU.

---

## Current State

| Need | Status |
|---|---|
| Move contracts | Deployed on both testnets — no work needed |
| Extension authorization | Owner-gated, one-time setup via `initialize_vault` + `authorize_extension` |
| Backend PTB builders | Not built — `deposit_for_receipt`, `redeem_receipt`, plus batch variants |
| Vault state query | Not built — need endpoints to query VaultConfig + Collection on-chain |
| Receipt event indexing | Not built — `ReceiptMintedEvent`, `ReceiptRedeemedEvent` on Sui |
| Frontend deposit/redeem UI | Not built |
| AI tools | Not built — `check_receipts`, `deposit_item`, `redeem_receipt` |

---

## Implementation Plan

### Backend (~3 days)

Add PTB builders to `src/endpoints/transactions.py` (same pattern as gate link/unlink):
- `POST /tx/build` with action `deposit_for_receipt` — takes `assembly_id`, `type_id`, `quantity`
- `POST /tx/build` with action `redeem_receipt` — takes `assembly_id`, `balance_id`, `to_ssu_owner`
- `POST /tx/build` with action `batch_deposit_for_receipt` — takes arrays of type_ids and quantities
- `POST /tx/build` with action `batch_redeem_receipt` — takes array of balance_ids

New endpoints:
- `GET /entity/receipts/{assembly_id}` — query open receipt supply from Collection object
- `GET /entity/receipts/held/{wallet}` — query Balance objects owned by a wallet via Sui GraphQL

Sui event indexing:
- Poll `ReceiptMintedEvent` and `ReceiptRedeemedEvent` to build a transaction log per SSU

### Frontend (~2 days)

- Deposit panel: select item type, enter quantity, sign PTB
- Redeem panel: show held Balance objects, sign to redeem
- Both follow the existing `ReconForm` / `TripCalculatorForm` pattern in `frontend/src/components/`

### AI tools (~1 day)

Add to `src/ai_tools.py`:
- `check_receipts` — list Balance objects held by current wallet
- `deposit_item` — build and guide PTB signing flow
- `redeem_receipt` — build and guide redeem PTB

### SSU Owner Setup Flow

One-time per SSU. HUGINN walks the owner through two PTB signatures:
1. `initialize_vault` — creates VaultConfig + Collection
2. `authorize_extension<VaultAuth>` — enables VaultAuth witness on the SSU

After this, no further owner involvement for individual deposits and redemptions.

---

## Strategic Note

Loash Industries also has an `inventory-hackathon` repo — they are building inventory tooling at the same layer we are. Their on-chain contracts are free infrastructure we can build on top of. Our value-add is the AI companion layer: lore-aware reasoning about receipts, courier contract facilitation, alerts for unclaimed claims. That is not something they are building.
