# CLAUDE.md — EVE Frontier Frontend (React)

**Stack:** React 19 + TypeScript, Vite, @evefrontier/dapp-kit v0.1.7, TanStack Query v5
**Entry:** `src/main.tsx` — components in `src/components/`, hooks in `src/hooks/`
**Deployment:** `npm run build` → `dist/` → served by FastAPI at port 8745

The app always loads at `http://135.181.95.84:8745/app?itemId=...&tenant=...` — `useSmartObject()` always resolves. No need to handle "no assembly" states.

---

## MANDATORY: Check dapp-kit before writing anything

Before writing any hook, fetch, GraphQL call, or data transform — check `frontend/docs/DAPP_KIT_COMPLETE_API.md`. If dapp-kit covers it, use dapp-kit.

| Need | dapp-kit |
|---|---|
| Assembly data + polling | `useSmartObject()` |
| Assembly + owner (one call) | `getAssemblyWithOwner()` + `transformToAssembly()` |
| Connected player's character | `getWalletCharacters()` → `parseCharacterFromJson()` |
| Type metadata | `getDatahubGameInfo(typeId)` |
| Energy / fuel config | `getEnergyUsageForType()`, `getAdjustedBurnRate()` |
| Status/type parsing | `parseStatus()`, `assertAssemblyType()` |
| Formatting | `formatDuration()`, `formatM3()`, `abbreviateAddress()` |
| Wallet connection | `useConnection()` |
| Transactions | `useSponsoredTransaction()` |
| Notifications | `useNotification()` |

---

## Critical: assemblyOwner ≠ connected player

`useSmartObject()` returns `assemblyOwner` — the owner of the SSU, not whoever has their wallet connected. Any visitor can open this SSU. They are different people.

- **SSU owner data:** `assemblyOwner` from `useSmartObject()`
- **Connected visitor's identity:** `walletAddress` from `useConnection()`
- **Connected visitor's character** (name, tribeId, etc.): call `getWalletCharacters(walletAddress)`, extract with:
  ```ts
  data?.address?.objects?.nodes?.[0]?.contents?.extract
    ?.asAddress?.asObject?.asMoveObject?.contents?.json
  ```
  then pass to `parseCharacterFromJson()`.

Never use `assemblyOwner.tribeId` for the visitor's tribe. Never use `assemblyOwner` for anything per-visitor.

---

## Standing Preferences

- Plan before implementing. Propose, wait for confirm.
- Check dapp-kit first — source is in `node_modules/@evefrontier/dapp-kit/` when docs are unclear.
- No emojis.
- Verify build passes before declaring done.

## Key Implementation Notes

- Chat endpoint: `POST /companion/stream` (SSE). Requires hardcoded `SERVER_TOKEN` in TerminalUI.tsx — don't remove it.
- API base: `window.location.origin` — no hardcoded host needed.
