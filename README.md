# EVE Frontier Companion

An AI-powered in-lore companion for EVE Frontier pilots. It lives inside the game universe — not outside it.

Built for the [EVE Frontier × Sui Hackathon 2026](https://evefrontier.com/en/news/eve-frontier-sui-2026-hackathon).

---

## What It Does

The companion runs inside the EVE Frontier in-game browser. When a pilot connects their wallet, the companion:

- Knows where they are — solar system, security status, local threats
- Reads their structure network — fuel levels, online status, assembly types
- Answers in-universe, in first person, as a shipboard intelligence
- Plans routes, monitors watcher alerts, and tracks courier contracts
- Never breaks the fiction. No "according to the game" language, ever.

The design principle: pilot jumps into an unknown system and types "where am I?" — companion answers in three seconds with facts from the World API, one line that feels like a warning from something that has been here before.

---

## Architecture

```
In-game browser
    └── React app (TypeScript + DApp Kit)
            └── FastAPI backend (Python)
                    ├── Claude API (AI responses, tool calls)
                    ├── EVE Frontier World API (live game state)
                    └── Galaxy DB (24,426 systems, gate topology)
```

**Frontend:** React 19 + Vite, served as static files from FastAPI. Connects to the pilot's wallet via EVE Frontier Client Wallet (Wallet Standard / DApp Kit). No separate Node.js server.

**Backend:** FastAPI on Python 3.12. Handles session management, AI context building, route planning, structure monitoring, and live data from the World API.

**AI:** Claude Sonnet (Anthropic). Receives a structured context block — current location, structure states, recent killmails, active alerts — and responds in character as the companion entity. Uses tool calls to query live data mid-conversation.

**Data:** Solar system geography and gate topology are pre-built from CCP's public World API using the included build scripts (`build_universe.py`, `build_gate_graph.py`).

---

## Features

| Feature | Description |
|---------|-------------|
| Companion chat | Streaming AI responses, in-universe voice, tool-augmented |
| Route planning | Shortest / safest path across the gate network |
| Structure monitor | Fuel status, online state, burn rate for your assemblies |
| Watcher alerts | Configurable alerts for structure state changes |
| Courier board | Post and claim hauling contracts between pilots |
| Tribe board | Live presence roster, session tracking |
| Session management | Per-wallet persistent context and memory |

---

## Running It Yourself

### Requirements

- Python 3.12+
- Node.js 20+
- Anthropic API key
- EVE Frontier World API access

### Backend

```bash
# Install Python dependencies
pip install -r requirements.txt

# Configure environment
cp .env.example .env
# Edit .env — fill in ANTHROPIC_API_KEY and WORLD_API_URL

# Build galaxy data (first time only)
python build_universe.py
python build_gate_graph.py

# Start the server
python main.py
# Runs on http://localhost:8745
```

### Frontend

```bash
cd frontend
npm install
npm run build
cp -r dist/* ../static/companion/
```

Open `http://localhost:8745/static/companion/index.html` in a browser (or the in-game browser).

---

## Project Structure

```
/
├── main.py                  # FastAPI app entry point
├── src/
│   ├── endpoints/           # API routers (companion, session, navigation, etc.)
│   ├── tools/               # AI tool implementations
│   ├── claude_client.py     # AI prompt construction and streaming
│   ├── context_builder.py   # Game state → AI context
│   ├── world_api.py         # EVE Frontier World API client
│   ├── galaxy_db.py         # Solar system and gate graph
│   └── route_engine.py      # Pathfinding
├── frontend/
│   └── src/                 # React + TypeScript source
├── build_universe.py        # Builds galaxy DB from World API
├── build_gate_graph.py      # Builds gate topology
└── docs/                    # Architecture and API reference
```

---

## Data Attribution

Solar system data, gate topology, item types, and other universe metadata are sourced from CCP Games' EVE Frontier World API and public game data. All EVE Frontier intellectual property belongs to CCP Games.

This project is an independent third-party tool built under CCP's developer program. It is not affiliated with or endorsed by CCP Games.

---

## License

MIT — see [LICENSE](LICENSE).

The license applies to the source code in this repository. EVE Frontier game data and assets remain the property of CCP Games.
