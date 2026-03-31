# System Overview — Eve Frontier Companion

**TL;DR:** React chat app → Vite build → Static files → FastAPI serves → In-game browser loads it.

---

## The Big Picture

```
User's Computer (in-game)
        ↓ (browser)
    http://135.181.95.84:8745/static/companion/index.html
        ↓
    FastAPI Server (VPS)
        ├── /static/companion/ ← Serves static HTML/CSS/JS files
        └── /player, /structures, /structure-chat ← API endpoints
```

When the user opens the URL in their in-game browser:
1. Browser requests `index.html` from FastAPI
2. FastAPI returns the HTML file
3. HTML loads JavaScript from `/static/companion/assets/`
4. React app initializes in the browser
5. React app uses `window.ethereum` to connect wallet
6. React app calls API endpoints to load data and chat

---

## Three Main Pieces

### 1. React App (Source Code)
**Location:** `/opt/eve-frontier/frontend/`

**What it is:** A JavaScript application written in React and TypeScript.

**What it does:**
- Connects to user's wallet (MetaMask/Eve Vault)
- Displays character info and available structures
- Sends chat messages to the backend
- Streams AI responses to the user

**How to modify it:** Edit `.ts`, `.tsx`, or `.css` files in `src/`. Then rebuild.

**Key files:**
- `src/App.tsx` — Main component
- `src/App.css` — Styling

### 2. Build Tool (Vite)
**Location:** Configuration in `/opt/eve-frontier/frontend/vite.config.ts`

**What it is:** A build system that compiles source code into production-ready files.

**What it does:** When you run `npm run build`, Vite:
1. Compiles TypeScript to JavaScript
2. Bundles React and dependencies
3. Minifies CSS and JavaScript
4. Outputs to `dist/` directory

**Output:** Plain HTML, CSS, and JavaScript files that any browser can understand.

**Why needed:** Browsers can't run TypeScript or JSX directly. Vite translates them.

### 3. Static File Deployment
**Location:** `/opt/eve-frontier/static/companion/`

**What it is:** The compiled React app, served by FastAPI.

**What it contains:**
- `index.html` — Entry point
- `assets/` — Minified JavaScript and CSS
- `favicon.svg`, `icons.svg` — Images

**How to deploy:** Copy files from `dist/` after building.

```bash
npm run build
cp -r /opt/eve-frontier/frontend/dist/* /opt/eve-frontier/static/companion/
```

---

## The Workflow

### Development (Testing Locally)

```bash
cd /opt/eve-frontier/frontend
npm install              # First time only
npm run dev              # Start dev server
```

- Dev server runs on `http://localhost:5173`
- Changes to source files reload instantly
- Can test from any machine at `http://135.181.95.84:5173`

### Production (Deploy to Game)

```bash
npm run build            # Compile to dist/
cp -r dist/* ../static/companion/  # Deploy
```

- Vite generates optimized, minified files
- Files copied to FastAPI's static mount
- Accessible at `http://135.181.95.84:8745/static/companion/index.html`

---

## Why Each Technology?

| Tech | Why | Alternative | Why Not |
|------|-----|-------------|---------|
| **React** | Manage UI state, handle interactions | Vue, Angular, Svelte | Overkill for chat, need lightweight |
| **TypeScript** | Catch errors before runtime | JavaScript | Less safe, harder to refactor |
| **Vite** | Fast builds, dev server | Webpack, Parcel | Slower, more complex config |
| **EIP-6963** | Standard wallet discovery | Custom auth, DApp Kit | Simpler, works with any wallet |
| **CSS** | Style the UI | SASS, Tailwind | Keep it simple, no framework |
| **FastAPI Static** | Serve files | Node.js, nginx | Already have FastAPI running |

---

## Key Concepts

### Static Files
Files that don't change: HTML, CSS, JavaScript, images, etc. Browser downloads them once and renders them locally. No computation on the server.

**Advantage:** Fast, reliable, simple to deploy.

