# TokenManager

## Overview

Manages RSA-2048 key generation, loading, and JWT token operations for log agent authentication. Issues bearer tokens that log agents use to authenticate requests to `/log/ingest`, and validates those tokens on the server side.

## When Should an Agent Use This Module?

- You need to issue JWT bearer tokens for log agents or other clients
- You need to validate JWT tokens in request handlers (use FastAPI `Depends` with `validate_token()`)
- You need to understand token lifetime, encryption, and key rotation behavior
- You're troubleshooting auth failures on `/log/ingest` or other Bearer JWT endpoints

## Key API

| Symbol | Type | Purpose | Agent Instruction | Gotchas |
|--------|------|---------|-------------------|---------|
| `TokenManager(key_dir)` | class constructor | Initialize key manager; load or generate RSA-2048 pair | Pass `.keys` or similar directory; keys persisted with encryption | Key dir created automatically; errors if TOKEN_KEY_PASSWORD env var changes after generation |
| `issue_token(agent_id, scope, lifetime_hours)` | method → `str` | Issue a new JWT bearer token for an agent | Call with agent_id (e.g., "log-agent-1"), scope (default "log-ingest"), hours (default 24) | Returns a JWT string; no expiry enforcement on issue—clock skew can affect validation |
| `validate_token(token)` | method → `Optional[Dict]` | Validate JWT; return claims dict or None if invalid | Pass the token string; check result for `None` before accessing payload | Returns `None` on invalid signature, expiration, or malformed token; never raises |
| `_get_encryption_password()` | private method → `bytes` | Derive or load password for key encryption at rest | Do not call; internal use only | Uses TOKEN_KEY_PASSWORD env var or derives from key_dir path; always 32 bytes (SHA-256) |
| `_load_or_generate_private_key()` | private method | Load existing private key or generate new RSA-2048 if missing | Do not call; internal use only | File permissions set to 0o600 (owner read/write only) on generation |

## Critical Gotchas & Pitfalls

• **Token algorithm is hardcoded to RS256** — despite `token_algorithm` in config, the code hardcodes RS256 in `jwt.encode()` (line 114) and `jwt.decode()` (line 120). Config value is loaded but ignored.

• **Scope parameter is required in token claims** — `issue_token()` includes `scope` in the JWT payload. Default scope is `"log-ingest"`. Tokens with different scopes will have different claims; validation does NOT check scope, so callers must verify it if needed.

• **Validation returns None, never raises** — old docs said `validate_token` raises on invalid signature. It doesn't. It catches `jwt.InvalidTokenError` and returns `None`. Check the return value explicitly: `if not payload: ...`

• **Key encryption password is critical** — if `TOKEN_KEY_PASSWORD` changes after key generation, the server cannot load the old key (password mismatch). Set it once in `.env` and never change it, or delete `.keys/` to regenerate. No password rotation mechanism.

• **Config file is optional** — if `config/token_config.json` is missing, defaults apply (24 hours, RS256). File is loaded at `__init__` time; changes require server restart.

• **Token lifetime in claims is absolute, not rolling** — `exp` claim is set to `iat + lifetime_hours`. No refresh token mechanism. Clients must request a new token before expiry.

## Architecture

**Key Lifecycle:**
1. `__init__` checks `config/token_config.json` for `token_lifetime_hours` and `token_algorithm` (defaults: 24h, RS256)
2. Derives or loads encryption password from `TOKEN_KEY_PASSWORD` env var or key directory path (always 32 bytes via SHA-256)
3. Checks for `{key_dir}/private_key.pem` and `{key_dir}/public_key.pem`
4. If missing, generates new RSA-2048 pair, encrypts private key with password, saves both
5. Loads private key; derives public key from it

**Token Format:**
```json
{
  "sub": "agent_id",
  "iat": 1710000000,
  "exp": 1710086400,
  "scope": "log-ingest"
}
```

**Algorithm:**
- Generation: `jwt.encode(payload, private_key, algorithm="RS256")` — always RS256
- Validation: `jwt.decode(token, public_key, algorithms=["RS256"])` — RS256 only

**Key Storage:**
- Private key: `{key_dir}/private_key.pem` (encrypted with 32-byte password, PKCS8 format, file mode 0o600)
- Public key: `{key_dir}/public_key.pem` (unencrypted, derived from private key at runtime)
- Encryption: `BestAvailableEncryption(password)` on save; tries password first, falls back to unencrypted (backward compat)

## Agent Guidance

**Primary Workflow**

1. Create TokenManager at server startup (e.g., in FastAPI lifespan)
   ```python
   token_manager = TokenManager(key_dir=".keys")
   ```

2. Bind to `/auth/token` endpoint to issue tokens on request
   ```python
   @app.post("/auth/token")
   async def get_token(agent_id: str):
       token = token_manager.issue_token(agent_id)
       return {"token": token}
   ```

3. Use `validate_token()` as a FastAPI `Depends` to protect endpoints
   ```python
   async def require_token(token: str = Header(..., alias="Authorization")):
       # Strip "Bearer " prefix
       actual_token = token.replace("Bearer ", "")
       payload = token_manager.validate_token(actual_token)
       if not payload:
           raise HTTPException(status_code=401, detail="Invalid token")
       return payload
   ```

4. Clients acquire and store token
   ```bash
   TOKEN=$(curl -X POST http://localhost:8745/auth/token \
     -H "Content-Type: application/json" \
     -d '{"code":"..."}' | jq -r '.access_token')
   # Store securely (DPAPI on Windows, 0o600 file on Unix)
   ```

5. Clients use token in Bearer header for protected requests
   ```bash
   curl -H "Authorization: Bearer $TOKEN" http://localhost:8745/log/ingest
   ```

**Best Practices & Anti-Patterns**

- Always check `validate_token()` result for `None` before accessing payload
  - ✅ `if payload: subject = payload["sub"]`
  - ❌ `subject = payload["sub"]` (crashes if invalid token)

- Set `TOKEN_KEY_PASSWORD` once in `.env` and keep it stable
  - ❌ Never rotate it without deleting `.keys/` first
  - ❌ Do not share key directory between servers with different passwords

- Issue tokens with appropriate `lifetime_hours`
  - ✅ Short-lived tokens (1–24 hours) for agents
  - ❌ Very long lifetimes (weeks/months) for security-critical log ingestion

- Scope parameter is informational; validation does not enforce it
  - If scope matters, check `payload["scope"]` after validation
  - Default scope is `"log-ingest"` for log agents

- Token expiry is absolute; no refresh token mechanism
  - Clients must request new tokens before expiry
  - UTC timestamps are used; ensure server clock is accurate

**Cross-Module Dependencies**

- **FastAPI endpoints:** `/auth/token` (issue), `/log/ingest` (validate via Depends)
- **Environment:** `TOKEN_KEY_PASSWORD` env var (optional; derives from key_dir if not set)
- **Configuration:** `config/token_config.json` (optional; defaults apply if missing)
- **Log agent:** `log-agent/auth_flow.py` acquires and uses tokens
- **Reference:** See `docs/ref/ship-ai.md` for full `/auth/token` endpoint flow and Bearer auth requirements

## Progressive Disclosure

Read this file by default. Load deeper files only when told above.

- Token/auth implementation details → `docs/ref/structure-ai.md` (blockchain Sui auth) or `log-agent/auth_flow.py` (agent-side flow)
- Full endpoint routing → `docs/ref/ship-ai.md` section "Authentication Methods"
- Key encryption internals → source code `src/token_manager.py` lines 47–103
