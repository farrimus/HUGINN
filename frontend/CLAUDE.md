# frontend/ -- React TypeScript App

React 19 + TypeScript dApp served as static files by the FastAPI backend. Runs inside the EVE Frontier in-game Chromium browser (787x838px fixed viewport).

Entry point: `src/main.tsx` -- EveFrontierProvider + QueryClientProvider setup.

## Build and Deploy

```bash
cd frontend
npm install            # first time only
npm run dev            # dev server at http://localhost:5173 (hot-reload)
npm run build          # compile to dist/
cp -r dist/* ../static/companion/   # deploy to FastAPI static mount
```

Accessible at `http://<server>:8745/static/companion/index.html`.

Vite base path is `/static/companion/` (set in `vite.config.ts`). Assets will 404 if this is wrong.

## Key Technologies

- React 19 + TypeScript 5.9
- @evefrontier/dapp-kit v0.1.7 -- wallet connection, assembly data, game types
- @tanstack/react-query -- data fetching and caching
- Vite -- build tool with React plugin

## dapp-kit Boundary

All game data access on the frontend goes through dapp-kit hooks. Do not fetch from World API or Sui RPC directly. See root `CLAUDE.md` Data Layer Boundary for the full table.

## File Layout

| Directory | What's there |
|-----------|-------------|
| src/components/ | 22 React components (panels, forms, UIs) |
| src/hooks/ | 6 custom hooks (streaming, session, alerts) |
| src/context/ | EntityContext -- React Query enrichment layer |
| src/styles/ | 7 CSS files (terminal theme, panels, gates, turrets) |
| src/types/ | TypeScript type definitions (eve.ts, terminal.ts) |
| src/features/ | Feature flags, tier capabilities |
| src/utils/ | Formatters, assembly utils, baseline builder |
| src/data/ | Static data (ship profiles, fuel types) |
| patches/ | dapp-kit multi-tenant patch (patch-package) |

See `frontend/src/CLAUDE.md` for component and hook details.

## Deep Reference

- Component rendering pipeline: `docs/FRONTEND_UI.md`
- dapp-kit hook API: `docs/DAPP_KIT_API.md`
- dapp-kit patch details: `docs/TECH_STACK_AND_DEPENDENCIES.md`
