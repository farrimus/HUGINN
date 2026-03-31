# Quick Start for Next Developer

**Status:** React companion app is built and deployed. It's working.

**Access:** `http://135.181.95.84:8745/static/companion/index.html` (in-game browser)

---

## What Is This?

An AI companion chat interface for EVE Frontier players. Built with React, deployed as static files, uses `window.ethereum` for wallet connection.

**Key tech:** React 18 + Vite + EIP-6963 wallet standard + FastAPI static files

---

## How It Works (30 seconds)

1. **React App** (`/opt/eve-frontier/frontend/`) — source code written in TypeScript
2. **Vite Build** — compiles TypeScript to JavaScript, bundles everything
3. **Static Files** (`/opt/eve-frontier/static/companion/`) — FastAPI serves the compiled files
4. **Browser Loads** — user opens URL in in-game browser, React app runs, connects wallet, chats with AI

**No Node.js server needed.** Pure static files + FastAPI = done.

---

## Read These (In Order)

1. **SYSTEM_OVERVIEW.md** — Understand the architecture (5 min read)
2. **FRONTEND_ARCHITECTURE.md** — Deep dive into React, Vite, wallet connection (15 min read)
3. **FRONTEND_DEPLOYMENT.md** — How to build and deploy (10 min read)

Then you know everything.

---

## Modify the App

```bash
cd /opt/eve-frontier/frontend
npm run dev                         # Start local dev server
# Edit src/App.tsx, src/App.css, etc.
# Changes reload automatically
```

Test locally, then:

```bash
npm run build                       # Compile to dist/
cp -r dist/* ../static/companion/   # Deploy to FastAPI static
```

Then visit: `http://135.181.95.84:8745/static/companion/index.html`

---

## File Locations

- **Source code:** `/opt/eve-frontier/frontend/src/`
  - `App.tsx` — Main component (wallet, structures, chat)
  - `App.css` — Styling
  - `main.tsx` — Entry point

- **Build config:** `/opt/eve-frontier/frontend/`
  - `vite.config.ts` — Build settings (critical: `base: '/static/companion/'`)
  - `tsconfig.json` — TypeScript settings
  - `package.json` — Dependencies

- **Deployed files:** `/opt/eve-frontier/static/companion/`
  - `index.html` — Entry point (loaded by browser)
  - `assets/` — Bundled JS and CSS
  - **Don't edit these manually.** Always rebuild from source.

- **Backend APIs:** `/opt/eve-frontier/` (FastAPI)
  - `GET /player/{wallet}/characters` — Character data
  - `GET /structures` — Structure list
  - `POST /structure-chat` — Chat endpoint (streams SSE)

---

## Development Workflow

```
Edit src/App.tsx
    ↓
npm run dev (test locally)
    ↓
npm run build (compile)
    ↓
cp -r dist/* ../static/companion/ (deploy)
    ↓
Test in browser at http://135.181.95.84:8745/static/companion/index.html
```

---

## Common Tasks

### Add a feature
1. Edit `src/App.tsx`
2. Test with `npm run dev`
3. Build and deploy

### Fix a bug
1. Find the code (search `src/`)
2. Fix it
3. Test with `npm run dev`
4. Build and deploy

### Change styling
1. Edit `src/App.css`
2. Test with `npm run dev`
3. Build and deploy

### Add a component
Create new file in `src/`, import in `App.tsx`, render it.

---

## Troubleshooting

| Problem | Solution |
|---------|----------|
| **Port 5173 in use** | `lsof -i :5173` then `kill -9 <PID>` or use different port |
| **Assets return 404** | Verify `base: '/static/companion/'` in vite.config.ts, rebuild, redeploy |
| **Blank page on load** | Check browser console (F12) for errors, check Network tab for 404s |
| **Wallet won't connect** | MetaMask/Eve Vault installed? Check if `window.ethereum` exists |
| **CSS not updating** | Hard refresh browser (Ctrl+Shift+R) |
| **TypeScript errors** | Run `npm run build` to see errors, fix `src/` files |

---

## Key Facts to Remember

- **Static files only.** No Node.js server. Copy to `/static/companion/` and you're done.
- **Vite is the compiler.** It translates TypeScript to JavaScript.
- **EIP-6963 is the wallet standard.** No custom auth code, use `window.ethereum`.
- **API base URL is dynamic.** `window.location.origin` makes it work from any network.
- **Don't edit `/static/companion/` directly.** Always rebuild from `src/`.
- **Vite needs the base path.** If you deploy to a different location, update `vite.config.ts`.

---

## If Something Breaks

1. Check browser console (F12) for JavaScript errors
2. Check Network tab (F12) for failed requests
3. Check backend is running: `lsof -i :8745`
4. Check files are deployed: `ls /opt/eve-frontier/static/companion/`
5. Hard refresh browser: Ctrl+Shift+R
6. Rebuild and redeploy: `npm run build && cp -r dist/* ../static/companion/`

---

## Next Steps

- **To test locally:** `npm run dev` then open `http://localhost:5173`
- **To deploy:** `npm run build && cp -r dist/* ../static/companion/`
- **To debug:** Open browser DevTools (F12), check Console and Network tabs
- **To understand more:** Read SYSTEM_OVERVIEW.md, FRONTEND_ARCHITECTURE.md, FRONTEND_DEPLOYMENT.md

---

## Questions Answered

**Q: Why Vite?**
A: Fast builds, simple config, supports React, includes dev server.

**Q: Why not the DApp Kit?**
A: DApp Kit is for full dApps with transactions. This is read-only chat. Plain EIP-6963 is simpler.

**Q: Why not a Node.js server?**
A: No need. Vite compiles to static files. FastAPI serves them. Simpler, faster, fewer moving parts.

**Q: How do I add new API endpoints?**
A: Backend is FastAPI in `/opt/eve-frontier/src/`. Frontend calls them with `fetch()`.

**Q: What if I want to deploy to a different path?**
A: Update `base` in `vite.config.ts`, rebuild, redeploy.

**Q: Can I run the app without rebuilding?**
A: Yes, with `npm run dev`. But for production, you must rebuild.

---

**Everything you need to know is in SYSTEM_OVERVIEW.md. Start there.**
