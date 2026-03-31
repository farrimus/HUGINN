# DApp Kit Integration - Technical Reference

## What Was Built

Pure React CLI terminal interface (776x828 viewport) with EVE Frontier DApp Kit wallet integration and AI chat. Black background, orange monospace text. No sidebars, no UI chrome—just three sections: visual status area (33%), chat history (scrollable), input field (bottom).

**Live:** http://135.181.95.84:8745/

---

## Architecture

### Frontend Stack
- **React 19** with TypeScript + Vite
- **@evefrontier/dapp-kit** (0.1.7) — wallet connection, smart objects, blockchain queries
- **@tanstack/react-query** (5.95.2) — data fetching state management
- **Vanilla CSS** — no frameworks, pure monospace terminal styling

### Backend
- **FastAPI** (Python 3.12) — already existed, unchanged
- `/structure-chat` endpoint — SSE streaming AI responses
- `/structures` endpoint — list available structures
- Serves React app at `/` and legacy CLI at `/legacy-cli`

---

## Component Tree

```
App.tsx (simple wrapper)
  └── TerminalUI (main component)
      ├── VisualArea (status display)
      │   └── Shows: wallet status, structure info, help text
      ├── chat-history (div, scrollable)
      │   └── Renders messages from useStructureChat hook
      └── input-field (text input)
          └── Handles: /connect, /list, /select <id>, chat messages
```

---

## Key Components & Files

### TerminalUI.tsx (Main Component)
**Location:** `frontend/src/components/TerminalUI.tsx`

**Responsibilities:**
- Uses `useConnection()` hook from DApp Kit → manages wallet state (isConnected, address, handleConnect)
- Uses `useStructureChat()` hook → manages chat messages, SSE streaming
- Fetches structures list from `/structures` endpoint on wallet connect
- Parses and executes CLI commands:
  - `/connect` — calls `handleConnect()` from DApp Kit
  - `/list` — displays available structures
  - `/select <id>` — selects structure for chatting
  - Any other text → sent as message to `/structure-chat` endpoint
- Auto-scrolls chat to bottom on new messages
- Passes SERVER_TOKEN via Bearer header for auth

### VisualArea.tsx (Status Display)
**Location:** `frontend/src/components/VisualArea.tsx`

**Responsibilities:**
- Displays ASCII header: "EVE FRONTIER STRUCTURE AI COMPANION v1.0 [ONLINE]"
- Shows wallet status: Disconnected/Connecting/Connected + truncated address
- Shows selected structure: name, system, owner address
- Renders as `<pre>` for monospace formatting

### useStructureChat.ts (SSE Streaming Hook)
**Location:** `frontend/src/hooks/useStructureChat.ts`

**Responsibilities:**
- Manages `messages` state (ChatMessage[])
- Sends message to `/structure-chat` POST with Bearer token
- Reads SSE response stream (Content-Type: text/event-stream)
- Parses `data: {JSON}` lines, accumulates AI text incrementally
- Returns `{ messages, isLoading, error, sendMessage }`

### Types.ts (Type Definitions)
**Location:** `frontend/src/types.ts`

**Interfaces:**
- `Structure` — id, system_name, owner_address, structure_name
- `ChatMessage` — id, role ('user'|'ai'|'system'), text, timestamp
- `ConnectionState` — isConnected, address, wallet
- `TerminalState` — wallet, selectedStructure, messages, isLoading, error

### Styling
**Location:** `frontend/src/styles/terminal.css`

**Layout:**
- `.terminal-screen` — flex column, 100vh, black bg
- `.visual-area` — flex: 0 0 33%, scrollable, border-bottom
- `.chat-history` — flex: 1, overflow-y: auto, scrollable
- `.input-field` — flex-shrink: 0, fixed at bottom, width 100%

**Colors:**
- Background: #000
- Text: #c8a560 (orange)
- Borders: #5a4a20 (dark brown)
- User messages: #4ade80 (green)
- System messages: #999 (gray, italic)

---

## Wallet Integration (DApp Kit)

### Provider Setup
**Location:** `frontend/src/main.tsx`

```typescript
<QueryClientProvider client={queryClient}>
  <EveFrontierProvider>
    <App />
  </EveFrontierProvider>
</QueryClientProvider>
```

- `QueryClient` — required by DApp Kit for data fetching
- `EveFrontierProvider` — wraps entire app, provides wallet context + hooks
- EVE Frontier Client Wallet detected via Wallet Standard (EIP-6963)

### Using the Wallet
**In TerminalUI.tsx:**

```typescript
const { isConnected, address, handleConnect } = useConnection()

// /connect command calls:
await handleConnect()

// Now isConnected=true, address=wallet address
// Structure list fetched automatically in useEffect
```

