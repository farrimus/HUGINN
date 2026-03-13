# EVE Frontier Blockchain Integration — Research Findings

**Date:** 2026-03-11
**Status:** Research complete — decisions recorded

This document records the findings from a full investigation of EVE Frontier's blockchain data access patterns, and the resulting decisions for the Ship AI Companion project.

---

## Chain

EVE Frontier (Stillness galaxy) is migrating from Ethereum/OP Sepolia to **Sui (Move)**. Some legacy EVM artifacts remain in documentation and hostnames. All new development targets Sui.

- **Chain name:** Pyrope (Stillness environment)
- **Sui RPC:** `pyrope-external-sync-node-rpc.live.tech.evefrontier.com` — resolves publicly, but all JSON-RPC read methods are whitelisted/blocked. This node is for transaction submission (write operations) only.
- **World API:** `world-api-stillness.live.tech.evefrontier.com` — the official REST abstraction over chain state. Publicly accessible, no auth for most endpoints.
- **Blockchain Gateway:** `blockchain-gateway-stillness.live.tech.evefrontier.com` — additional REST endpoints including `/me` routes. Same Cloudflare infrastructure as World API. Accessible from external browsers; DNS not yet propagated to this VPS as of 2026-03-11.

---

## Authentication

EVE Frontier uses **EVE Vault** (a Chrome extension) as the player wallet. Authentication for the `/me` endpoints works as follows:

1. Player authenticates via FusionAuth (CCP's identity provider) using the EVE Vault extension.
2. FusionAuth returns an OpenID Connect JWT (`id_token`) via an OAuth2 authorization code flow with Sui zkLogin nonce injection.
3. The JWT is the Bearer token: `Authorization: Bearer <id_token>`.
4. Token lifetime: 30–60 minutes. Refresh via FusionAuth `/api/jwt/vend`.

**EVE Vault does NOT expose the JWT to web pages.** There is no `window.suiWallet`, no injected provider, no `postMessage` API that a DApp can use to retrieve the token. This is confirmed from the official EVE Vault repository.

**Conclusion: JWT-authenticated `/me` endpoints are not accessible from our web app.** This is a platform limitation with no clean workaround for personal-use tools. Deferred until EVE Frontier provides a developer API key or web-accessible auth flow.

---

## What the World API provides without auth

| Endpoint | Data |
|---|---|
| `GET /v2/solarsystems` | Full system list (24,501 systems), paginated |
| `GET /v2/solarsystems/{id}` | System detail: name, location, constellation, gate links |
| `GET /v2/ships` | All ship types (class, name, description) |
| `GET /v2/ships/{id}` | Ship type detail: hull stats, slots, resistances, capacitor, physics |
| `GET /v2/types` | All item types |
| `GET /v2/tribes` | All tribes |
| `GET /v2/constellations` | All constellations |
| `GET /v2/characters/me/jumps` | **Requires Bearer token** — gate jump history |

All list endpoints are paginated: `{ data: [...], metadata: { limit, offset, total } }`.

---

## What requires auth (deferred)

All of these require the OIDC JWT Bearer token from EVE Vault:

- `GET /v2/smartships/me` — player's ship instances (instanceId + typeId)
- `GET /v2/smartassemblies/me` — player's owned smart assemblies
- `GET /v2/characters/me/jumps` — gate jump history
- Killmails — endpoint path TBD (present in blockchain-gateway, not in World API spec)

---

## Smart Assemblies (on-chain)

Smart assemblies (Gates, Storage Units, Turrets) are on-chain Sui objects owned by a `Character`. Key facts:

- **Location:** v0.0.18 (released 2026-03-11) adds opt-in location publishing for smart assemblies. Automatic for Gates, Storage Units, and Turrets. Player/ship location is a separate opt-in toggle.
- **Ownership:** Controlled via `OwnerCap` objects. Only the wallet address in `character_address` can borrow caps.
- **Character discovery:** Query `PlayerProfile` objects owned by a wallet address to get `character_id`, then fetch the `Character` object. Requires Sui GraphQL or SDK.
- **Sui GraphQL:** An internal indexer exists at `graphql-stillness-internal.live.evefrontier.tech`. The "internal" subdomain suggests it may not be publicly accessible; not confirmed.

---

## Decisions for Ship AI Companion

### What we build now

| Data | Source | Notes |
|---|---|---|
| Current system | Log agent (chat log) | Working pattern, pending Windows deployment |
| System topology, gate links | World API `/v2/solarsystems/{id}` | Working |
| Ship type stats | World API `/v2/ships/{SHIP_TYPE_ID}` | Configure `SHIP_TYPE_ID` in `.env` |
| Recent events (combat, docking) | Log agent | Pending deployment + regex verification |

### What we defer

| Data | Reason |
|---|---|
| Current ship instance | Requires JWT auth — platform wall |
| Jump history | Requires JWT auth — platform wall |
| Killmails | Requires JWT auth — platform wall |
| Smart assembly states | Requires JWT auth — platform wall |
| Direct Sui chain reads | Sui RPC read methods are all blocked |

### New env vars

```
SERVER_TOKEN=your-server-auth-secret    # server-to-server auth (X-Server-Token header)
SHIP_TYPE_ID=                           # integer ship type ID, e.g. 84955 for Moa
SUI_RPC_URL=https://pyrope-external-sync-node-rpc.live.tech.evefrontier.com
BLOCKCHAIN_GW_URL=https://blockchain-gateway-stillness.live.tech.evefrontier.com
```

`WORLD_API_KEY` / `WORLD_API_BASE_URL` — `WORLD_API_BASE_URL` is already in `.env`. `WORLD_API_KEY` is NOT stored — it is the runtime JWT from EVE Vault and is not accessible to our server.

### Rename completed (2026-03-11)

`SHIP_TOKEN` → `SERVER_TOKEN` throughout: `.env`, `.env.example`, `src/auth.py`, `static/index.html`, `log-agent/log_agent.py`, `log-agent/.env.example`, all tests, all docs. Header renamed `X-Ship-Token` → `X-Server-Token`.

---

## Builder scaffold reference

- **Repo:** `https://github.com/projectawakening/builder-examples`
- **World contracts:** `https://github.com/evefrontier/world-contracts`
- **Move error decoder:** `https://evefrontier.github.io/world-contracts/`
- **Docs:** `https://docs.evefrontier.com/smart-assemblies/introduction`
- Smart assemblies: Gates, Storage Units, Turrets — programmable via custom Move contract extensions
- `OwnerCap` borrow-use-return pattern controls all assembly operations
- Sponsored transactions: players sign intents, sponsor covers gas + submission
