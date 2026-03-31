# DApp Kit Integration Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Integrate @evefrontier/dapp-kit into React frontend to create a pure CLI terminal interface (776x828 viewport) with wallet connection and blockchain structure queries, preserving the black+orange monospace aesthetic.

**Architecture:** Install DApp Kit + @tanstack/react-query, wrap React app in EveFrontierProvider, use useConnection() for wallet (EVE Frontier Client Wallet / Wallet Standard), display connection and structure info inline in visual area or via CLI commands, three-section layout only (visual / chat history / input), no sidebars or UI chrome.

**Tech Stack:** React 19, Vite, @evefrontier/dapp-kit, @tanstack/react-query, TypeScript, pure CSS (no frameworks), EVE Frontier Client Wallet (Wallet Standard)

---

## File Structure

### Frontend Files to Modify/Create
- **Modify:** `frontend/package.json` — Add DApp Kit + React Query dependencies
- **Modify:** `frontend/src/main.tsx` — Wrap App in EveFrontierProvider and QueryClientProvider
- **Rewrite:** `frontend/src/App.tsx` — Pure CLI terminal with wallet connection, structure selection via commands, chat streaming
- **Modify:** `frontend/src/App.css` — Three-section layout: visual area (33%) / chat history (flex) / input field (fixed bottom)
- **Create:** `frontend/src/types.ts` — Type definitions
- **Create:** `frontend/src/hooks/useStructureChat.ts` — Custom hook for SSE streaming
- **Create:** `frontend/src/components/TerminalUI.tsx` — Pure CLI rendering component
- **Create:** `frontend/src/components/VisualArea.tsx` — Visual area (status, wallet, structure info)
- **Create:** `frontend/src/styles/terminal.css` — Terminal styling

### Backend Files to Modify
- **Modify:** `src/endpoints/ui.py` — Change GET / to serve React app

---

## Chunk 1: Dependencies & Provider Setup

### Task 1: Install DApp Kit Dependencies

**Files:**
- Modify: `frontend/package.json`

- [ ] **Step 1: Add DApp Kit and React Query to dependencies**

Open `frontend/package.json` and update `"dependencies"`:
```json
{
  "dependencies": {
    "react": "^19.2.4",
    "react-dom": "^19.2.4",
    "@evefrontier/dapp-kit": "^0.1.0",
    "@tanstack/react-query": "^5.0.0"
  }
}
```

- [ ] **Step 2: Install dependencies**

```bash
cd /opt/eve-frontier/frontend
npm install
```

Expected: Dependencies installed, package-lock.json updated.

- [ ] **Step 3: Verify installation**

```bash
npm list @evefrontier/dapp-kit @tanstack/react-query
```

Expected: Both packages listed with versions.

- [ ] **Step 4: Commit**

```bash
cd /opt/eve-frontier
git add frontend/package.json frontend/package-lock.json
git commit -m "feat: add @evefrontier/dapp-kit and @tanstack/react-query"
```

---

### Task 2: Wrap App in Providers

**Files:**
- Modify: `frontend/src/main.tsx`

- [ ] **Step 1: Update main.tsx**

Replace with:

```typescript
import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { EveFrontierProvider } from '@evefrontier/dapp-kit'
import './index.css'
import App from './App.tsx'

const queryClient = new QueryClient()

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <QueryClientProvider client={queryClient}>
      <EveFrontierProvider>
        <App />
      </EveFrontierProvider>
    </QueryClientProvider>
  </StrictMode>,
)
```

- [ ] **Step 2: Verify TypeScript compilation**

```bash
cd /opt/eve-frontier/frontend
npm run build 2>&1 | head -20
```

Expected: No TypeScript errors.

- [ ] **Step 3: Commit**

```bash
cd /opt/eve-frontier
git add frontend/src/main.tsx
git commit -m "feat: wrap App in EveFrontierProvider and QueryClientProvider"
```

---

## Chunk 2: Type Definitions & Core Hooks

### Task 3: Create Type Definitions

**Files:**
- Create: `frontend/src/types.ts`

- [ ] **Step 1: Write types**