- `useConnection()` — React hook from DApp Kit
- `handleConnect()` — opens wallet connection UI (EVE Frontier Client Wallet / Eve Vault)
- Returns `isConnected` boolean, `address` string
- No manual signing/JWT needed—DApp Kit handles it

---

## Chat Flow

### User Types Message

1. **Input validation** — check if structure selected
2. **Send to backend** — POST `/structure-chat`
   - Headers: `Authorization: Bearer {SERVER_TOKEN}`
   - Body: `{ assembly_id, message, history }`
3. **Backend processes**
   - Loads structure profile + killmails
   - Builds Claude context with tools
   - Streams response via SSE
4. **Frontend parses SSE** — hook reads `data: {JSON}` lines
5. **Accumulates AI text** — updates message state incrementally
6. **Renders in chat-history** — live streaming effect

### Authentication

Currently uses hardcoded `SERVER_TOKEN` from env:
```typescript
const SERVER_TOKEN = import.meta.env.VITE_SERVER_TOKEN || '5740edb0fb25a051db4a932c3622bd69ce47d487bc501f2bde4cb7e19907c454'
```

**Future:** Can be replaced with DApp Kit JWT once backend implements token exchange.

---

## File Locations

```
frontend/
  src/
    components/
      TerminalUI.tsx      ← Main component, command parsing, wallet integration
      VisualArea.tsx      ← Status display
    hooks/
      useStructureChat.ts ← SSE streaming, message management
    styles/
      terminal.css        ← Layout, colors, scrollbars
    types.ts              ← Type definitions
    App.tsx               ← Wrapper (just renders TerminalUI)
    main.tsx              ← Provider setup
    index.css             ← Global styles
    App.css               ← Reset styles
  dist/                   ← Built production files
  package.json            ← Dependencies (@evefrontier/dapp-kit, @tanstack/react-query)
  vite.config.ts          ← Build config (base: '/static/companion/')

static/
  companion/              ← Built React app deployed here
    index.html
    assets/
```

---

## Build & Deployment

### Build
```bash
cd frontend && npm run build
# Creates dist/ with index.html + assets/
```

### Deployment
```bash
cp -r frontend/dist static/companion
# Served by FastAPI at /static/companion/
```

### Routes
- `GET /` → `static/companion/index.html` (React CLI app)
- `GET /legacy-cli` → `static/building-terminal.html` (old vanilla JS terminal)
- `GET /ship-ai` → legacy
- `GET /debug-terminal` → legacy
- `POST /structure-chat` → backend AI endpoint
- `GET /structures` → list structures

---

## How to Extend

### Add a New CLI Command
**In TerminalUI.tsx, handleSend():**

```typescript
if (trimmed === '/mycommand') {
  // Do something
  setInputValue('')
  return
}
```

### Add a Tool to AI
**Backend only** — `/src/tools.py` and `/src/endpoints/structures.py`

Already has: `assess_threat_level`, `get_structure_status`, `detect_alerts`, `analyze_killmail_patterns`, `query_memory_events`, `plan_evasion_route`

### Customize Styling
Edit `frontend/src/styles/terminal.css`

Colors: Change #c8a560 (orange) and #000 (black)
Layout: Adjust flex ratios (.visual-area flex: 0 0 X%)

### Customize Visual Area
**In VisualArea.tsx, modify lines array:**

```typescript
const lines: string[] = []
lines.push('Custom header here')
// Add more ASCII art
```

---

## Known Limitations & Future Work

- Authentication uses hardcoded token (should use DApp Kit JWT)
- System messages logged to console (could store in state)
- No `/help` command listing all commands
- No `/disconnect` command
- No message persistence (clears on reload)
- Chunk size warning during build (can optimize with code splitting)

---

## Troubleshooting

**Wallet not connecting:**
- Verify EVE Frontier Client Wallet is installed
- Check browser console for errors
- Ensure EveFrontierProvider wraps the app

**Chat not responding:**
- Check backend is running on port 8745
- Verify SERVER_TOKEN in env matches backend
- Check network tab for `/structure-chat` POST status

**React app not loading at /:**
- Verify `static/companion/index.html` exists
- Check `src/endpoints/ui.py` returns correct FileResponse
- Restart backend: `python -m uvicorn main:app --port 8745`

---

## Dependencies

| Package | Version | Purpose |
|---------|---------|---------|
| react | ^19.2.4 | UI framework |
| react-dom | ^19.2.4 | DOM rendering |
| @evefrontier/dapp-kit | ^0.1.0 | Wallet + blockchain integration |
| @tanstack/react-query | ^5.0.0 | Data fetching state |
| typescript | ~5.9.3 | Type checking |
| vite | ^8.0.1 | Build tool |

No UI frameworks (no Material-UI, Chakra, etc.)—pure CSS for minimal bundle size.