**Disadvantage:** All logic runs in the browser (can't hide API keys, etc.).

### Vite Base Path
When the app is deployed at `/static/companion/`, Vite must know this to generate correct asset paths.

```typescript
// vite.config.ts
base: '/static/companion/',
```

This makes the built `index.html` use:
```html
<script src="/static/companion/assets/index-*.js"></script>
<link href="/static/companion/assets/index-*.css" rel="stylesheet">
```

If you forget this and deploy to a different path, assets won't load (404 errors).

### EIP-6963 Wallet Connection
Standard protocol for web pages to discover and connect to wallets. Browser provides `window.ethereum` object that the app can call:

```typescript
const accounts = await window.ethereum.request({
  method: "eth_requestAccounts",
});
```

User's wallet (MetaMask, Eve Vault) shows a connection prompt. User approves. App gets wallet address.

### Server-Sent Events (SSE)
Backend streams AI response in chunks:

```
data: {"text": "I "}
data: {"text": "am "}
data: {"text": "ready"}
data: [DONE]
```

Browser reads stream and logs each chunk, making the response appear incrementally rather than all at once.

---

## File Flow

### From Source to Browser

```
/opt/eve-frontier/frontend/src/App.tsx
        ↓ (npm run build)
    Vite compiles, bundles, minifies
        ↓
/opt/eve-frontier/frontend/dist/index.html
/opt/eve-frontier/frontend/dist/assets/index-*.js
/opt/eve-frontier/frontend/dist/assets/index-*.css
        ↓ (cp -r dist/* ../static/companion/)
/opt/eve-frontier/static/companion/index.html
/opt/eve-frontier/static/companion/assets/index-*.js
/opt/eve-frontier/static/companion/assets/index-*.css
        ↓ (FastAPI StaticFiles serves)
Browser loads index.html
        ↓
Browser loads assets from /static/companion/assets/
        ↓
React app initializes
```

---

## Common Questions

### "Why do I need to run `npm run build`?"
Browsers can't understand TypeScript or JSX directly. `npm run build` translates them to plain JavaScript that all browsers understand, and optimizes the code for production.

### "What's Vite?"
A tool that compiles your source code into files browsers can load. Similar to Webpack or Parcel, but faster and simpler to configure.

### "Why not use the DApp Kit?"
DApp Kit is for full dApps that need to handle transactions. This is read-only companion chat. Vanilla EIP-6963 is simpler and lighter.

### "Can I edit files in `/static/companion/` directly?"
No. Always edit source files in `src/` and rebuild. The `/static/companion/` folder is generated.

### "How do I add a new feature?"
1. Edit `src/App.tsx` or create a new component
2. Test with `npm run dev`
3. Build with `npm run build`
4. Deploy with `cp -r dist/* ../static/companion/`

### "How do I deploy to a different server?"
Change the hardcoded IP in the client-side URL (user enters in their browser), and ensure the backend API endpoints are accessible from the client's network.

---

## API Integration

The React app calls these backend endpoints:

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/player/{wallet}/characters` | GET | Load player character data |
| `/structures` | GET | List available structures |
| `/structure-chat` | POST | Send message, receive SSE response |

The base URL is `window.location.origin`, so the app automatically targets the server it was served from:

- Served from `http://135.181.95.84:8745/static/companion/`
- API calls go to `http://135.181.95.84:8745/player/...`
- Works the same whether accessed from in-game, localhost, or any other network

---

## Performance & Optimization

- **Bundle size:** ~195 KB JS + 5 KB CSS (gzip: ~62 KB + 1.6 KB)
- **Load time:** <1 second over typical network
- **Streaming responses:** AI chat appears incrementally (doesn't wait for full response)
- **No server-side rendering:** All computation in the browser
- **No build server needed:** Pure static files

---

## For New Developers

1. **Understand the system:** Read this file
2. **Understand the frontend:** Read `FRONTEND_ARCHITECTURE.md`
3. **Understand deployment:** Read `FRONTEND_DEPLOYMENT.md`
4. **Start developing:**
   - Edit `/opt/eve-frontier/frontend/src/`
   - Test with `npm run dev`
   - Build with `npm run build`
   - Deploy to `/static/companion/`

---

## Debugging Checklist

- **App doesn't load?** Check browser console (F12) for JavaScript errors
- **Page loads but blank?** Check Network tab (F12) — are JS/CSS files 200 OK?
- **Assets return 404?** Verify deployment step (`cp -r dist/* ../static/companion/`)
- **Wallet won't connect?** Check if `window.ethereum` exists (MetaMask/Eve Vault installed?)
- **API calls fail?** Check if backend is running (`lsof -i :8745`)
- **CSS not applying?** Hard refresh browser (Ctrl+Shift+R)

---

## Next Steps

To modify or extend the companion:
1. Clone/pull the latest code
2. Make changes to `/opt/eve-frontier/frontend/src/`
3. Test locally with `npm run dev`
4. Build with `npm run build`
5. Deploy with `cp -r dist/* ../static/companion/`
6. Open URL in browser: `http://135.181.95.84:8745/static/companion/index.html`

Everything else is automatically handled by Vite and FastAPI.
