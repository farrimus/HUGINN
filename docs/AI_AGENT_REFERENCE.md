# AI Agent Reference Guide - EVE Frontier Companion

**Purpose:** Complete, accurate reference for AI agents building and maintaining the EVE Frontier companion UI.

**Status:** Verified from source code 2026-03-27 | Single source of truth

---

## Quick Navigation

1. **[Stack Overview](#stack-overview)** — What's actually used
2. **[Architecture](#architecture)** — How it all fits together
3. **[API Reference](#api-reference)** — Endpoints and contracts
4. **[Hooks Reference](#hooks-reference)** — All custom hooks with signatures
5. **[Type Reference](#type-reference)** — All interfaces
6. **[CLI Commands](#cli-commands)** — All terminal commands
7. **[Building & Deploying](#building-and-deploying)** — Dev to production workflow
8. **[File Map](#file-map)** — Where everything lives
9. **[Common Tasks](#common-tasks)** — How to do common operations
10. **[Troubleshooting](#troubleshooting)** — Debugging guide

---

## STACK OVERVIEW

### What's Actually Used

| Layer | Tech | Version | Purpose |
|-------|------|---------|---------|
| **Build Tool** | Vite | 8.0.1 | Compile TypeScript to JavaScript, bundle, minify |
| **Framework** | React | 19.2.4 | UI component system |
| **Language** | TypeScript | ~5.9.3 | Type-safe development |
| **Wallet SDK** | @evefrontier/dapp-kit | 0.1.0 | Wallet connection, smart objects |
| **Data Fetching** | @tanstack/react-query | 5.0.0 | Cache & state management |
| **Styling** | Vanilla CSS | — | No frameworks; terminal aesthetic |
| **Backend** | FastAPI | — | Python, port 8745 |

### What's NOT Used

- ❌ EIP-6963 (outdated docs claim this)
- ❌ `window.ethereum` (outdated docs claim this)
- ❌ Node.js server (static files only)
- ❌ Material-UI, Chakra, Tailwind, or any CSS framework
- ❌ Redux, Zustand, or complex state management (React hooks + React Query is enough)

---

## ARCHITECTURE

### System Flow

```
User in in-game browser
    ↓
GET /static/companion/index.html
    ↓
FastAPI returns static files
    ↓
Browser loads React app (index-*.js, index-*.css)
    ↓
React app uses EveFrontierProvider (DApp Kit)
    ↓
User clicks /connect
    ↓
useConnection() hook from DApp Kit opens wallet modal
    ↓
Wallet connected → walletAddress available
    ↓
App fetches /structures via fetch()
    ↓
User selects /select <id>
    ↓
User sends message → POST /structure-chat
    ↓
Backend streams SSE response (data: {JSON} lines)
    ↓
useStructureChat hook parses SSE, accumulates text
    ↓
React updates UI with new messages
```

### Component Hierarchy

```
<QueryClientProvider>
  <EveFrontierProvider>
    <App />
      └── <TerminalUI />
          ├── <InfoPanel />
          ├── <BaselinePanel /> (via useToolOutput)
          ├── <ToolOutputFormatter /> (via useToolOutput)
          └── Message rendering (via useStructureChat)
  </EveFrontierProvider>
</QueryClientProvider>
```

### Data Flow

1. **Wallet Connection**
   - `useConnection()` → `handleConnect()` → DApp Kit opens modal
   - Returns: `{ isConnected, walletAddress, handleConnect, handleDisconnect }`

2. **Structure Loading**
   - `fetch(/structures)` → returns list of structures
   - Stored in local state via `useState`

3. **Chat**
   - User sends message → `useStructureChat().sendMessage()`
   - `sendMessage()` → `POST /structure-chat` with Bearer auth
   - Backend streams SSE response
   - Hook parses `data: {JSON}` lines
   - Accumulates text incrementally
   - Updates React state
   - Component renders new messages

4. **Tool Output**
   - Backend sends `{"tool_result": {...}}`
   - Hook calls `useToolOutput().display(toolName, data)`
   - Formatter renders tool output with animation
   - Queue handles multiple tools in sequence

---

## API REFERENCE

### GET /structures

**Purpose:** Fetch list of available structures

**Request:**
```
GET /structures
```

**Response:**
```json
{
  "structures": [
    {
      "id": "uuid-or-identifier",
      "system_name": "Jita",
      "owner_address": "0x...",
      "structure_name": "Trading Post"
    }
  ]
}
```

**Error Handling:**
- HTTP 4xx/5xx → catch and display error message in terminal

---

### POST /structure-chat

**Purpose:** Send chat message, receive AI response via SSE

**Request:**
```
POST /structure-chat
Authorization: Bearer {serverToken}
Content-Type: application/json

{
  "assembly_id": "structure-id",
  "message": "user message text",
  "history": [
    {
      "role": "user",
      "content": "previous user message"
    },
    {
      "role": "assistant",
      "content": "previous AI response"
    }
  ]
}
```

**Response:** Server-Sent Events (Content-Type: text/event-stream)

Each message is a line starting with `data: ` followed by JSON:

```
data: {"content": "I "}
data: {"content": "am "}
data: {"content": "ready"}
data: {"content": ".", "done": true}
```

**Tool Use Format:**
```
data: {"toolUse": {"name": "assess_threat_level", "input": {"structure_id": "..."}}}
```

**Tool Result Format:**
```
data: {"tool_result": {"tool_name": "assess_threat_level", "data": {"threat_level": "high", ...}}}
```

**Completion:**
- `"done": true` signals end of response
- Stream may close after completion

**Error Handling:**
- HTTP error → catch, throw, display in terminal
- Parse error → log and skip malformed lines
- Stream error → caught by fetch, triggers `onError` callback

---

### GET /chat (SSE Stream)

**Purpose:** Long-lived SSE connection for real-time messages

**Request:**
```
GET /chat
X-Server-Token: {serverToken}
```

**Response:** Server-Sent Events stream

```
data: {"text": "message from backend"}
data: {"tool": "tool_name"}
data: {"tool_result": {"tool_name": "...", "data": {...}}}
data: {"visual": "panel_type"}
```

**Auto-reconnect:** Yes, 5s backoff on error

---

## HOOKS REFERENCE

### useConnection() ← from @evefrontier/dapp-kit

**Signature:**
```typescript
const {
  isConnected: boolean,
  walletAddress: string | null,
  handleConnect: () => Promise<void>,
  handleDisconnect: () => void,
  wallet: object | null
} = useConnection()
```

**Purpose:** Manage wallet connection via DApp Kit

**Behavior:**
- `isConnected` — true when wallet is connected
- `walletAddress` — user's wallet address (null if disconnected)
- `handleConnect()` — opens DApp Kit wallet modal, user selects wallet
- `handleDisconnect()` — closes connection

**Example:**
```typescript
const { isConnected, walletAddress, handleConnect } = useConnection()

// In UI
{isConnected ? (
  <div>Connected: {walletAddress}</div>
) : (
  <button onClick={handleConnect}>Connect Wallet</button>
)}
```

---

### useStructureChat()

**Signature:**
```typescript
const {
  messages: ChatMessage[],
  isLoading: boolean,
  error: string | null,
  sendMessage: (assemblyId: string, userMessage: string, serverToken: string) => Promise<void>
} = useStructureChat()
```

**Purpose:** Manage chat with `/structure-chat` endpoint via SSE

**Behavior:**
- `messages` — accumulated chat history
- Each message has: `{ id, role ('user'|'assistant'), content, timestamp }`
- `sendMessage()` — sends message, parses SSE response, updates state
- `isLoading` — true while SSE stream is active

**Example:**
```typescript
const { messages, sendMessage } = useStructureChat()

await sendMessage('structure-123', 'Hello!', 'my-token')

// messages now includes both user and AI response
messages.forEach(msg => console.log(`${msg.role}: ${msg.content}`))
```

**SSE Parsing:**
- Reads `data: {JSON}` lines from stream
- `data.content` → accumulates as message text
- `data.toolUse` → tool was called by AI
- `data.done: true` → response complete

---

### useSSEChat(options)

**Signature:**
```typescript
const {
  isConnected: boolean,
  disconnect: () => void
} = useSSEChat({
  serverToken: string,
  onMessage?: (msg: SSEMessage) => void,
  onError?: (err: Error) => void,
  onConnected?: () => void
})
```

**Purpose:** Generic SSE connection handler with auto-reconnect

**Behavior:**
- Connects to `/chat` endpoint on mount
- Auto-reconnects on error (5s backoff)
- Calls `onMessage` for each parsed message
- Calls `onError` if connection fails
- Calls `onConnected` when connected

**Interface:**
```typescript
interface SSEMessage {
  text?: string;
  tool?: string;
  tool_result?: {
    tool_name: string;
    data: any;
  };
  visual?: string;
}
```

**Example:**
```typescript
useSSEChat({
  serverToken: 'my-token',
  onMessage: (msg) => {
    if (msg.text) console.log('AI:', msg.text)
    if (msg.tool_result) console.log('Tool:', msg.tool_result)
  },
  onError: (err) => console.error('SSE error:', err)
})
```

---

### useToolOutput()

**Signature:**
```typescript
const {
  currentToolType: ToolType | null,
  currentData: ToolOutputData | null,
  isAnimating: boolean,
  queueLength: number,
  display: (toolType: ToolType, data: ToolOutputData) => void,
  finishAnimation: () => void,
  clearQueue: () => void
} = useToolOutput()
```

**Purpose:** Manage tool output display with queue animation

**Behavior:**
- `display()` → queues tool output for display
- If animating, adds to queue; otherwise starts immediately
- `finishAnimation()` → moves to next queued item or stops
- `isAnimating` → true if currently showing tool output
- `queueLength` → how many items waiting

**ToolType:**
```typescript
type ToolType = 'baseline' | 'system-intel' | 'threat-assessment' |
                'pilot-profile' | 'memory-search' | 'memory-summary'
```

**Example:**
```typescript
const { display, finishAnimation } = useToolOutput()

// Display tool output
display('threat-assessment', {
  threat_level: 'high',
  threats: [...]
})

// After animation completes
finishAnimation() // Shows next queued item
```

---

### useCharacterData(walletAddress)

**Signature:**
```typescript
const {
  data: CharacterData | null,
  isLoading: boolean,
  error: string | null
} = useCharacterData(walletAddress: string | null)
```

**Purpose:** Fetch character data for connected wallet

**Status:** PLACEHOLDER (returns null)

**TODO:** Integrate with DApp Kit GraphQL query `getWalletCharacters()`

**Will Return:**
```typescript
interface CharacterData {
  character?: {
    id: string;
    name: string;
    wallet: string;
  };
  structures?: {
    count: number;
  };
}
```

---

## TYPE REFERENCE

### Core Types (types.ts)

```typescript
interface Structure {
  id: string;                    // Unique identifier
  system_name: string;           // Location (e.g., "Jita")
  owner_address: string;         // Wallet address
  structure_name: string;        // Display name
}

interface ChatMessage {
  id: string;                    // Unique per message
  role: 'user' | 'ai' | 'system'; // Message source
  text: string;                  // Message content
  timestamp: number;             // Unix timestamp
}

interface ConnectionState {
  isConnected: boolean;
  address: string | null;        // Wallet address
  wallet: string | null;         // Wallet name
}

interface TerminalState {
  wallet: ConnectionState;
  selectedStructure: Structure | null;
  messages: ChatMessage[];
  isLoading: boolean;
  error: string | null;
}
```

### Tool Types (types/terminal.ts)

```typescript
interface BaselinePanelData {
  crudVersion: string;
  signature: string;             // Wallet address
  shellName: string;             // Character name
  accessLevel: string;           // Permission level
  assemblySignature: string;     // Structure ID
  location: string;              // Location name
}

interface SystemIntelData {
  systemName: string;
  threat?: number;
  activity?: number;
  [key: string]: any;
}

interface ThreatAssessmentData {
  threatLevel: 'low' | 'medium' | 'high' | 'critical';
  threats: Array<{
    type: string;
    count?: number;
    description?: string;
  }>;
  recommendation?: string;
}

interface PilotProfileData {
  pilotName: string;
  corporation?: string;
  securityStatus?: number;
  engagements?: number;
  [key: string]: any;
}

interface MemorySearchData {
  query: string;
  results: Array<{
    title: string;
    content: string;
    relevance?: number;
  }>;
}

interface MemorySummaryData {
  eventName: string;
  summary: string;
  timestamp?: number;
  participants?: string[];
}

type ToolType =
  | 'baseline'
  | 'system-intel'
  | 'threat-assessment'
  | 'pilot-profile'
  | 'memory-search'
  | 'memory-summary'

type ToolOutputData =
  | BaselinePanelData
  | SystemIntelData
  | ThreatAssessmentData
  | PilotProfileData
  | MemorySearchData
  | MemorySummaryData
```

### Internal Types

```typescript
interface TerminalLog {
  text: string;
  type: 'info' | 'user' | 'ai' | 'error' | 'warning' | 'command';
  timestamp: number;
}

interface SSEMessage {
  text?: string;
  tool?: string;
  tool_result?: {
    tool_name: string;
    data: any;
  };
  visual?: string;
}

interface UseStructureChatReturn {
  messages: ChatMessage[];
  isLoading: boolean;
  error: string | null;
  sendMessage: (assemblyId: string, userMessage: string, serverToken: string) => Promise<void>;
}

interface UseSSEChatOptions {
  serverToken: string;
  onMessage?: (msg: SSEMessage) => void;
  onError?: (err: Error) => void;
  onConnected?: () => void;
}
```

---

## CLI COMMANDS

All commands are parsed in `TerminalUI.tsx` in the `handleCommand()` function.

### /connect

**Purpose:** Connect user's wallet

**Action:** Calls `handleConnect()` from `useConnection()` hook

**Response:**
```
Initiating wallet connection...
```

**Error:**
```
Wallet already connected
```

---

### /disconnect

**Purpose:** Disconnect wallet

**Action:** Calls `handleDisconnect()` from `useConnection()` hook

**Response:**
```
Wallet disconnected
```

**Error:**
```
Wallet not connected
```

---

### /list

**Purpose:** Show all available structures

**Requires:** Wallet connected

**Response:**
```
Available structures:
  [structure-id-1] Trading Post in Jita
  [structure-id-2] Refinery in Amarr
```

**Error:**
```
Connect wallet first with /connect
No structures available
```

---

### /select <structure-id>

**Purpose:** Select a structure for chatting

**Requires:** Wallet connected, valid structure ID

**Response:**
```
Selected structure: Trading Post in Jita
Ready to chat. Send a message to begin.
```

**Error:**
```
Connect wallet first with /connect
Usage: /select <structure-id>
Structure 'invalid-id' not found
```

---

### /help

**Purpose:** Show all available commands

**Response:**
```
Available commands:
  /connect - Connect wallet
  /disconnect - Disconnect wallet
  /list - List available structures
  /select <id> - Select a structure
  /help - Show this message
Regular text is sent to AI chat
```

---

### [Text Message]

**Purpose:** Send message to AI

**Requires:** Structure selected

**Action:**
1. User types text and presses Enter
2. `handleChatMessage()` called
3. Validates structure is selected
4. Calls `useStructureChat().sendMessage()`
5. Message sent to `/structure-chat` endpoint
6. SSE response parsed and displayed

**Response:**
```
[You]: Hello!
[AI response streams in...]
```

**Error:**
```
Select a structure first with /select <id>
Error: {error message}
```

---

## BUILDING AND DEPLOYING

### Development Workflow

```bash
# 1. Install dependencies (first time only)
cd /opt/eve-frontier/frontend
npm install

# 2. Start dev server
npm run dev
# Open http://localhost:5173

# 3. Edit files in src/
# Changes auto-reload in browser

# 4. Test locally at http://localhost:5173
```

### Production Build

```bash
# 1. Create production build
npm run build
# Output: frontend/dist/

# 2. Deploy to static files
cp -r frontend/dist/* /opt/eve-frontier/static/companion/

# 3. Verify deployment
ls /opt/eve-frontier/static/companion/
# Should show: index.html, assets/, favicon.svg, icons.svg

# 4. Access in browser
# http://135.181.95.84:8745/static/companion/index.html
```

### Build Process Details

**What `npm run build` does:**

1. Runs TypeScript compiler (`tsc -b`)
   - Checks type safety
   - Catches errors before bundling

2. Runs Vite bundler
   - Compiles TypeScript → JavaScript
   - Bundles all dependencies
   - Minifies code and CSS
   - Generates source maps

3. Outputs to `dist/`
   - `index.html` — Entry point
   - `assets/index-[hash].js` — Bundled JavaScript
   - `assets/index-[hash].css` — Bundled CSS
   - Static assets copied

**Critical:** vite.config.ts has `base: '/static/companion/'`
- All asset references use this prefix
- Without it, assets load as `/assets/` (wrong path)

---

## FILE MAP

```
/opt/eve-frontier/
├── frontend/
│   ├── src/
│   │   ├── components/
│   │   │   ├── TerminalUI.tsx       [640 lines]
│   │   │   │   ├── useConnection hook
│   │   │   │   ├── handleCommand() for CLI
│   │   │   │   ├── handleChatMessage()
│   │   │   │   └── /structures endpoint call
│   │   │   ├── InfoPanel.tsx         Status display panel
│   │   │   ├── ToolOutputFormatter.tsx Tool output rendering
│   │   │   ├── BaselinePanel.tsx    Baseline system panel
│   │   │   └── VisualArea.tsx       Legacy visual area
│   │   │
│   │   ├── hooks/
│   │   │   ├── useConnection() [EXTERNAL @evefrontier/dapp-kit]
│   │   │   ├── useStructureChat.ts  [178 lines] SSE chat
│   │   │   ├── useSSEChat.ts        [149 lines] Generic SSE
│   │   │   ├── useCharacterData.ts  [16 lines] PLACEHOLDER
│   │   │   └── useToolOutput.ts     [83 lines] Tool queue
│   │   │
│   │   ├── types/
│   │   │   ├── types.ts             Core interfaces
│   │   │   └── terminal.ts          Tool types
│   │   │
│   │   ├── styles/
│   │   │   ├── terminal.css         Main layout
│   │   │   ├── info-panel.css       Panel styles
│   │   │   └── (App.css)
│   │   │
│   │   ├── App.tsx                  [8 lines] Wrapper
│   │   ├── main.tsx                 [18 lines] Provider setup
│   │   └── index.css
│   │
│   ├── vite.config.ts               Build config
│   ├── package.json                 Dependencies
│   ├── tsconfig.json                TypeScript config
│   ├── eslint.config.js             Linting
│   └── dist/                        [Generated - DO NOT EDIT]
│
├── static/
│   └── companion/                   [Generated from dist/]
│       ├── index.html               Entry point
│       ├── assets/
│       │   ├── index-[hash].js
│       │   └── index-[hash].css
│       ├── favicon.svg
│       └── icons.svg
│
└── docs/
    ├── TRUTH_FACTS.md               Verified facts
    ├── AI_AGENT_REFERENCE.md        THIS FILE
    ├── AGENT_GUIDE_BUILDER_AND_DAPP_KIT.md [Outdated]
    ├── DAPP_KIT_INTEGRATION.md      [Partially outdated]
    ├── FRONTEND_ARCHITECTURE.md     [Outdated - claims EIP-6963]
    ├── QUICK_START.md               [Human-focused]
    ├── SYSTEM_OVERVIEW.md           [Human-focused]
    └── README.md                    [Index]
```

---

## COMMON TASKS

### Add a New CLI Command

**File:** `frontend/src/components/TerminalUI.tsx`

**Location:** In `handleCommand()` function (line ~121)

**Pattern:**
```typescript
} else if (command === '/mycommand') {
  // Your logic here
  addLog('Command result', 'info')
} else if (command === '/another') {
```

**Example: Add /status command**
```typescript
} else if (command === '/status') {
  if (!isConnected) {
    addLog('Wallet not connected', 'warning')
  } else if (!selectedStructure) {
    addLog('No structure selected', 'warning')
  } else {
    addLog(`Status: Connected to ${selectedStructure.structure_name}`, 'info')
  }
}
```

---

### Add a New Hook

**File:** `frontend/src/hooks/useMyHook.ts`

**Template:**
```typescript
import { useState, useCallback, useEffect } from 'react'

interface UseMyHookReturn {
  state: any;
  action: () => void;
}

export function useMyHook(): UseMyHookReturn {
  const [state, setState] = useState(initialValue)

  const action = useCallback(() => {
    // Your logic
    setState(newValue)
  }, [dependencies])

  useEffect(() => {
    // Setup/cleanup if needed
  }, [dependencies])

  return { state, action }
}
```

**Then import in TerminalUI.tsx:**
```typescript
import { useMyHook } from '../hooks/useMyHook'

export function TerminalUI() {
  const { state, action } = useMyHook()
  // ...
}
```

---

### Add a New Type

**File:** `frontend/src/types.ts` or `frontend/src/types/terminal.ts`

**Pattern:**
```typescript
export interface MyType {
  field1: string;
  field2: number;
  field3?: boolean;  // Optional
}

export type MyUnion = TypeA | TypeB | TypeC
```

**Import where needed:**
```typescript
import { MyType } from '../types'
```

---

### Change Styling

**Files:**
- Main layout: `frontend/src/styles/terminal.css`
- Panel styling: `frontend/src/styles/info-panel.css`
- Component styles: `frontend/src/styles/App.css`

**Key Selectors:**
```css
.terminal-ui           /* Main container */
.terminal-screen       /* Full screen */
.visual-area           /* Top section */
.chat-history          /* Message area */
.input-field           /* Input bar */
.line-info, .line-user, .line-ai, .line-error  /* Message colors */
```

**Colors:**
- Background: `#000` (black)
- Text: `#c8a560` (orange)
- User: `#4ade80` (green)
- Error: `#ef4444` (red)
- Border: `#5a4a20` (dark brown)

---

### Test Locally

```bash
npm run dev
# Browser opens to http://localhost:5173
# Edit src/ files → auto-reload
# F12 to open DevTools → Console for errors
```

---

### Deploy Changes

```bash
# 1. Stop dev server (Ctrl+C)

# 2. Build
npm run build

# 3. Deploy
cp -r dist/* ../static/companion/

# 4. Reload in browser
# Ctrl+Shift+R (hard refresh)
```

---

## TROUBLESHOOTING

### App doesn't load / blank page

**Check:**
1. Browser console (F12) for JavaScript errors
2. Network tab (F12) — are JS/CSS files returning 200?
3. Is `/static/companion/index.html` deployed?
4. Is FastAPI running (`lsof -i :8745`)?

**Fix:**
```bash
# Redeploy
npm run build
cp -r dist/* ../static/companion/
```

---

### Assets return 404 (JS/CSS not loading)

**Cause:** Incorrect vite.config.ts `base` path

**Check:** `vite.config.ts` line 7
```typescript
base: '/static/companion/'  // Must be correct
```

**Fix:**
1. Update base if needed
2. Rebuild: `npm run build`
3. Redeploy: `cp -r dist/* ../static/companion/`

---

### Wallet won't connect

**Check:**
1. EVE Frontier Client Wallet installed?
2. Browser console for DApp Kit errors
3. Is EveFrontierProvider wrapping the app? (main.tsx)

**Fix:**
```typescript
// main.tsx must have:
<EveFrontierProvider queryClient={queryClient}>
  <App />
</EveFrontierProvider>
```

---

### Chat not responding / /structure-chat fails

**Check:**
1. Is backend running? `lsof -i :8745`
2. Network tab (F12) — what's /structure-chat returning?
3. Is serverToken correct?
4. Is endpoint URL correct? (should be `/structure-chat`, not `http://...`)

**Debug:**
```typescript
// In TerminalUI.tsx, add logging:
console.log('Sending to:', `${API_BASE_URL}/structure-chat`)
console.log('With token:', SERVER_TOKEN)
```

---

### CSS not updating

**Fix:**
```bash
# Hard refresh browser
Ctrl+Shift+R (or Cmd+Shift+R on Mac)

# OR rebuild and redeploy
npm run build
cp -r dist/* ../static/companion/
```

---

### TypeScript errors

**Check:** Run type check
```bash
npm run lint
# Shows all type errors
```

**Fix:** Resolve errors in src/ files based on message

---

### Port 5173 already in use

**Find process:**
```bash
lsof -i :5173
```

**Kill process:**
```bash
kill -9 <PID>
```

**Or use different port:**
```bash
npm run dev -- --port 5174
```

---

## BEST PRACTICES FOR AGENTS

1. **Always read source code first** before trusting docs
2. **Use type signatures** — understand what hooks return
3. **Check API contracts** — know exact request/response format
4. **Verify file locations** — don't assume based on convention
5. **Build before deploying** — `npm run build` always
6. **Test locally first** — `npm run dev` to validate changes
7. **Use console.log debugging** — F12 DevTools is your friend
8. **Don't edit generated files** — never manually change `/static/companion/` or `dist/`
9. **Update types when adding fields** — keep types.ts in sync
10. **Test SSE parsing** — mock response format when testing

---

## SUMMARY TABLE

| Task | File | Command | Time |
|------|------|---------|------|
| Edit code | `src/**` | Edit then save | Instant (dev) |
| Test locally | — | `npm run dev` | Immediate |
| Build | — | `npm run build` | 3-5s |
| Deploy | — | `cp -r dist/* ../static/companion/` | 1s |
| Access production | Browser | `http://135.181.95.84:8745/static/companion/index.html` | Live |

---

**Last verified:** 2026-03-27
**Source:** Direct code inspection + test execution
**Status:** Production-ready reference for AI agents

