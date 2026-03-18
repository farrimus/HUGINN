# Operations Reference

**Last updated:** 2026-03-17
**Contents:** Configuration, running the system, known gaps, lore reference

---

## Configuration

### Token Authentication Configuration

**Environment Variables:**

```bash
# Existing (still supported for backward compatibility)
SERVER_TOKEN=your-static-token          # Legacy; for old X-Server-Token header

# New (for JWT token system)
JWT_SECRET=your-secret-key              # Used by structure_auth for Sui wallet JWTs
TOKEN_KEY_PASSWORD=encryption-password  # Password for encrypting RSA private key (optional)
                                         # If not set, derived from key directory path

# Token lifetime (in TokenManager config)
# See config/token_config.json for token_lifetime_hours (default: 24)
```

**Configuration File: config/token_config.json**

```json
{
  "token_lifetime_hours": 24,
  "token_algorithm": "RS256",
  "token_key_dir": ".keys",
  "token_validation_enabled": true,
  "auth_endpoints": {
    "token": "/auth/token"
  }
}
```

**Key Management:**

- RSA keys stored: `<token_key_dir>/` (default: `.keys/`)
  - `private_key.pem` — Encrypted with TOKEN_KEY_PASSWORD (PBKDF2)
  - `public_key.pem` — Public key for client-side validation (optional)
- Keys generated: Automatically on first startup
- Key rotation: Delete key files and restart server (invalidates all outstanding tokens)

**Deployment Checklist:**

- [ ] Set TOKEN_KEY_PASSWORD environment variable (strong random password)
- [ ] Ensure `config/token_config.json` exists with correct token_key_dir
- [ ] Create `.keys/` directory with proper permissions (readable by app only)
- [ ] Configure token_lifetime_hours based on your security policy (default 24h)
- [ ] (Optional) Distribute public key if using multi-server setup

---

### Server `.env`
```
ANTHROPIC_API_KEY=sk-ant-...
# World API: WORLD_API_BASE_URL overrides WORLD_API_ENV. Default env is "utopia".
WORLD_API_BASE_URL=https://world-api-utopia.live.tech.evefrontier.com
WORLD_API_ENV=utopia
SERVER_TOKEN=<random secret — must match overlay config.h and log-agent .env>
PORT=8745
JWT_SECRET=<random secret for structure JWT signing>
TOKEN_KEY_PASSWORD=<password for RSA private key encryption>
# Structure AI identity
STRUCTURE_ID=keep-7a
STRUCTURE_SYSTEM_NAME=JITA
NOVA_REGISTRY_OBJECT_ID=0x89e9b9b90acc3b7b576c7fe81015e0a6d333d9ae3e69133c8b1786c826f05dc0
NOVA_RPC_URL=https://fullnode.testnet.sui.io
# Background polling
SSU_OBJECT_ID=<Sui object ID of the deployed SSU — leave blank to disable SSU state polling>
TURRET_OBJECT_IDS=<comma-separated Sui object IDs of turrets — leave blank to disable>
# Player-owned structure IDs for Ship AI context (comma-separated Sui object IDs)
PLAYER_STRUCTURE_IDS=<comma-separated Sui object IDs of player's own structures>
# Deal mechanic — PATRON access for strangers
VPS_SUI_ADDRESS=0x9a3e...    # VPS deployer wallet address — receives SUI coin payments
EVE_FRONTIER_PACKAGE=0xd12a70c74c1e759445d6f209b01d43d860e97fcf2ef72ccbbd00afd828043f75
```

### Log Agent `log-agent/.env` (Windows)
```
SERVER_URL=http://your-vps-ip:8745
SERVER_TOKEN=change-this-to-match-server
LOG_BASE_PATH=C:\Users\Markus\Documents\Frontier\logs
```

---

## Running the System

### Server

```bash
cd /opt/eve-frontier
source .venv/bin/activate
./start.sh
# or: uvicorn main:app --host 0.0.0.0 --port 8745
```

**During startup, the server performs token system initialization:**

1. **TokenManager Creation:**
   ```python
   token_manager = TokenManager(key_dir=".keys")
   # - Loads or creates RSA key pair
   # - Private key encrypted with TOKEN_KEY_PASSWORD
   ```

