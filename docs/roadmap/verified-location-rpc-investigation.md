# Verified Location via EVE Frontier RPC Bridge

**Status:** Two paths identified. Path A (POD export) requires no CCP cooperation and works today. Path B (Sign In With Sui via zkLogin) requires one CCP endpoint — the mechanics on both sides already exist.
**Goal:** Allow a player to press a button in HUGINN's TerminalUI to prove their current solar system, giving the AI companion verified location context instead of self-reported data.

---

## What We're Trying to Do

HUGINN currently relies on the player manually typing `/system <name>` to set their location. This is unverified — anyone can claim to be anywhere. We want a button that proves location using data signed or sourced directly from the game client.

**SSU system name is already solved** — `assembly?.solarSystem?.name` comes through dapp-kit's `useSmartObject()` from on-chain data and is already displayed in the baseline panel. No World API needed for this.

The remaining goal is **player current location** — which system is the visiting pilot actually in, verified, not self-reported. Use case: verified intel submissions. HUGINN could mark intel as cryptographically confirmed vs self-reported.

---

## What We Discovered

### EVE Frontier World API

Swagger UI: `https://world-api-stillness.live.tech.evefrontier.com/docs/index.html`
OpenAPI spec: `https://world-api-stillness.live.tech.evefrontier.com/docs/doc.json`

**Most endpoints are public — only `characters/me` requires auth.**

| Endpoint | Auth | Notes |
|---|---|---|
| `GET /health` | None | Health check |
| `GET /config` | None | Returns `podPublicSigningKey` |
| `POST /v2/pod/verify` | None | Verifies any POD |
| `GET /v2/solarsystems` | None | Paginated, max 1000/page |
| `GET /v2/solarsystems/{id}` | None | Full system detail + POD format |
| `GET /v2/constellations` | None | Paginated |
| `GET /v2/constellations/{id}` | None | |
| `GET /v2/ships` | None | Paginated |
| `GET /v2/ships/{id}` | None | |
| `GET /v2/types` | None | Paginated |
| `GET /v2/types/{id}` | None | |
| `GET /v2/tribes` | None | Paginated |
| `GET /v2/tribes/{id}` | None | |
| `GET /v2/characters/me/jumps` | **Bearer** | Jump history, most recent = current system |
| `GET /v2/characters/me/jumps/{id}` | **Bearer** | Single jump; `?format=pod` returns signed POD (HTTP 201) |

No auth/token endpoint exists in the spec. `BearerAuth` is declared with no token acquisition flow documented.

**Key schemas:**

`v2.jumpResponse`:
```json
{
  "id": 1741297384412,
  "time": "2025-03-06T21:43:04.412Z",
  "origin":      { "id": 30018090, "name": "Moh", "constellationId": 21000123, "regionId": 11000012, "location": { "x": 1.2, "y": 3.4, "z": 5.6 } },
  "destination": { "id": 30018092, "name": "Skarkon", "constellationId": 21000124, "regionId": 11000012, "location": { "x": 7.8, "y": 9.0, "z": 1.1 } },
  "ship": { "instanceId": 123456, "typeId": 789 }
}
```

`id` is a Unix millisecond timestamp — sortable. Highest ID = most recent jump = current system.

`pod.Pod` (what `POST /v2/pod/verify` accepts, and what `?format=pod` returns):
```json
{
  "entries": {
    "destinationId": { "valueType": "int",    "bigVal": {} },
    "originId":      { "valueType": "int",    "bigVal": {} },
    "shipId":        { "valueType": "int",    "bigVal": {} },
    "time":          { "valueType": "date",   "timeVal": "2025-03-06T21:43:04Z" },
    "pod_type":      { "valueType": "string", "stringVal": "evefrontier.jump" }
  },
  "signature": "base64...",
  "signerPublicKey": "base64..."
}
```

