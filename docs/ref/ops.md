# Operations Reference

**Last updated:** 2026-03-16
**Contents:** Configuration, running the system, known gaps, lore reference

---

## Configuration

### Server `.env`
```
ANTHROPIC_API_KEY=sk-ant-...
# World API: WORLD_API_BASE_URL overrides WORLD_API_ENV. Default env is "utopia".
WORLD_API_BASE_URL=https://world-api-utopia.live.tech.evefrontier.com
WORLD_API_ENV=utopia
SERVER_TOKEN=<random secret — must match overlay config.h and log-agent .env>
PORT=8745
JWT_SECRET=<random secret for structure JWT signing>
# Structure AI identity
STRUCTURE_ID=keep-7a
STRUCTURE_SYSTEM_NAME=JITA
NOVA_REGISTRY_OBJECT_ID=0x89e9b9b90acc3b7b576c7fe81015e0a6d333d9ae3e69133c8b1786c826f05dc0
NOVA_RPC_URL=https://fullnode.testnet.sui.io
# Background polling
SSU_OBJECT_ID=<Sui object ID of the deployed SSU — leave blank to disable SSU state polling>
TURRET_OBJECT_IDS=<comma-separated Sui object IDs of turrets — leave blank to disable>
# Blockchain gateway (Phase 2 — verify DNS first; see structure-ai.md for DNS check command)
BLOCKCHAIN_GW_URL=https://blockchain-gateway-stillness.live.tech.evefrontier.com
# Player-owned structure IDs for Ship AI context (Phase 3 — comma-separated Sui object IDs)
PLAYER_STRUCTURE_IDS=<comma-separated Sui object IDs of player's own structures>
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
# 91+ passing (2026-03-16 baseline — 4 test files covered in this run)
```

### Diagnostics
```bash
# Full pipeline state
curl -H "X-Server-Token: $SERVER_TOKEN" http://localhost:8745/debug | jq

# Gate graph availability
curl -H "X-Server-Token: $SERVER_TOKEN" http://localhost:8745/data/gate-graph | jq '.built_at, (.adj | length)'

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
| `ssu_poller.poll_ssu_state` | Two-hop RPC confirmed working; `_extract_fuel_pct()` is deprecated (retained for compatibility). `connected_assembly_ids` written each cycle. | Resolved |
| `blockchain_client._parse_inventory` | Field path (`inventory`, `items`, `storageItems`) not confirmed — depends on real gateway response. Must curl-verify before relying on INVENTORY line. | **High** |
| Blockchain gateway DNS | DNS was not resolving from VPS as of 2026-03-11. Re-verify before Phase 2/3 data flows live. | **High** |
| WatchTower webhook | Not implemented — deferred post-hackathon. Would POST shield/fuel alerts to Discord/Slack. | Medium |
| A* memory usage | Path stored as full list per heap entry (quadratic). Acceptable for dev/debug server; optimize before client-side port. | Medium |
| `memory_store.rebuild_summary()` | Claude summarization call not yet tested end-to-end — mock used in unit tests | Medium |
| SSE keep-alive | Server does not send `: keep-alive` comments. Add to `event_stream()` if drops appear. | Low |
| `world_api.get_system_by_id()` | Defined but never called — dead code | Low |
| `/debug`, `/health` endpoints | No test coverage | Low |
| Buffer persistence | In-memory only — `current_route`/`pending_alternative` and ring buffer lost on server restart | Low |
| Multi-user | Single shared buffer — designed for one player | Out of scope |
| `LogFileHandler` encoding fixes | Integration-level only; no unit tests | Low |
| `PeriodicBootstrap` / `HeartbeatEmitter` | No unit tests (side-effect threads) | Low |
| `test_context_builder.py` | Does not yet cover the `current_route` / ROUTE PLANNED line | Low |

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
