# Agent Guide: Builder Scaffold & DApp Kit

**Purpose:** Quick reference for agents extending the EVE Frontier React companion terminal.

---

## The Stack at a Glance

| Layer | Tech | Purpose |
|-------|------|---------|
| **Build Tool** | Vite + React 19 | Frontend bundling, dev server, hot reload |
| **Wallet** | @evefrontier/dapp-kit | EVE Frontier wallet connection (replaces custom auth) |
| **Data Fetching** | @tanstack/react-query | State management for async operations |
| **Styling** | Vanilla CSS | Black terminal with orange text, no frameworks |

---

## File Map (Frontend)

```
frontend/
├── src/
│   ├── main.tsx           ← Provider setup: EveFrontierProvider + QueryClient
│   ├── App.tsx            ← Simple wrapper, renders TerminalUI
│   ├── components/
│   │   ├── TerminalUI.tsx ← Main logic: commands, chat, wallet integration
│   │   └── VisualArea.tsx ← Status display (ASCII header, wallet state)
│   ├── hooks/
│   │   └── useStructureChat.ts ← SSE streaming from /structure-chat endpoint
│   ├── types.ts           ← ChatMessage, Structure, etc.
│   └── styles/
│       └── terminal.css   ← Layout (flex columns), colors (#c8a560 orange)
├── vite.config.ts         ← base: '/static/companion/', port 5173
├── package.json           ← @evefrontier/dapp-kit, @tanstack/react-query, React 19
└── dist/                  ← Built output → copied to /static/companion/
```

---

## Core Concepts

### 1. Provider Setup (main.tsx)
The app is wrapped in two providers:
```typescript
<QueryClientProvider>
  <EveFrontierProvider>
    <App />
  </EveFrontierProvider>
</QueryClientProvider>
```
- **QueryClient** — required by DApp Kit for data caching
- **EveFrontierProvider** — enables `useConnection()` hook + wallet context

### 2. Wallet Connection (DApp Kit)
The `useConnection()` hook handles all wallet logic:
```typescript
const { isConnected, walletAddress, handleConnect, handleDisconnect } = useConnection()
```
- No JWT tokens, no assembly_id signing—DApp Kit does it
- `handleConnect()` opens the EVE Frontier wallet modal
- Returns `walletAddress` once connected

### 3. Chat Streaming (useStructureChat Hook)
Manages SSE streaming from the backend:
```typescript
const { messages, isLoading, sendMessage } = useStructureChat()

// Call this when user types a message
await sendMessage(assemblyId, userMessage, serverToken)

// Hook parses `data: {JSON}` lines from /structure-chat endpoint
// Accumulates AI text incrementally
```

### 4. Terminal Commands (TerminalUI)
Commands are parsed in `handleCommand()`:
- `/connect` — calls `handleConnect()` from DApp Kit
- `/disconnect` — calls `handleDisconnect()`
- `/list` — fetches `/structures` endpoint, shows structure list
- `/select <id>` — picks a structure for chat
- `/help` — lists commands
- Anything else → sent to `/structure-chat` as a chat message

---

## Common Tasks for Agents

### Add a New CLI Command
**File:** `frontend/src/components/TerminalUI.tsx`, `handleCommand()` function

Pattern:
```typescript
} else if (command === '/mycommand') {
  // Your logic here
  addLog('Result text', 'info')
} else {
```

### Add a New Hook
**File:** `frontend/src/hooks/useMyHook.ts`

Template:
```typescript
import { useState, useCallback } from 'react'

export function useMyHook() {
  const [state, setState] = useState(initialValue)

  const doSomething = useCallback(async () => {
    // Your logic
  }, [dependencies])

  return { state, doSomething }
}
```

### Add a New Component
**File:** `frontend/src/components/MyComponent.tsx`

Use TypeScript, export as named export, add JSDoc comments only if non-obvious.

### Customize Terminal Styling
**File:** `frontend/src/styles/terminal.css`

Key selectors:
- `.terminal-ui` — main container
- `.terminal-output` — chat area
- `.terminal-input-area` — input bar
- `.line-info`, `.line-user`, `.line-ai`, `.line-error` — log colors

Colors:
- Background: `#000`
- Text: `#c8a560` (orange)
- User messages: `#4ade80` (green)
- Errors: `#ef4444` (red)

### Update the Visual Area
**File:** `frontend/src/components/VisualArea.tsx`

Modify the `lines` array to change ASCII art / status display.

---

## Backend Integration Points

### /structure-chat Endpoint
**What it does:** Streams AI responses via SSE

**Request:**
```json
{
  "assembly_id": "structure-id",
  "message": "user text",
  "history": [{"role": "user|assistant", "content": "text"}]
}
```

**Response:** Server-Sent Events, each line is `data: {JSON}`
```json
{"content": "text chunk", "done": false}
{"content": "more text", "done": true}
```

**Location:** Backend in `src/endpoints/structures.py`

### /structures Endpoint
**What it does:** Returns list of structures

**Response:**
```json
{
  "structures": [
    {
      "id": "structure-id",
      "structure_name": "Trading Post",
      "system_name": "Jita",
      "owner_address": "0x..."
    }
  ]
}
```

**Location:** Backend in `src/endpoints/structures.py`

---

## Build & Deploy

### Development
```bash
cd frontend
npm install
npm run dev
# React dev server on http://localhost:5173
# Proxies /structure-chat and /structures to backend
```

### Production Build
```bash
cd frontend
npm run build
# Output: dist/
```

### Deploy to Live Server
```bash
cp -r frontend/dist/* /path/to/static/companion/
# OR on prod server:
# $ cp -r dist static/companion
# Then restart FastAPI
```

**Live URL:** http://135.181.95.84:8745/

---

## Key Dependencies

| Package | Version | Why |
|---------|---------|-----|
| react | ^19.2.4 | UI framework |
| @evefrontier/dapp-kit | ^0.1.0 | Wallet + smart objects |
| @tanstack/react-query | ^5.0.0 | Data fetching state |
| vite | ^8.0.1 | Build tool |
| typescript | ~5.9.3 | Type safety |

**No material-ui, chakra, or other UI frameworks—pure CSS for minimal bundle size.**

---

## Debugging Checklist

| Issue | Check |
|-------|-------|
| Wallet won't connect | EVE Frontier Client Wallet installed? EveFrontierProvider in main.tsx? |
| Chat not responding | Backend running on 8745? /structure-chat endpoint exists? SERVER_TOKEN valid? |
| Terminal not loading | /static/companion/index.html exists? Vite build completed? |
| Build errors | `npm install` in frontend/? Node version ≥18? |

---

## Quick Cheat Sheet

**Run dev server:**
```bash
cd frontend && npm run dev
```

**Type-check without building:**
```bash
npm run lint
```

**Force clean rebuild:**
```bash
rm -rf node_modules dist && npm install && npm run build
```

**Check what's deployed:**
```bash
ls -la static/companion/
```

---

**Last updated:** 2026-03-26
**Status:** Live, production-ready
**Contact:** @Markús Þór (project owner)