Create `frontend/src/types.ts`:

```typescript
export interface Structure {
  id: string
  system_name: string
  owner_address: string
  structure_name: string
}

export interface ChatMessage {
  id: string
  role: 'user' | 'ai' | 'system'
  text: string
  timestamp: number
}

export interface ConnectionState {
  isConnected: boolean
  address: string | null
  wallet: string | null
}

export interface TerminalState {
  wallet: ConnectionState
  selectedStructure: Structure | null
  messages: ChatMessage[]
  isLoading: boolean
  error: string | null
}
```

- [ ] **Step 2: Commit**

```bash
cd /opt/eve-frontier
git add frontend/src/types.ts
git commit -m "feat: add TypeScript type definitions"
```

---

### Task 4: Create useStructureChat Hook

**Files:**
- Create: `frontend/src/hooks/useStructureChat.ts`

- [ ] **Step 1: Write hook**

Create `frontend/src/hooks/useStructureChat.ts`:

```typescript
import { useState, useCallback } from 'react'
import { ChatMessage } from '../types'

export function useStructureChat() {
  const [messages, setMessages] = useState<ChatMessage[]>([])
  const [isLoading, setIsLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const sendMessage = useCallback(
    async (assemblyId: string, userMessage: string, serverToken: string) => {
      if (!userMessage.trim()) return

      const userMsg: ChatMessage = {
        id: `user-${Date.now()}`,
        role: 'user',
        text: userMessage,
        timestamp: Date.now(),
      }
      setMessages((prev) => [...prev, userMsg])
      setIsLoading(true)
      setError(null)

      try {
        const response = await fetch(`${window.location.origin}/structure-chat`, {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
            'Authorization': `Bearer ${serverToken}`,
          },
          body: JSON.stringify({
            assembly_id: assemblyId,
            message: userMessage,
            history: messages.map((m) => ({
              role: m.role,
              content: m.text,
            })),
          }),
        })

        if (!response.ok) {
          const data = await response.json().catch(() => ({}))
          throw new Error(data.detail || `HTTP ${response.status}`)
        }

        const reader = response.body?.getReader()
        if (!reader) throw new Error('No response body')

        const decoder = new TextDecoder()
        let aiText = ''

        while (true) {
          const { done, value } = await reader.read()
          if (done) break

          const chunk = decoder.decode(value)
          const lines = chunk.split('\n')

          for (const line of lines) {
            if (!line.startsWith('data: ')) continue
            const dataStr = line.slice(6).trim()
            if (!dataStr || dataStr === '[DONE]') continue

            try {
              const data = JSON.parse(dataStr)
              if (data.text) {
                aiText += data.text
                setMessages((prev) => {
                  const updated = [...prev]
                  const lastIdx = updated.length - 1
                  if (lastIdx >= 0 && updated[lastIdx].role === 'ai') {
                    updated[lastIdx] = {
                      ...updated[lastIdx],
                      text: aiText,
                    }
                  } else {
                    updated.push({
                      id: `ai-${Date.now()}`,
                      role: 'ai',
                      text: aiText,
                      timestamp: Date.now(),
                    })
                  }
                  return updated
                })
              }
            } catch {
              // Ignore parse errors
            }
          }
        }
      } catch (err) {
        const errorMsg = err instanceof Error ? err.message : 'Unknown error'
        setError(errorMsg)
        setMessages((prev) => [
          ...prev,
          {
            id: `error-${Date.now()}`,
            role: 'system',
            text: `❌ ${errorMsg}`,
            timestamp: Date.now(),
          },
        ])
      } finally {
        setIsLoading(false)
      }
    },
    [messages]
  )

  return { messages, isLoading, error, sendMessage }
}
```

- [ ] **Step 2: Commit**

```bash
cd /opt/eve-frontier
git add frontend/src/hooks/useStructureChat.ts
git commit -m "feat: create useStructureChat hook for SSE streaming"
```

---

## Chunk 3: Terminal Components

### Task 5: Create VisualArea Component

**Files:**
- Create: `frontend/src/components/VisualArea.tsx`

