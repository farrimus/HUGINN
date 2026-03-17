# Setup Guide — EVE Frontier Ship AI Companion

This guide covers server setup, log-agent deployment, and token authentication configuration.

---

## Server Setup

### Prerequisites

- Python 3.10+
- 4 GB RAM minimum
- Linux VPS or local machine
- Git

### Installation

1. Clone the repository:
   ```bash
   git clone <repo-url>
   cd eve-frontier
   ```

2. Create virtual environment:
   ```bash
   python3 -m venv .venv
   source .venv/bin/activate
   ```

3. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

4. Configure environment:
   ```bash
   cp .env.example .env
   # Edit .env with your API keys and settings
   ```

5. Download/build universe data:
   ```bash
   # If you have ResFiles available
   python build_universe.py

   # Fetch type names from World API
   python build_types.py
   ```

6. Run server:
   ```bash
   python main.py
   # Server listens on http://0.0.0.0:8745
   ```

### Verify Setup

- Health check: `curl http://localhost:8745/health`
- Debug endpoint: `curl http://localhost:8745/debug`

---

## Token Authentication Setup

The ship AI companion uses JWT-based token authentication to secure log-agent communication.

### Server Setup

1. Token keys are automatically generated on first server startup at:
   ```
   /root/.openclaw/token_keys/
   ```

2. Keys are persistent and backed up via Syncthing.

3. To rotate keys (invalidate all tokens):
   ```bash
   rm /root/.openclaw/token_keys/*
   systemctl restart openclaw-gateway
   ```

### Log-Agent Setup

1. Set environment variables:
   ```bash
   export AGENT_ID="log-agent-001"
   export SERVER_URL="http://<server-ip>:8745"
   ```

2. Run log-agent. It will:
   - Request a token from `/auth/token`
   - Store token securely (Windows DPAPI encryption)
   - Include token in all requests

3. Tokens expire after 24 hours and must be refreshed (see Phase 2).

### Troubleshooting

- **"Invalid token"**: Token expired. Restart log-agent.
- **"Missing Authorization header"**: Client not sending token. Check auth_flow initialization.

---

## Database Setup

### EVE Universe Database

The server uses SQLite for EVE Frontier universe data:

```bash
# Database location
data/eve_universe.db

# Contains: Regions, Constellations, SolarSystems, Planets, Moons, Stations, Lagrange points
```

### Memory Store

Per-structure memory and pilot profiles:

```bash
# Location
data/memory/{structure_id}/
├── events.jsonl       # Immutable event log
├── summary.json       # Current summary
└── pilots/            # Pilot profile snapshots
```

---

## Testing

### Run Server Tests

```bash
pytest tests/ -v
```

### Run Log-Agent Tests

```bash
cd log-agent
pytest tests/ -v
```

---

## Troubleshooting

### Server won't start

- Check Python version: `python --version` (need 3.10+)
- Check port 8745 availability: `lsof -i :8745`
- Check environment: `cat .env`

### Log-agent can't connect

- Check server is running: `curl http://localhost:8745/health`
- Check firewall: `sudo ufw allow 8745`
- Check token generation: Server logs show "token issued"

### Missing universe data

- Run `python build_universe.py` to build from ResFiles
- Run `python build_types.py` to fetch type names
- Check `data/systems.json` exists

---

## Next Steps

See `docs/CODEBASE.md` for architecture overview and component details.