2. **Auth Router Registration:**
   ```python
   init_auth(token_manager)
   app.include_router(auth_router)
   # - Registers /auth/token endpoint
   # - Binds TokenManager to validate_token() dependency
   ```

3. **Server Ready for Token Requests:**
   - `/auth/token` endpoint available (no auth required)
   - Protected endpoints require Bearer JWT validation
   - Tokens issued with 24-hour lifetime

**Logs to watch:**
```
INFO: TokenManager initialized with RSA keys
INFO: auth_router registered, /auth/token available
```

If you see errors about missing keys or encryption failure, check:
- TOKEN_KEY_PASSWORD environment variable set
- `.keys/` directory exists and is writable
- Sufficient permissions to read/write key files

### Build universe data (one-time after deploy)
```bash
# Rebuild system index from World API
curl -X POST -H "X-Server-Token: $SERVER_TOKEN" http://localhost:8745/admin/rebuild-index
# Generates data/gate_graph.json alongside data/system_index.json

# Build systems.json + gates.json from ResFiles (requires starmapcache.json + eve_universe.db)
python build_universe.py
```

### Log Agent (Windows)
```bash
cd log-agent
python -m venv venv && venv\Scripts\activate
pip install -r requirements.txt
copy .env.example .env   # edit LOG_BASE_PATH, SERVER_URL, SERVER_TOKEN
python log_agent.py
```

### Run tests
```bash
cd /opt/eve-frontier
.venv/bin/pytest tests/ -q
# 258 passing (2026-03-17 baseline)
```

### Diagnostics

**Token Acquisition:**

```bash
# Request a token (no auth required)
curl -X POST http://localhost:8745/auth/token \
  -H "Content-Type: application/json" \
  -d '{"agent_id": "test-agent-001"}'

# Response:
{
  "access_token": "eyJhbGciOiJSUzI1NiIs...",
  "token_type": "Bearer",
  "expires_in": 86400
}

# Extract token for use in other requests:
TOKEN=$(curl -s -X POST http://localhost:8745/auth/token \
  -H "Content-Type: application/json" \
  -d '{"agent_id": "test-agent"}' | jq -r '.access_token')
```

**Using Bearer Token (NEW - Primary Method):**

```bash
# POST to protected endpoint with Bearer token
curl -X POST http://localhost:8745/log/ingest \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"event": "test_event"}'

# Full pipeline state
curl -H "Authorization: Bearer $TOKEN" http://localhost:8745/debug | jq

# Gate graph availability
curl -H "Authorization: Bearer $TOKEN" http://localhost:8745/data/gate-graph | jq '.built_at, (.adj | length)'

# Check token validity (will fail with 401 if invalid/expired)
curl -X GET http://localhost:8745/log/ingest \
  -H "Authorization: Bearer $TOKEN" -w "\nStatus: %{http_code}\n"
```

**Legacy X-Server-Token (Deprecated, may not work):**

```bash
# Old style (not recommended, included for reference)
curl -X POST http://localhost:8745/log/ingest \
  -H "X-Server-Token: static-token" \
  -d '{"event": "test_event"}'
```

**Troubleshooting Token Issues:**

| Error | Cause | Solution |
|-------|-------|----------|
| 401 Unauthorized | Token expired or invalid | Request new token via /auth/token |
| 401 "Missing Authorization header" | No Bearer auth sent | Include `Authorization: Bearer <token>` header |
| 401 "Invalid or expired token" | Token signature invalid | Token may be expired or corrupted |
| 500 "TokenManager not initialized" | Server startup failed | Check logs for key generation errors |
| "DPAPI not available" (Windows overlay) | Encryption failed | Check TOKEN_KEY_PASSWORD env var set |

**Check logs for token-related errors:**

```bash
grep -i "token\|auth" /var/log/app.log | tail -20
```

**Additional diagnostics:**

```bash
# Check safe_jump_temp for named systems vs ef-map.com
python scripts/check_temps.py UR8-K7K EVV-7GK

# Analyze gamelog structure (Windows)
python analyze_logs.py "C:\...\Frontier\logs\Gamelogs"

# Debug chatlog encoding (Windows)
python diagnose.py
```

---

## Known Gaps & TODOs

