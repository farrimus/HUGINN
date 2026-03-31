# EVE Frontier - True Facts (Verified from Source Code)

**Verified:** 2026-03-27 | Source: Code inspection + official docs

---

## 1. TECH STACK (Actual)

### Frontend
- **React** 19.2.4
- **Vite** 8.0.1 (build tool, NOT a framework)
- **TypeScript** ~5.9.3
- **@evefrontier/dapp-kit** 0.1.0 (wallet SDK)
- **@tanstack/react-query** 5.0.0 (data fetching)
- **Vanilla CSS** only (no Tailwind, Material-UI, Chakra)

### Backend
- **FastAPI** (Python 3.12)
- **Port 8745**
- No Node.js server

### Build Output
- Static files only (HTML + JS + CSS)
- Deployed to `/static/companion/`
- Served by FastAPI's StaticFiles handler

---

## 2. WALLET INTEGRATION (Actual)

**NOT EIP-6963** (docs are outdated)
**NOT `window.ethereum`** (docs are outdated)

**ACTUAL:** `@evefrontier/dapp-kit`
- Provider: `EveFrontierProvider`
- Hook: `useConnection()` from `@evefrontier/dapp-kit`
- Returns: `{ isConnected, walletAddress, handleConnect, handleDisconnect }`
- Works with: EVE Frontier Client Wallet, Eve Vault

---

## 3. BUILDER SCAFFOLD vs DAPP KIT

**Builder Scaffold** (what this project uses):
- Vite + React + TypeScript
- `@evefrontier/dapp-kit` for wallet
- Custom hooks for chat/SSE
- Terminal-style UI with vanilla CSS
- For read-only companions, chat interfaces

**DApp Kit** (`@evefrontier/dapp-kit`):
- React SDK for EVE Frontier dApps
- Includes: useConnection, useSmartObject, useNotification, useSponsoredTransaction
- Requires QueryClient from @tanstack/react-query
- Modular imports for tree-shaking
- Version 0.1.0 (early stage)

**Relationship:** Builder scaffold uses DApp Kit internally

---

## 4. PROJECT STRUCTURE (Actual)

```
frontend/
├── src/
│   ├── components/
│   │   ├── TerminalUI.tsx        Main component (wallet, structures, chat)
│   │   ├── InfoPanel.tsx         Status display
│   │   ├── ToolOutputFormatter.tsx Tool output display
│   │   ├── BaselinePanel.tsx      System info panel
│   │   └── VisualArea.tsx         Legacy visual area
│   ├── hooks/
│   │   ├── useConnection()        [FROM @evefrontier/dapp-kit]
│   │   ├── useStructureChat.ts    SSE chat to /structure-chat endpoint
│   │   ├── useSSEChat.ts          Generic SSE connection handler
│   │   ├── useCharacterData.ts    [PLACEHOLDER - TODO integrate DApp Kit GraphQL]
│   │   └── useToolOutput.ts       Tool animation queue management
│   ├── types/
│   │   ├── types.ts              Core interfaces (Structure, ChatMessage, etc)
│   │   └── terminal.ts           Tool types (BaselinePanel, ThreatAssessment, etc)
│   ├── styles/
│   │   ├── terminal.css          Main layout & colors
│   │   ├── info-panel.css        Panel styling
│   │   └── (App.css)
│   ├── App.tsx                   Wrapper
│   └── main.tsx                  Provider setup
├── vite.config.ts               base: '/static/companion/'
├── package.json
└── dist/                        [Generated - DO NOT EDIT]

static/
└── companion/                   [Generated from frontend/dist/]
```

---

## 5. HOOKS IMPLEMENTED (Custom)

### useStructureChat()
- **Purpose:** Manage chat with backend /structure-chat endpoint
- **Inputs:** assemblyId, userMessage, serverToken
- **Outputs:** { messages[], isLoading, error, sendMessage() }
- **Streaming:** SSE with `data: {JSON}` format
- **Response fields:** content, toolUse (name, input), done

### useSSEChat(options)
- **Purpose:** Generic SSE connection handler
- **Options:** { serverToken, onMessage, onError, onConnected }
- **Auto-reconnect:** 5s backoff on error
- **Endpoint:** `/chat`
- **Headers:** `X-Server-Token`

### useToolOutput()
- **Purpose:** Manage tool output display with queue animation
- **Outputs:** { currentToolType, currentData, isAnimating, display(), finishAnimation(), clearQueue() }
- **Queue:** Handles multiple tool outputs in sequence

### useCharacterData(walletAddress)
- **Status:** PLACEHOLDER (returns null)
- **TODO:** Integrate with DApp Kit GraphQL `getWalletCharacters()` query
- **Will return:** Character name, ID, structure count

---

## 6. CLI COMMANDS (Verified)

All in `TerminalUI.tsx` handleCommand():

| Command | Action |
|---------|--------|
| `/connect` | Call `handleConnect()` from useConnection hook |
| `/disconnect` | Call `handleDisconnect()` from useConnection hook |
| `/list` | Show all available structures |
| `/select <id>` | Select structure for chat |
| `/help` | Show available commands |
| `<any text>` | Send to `/structure-chat` endpoint as AI chat |