Each entry value is a typed discriminated union. `valueType` tells you which field to read: `stringVal`, `bigVal`, `boolVal`, `bytesVal`, or `timeVal`. Full enum: `null | string | bytes | cryptographic | int | boolean | eddsa_pubkey | date`.

`v2.verifyResponse`:
```json
{ "isValid": true, "error": "" }
```

### CORS Block

The World API does not allow cross-origin requests from our frontend's origin. Both authenticated and unauthenticated endpoints returned "Failed to fetch" from the in-game browser. All World API calls must be proxied through the Python backend — direct browser-to-World-API calls are impossible regardless of auth.

### Game Client Storage

`localStorage`, `sessionStorage` — no auth tokens or session data. The game client does not expose its session to dApp page JS via storage.

### Window Globals Injected Into the dApp Panel

```
_eveFrontierRpcRequest    eveFrontierRpcRequest    callWallet
WALLET_API_CHAIN          ccpPython                __pythonCall
```

Notably absent: `_get_token`, `_get_refresh_token`, anything token-related.

### The RPC Bridge

`eveFrontierRpcRequest` and `callWallet` are the same function:

```javascript
function eveFrontierRpcRequest(request, interval = 10, timeout = 30000) {
  return new Promise((resolve, reject) => {
    const startTime = Date.now();
    let requestId = null;
    function poll() {
      _eveFrontierRpcRequest(requestId, request)
        .then(response => {
          if (requestId === null) requestId = response.id;
          if (response.status === 'done') { resolve(response.response); return; }
          if (response.status === 'pending') {
            if (Date.now() - startTime >= timeout) { reject(new Error(`Request ${requestId} timed out`)); return; }
            setTimeout(poll, interval);
            return;
          }
          if (response.status === 'failed') {
            reject(new Error(`Request ${requestId} failed: ${response.response}`));
            return;
          }
        }).catch(err => reject(err));
    }
    poll();
  });
}
```

`_eveFrontierRpcRequest` routes to `ccpPython.pythonCall` — the game engine's browser-to-Python IPC layer.

### Protocol: JSON-RPC 2.0

Confirmed by trial and error. Correct calling convention:

```javascript
const result = await eveFrontierRpcRequest({ method: "method_name", params: {} });
// resolves to: { jsonrpc: "2.0", id: N, result: ... }
// or on error: { jsonrpc: "2.0", id: N, error: { code, message } }
```

`WALLET_API_CHAIN = "sui:testnet"` — testnet environment.

### What `eveFrontierRpcRequest` Actually Is — Wallet Bridge Only

Decompiled engine analysis (`frontier/cycle_hub/client/`) confirmed:

- The bridge behind `eveFrontierRpcRequest` is `SuiWalletProvider._handle_json_rpc_request`, forwarding to `SuiWalletService`
- This is a **Sui Wallet Standard bridge only** — it handles signing operations, not game data
- Callable methods are wallet operations: `signTransaction`, `signPersonalMessage`, `signAndExecuteTransaction`, `evefrontier:sponsoredTransaction`, `getAccounts`, etc.
- All game-data method guesses returned "Method not found" because they were the wrong bridge entirely

### The Token Provider — Found But Inaccessible

Decompiled engine analysis (`frontier/cycle_hub/client/token_provider.pyc`) found:

- `TokenProvider._get_token` calls `monolithconfig.get_user_jwt()` — this IS the World API Bearer token
- `_get_token` and `_get_refresh_token` are registered via `RegisterFunction` as browser-callable
- **But they are registered into the Cycle Hub browser context** (the game's own trusted UI), not the dApp panel context where our code runs
- Confirmed by probing: `typeof window._get_token === "undefined"` in the dApp panel

This is intentional security design. CCP does not expose the user JWT to untrusted third-party dApp pages. Any random structure dApp could otherwise steal the player's World API auth token.

### Methods Tried via `eveFrontierRpcRequest` — All "Method not found"

```
system.listMethods    system.list_methods    rpc.discover
get_token             get_jwt                get_auth_token
get_world_api_token   get_session            authenticate
get_location          get_character_location get_current_location
get_current_system    get_jumps              get_character_jumps
get_character         get_character_info
getJwt                getAuthToken           getLocation           getJumps
getToken              getJWT                 getCurrentLocation    getCharacterLocation
```

### FusionAuth OAuth2 Infrastructure — Exists But Closed

CCP runs FusionAuth at `https://auth.evefrontier.com/`. The OpenID Connect discovery endpoint (`/.well-known/openid-configuration`) confirms:

- **Authorization endpoint:** `https://auth.evefrontier.com/oauth2/authorize`
- **Token endpoint:** `https://auth.evefrontier.com/oauth2/token`
- **Supported flows:** Authorization Code, Password, Implicit, Refresh Token, Device Code
- **No `registration_endpoint`** — dynamic client registration is not supported
- **Scopes:** `openid`, `offline_access`, `email`, `phone`, `profile` — standard OIDC only, no game-specific scopes (no `world_api`, no `jumps`)

The SIWE-style JWT exchange is therefore not a self-serve option. A third-party app would need CCP to manually issue a `client_id` and add game-scoped claims. That requires contacting CCP directly and is not a documented developer offering.

### POD Export from evefrontier.com — The Designed Third-Party Path

The official mechanism for verified player data in external apps is player-exported PODs:

> "Participants can go to their account on evefrontier.com and export the starting system and the system jumps."
> "Players use PODs to prove that people reached a system without having to create Smart Storage Units."

The flow requires no third-party auth at all:

```
1. Player logs in at evefrontier.com/account
2. Player exports their latest jump as a POD (website handles JWT internally)
3. Player submits the POD JSON to the third-party app (paste / slash command)
4. Backend calls POST /v2/pod/verify  — no auth required
5. Backend checks signature against podPublicSigningKey from GET /config
6. Location marked as cryptographically verified
```

This is a **manual player-initiated flow** — the player actively exports and submits the POD. HUGINN never holds a JWT. Verification uses only the public key from `GET /config`, which requires no auth.

**Critically: after verifying the POD, resolving the system name requires no auth either.** The POD's `destinationId` entry (a `bigVal` int) can be passed directly to `GET /v2/solarsystems/{id}` — a public endpoint — to get the full system name, region, constellation, and 3D coordinates. Path A is entirely auth-free end to end.

### How Community Third-Party Tools Access Data

EF-Map (a working EVE Frontier map tool) does not use the World API for game state. Their approach:

- **On-chain data**: Sui GraphQL + their own indexer → PostgreSQL pipeline
- **Game client data**: A native Windows DLL injected into the game process reads game memory via DirectX 12 overlay (not replicable in a web dApp)
- **No World API auth**: They confirmed the auth migration to EVE Vault / zkLogin but do not rely on World API private endpoints

This confirms that third-party tools in the community bypass the World API entirely, reading on-chain data instead.

---

## Current State

| Need | Status |
|---|---|
| SSU system name | **Solved** — dapp-kit `solarSystem.name` |
| Player current system (verified) | **Path exists** — POD export from evefrontier.com |
| Player current system (zero-click) | Blocked — requires World API JWT |
| JWT from game client (dApp panel) | Inaccessible by design — Cycle Hub context only |
| JWT via FusionAuth OAuth2 (self-serve) | Blocked — no dynamic registration, no game scopes |
| JWT via zkLogin signPersonalMessage (SIWS) | Possible — mechanics in place, needs one CCP endpoint |
| JWT via OAuth2 redirect (CCP-issued client_id) | Possible — requires CCP to register HUGINN as a client |

---

## Paths Forward

### Path A: POD Export (no CCP cooperation needed)

Player exports their jump POD from `evefrontier.com/account` and submits it to HUGINN via a slash command (e.g. `/provemylocation`). HUGINN verifies the signature and marks the location as confirmed. This is the designed third-party integration model and works today.

Implementation — entirely auth-free:
```
1. Player: /provemylocation  →  HUGINN replies with export instructions
2. Player: exports POD from evefrontier.com/account, pastes JSON
3. Backend: POST /v2/pod/verify  (no auth) → { isValid: true }
4. Backend: read entries.destinationId.bigVal, entries.time.timeVal
5. Backend: GET /v2/solarsystems/{destinationId}  (no auth) → { name, regionId, ... }
6. HUGINN: stores verified system_name + timestamp, marks intel as confirmed
```

### Path B: Sign In With Sui via zkLogin (requires one CCP endpoint)

EVE Vault signs using Sui's zkLogin. When our dApp calls `signPersonalMessage`, the resulting signature is not a plain wallet signature — it is a Groth16 ZK proof tied to the player's FusionAuth identity. This is more powerful than it appears.

**What the zkLogin signature reveals:**
- `iss` — confirms the signer is an authenticated EVE Frontier FusionAuth user
- `aud` — the client_id used (EVE Vault's)
- `kid` — JWK key ID for verification

**What it keeps private:**
- `sub` — the user's FusionAuth identity is NOT exposed in the proof, by design

A third party verifying the signature can confirm the signer is a valid EVE Frontier account but cannot extract which account. However, **CCP can** — they have the `address → FusionAuth user` mapping stored from registration (the zkLogin address is derived from `sub + iss + aud + salt`, and CCP holds the salt). Their backend can verify the signature, look up the user, and issue a World API JWT.

**The flow if CCP builds this endpoint:**

```
1. HUGINN backend: generate a challenge nonce
2. Frontend: const sig = await signPersonalMessage(nonce)  // EVE Vault zkLogin sig
3. Frontend: POST our_backend/session/prove-location { address, sig }
4. Backend: POST ccp.../auth/siws { address, sig, nonce }  // "Sign In With Sui"
5. CCP backend: verify zkLogin sig → look up address → issue World API JWT
6. Backend: GET world-api.../v2/characters/me/jumps  Authorization: Bearer {jwt}
7. HUGINN: uses verified system, marks location as confirmed
```

This is cleaner than a full OAuth2 redirect — no page navigations, the player signs a single prompt in the dApp and the token exchange happens silently in the background.

The specific ask to CCP:

> "You run FusionAuth at auth.evefrontier.com and EVE Vault uses zkLogin to derive player Sui addresses. You already have the address→user mapping. Is there an endpoint (or could you add one) that accepts a zkLogin-signed challenge and returns a World API Bearer token?"

The infrastructure on both sides exists. The one missing piece is that CCP has not documented or exposed this endpoint. A fallback is the standard OAuth2 Authorization Code redirect — CCP registers HUGINN as a client, player is redirected to `auth.evefrontier.com/oauth2/authorize`, and a JWT is returned via callback. This works but requires a page navigation out of the dApp and CCP to add game-scoped claims to the token.

---

## Test Commands in TerminalUI (to be removed when feature is built)

Four diagnostic slash commands added during this investigation:

- `/testloc` — confirmed CORS blocks all World API calls from the browser
- `/testwnd` — found `eveFrontierRpcRequest`, `callWallet`, `WALLET_API_CHAIN`, `ccpPython` on window; no token globals
- `/testrpc` — confirmed JSON-RPC 2.0 protocol; all game-data method guesses returned "Method not found"; identified bridge as wallet-only
- `/testtoken` — confirmed `_get_token` / `_get_refresh_token` are undefined in the dApp panel context

---

## Notes on the ZK Proximity Repo

The `eve-frontier-proximity-zk-poc` repo (official CCP repo) implements Groth16 ZK circuits for location/distance attestation on Sui. Our immediate need (verified player system) is solved by the POD export path — the player exports a server-signed POD, we verify the signature. The ZK repo assumes location data already exists (hardcoded in tests) and focuses on proving facts about that data without revealing exact coordinates. Relevant only if we later need to prove proximity or distance between objects without disclosing positions.
