# Frontend Deployment Guide

## Quick Start

### Local Development
```bash
cd /opt/eve-frontier/frontend
npm install              # First time only
npm run dev              # Start dev server at http://localhost:5173
```

Open `http://localhost:5173` in your browser. Changes to source files reload automatically.

From another machine, access at `http://135.181.95.84:5173`.

### Production Build & Deploy

```bash
cd /opt/eve-frontier/frontend
npm run build                          # Compile to dist/
cp -r dist/* ../static/companion/      # Deploy static files
```

Then access at: `http://135.181.95.84:8745/static/companion/index.html`

---

## What Happens During Build

Vite transforms your source code:

**Input:** TypeScript + React JSX
```typescript
// src/App.tsx
import { useState } from "react";
export default function App() {
  const [count, setCount] = useState(0);
  return <button onClick={() => setCount(count + 1)}>{count}</button>;
}
```

**Output:** Plain JavaScript that browsers understand
```javascript
// dist/assets/index-*.js
const App=()=>{const[e,t]=useState(0);return React.createElement("button",{onClick:()=>t(e+1)},e)};
```

**Also outputs:**
- `dist/index.html` — HTML file that loads the JavaScript
- `dist/assets/index-*.css` — All CSS bundled and minified
- `dist/favicon.svg` — Icon

---

## Build Configuration

File: `/opt/eve-frontier/frontend/vite.config.ts`

```typescript
export default defineConfig({
  plugins: [react()],           // Enable React JSX support
  base: '/static/companion/',   // Where the app will be served from
  server: {
    host: '0.0.0.0',           // Listen on all interfaces (allows remote access)
    port: 5173,                 // Dev server port
  },
});
```

**Key setting:** `base: '/static/companion/'`

This tells Vite to generate asset paths like `/static/companion/assets/index-*.js` instead of `/assets/index-*.js`. Without this, asset loading fails.

---

## Directory Layout

### Source Code
```
/opt/eve-frontier/frontend/           ← npm install, npm run build here
├── src/                              ← Edit these files
│   ├── App.tsx                       ← Main component (wallet, chat, structures)
│   ├── App.css                       ← Styling (gold/brown terminal theme)
│   ├── main.tsx                      ← Entry point
│   └── index.css                     ← Base styles
├── vite.config.ts                    ← Build config
├── tsconfig.json                     ← TypeScript settings
├── package.json                      ← Dependencies
└── dist/                             ← Generated after npm run build (do not edit)
```

### Built/Deployed Files
```
/opt/eve-frontier/static/companion/                ← FastAPI serves from here
├── index.html                                     ← Entry point (loaded by browser)
├── assets/
│   ├── index-ebzpvV3D.css                        ← Bundled CSS
│   └── index-BT-abPj9.js                         ← Bundled JavaScript (React + dependencies)
├── favicon.svg                                    ← Icon
└── icons.svg                                      ← Icons
```

---

## Development Workflow

### 1. Edit Source Code
```bash
# Modify /opt/eve-frontier/frontend/src/App.tsx, App.css, etc.
# Changes are reflected instantly in the dev server
```

### 2. Run Dev Server
```bash
npm run dev
# Listens on http://0.0.0.0:5173
# Access from remote: http://135.181.95.84:5173
```

### 3. Test in Browser
- Open `http://localhost:5173` (same machine as dev server)
- Or `http://135.181.95.84:5173` (from another machine)
- Changes auto-reload

### 4. Build for Production
```bash
npm run build
# Outputs to dist/
```

### 5. Deploy to Static Folder
```bash
cp -r dist/* ../static/companion/
```

### 6. Verify in Game
- Open in-game browser
- Navigate to `http://135.181.95.84:8745/static/companion/index.html`
- Should load and function normally

---

## Troubleshooting

### "Port 5173 already in use"
```bash
# Kill the process using port 5173
lsof -i :5173
kill -9 <PID>

# Or use a different port
npm run dev -- --port 5174
```

### Assets not loading (404 errors)
**Cause:** `base` in vite.config.ts doesn't match deployment path.

**Fix:** Verify `base: '/static/companion/'` matches actual deployment location.

```bash
# Check what's actually in static folder
ls -la /opt/eve-frontier/static/companion/assets/
```

### CSS/JS not applying after deploy
**Cause:** Browser cached old version.

**Fix:** Hard refresh in browser (Ctrl+Shift+R or Cmd+Shift+R).

### TypeScript compilation errors
```bash
# Check for type errors
npm run build
# Look at error messages and fix src/ files

# Or type-check without building
npx tsc --noEmit
```

### App loads but shows blank screen
1. Open browser DevTools (F12)
2. Check Console tab for JavaScript errors
3. Check Network tab — are JS/CSS files loading?
4. If files return 404, check deployment step (did you copy to static/companion/?)

---

## Dependencies

File: `/opt/eve-frontier/frontend/package.json`

```json
{
  "dependencies": {
    "react": "^18.3.1",
    "react-dom": "^18.3.1"
  },
  "devDependencies": {
    "@vitejs/plugin-react": "^4.2.1",
    "typescript": "^5.3.3",
    "vite": "^5.0.8"
  }
}
```

**Install/Update:**
```bash
npm install              # Install all dependencies
npm update               # Update to latest compatible versions
npm install react@latest # Update specific package
```

---

## Performance Notes

- **Bundle size:** ~195 KB (JS) + 5 KB (CSS) uncompressed → ~62 KB + 1.6 KB gzipped
- **Load time:** <1 second on typical network
- **No build server required:** Pure static files, served by FastAPI
- **Zero server-side rendering:** All computation in the browser

---

## Common Tasks

### Add a new component
```typescript
// src/MyComponent.tsx
export default function MyComponent() {
  return <div>Hello</div>;
}

// src/App.tsx
import MyComponent from "./MyComponent";

export default function App() {
  return (
    <div>
      <MyComponent />
    </div>
  );
}
```

### Add CSS
```css
/* src/App.css */
.my-class {
  color: #c8a560;
  background: #0a0804;
}
```

### API call
```typescript
const res = await fetch(`${API_BASE_URL}/endpoint`);
const data = await res.json();
```

---

## Git Workflow

```bash
# Create a branch for your changes
git checkout -b feature/my-feature

# Make edits to src/ files
# Test with npm run dev

# Build and test production
npm run build
cp -r dist/* ../static/companion/

# Commit changes (source files only, not dist/)
git add src/ vite.config.ts package.json
git commit -m "feat: add new component"

# Push and create PR
git push origin feature/my-feature
```

**Note:** Do not commit the `dist/` or `node_modules/` folders. They're generated automatically.

---

## Next Steps for New Agents

1. **Read** `FRONTEND_ARCHITECTURE.md` to understand the system
2. **Edit** source files in `/opt/eve-frontier/frontend/src/`
3. **Test locally** with `npm run dev`
4. **Build** with `npm run build`
5. **Deploy** by copying `dist/` to `/static/companion/`
6. **Verify** in-game at `http://135.181.95.84:8745/static/companion/index.html`

Do not manually edit files in `/static/companion/` — always rebuild from source.
