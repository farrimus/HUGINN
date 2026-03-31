# Setup and Deployment

## Requirements

- Python 3.12+
- Node.js 20+
- Anthropic API key
- EVE Frontier World API access

---

## Backend

### 1. Install dependencies

```bash
pip install -r requirements.txt
```

### 2. Configure environment

```bash
cp .env.example .env
```

Edit `.env` and fill in at minimum:
- `ANTHROPIC_API_KEY` — from console.anthropic.com
- `WORLD_API_URL` — EVE Frontier World API base URL

### 3. Build galaxy data (first time only)

These scripts build the local SQLite database from CCP's World API. Takes a few minutes.

```bash
python build_universe.py      # Solar systems, regions, celestials
python build_gate_graph.py    # Gate topology for pathfinding
python build_types.py         # Item type metadata
```

The output (`data/eve_universe.db`, `data/gate_graph.json`) is gitignored and must be built locally.

**Note on `build_universe.py`:** This script requires two input files sourced from CCP's
eve-frontier-tools data export — `data/starmapcache.json` and `data/type_names_all.json` —
which are not included in this repository. Place them in `data/` before running.
`build_gate_graph.py` and `build_types.py` have no external dependencies and fetch live
from the World API.

### 4. Start the server

```bash
python main.py
# Runs on http://localhost:8745
```

---

## Frontend

### 1. Install dependencies

```bash
cd frontend
npm install
```

### 2. Build

```bash
npm run build
```

This compiles TypeScript → JavaScript and outputs to `frontend/dist/`.

### 3. Deploy to static files

```bash
cp -r frontend/dist/* static/companion/
```

FastAPI serves the files at `/static/companion/`. The app is accessible at:
```
http://localhost:8745/static/companion/index.html
```

In production, replace `localhost` with your server IP.

---

## Development Workflow

### Frontend hot-reload (dev server)

```bash
cd frontend
npm run dev
# Runs on http://localhost:5173 with hot-reload
```

The dev server is accessible remotely at `http://<server-ip>:5173`.

### Frontend build → deploy

```bash
cd frontend && npm run build && cp -r dist/* ../static/companion/
```

Always rebuild from `frontend/src/` — never edit `static/companion/` directly.

---

## File Locations

| What | Where |
|------|-------|
| Backend source | `src/` |
| Frontend source | `frontend/src/` |
| Build output | `frontend/dist/` (generated) |
| Deployed static files | `static/companion/` (generated) |
| Galaxy database | `data/eve_universe.db` (generated) |
| Gate graph | `data/gate_graph.json` (generated) |
| AI prompts | `prompts/` |

---

## Vite Base Path

The frontend must know its deployment path. This is set in `frontend/vite.config.ts`:

```typescript
base: '/static/companion/',
```

If you deploy to a different path, update this value and rebuild.

---

## Troubleshooting

| Problem | Fix |
|---------|-----|
| Assets return 404 after deploy | Verify `base: '/static/companion/'` in vite.config.ts, rebuild, redeploy |
| Blank page on load | Check browser console (F12) → Console and Network tabs |
| Wallet won't connect | Only works in EVE Frontier in-game browser with EVE Frontier Client Wallet |
| Port 5173 in use | `lsof -i :5173` then `kill -9 <PID>` |
| TypeScript errors on build | `npm run build` shows full error list — fix `src/` files |
| CSS not updating | Hard refresh (Ctrl+Shift+R) |
| Backend not running | `lsof -i :8745` to check; `python main.py` to start |