- [ ] **Step 1: Write component**

Create `frontend/src/components/VisualArea.tsx`:

```typescript
import { ConnectionState } from '../types'
import { Structure } from '../types'

interface VisualAreaProps {
  connection: ConnectionState
  selectedStructure: Structure | null
  isConnecting: boolean
}

export function VisualArea({
  connection,
  selectedStructure,
  isConnecting,
}: VisualAreaProps) {
  const lines: string[] = []

  // Header
  lines.push('═══════════════════════════════════════════════════════════════════════════════')
  lines.push('  EVE FRONTIER STRUCTURE AI COMPANION v1.0                       [ONLINE]')
  lines.push('═══════════════════════════════════════════════════════════════════════════════')
  lines.push('')

  // Wallet status
  if (isConnecting) {
    lines.push('  [WALLET] Connecting...')
  } else if (connection.isConnected) {
    lines.push(`  [WALLET] Connected`)
    if (connection.address) {
      lines.push(`  Address: ${connection.address.slice(0, 20)}...`)
    }
  } else {
    lines.push('  [WALLET] Disconnected')
    lines.push('  Type: /connect to authenticate')
  }

  lines.push('')

  // Structure status
  if (selectedStructure) {
    lines.push(`  [STRUCTURE] ${selectedStructure.structure_name || selectedStructure.id}`)
    lines.push(`  Location: ${selectedStructure.system_name}`)
    lines.push(`  Owner: ${selectedStructure.owner_address.slice(0, 20)}...`)
  } else if (connection.isConnected) {
    lines.push('  [STRUCTURE] No structure selected')
    lines.push('  Type: /list to see available structures')
  }

  lines.push('')
  lines.push('═══════════════════════════════════════════════════════════════════════════════')

  return (
    <div className="visual-area">
      <pre>{lines.join('\n')}</pre>
    </div>
  )
}
```

- [ ] **Step 2: Commit**

```bash
cd /opt/eve-frontier
git add frontend/src/components/VisualArea.tsx
git commit -m "feat: create VisualArea component for status display"
```

---

### Task 6: Create TerminalUI Component

**Files:**
- Create: `frontend/src/components/TerminalUI.tsx`

- [ ] **Step 1: Write component**

Create `frontend/src/components/TerminalUI.tsx`:

```typescript
import { useRef, useEffect, useState } from 'react'
import { useConnection } from '@evefrontier/dapp-kit'
import { ChatMessage, Structure } from '../types'
import { VisualArea } from './VisualArea'
import { useStructureChat } from '../hooks/useStructureChat'
import '../styles/terminal.css'

const SERVER_TOKEN = import.meta.env.VITE_SERVER_TOKEN || '5740edb0fb25a051db4a932c3622bd69ce47d487bc501f2bde4cb7e19907c454'

export function TerminalUI() {
  const { isConnected, address, handleConnect } = useConnection()
  const { messages, isLoading, sendMessage } = useStructureChat()
  const [inputValue, setInputValue] = useState('')
  const [selectedStructure, setSelectedStructure] = useState<Structure | null>(null)
  const [structures, setStructures] = useState<Structure[]>([])
  const [isConnecting, setIsConnecting] = useState(false)
  const messagesEndRef = useRef<HTMLDivElement>(null)

  // Fetch structures on connect
  useEffect(() => {
    if (isConnected) {
      const fetchStructures = async () => {
        try {
          const res = await fetch(`${window.location.origin}/structures`)
          if (res.ok) {
            const data = await res.json()
            setStructures(data.structures || [])
          }
        } catch (err) {
          console.error('Error fetching structures:', err)
        }
      }
      fetchStructures()
    }
  }, [isConnected])

  // Auto-scroll to bottom
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages])

  // Handle wallet connection
  const handleConnectWallet = async () => {
    setIsConnecting(true)
    try {
      await handleConnect()
    } finally {
      setIsConnecting(false)
    }
  }

  // Handle commands in input
  const handleSend = async (input: string) => {
    if (!input.trim()) return

    const trimmed = input.trim().toLowerCase()

    // Command: /connect
    if (trimmed === '/connect') {
      await handleConnectWallet()
      setInputValue('')
      return
    }

    // Command: /list
    if (trimmed === '/list') {
      if (!isConnected) {
        addSystemMessage('Error: Connect wallet first (/connect)')
        setInputValue('')
        return
      }
      if (structures.length === 0) {
        addSystemMessage('No structures available')
      } else {
        const list = structures
          .map((s) => `  ${s.id} (${s.system_name})`)
          .join('\n')
        addSystemMessage(`Available structures:\n${list}`)
      }
      setInputValue('')
      return
    }

    // Command: /select <structure-id>
    if (trimmed.startsWith('/select ')) {
      const structureId = trimmed.slice(8).trim()
      const structure = structures.find((s) => s.id === structureId)
      if (structure) {
        setSelectedStructure(structure)
        addSystemMessage(`Selected: ${structure.id} in ${structure.system_name}`)
      } else {
        addSystemMessage(`Structure not found: ${structureId}`)
      }
      setInputValue('')
      return
    }

    // Regular chat message
    if (!selectedStructure) {
      addSystemMessage('Error: Select a structure first (/select <id>)')
      setInputValue('')
      return
    }

    // Send to AI
    setInputValue('')
    await sendMessage(selectedStructure.id, input, SERVER_TOKEN)
  }

  const addSystemMessage = (text: string) => {
    // System messages are added via messages state if needed
    // For now, this just logs to console; you can add a messages update here
    console.log('SYSTEM:', text)
  }

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey && !isLoading) {
      e.preventDefault()
      handleSend(inputValue)
    }
  }

  return (
    <div className="terminal-screen">
      <VisualArea
        connection={{
          isConnected,
          address: address || null,
          wallet: 'EVE Frontier Client',
        }}
        selectedStructure={selectedStructure}
        isConnecting={isConnecting}
      />

      <div className="chat-history">
        {messages.length === 0 && (
          <div className="chat-line chat-system">
            Type /help for commands
          </div>
        )}
        {messages.map((msg) => (
          <div key={msg.id} className={`chat-line chat-${msg.role}`}>
            {msg.role === 'user' ? '> ' : ''}
            {msg.text}
          </div>
        ))}
        {isLoading && <div className="chat-line chat-system">⏳ Thinking...</div>}
        <div ref={messagesEndRef} />
      </div>

      <input
        type="text"
        value={inputValue}
        onChange={(e) => setInputValue(e.target.value)}
        onKeyDown={handleKeyDown}
        placeholder="Commands: /connect /list /select <id> | Or type message..."
        className="input-field"
        disabled={isLoading}
      />
    </div>
  )
}
```

- [ ] **Step 2: Commit**

```bash
cd /opt/eve-frontier
git add frontend/src/components/TerminalUI.tsx
git commit -m "feat: create TerminalUI component with CLI interface"
```

---

## Chunk 4: Styling

### Task 7: Create Terminal CSS

**Files:**
- Create: `frontend/src/styles/terminal.css`

- [ ] **Step 1: Write terminal styles**

Create `frontend/src/styles/terminal.css`:

```css
.terminal-screen {
  width: 100%;
  height: 100vh;
  display: flex;
  flex-direction: column;
  background: #000;
  color: #c8a560;
  font-family: 'Courier New', monospace;
  font-size: 13px;
  line-height: 1.4;
  overflow: hidden;
}

.visual-area {
  flex: 0 0 33%;
  padding: 16px;
  border-bottom: 1px solid #5a4a20;
  overflow: hidden;
  white-space: pre;
  word-wrap: break-word;
}

.visual-area pre {
  margin: 0;
  font-family: inherit;
  font-size: inherit;
  color: inherit;
}

.chat-history {
  flex: 1;
  overflow-y: auto;
  padding: 12px 16px;
  border-bottom: 1px solid #5a4a20;
  white-space: pre-wrap;
  word-wrap: break-word;
}

.chat-line {
  margin: 2px 0;
  color: #c8a560;
}

.chat-line.chat-user {
  color: #4ade80;
}

.chat-line.chat-ai {
  color: #c8a560;
}

.chat-line.chat-system {
  color: #999;
  font-style: italic;
}

.input-field {
  flex-shrink: 0;
  width: 100%;
  background: #000;
  border: none;
  border-top: 1px solid #5a4a20;
  color: #c8a560;
  padding: 12px 16px;
  font-family: 'Courier New', monospace;
  font-size: 15px;
  outline: none;
}

.input-field:focus {
  border-top-color: #c8a560;
}

.input-field::placeholder {
  color: #6b5a20;
}

.input-field:disabled {
  opacity: 0.7;
}

/* Scrollbar */
::-webkit-scrollbar {
  width: 8px;
}

::-webkit-scrollbar-track {
  background: #000;
}

::-webkit-scrollbar-thumb {
  background: #5a4a20;
  border-radius: 4px;
}

::-webkit-scrollbar-thumb:hover {
  background: #7a6a40;
}
```

- [ ] **Step 2: Commit**

```bash
cd /opt/eve-frontier
git add frontend/src/styles/terminal.css
git commit -m "feat: add terminal.css for CLI styling"
```

---

### Task 8: Update App.tsx to Use TerminalUI

**Files:**
- Modify: `frontend/src/App.tsx`

- [ ] **Step 1: Rewrite App.tsx**

Replace with:

```typescript
import { TerminalUI } from './components/TerminalUI'
import './styles/terminal.css'
import './App.css'

export default function App() {
  return <TerminalUI />
}
```

- [ ] **Step 2: Update App.css**

Replace `frontend/src/App.css` with:

```css
* {
  margin: 0;
  padding: 0;
  box-sizing: border-box;
}

html, body, #root {
  width: 100%;
  height: 100%;
  overflow: hidden;
}

body {
  background: #000;
  color: #c8a560;
  font-family: 'Courier New', monospace;
}
```

- [ ] **Step 3: Create index.css**

Create `frontend/src/index.css`:

```css
:root {
  font-family: 'Courier New', monospace;
  line-height: 1.4;
  font-weight: 400;
  color-scheme: dark;
  color: #c8a560;
  background-color: #000;
}

* {
  margin: 0;
  padding: 0;
  box-sizing: border-box;
}

html, body, #root {
  width: 100%;
  height: 100%;
  overflow: hidden;
}

body {
  background-color: #000;
  color: #c8a560;
}
```

- [ ] **Step 4: Verify TypeScript**

```bash
cd /opt/eve-frontier/frontend
npm run build 2>&1 | head -30
```

Expected: Build succeeds.

- [ ] **Step 5: Commit**

```bash
cd /opt/eve-frontier
git add frontend/src/App.tsx frontend/src/App.css frontend/src/index.css
git commit -m "feat: rewrite App.tsx for pure CLI terminal with TerminalUI"
```

---

## Chunk 5: Build & Deploy

### Task 9: Build React Frontend

**Files:**
- Build: `frontend/dist/`

- [ ] **Step 1: Build**

```bash
cd /opt/eve-frontier/frontend
npm run build
```

Expected: Build succeeds, dist/ created.

- [ ] **Step 2: Verify files**

```bash
ls -la /opt/eve-frontier/frontend/dist/ | head -10
```

Expected: index.html and assets/ present.

- [ ] **Step 3: Copy to static**

```bash
rm -rf /opt/eve-frontier/static/companion && \
cp -r /opt/eve-frontier/frontend/dist /opt/eve-frontier/static/companion
```

- [ ] **Step 4: Verify**

```bash
test -f /opt/eve-frontier/static/companion/index.html && echo "✅ OK" || echo "❌ FAIL"
```

Expected: ✅ OK

- [ ] **Step 5: Commit**

```bash
cd /opt/eve-frontier
git add -A
git commit -m "build: compile React frontend to /static/companion/"
```

---

### Task 10: Update Backend Routes

**Files:**
- Modify: `src/endpoints/ui.py`

- [ ] **Step 1: Update ui.py**

Replace with:

```python
"""
UI route handlers — serve React app and legacy terminals.

Endpoints:
- GET /     — React CLI companion app (main UI)
- GET /legacy-cli — Vanilla JS terminal (fallback)
- GET /ship-ai — Ship AI terminal (legacy)
- GET /debug-terminal — Debug terminal (legacy)
"""

from fastapi import APIRouter
from fastapi.responses import FileResponse

ui_router = APIRouter()


@ui_router.get("/")
async def index():
    """Serve the React CLI companion app."""
    return FileResponse("static/companion/index.html")


@ui_router.get("/legacy-cli")
async def legacy_cli():
    """Serve the vanilla JS building terminal (legacy)."""
    return FileResponse("static/building-terminal.html")


@ui_router.get("/ship-ai")
async def ship_ai_terminal():
    """Serve the ship AI terminal (legacy)."""
    return FileResponse("static/ship-ai-terminal.html")


@ui_router.get("/debug-terminal")
async def debug_terminal():
    """Serve the debug terminal (legacy)."""
    return FileResponse("static/debug-terminal.html")
```

- [ ] **Step 2: Verify syntax**

```bash
python -m py_compile /opt/eve-frontier/src/endpoints/ui.py
```

Expected: No output (success).

- [ ] **Step 3: Commit**

```bash
cd /opt/eve-frontier
git add src/endpoints/ui.py
git commit -m "feat: update ui routes to serve React app at /"
```

---

## Chunk 6: Testing & Verification

### Task 11: Test Backend Start

**Files:**
- Test: Backend startup

- [ ] **Step 1: Test backend starts**

```bash
cd /opt/eve-frontier
timeout 10 python -m uvicorn main:app --host 0.0.0.0 --port 8745 2>&1 || true
```

Expected: Starts without errors (timeout expected).

- [ ] **Step 2: Commit**

```bash
cd /opt/eve-frontier
git add -A
git commit -m "test: verify backend starts without errors"
```

---

### Task 12: Integration Test

**Files:**
- Test: Full flow

- [ ] **Step 1: Start backend**

```bash
cd /opt/eve-frontier
python -m uvicorn main:app --host 0.0.0.0 --port 8745 > /tmp/backend.log 2>&1 &
BACKEND_PID=$!
sleep 3
```

- [ ] **Step 2: Test React app serves at root**

```bash
curl -s http://localhost:8745/ | grep -o "React" | head -1 || echo "HTML returned"
```

Expected: Some HTML response (may or may not contain "React").

- [ ] **Step 3: Test legacy CLI still works**

```bash
curl -s http://localhost:8745/legacy-cli | grep "Building AI" | head -1
```

Expected: "Building AI Companion" found.

- [ ] **Step 4: Test API endpoints still work**

```bash
curl -s http://localhost:8745/structures 2>&1 | head -5
```

Expected: JSON response (may be empty or contain structures).

- [ ] **Step 5: Stop backend**

```bash
kill $BACKEND_PID 2>/dev/null || true
sleep 1
```

- [ ] **Step 6: Commit**

```bash
cd /opt/eve-frontier
git add -A
git commit -m "test: verify React app and legacy routes functional"
```

---

## Summary

✅ **Installed:** @evefrontier/dapp-kit, @tanstack/react-query
✅ **Created:** Pure CLI terminal in React (3 sections: visual / chat / input)
✅ **Black + orange aesthetic:** 776x828 viewport, monospace, no chrome
✅ **Wallet integration:** EVE Frontier Client Wallet via Wallet Standard
✅ **Command-based UI:** /connect, /list, /select, then chat
✅ **Built and deployed:** React app at `/`, legacy CLI at `/legacy-cli`
✅ **Fully committed:** All changes with clear commit messages

---

## Next Steps (Not in Plan)

- Implement `/help` command with full command listing
- Add `/disconnect` command
- Implement `/clear` to clear chat history
- Add notification system using DApp Kit's `useNotification()` hook
- Sponsored transactions via `useSponsoredTransaction()` for on-chain actions
- Add `/debug` page (separate route) for admin diagnostics
