# EVE Frontier Companion — Frontend

React 19 + TypeScript app served as static files from the FastAPI backend. Runs inside the EVE Frontier in-game browser.

See the [root README](../README.md) for full project context.

---

## Quick Start

```bash
npm install
npm run dev       # Dev server at http://localhost:5173
```

## Build and Deploy

```bash
npm run build                        # Compiles to dist/
cp -r dist/* ../static/companion/    # Deploy to FastAPI static mount
```

The app is then accessible at `http://<server>:8745/static/companion/index.html`.

## Key Technologies

- **React 19** + TypeScript
- **@evefrontier/dapp-kit** — wallet connection and assembly data
- **@tanstack/react-query** — data fetching and caching
- **Vite** — build tool (base path: `/static/companion/`)

## Architecture

See [`docs/ARCHITECTURE.md`](../docs/ARCHITECTURE.md) for the full system overview including frontend component structure, wallet connection flow, and build pipeline.