---

## 7. API CONTRACTS (Verified from Code)

### GET /structures
**Response:**
```json
{
  "structures": [
    {
      "id": "string",
      "system_name": "string",
      "owner_address": "string",
      "structure_name": "string"
    }
  ]
}
```

### POST /structure-chat
**Request:**
```json
{
  "assembly_id": "string",
  "message": "string",
  "history": [
    {
      "role": "user|assistant",
      "content": "string"
    }
  ]
}
```
**Headers:** `Authorization: Bearer {serverToken}`

**Response:** Server-Sent Events (text/event-stream)
```
data: {"content": "text chunk", "done": false}
data: {"content": "more text", "done": true}
data: {"toolUse": {"name": "tool_name", "input": {...}}}
data: {"tool_result": {"tool_name": "...", "data": {...}}}
```

### GET /chat (SSE)
**Purpose:** Streaming connection for real-time messages
**Headers:** `X-Server-Token: {serverToken}`
**Response:** SSE format
```
data: {"text": "response text"}
data: {"tool": "tool_name"}
data: {"tool_result": {"tool_name": "...", "data": {...}}}
```

---

## 8. TYPE DEFINITIONS (Verified)

### From types.ts
```typescript
interface Structure {
  id: string;
  system_name: string;
  owner_address: string;
  structure_name: string;
}

interface ChatMessage {
  id: string;
  role: 'user' | 'ai' | 'system';
  text: string;
  timestamp: number;
}

interface ConnectionState {
  isConnected: boolean;
  address: string | null;
  wallet: string | null;
}

interface TerminalState {
  wallet: ConnectionState;
  selectedStructure: Structure | null;
  messages: ChatMessage[];
  isLoading: boolean;
  error: string | null;
}
```

### From types/terminal.ts
```typescript
interface BaselinePanelData {
  crudVersion: string;
  signature: string;
  shellName: string;
  accessLevel: string;
  assemblySignature: string;
  location: string;
}

interface SystemIntelData { /* threat info */ }
interface ThreatAssessmentData { /* threat data */ }
interface PilotProfileData { /* pilot data */ }
interface MemorySearchData { /* search results */ }
interface MemorySummaryData { /* summary */ }

type ToolType = 'baseline' | 'system-intel' | 'threat-assessment' | 'pilot-profile' | 'memory-search' | 'memory-summary';
type ToolOutputData = BaselinePanelData | SystemIntelData | ThreatAssessmentData | PilotProfileData | MemorySearchData | MemorySummaryData;
```

---

## 9. BUILD & DEPLOYMENT (Verified)

### Dev Build
```bash
cd frontend
npm install
npm run dev
# Runs on http://localhost:5173
# Auto-reload on file changes
```

### Production Build
```bash
npm run build
# Output: frontend/dist/
# Vite compiles TS → JS, bundles, minifies
```

### Deploy
```bash
cp -r frontend/dist/* /opt/eve-frontier/static/companion/
# FastAPI serves at http://135.181.95.84:8745/static/companion/index.html
```

---

## 10. VITE CONFIG (Verified)

```typescript
base: '/static/companion/'  // Critical - all asset paths use this
server: {
  host: '0.0.0.0',
  port: 5173,
}
```

**Why base matters:** Without correct base path, asset loading fails (404 errors).

---

## 11. AUTHENTICATION (Current State)

**Hardcoded token in code:**
```typescript
const SERVER_TOKEN = "5740edb0fb25a051db4a932c3622bd69ce47d487bc501f2bde4cb7e19907c454"
```

**Method:** Bearer token in Authorization header
```
Authorization: Bearer {token}
```

**Future:** Should be replaced with DApp Kit JWT once backend implements token exchange.

---

## 12. KNOWN ISSUES & TODOS

- [ ] `useCharacterData()` is placeholder (needs DApp Kit GraphQL integration)
- [ ] Authentication uses hardcoded token (should use DApp Kit JWT)
- [ ] No persistence (clears on page reload)
- [ ] No command history
- [ ] No autocomplete

---

## 13. WHAT'S MISSING FROM OFFICIAL DOCS

- ❌ Actual hook signatures (useStructureChat, useSSEChat, useToolOutput)
- ❌ Complete API contracts (SSE response format)
- ❌ Type definitions reference
- ❌ CLI commands reference
- ❌ Builder scaffold explanation
- ❌ Relationship between DApp Kit and builder scaffold
- ❌ What useConnection() actually returns
- ❌ What @evefrontier/dapp-kit exports

---

## 14. DOCUMENTATION ERRORS

| Doc File | Error | Truth |
|----------|-------|-------|
| FRONTEND_ARCHITECTURE.md | Claims EIP-6963 + window.ethereum | Uses @evefrontier/dapp-kit + useConnection |
| QUICK_START.md | Says "no DApp Kit" | Code uses @evefrontier/dapp-kit |
| README.md | Mentions "AGENT_GUIDE_BUILDER_AND_DAPP_KIT.md" | Doesn't exist |

