# structure_auth

## Overview
Handles Sui wallet-based authentication for Structure AI. Verifies Sui `signPersonalMessage` signatures, manages single-use nonces with TTL, and issues/decodes JWTs for wallet-authenticated structure access.

## When Should an Agent Use This Module?
- Authenticating structures via Sui wallet (multi-step: challenge → sign → verify)
- Looking up EVE Frontier character by wallet address
- Verifying Sui ed25519 or zkLogin signatures
- Issuing/decoding JWT tokens for structure access
- Protecting endpoints with `require_structure_jwt()` dependency

## Key API
| Symbol | Type | Purpose | Agent Instruction | Gotchas |
|--------|------|---------|-------------------|---------|
| `NonceStore` | Class | In-memory single-use nonce store with 5min TTL (GIL thread-safe) | Instantiate once; use `issue()` to create nonce, `consume(nonce)` to validate | TTL default is 300s; expired nonces auto-evict on `issue()` |
| `NonceStore.issue()` | Method → str | Generate 32-byte random hex nonce, store with expiry | Called by `/auth/challenge` endpoint | Returns nonce immediately; valid for 5 minutes |
| `NonceStore.consume(nonce)` | Method → bool | Mark nonce as used (pops from store). Returns True only if present AND not expired | Called by `/auth/verify` endpoint to anti-replay | Must call exactly once per nonce; second call returns False |
| `verify_sui_personal_message(message_bytes, signature_b64, expected_address)` | Function → bool | Verify Sui compact signature (ed25519 flag 0x00 or zkLogin 0x03/0x05). Raises ValueError/InvalidSignature on error | Called by `/auth/verify` and `/auth/deal/claim` | zkLogin (0x03, 0x05) skips Groth16 proof, trusts nonce anti-replay; ed25519 (0x00) does full crypto verification |
| `issue_jwt(payload)` | Function → str | Issue HS256 JWT with 24h expiry | Called by `/auth/verify` + `/auth/deal/claim` to create access tokens | Requires `JWT_SECRET` env var; warns if unset |
| `decode_jwt(token)` | Function → dict | Decode and verify JWT signature; raises on expiry or tampering | Called by `require_structure_jwt()` dependency to validate incoming tokens | Decoding failure raises exception; endpoint must catch and return 401 |
| `lookup_character(address)` | Async Function → dict | Query World API `/v2/smartcharacters?address={address}` for character by wallet | Called by `/auth/verify` to populate JWT with character metadata | Returns `{id, name}` or `{}` on failure; gracefully degrades if World API unavailable |
| `nonce_store` | Global | Singleton NonceStore instance with 300s TTL | Use directly: `nonce_store.issue()`, `nonce_store.consume(nonce)` | Per-application instance; shared across all endpoints |
| `JWT_SECRET` | Constant (env) | HS256 signing key from `JWT_SECRET` env var | Referenced internally by `issue_jwt` + `decode_jwt` | Default `"change-me-in-production"` triggers warning log |
| `JWT_ALGORITHM` | Constant | Algorithm name: `"HS256"` | Do not override | Hardcoded; not configurable |
| `JWT_EXPIRY_HOURS` | Constant | Expiry duration: `24` hours | Control via code change only (no env var) | Fixed 24h; deal JWTs use same expiry, deal limits enforced by `DealStore` |
| `NONCE_TTL_SECONDS` | Constant | TTL for nonces: `300` seconds (5 minutes) | Control via NonceStore constructor | Matches `/auth/challenge` response `expires_in_seconds` field |

## Critical Gotchas & Pitfalls

• **zkLogin signatures (flag 0x03, 0x05):** Groth16 proof verification is skipped because Sui testnet lacks `sui_verifyPersonalMessageSignature` RPC. Replay protection relies entirely on nonce TTL. Full verification deferred post-hackathon.

• **Nonce reuse is a hard error:** `NonceStore.consume()` returns False on second call to same nonce (already popped). Every `/auth/verify` call must consume exactly once. Double-consume = auth failure.

• **Address case sensitivity:** Sui addresses are hex strings; comparison is case-insensitive but stored as-is. When checking `expected_address` in verification, comparison is done `.lower()`.

• **JWT expiry is absolute:** All JWTs expire after 24h from issue time. For PATRON tiers with message limits, `DealStore` enforces limits separately; expired PATRON JWT + remaining messages = still rejected (JWT expiry takes precedence).

• **World API is optional:** `lookup_character()` gracefully returns `{}` if World API is unavailable. Character metadata is enriched context only; auth succeeds without it.

## Architecture

```
Client → GET /auth/challenge → nonce_store.issue() → {nonce, expires_in_seconds: 300}
         [Client signs nonce with Sui wallet]
       → POST /auth/verify → consume_nonce + verify_sui_personal_message() + lookup_character() → issue_jwt(payload) → {access_token}
       → Use Bearer token for /structure/* endpoints, validated by require_structure_jwt() → decode_jwt()
```

**Key flow:**
1. `/auth/challenge`: `nonce_store.issue()` generates 32-byte hex nonce, stored with 5min TTL
2. Client signs nonce offline (Sui wallet, PersonalMessage type)
3. `/auth/verify`: `nonce_store.consume(nonce)` pops nonce; if valid, calls `verify_sui_personal_message()` (ed25519 or zkLogin)
4. On success: `lookup_character(address)` fetches EVE character; `issue_jwt()` creates Bearer token
5. Protected endpoints validate token via `require_structure_jwt()` → `decode_jwt(token)` → payload dict

## Agent Guidance

**Primary Workflow**
1. When designing wallet-auth endpoints, use `/auth/challenge` + `/auth/verify` two-step pattern (not single-step)
2. Always call `nonce_store.consume()` before `verify_sui_personal_message()` to prevent replay
3. Wrap `decode_jwt()` calls in try/except; catch exceptions as 401 auth errors
4. For character enrichment, call `lookup_character()` after signature verification succeeds

**Best Practices & Anti-Patterns**

- **Always:** Use `nonce_store.consume()` before verifying signature — reuse attempt = hard security error
- **Always:** Set `JWT_SECRET` to a strong random value in production; default warning log is intentional
- **Never:** Re-verify an already-consumed nonce (it's been popped); second call returns False
- **Never:** Ignore `verify_sui_personal_message()` exceptions; ValueError = format error (client bug), InvalidSignature = signature mismatch (attacker or wrong address)
- **Prefer:** ed25519 signatures (flag 0x00) for full cryptographic verification; zkLogin (0x03/0x05) currently relies on nonce anti-replay only
- **On World API downtime:** `lookup_character()` returns `{}` — auth continues without character data; endpoints should have fallback

**Cross-Module Dependencies**

- **nova_client:** Not used by structure_auth directly (tier resolution happens in endpoints via nova_client + AccessRegistry)
- **deal_store:** Uses same `nonce_store` singleton and `verify_sui_personal_message()` for deal claim flow
- **memory_store:** Populated by endpoints after successful auth with pilot profiles
- **token_manager:** Separate JWT system for agent tokens (different signing key, different endpoints)

## Progressive Disclosure
Read this file by default. Load deeper files only when told above.
- JWT internals, ed25519 format, BCS encoding → `references/structure_auth-deep.md`
- Deal mechanic (PATRON tier, payment methods, claim flow) → `docs/ref/structure-ai.md` (deal_store section)