| Area | Gap | Priority |
|------|-----|----------|
| Ship stat auto-extraction | Manual input via F7 panel — SHIPS table covers all 13 ships; fuel qty + adaptive still manual | Medium |
| Route engine calibration | Formulas verified against spec; real in-game testing needed to confirm edge cases | Medium |
| ef-map golden tests | `tests/test_ef_map_comparison.py` has 1 confirmed system (UR8-K7K=36.9°). Use `scripts/check_temps.py` to add more from ef-map.com. | Medium |
| Blend / time-optimized routing | Deferred future feature. Design doc: `docs/future-features/blend-routing.md`. Shows fewest-jump + least-fuel side by side; time model needs ship jump cooldown formula from ef-map. | Medium |
| `ssu_poller.poll_ssu_state` | Two-hop RPC field paths verified live 2026-03-16 — `energy_source_id` bare string, `fuel.fields.quantity/max_capacity`, `connected_assembly_ids` plain array. All handled correctly. | Resolved |
| Assembly type labels | Real struct names confirmed: `Gate`, `Turret`, `StorageUnit`. `_TYPE_LABELS` updated. | Resolved |
| SSU self-reference in connected list | SSU lists itself in NetworkNode `connected_assembly_ids`. Filtered in `_ssu_loop` before resolving. | Resolved |
| `poll_ssu_inventory` | Resolved — inventory now read via Sui dynamic fields RPC (`suix_getDynamicFields` + `sui_getObject`). No gateway needed. | Resolved |
| Blockchain gateway DNS | Resolved — no gateway exists; all chain data goes through Sui RPC (`fullnode.testnet.sui.io`). `blockchain_client.py` removed. | Resolved |
| `system_name` for player structures | Not available on-chain — location is a hashed game mechanic. `get_player_structures_in_system` returns all cached structures regardless of system. | Known limitation |
| WatchTower webhook | Not implemented — deferred post-hackathon. Would POST shield/fuel alerts to Discord/Slack. | Medium |
| A* memory usage | Path stored as full list per heap entry (quadratic). Acceptable for dev/debug server; optimize before client-side port. | Medium |
| `memory_store.rebuild_summary()` | Claude summarization call not yet tested end-to-end — mock used in unit tests | Medium |
| SSE keep-alive | Resolved — all three `event_stream()` generators yield `: keep-alive\n\n` before the first data chunk. | Resolved |
| `world_api.get_system_by_id()` | Defined but never called — dead code | Low |
| `/debug`, `/health` endpoints | No test coverage | Low |
| Buffer persistence | In-memory only — `current_route`/`pending_alternative` and ring buffer lost on server restart | Low |
| Multi-user | Single shared buffer — designed for one player | Out of scope |
| `LogFileHandler` encoding fixes | Integration-level only; no unit tests | Low |
| `PeriodicBootstrap` / `HeartbeatEmitter` | No unit tests (side-effect threads) | Low |
| `test_context_builder.py` | Does not yet cover the `current_route` / ROUTE PLANNED line | Low |
| Deal mechanic on-chain enforcement | PATRON tier enforced server-side (`DealStore`); no on-chain contract yet. Post-hackathon: deploy `pay_for_access_time` / `pay_for_access_tokens` Move functions. | Post-hackathon |
| LUX token payment | LUX CoinType not yet located in EVE Frontier contracts — `sui` payment method uses SUI coin only. | Medium |
| LocationRevealedEvent coverage | 9 events exist on testnet (all from game server). Run `POST /admin/rebuild-location-index` after deploy to seed the index. | Medium |
| `structure_chat` NONE tier | NONE is now routed to `lobby_client` (same as VETTED). Lobby persona should explicitly mention the deal mechanic. | Medium |

---

## Lore Reference (use verbatim in responses and prompts)

- **Systems:** alphanumeric (UTR-SN4, I.59R.8J2)
- **Enemies:** "Faulty" drones — Scout, Analyzer, Repair (corrupted pre-Collapse automation)
- **Weapons:** Coilgun, Autocannon, Mass Driver, Railgun
- **Hit qualities:** Penetrates, Smashes, Hits, Grazes, Glances Off
- **Materials:** Carbonaceous Ore, Hermetite, Aestasium, Feldspar Crystals, Iridosmine Nodules
- **Structures:** Keep, Fabricator, Citadel, Stellar Constructions
- **Currency:** LUX
- **Keeper:** NPC AI entity — sends `Channel changed to Local` messages in chat (triggers system_change)
