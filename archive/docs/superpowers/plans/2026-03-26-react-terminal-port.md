# React Terminal Port Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Port the vanilla JS building terminal (app-building.js, info-panel.js, panel-formatter.js) to React components with perfect visual/functional parity. Make the React app the single source of truth for the terminal interface.

**Architecture:** The vanilla terminal uses ES6 classes (BuildingAITerminal, InfoPanel, ToolOutputFormatter) connected via SSE. The React version replaces these with: (1) Custom hooks for SSE, data fetching, and state (useSSEChat, useCharacterData, useToolOutput); (2) React components for visual rendering (BaselinePanel, InfoPanel, ToolOutputFormatter, VisualArea); (3) TypeScript types for all tool outputs; (4) CSS animations ported as-is for identical visual behavior.

**Tech Stack:** React 19 + TypeScript, @tanstack/react-query, @evefrontier/dapp-kit, Vite build system, vanilla CSS (no CSS-in-JS).

**Timeline:** ~6 hours focused work. Frequent commits (every task).

---

## Chunk 1: Setup & Data Types

### Task 1: Create TypeScript types for all tool outputs

**Files:**
- Create: `src/types/terminal.ts`

**Steps:**

- [ ] **Step 1: Write the types file with all tool output interfaces**

```typescript
// src/types/terminal.ts

/**
 * All tool output types and baseline panel data
 */

export interface BaselinePanelData {
  crudVersion: string;
  signature: string;
  shellName: string;
  accessLevel: string;
  assemblySignature: string;
  location: string;
}

export interface SystemIntelData {
  system: string;
  starClass: string;
  minTemp: string;
  planets: string;
  kills24h: string;
  gates: string;
}

export interface ThreatAssessmentData {
  level: string;
  topAggressor: string;
  dominantShip: string;
  escalation: string;
}

export interface PilotProfileData {
  visits: string;
  firstVisit: string;
  lastVisit: string;
  tier: string;
  [key: string]: string;
}

export interface MemorySearchData {
  query: string;
  results: string[];
}

export interface MemorySummaryData {
  attacks: string;
  contacts: string;
  docking: string;
  [key: string]: string;
}

export type ToolOutputData =
  | BaselinePanelData
  | SystemIntelData
  | ThreatAssessmentData
  | PilotProfileData
  | MemorySearchData
  | MemorySummaryData;

export type ToolType =
  | 'baseline'
  | 'system_intel'
  | 'threat_assessment'
  | 'pilot_profile'
  | 'memory_search'
  | 'memory_summary';

export interface ToolResult {
  tool_name: ToolType;
  data: ToolOutputData;
}

export interface SSEMessage {
  text?: string;
  tool?: string;
  tool_result?: ToolResult;
  visual?: string;
}

export interface CharacterData {
  wallet: string;
  character: {
    id: number;
    name: string;
  };
  owned_structures: {
    [key: string]: string[];
  };
  total_structures: number;
}
```

- [ ] **Step 2: Verify types compile**

Run: `cd /opt/eve-frontier/frontend && npx tsc --noEmit`

Expected: No errors

- [ ] **Step 3: Commit**

```bash
cd /opt/eve-frontier
git add docs/superpowers/plans/2026-03-26-react-terminal-port.md
git add frontend/src/types/terminal.ts
git commit -m "feat: add TypeScript types for terminal tool outputs and SSE messages"
```

---

### Task 2: Create directory structure and CSS files

**Files:**
- Copy: `/static/styles/info-panel.css` → `src/styles/info-panel.css`
- Copy: `/static/styles/panel-formatter.css` → `src/styles/panel-formatter.css`
- Modify: `src/styles/terminal.css` (merge building-terminal.css styles)

**Steps:**

- [ ] **Step 1: Copy CSS files from vanilla to React**

```bash
cd /opt/eve-frontier/frontend
cp ../static/styles/info-panel.css src/styles/
cp ../static/styles/panel-formatter.css src/styles/
```

- [ ] **Step 2: Create merged terminal.css**

```css
/* src/styles/terminal.css */
* {
  margin: 0;
  padding: 0;
  box-sizing: border-box;
}

body {
  background: #000;
  color: #c8a560;
  font-family: 'Courier New', monospace;
  overflow: hidden;
}

.terminal-screen {
  width: 100%;
  height: calc(100vh - 50px);
  max-height: 828px;
  display: flex;
  flex-direction: column;
  overflow: hidden;
}

#visual-area {
  flex: 0 0 33%;
  padding: 16px;
  border-bottom: 1px solid #5a4a20;
  overflow: hidden;
  font-size: 13px;
  line-height: 1.4;
  white-space: pre-wrap;
  word-wrap: break-word;
}

#chat-history {
  flex: 1;
  overflow-y: auto;
  padding: 12px 16px;
  border-bottom: 1px solid #5a4a20;
  font-size: 13px;
  line-height: 1.4;
  white-space: pre-wrap;
  word-wrap: break-word;
}

#input-field {
  flex-shrink: 0;
  background: #000;
  border: none;
  border-top: 1px solid #5a4a20;
  color: #c8a560;
  padding: 12px 16px;
  font-family: 'Courier New', monospace;
  font-size: 15px;
  outline: none;
}

#input-field:focus {
  border-top-color: #c8a560;
}

#input-field::placeholder {
  color: #6b5a20;
}
```

- [ ] **Step 3: Verify files exist**

Run: `ls -lh /opt/eve-frontier/frontend/src/styles/`

Expected: `info-panel.css`, `panel-formatter.css`, `terminal.css` all present

- [ ] **Step 4: Commit**

```bash
cd /opt/eve-frontier
git add frontend/src/styles/info-panel.css
git add frontend/src/styles/panel-formatter.css
git add frontend/src/styles/terminal.css
git commit -m "feat: port terminal CSS from vanilla JS to React"
```

---

## Chunk 2: Custom Hooks (SSE, Data Fetching, State)

### Task 3: Create useSSEChat hook

**Files:**
- Create: `src/hooks/useSSEChat.ts`

**Steps:**

- [ ] **Step 1: Write hook with SSE connection logic**

```typescript
// src/hooks/useSSEChat.ts

import { useCallback, useEffect, useRef } from 'react';

interface SSEMessage {
  text?: string;
  tool?: string;
  tool_result?: {
    tool_name: string;
    data: any;
  };
  visual?: string;
}

interface UseSSEChatOptions {
  serverToken: string;
  onMessage?: (msg: SSEMessage) => void;
  onError?: (err: Error) => void;
  onConnected?: () => void;
}

/**
 * Hook to manage SSE connection to /chat endpoint
 * Automatically reconnects on error with 5s backoff
 */
export function useSSEChat(options: UseSSEChatOptions) {
  const { serverToken, onMessage, onError, onConnected } = options;
  const eventSourceRef = useRef<EventSource | null>(null);
  const reconnectTimeoutRef = useRef<NodeJS.Timeout | null>(null);

  const connect = useCallback(() => {
    if (eventSourceRef.current) {
      return;
    }

    try {
      const url = new URL('/chat', window.location.origin);
      const eventSource = new EventSource(url.toString());

      eventSource.addEventListener('message', (event) => {
        try {
          const data = JSON.parse(event.data);
          onMessage?.(data);
        } catch (parseErr) {
          console.error('Failed to parse SSE message:', event.data);
        }
      });

      eventSource.addEventListener('error', () => {
        console.warn('SSE connection error, reconnecting in 5s...');
        eventSource.close();
        eventSourceRef.current = null;
        reconnectTimeoutRef.current = setTimeout(connect, 5000);
        onError?.(new Error('SSE connection lost'));
      });

      eventSource.addEventListener('open', () => {
        console.log('Connected to SSE /chat endpoint');
        onConnected?.();
      });

      eventSourceRef.current = eventSource;
    } catch (err) {
      const error = err instanceof Error ? err : new Error(String(err));
      onError?.(error);
    }
  }, [onMessage, onError, onConnected]);

  const disconnect = useCallback(() => {
    if (eventSourceRef.current) {
      eventSourceRef.current.close();
      eventSourceRef.current = null;
    }
    if (reconnectTimeoutRef.current) {
      clearTimeout(reconnectTimeoutRef.current);
      reconnectTimeoutRef.current = null;
    }
  }, []);

  useEffect(() => {
    connect();
    return () => disconnect();
  }, [connect, disconnect]);

  return { isConnected: !!eventSourceRef.current, disconnect };
}
```

- [ ] **Step 2: Verify syntax with TypeScript compiler**

Run: `cd /opt/eve-frontier/frontend && npx tsc --noEmit src/hooks/useSSEChat.ts`

Expected: No errors

- [ ] **Step 3: Commit**

```bash
cd /opt/eve-frontier
git add frontend/src/hooks/useSSEChat.ts
git commit -m "feat: add useSSEChat hook for SSE connection and message handling"
```

---

### Task 4: Create useCharacterData hook

**Files:**
- Create: `src/hooks/useCharacterData.ts`

**Steps:**

- [ ] **Step 1: Write hook for fetching character data**

```typescript
// src/hooks/useCharacterData.ts

import { useQuery } from '@tanstack/react-query';

interface CharacterResponse {
  wallet: string;
  character: {
    id: number;
    name: string;
  };
  owned_structures: {
    [key: string]: string[];
  };
  total_structures: number;
}

/**
 * Fetch character data from /player/{wallet}/characters endpoint
 * Returns character name, owned structures, and metadata
 */
export function useCharacterData(walletAddress: string | null) {
  return useQuery({
    queryKey: ['character', walletAddress],
    queryFn: async () => {
      if (!walletAddress) {
        return null;
      }

      const response = await fetch(
        `${window.location.origin}/player/${walletAddress}/characters`
      );

      if (!response.ok) {
        throw new Error(`Failed to fetch character: HTTP ${response.status}`);
      }

      return (await response.json()) as CharacterResponse;
    },
    enabled: !!walletAddress,
    staleTime: 1000 * 60 * 5, // 5 minutes
    retry: 2,
  });
}
```

- [ ] **Step 2: Verify TypeScript**

Run: `cd /opt/eve-frontier/frontend && npx tsc --noEmit src/hooks/useCharacterData.ts`

Expected: No errors

- [ ] **Step 3: Commit**

```bash
cd /opt/eve-frontier
git add frontend/src/hooks/useCharacterData.ts
git commit -m "feat: add useCharacterData hook for fetching player character from API"
```

---

### Task 5: Create useToolOutput hook

**Files:**
- Create: `src/hooks/useToolOutput.ts`

**Steps:**

- [ ] **Step 1: Write hook for managing tool output state**

```typescript
// src/hooks/useToolOutput.ts

import { useState, useCallback } from 'react';
import { ToolType, ToolOutputData } from '../types/terminal';

interface ToolOutputState {
  toolType: ToolType | null;
  data: ToolOutputData | null;
  isAnimating: boolean;
}

/**
 * Manages current tool output display state
 * Handles animation queueing when rapid tool updates arrive
 */
export function useToolOutput() {
  const [current, setCurrent] = useState<ToolOutputState>({
    toolType: null,
    data: null,
    isAnimating: false,
  });

  const [queued, setQueued] = useState<ToolOutputState | null>(null);

  const display = useCallback((toolType: ToolType, data: ToolOutputData) => {
    setCurrent((prev) => {
      if (prev.isAnimating) {
        // Queue for later display
        setQueued({ toolType, data, isAnimating: false });
        return prev;
      }
      return { toolType, data, isAnimating: true };
    });
  }, []);

  const finishAnimation = useCallback(() => {
    setCurrent((prev) => {
      if (queued) {
        // Display queued content
        setQueued(null);
        return { ...queued, isAnimating: true };
      }
      return { ...prev, isAnimating: false };
    });
  }, [queued]);

  return {
    current,
    queued,
    display,
    finishAnimation,
  };
}
```

- [ ] **Step 2: Verify TypeScript**

Run: `cd /opt/eve-frontier/frontend && npx tsc --noEmit src/hooks/useToolOutput.ts`

Expected: No errors

- [ ] **Step 3: Commit**

```bash
cd /opt/eve-frontier
git add frontend/src/hooks/useToolOutput.ts
git commit -m "feat: add useToolOutput hook for managing panel animation state"
```

---

## Chunk 3: Visual Components

### Task 6: Create BaselinePanel component

**Files:**
- Create: `src/components/BaselinePanel.tsx`

**Steps:**

- [ ] **Step 1: Write BaselinePanel component**

```typescript
// src/components/BaselinePanel.tsx

import { BaselinePanelData } from '../types/terminal';

interface BaselinePanelProps {
  data: BaselinePanelData;
}

const DIVIDER = '═════════════════════════════════════════════════════════════';

/**
 * Displays baseline player information panel
 * Shows wallet, character name, access level, etc.
 * All missing fields display as [REDACTED]
 */
export function BaselinePanel({ data }: BaselinePanelProps) {
  const fields = [
    { label: 'CRUD - Version', value: data.crudVersion || '[REDACTED]' },
    { label: 'SIGNATURE', value: data.signature || '[REDACTED]' },
    { label: 'SHELL NAME', value: data.shellName || '[REDACTED]' },
    { label: 'ACCESS LEVEL', value: data.accessLevel || '[REDACTED]' },
    { label: 'ASSEMBLY SIGNATURE', value: data.assemblySignature || '[REDACTED]' },
    { label: 'LOCATION', value: data.location || '[REDACTED]' },
  ];

  const padLabel = (label: string): string => {
    const padding = 38;
    return label.padEnd(padding, ' ');
  };

  const truncateValue = (value: string, maxLen: number = 30): string => {
    return value.length > maxLen ? value.substring(0, maxLen - 3) + '...' : value;
  };

  const lines = [
    DIVIDER,
    ...fields.map((f) => padLabel(f.label) + truncateValue(f.value)),
    DIVIDER,
  ];

  return (
    <pre style={{ whiteSpace: 'pre-wrap', wordWrap: 'break-word' }}>
      {lines.join('\n')}
    </pre>
  );
}
```

- [ ] **Step 2: Verify component syntax**

Run: `cd /opt/eve-frontier/frontend && npx tsc --noEmit src/components/BaselinePanel.tsx`

Expected: No errors

- [ ] **Step 3: Commit**

```bash
cd /opt/eve-frontier
git add frontend/src/components/BaselinePanel.tsx
git commit -m "feat: add BaselinePanel component for displaying player info"
```

---

### Task 7: Create ToolOutputFormatter component

**Files:**
- Create: `src/components/ToolOutputFormatter.tsx`

**Steps:**

- [ ] **Step 1: Write formatter component**

```typescript
// src/components/ToolOutputFormatter.tsx

import {
  ToolType,
  SystemIntelData,
  ThreatAssessmentData,
  PilotProfileData,
  MemorySearchData,
  MemorySummaryData,
} from '../types/terminal';

const DIVIDER = '═════════════════════════════════════════════════════════════';

interface ToolOutputFormatterProps {
  toolType: ToolType;
  data: any;
}

const padLabel = (label: string): string => {
  const padding = 38;
  return label.padEnd(padding, ' ');
};

const truncateValue = (value: string, maxLen: number = 30): string => {
  return value.length > maxLen ? value.substring(0, maxLen - 3) + '...' : value;
};

function formatSystemIntel(data: SystemIntelData): string {
  const fields = [
    { label: 'SYSTEM:', value: data.system || '[REDACTED]' },
    { label: 'STAR CLASS:', value: data.starClass || '[REDACTED]' },
    { label: 'MIN TEMP:', value: data.minTemp || '[REDACTED]' },
    { label: 'PLANETS:', value: data.planets || '[REDACTED]' },
    { label: 'KILLS (24H):', value: data.kills24h || '[REDACTED]' },
    { label: 'GATES:', value: data.gates || '[REDACTED]' },
  ];

  const lines = [
    DIVIDER,
    ...fields.map((f) => padLabel(f.label) + truncateValue(f.value)),
    DIVIDER,
  ];

  return lines.join('\n');
}

function formatThreat(data: ThreatAssessmentData): string {
  const fields = [
    { label: 'THREAT LEVEL:', value: data.level || '[REDACTED]' },
    { label: 'TOP AGGRESSOR:', value: data.topAggressor || '[REDACTED]' },
    { label: 'DOMINANT SHIP:', value: data.dominantShip || '[REDACTED]' },
    { label: 'ESCALATION:', value: data.escalation || '[REDACTED]' },
    { label: '', value: '' },
    { label: '', value: '' },
  ];

  const lines = [
    DIVIDER,
    ...fields.map((f) =>
      f.label ? padLabel(f.label) + truncateValue(f.value) : ''
    ),
    DIVIDER,
  ];

  return lines.join('\n');
}

function formatPilotProfile(data: PilotProfileData): string {
  const fields = [
    { label: 'VISITS:', value: data.visits || '[REDACTED]' },
    { label: 'FIRST VISIT:', value: data.firstVisit || '[REDACTED]' },
    { label: 'LAST VISIT:', value: data.lastVisit || '[REDACTED]' },
    { label: 'TIER:', value: data.tier || '[REDACTED]' },
    { label: '', value: '' },
    { label: '', value: '' },
  ];

  const lines = [
    DIVIDER,
    ...fields.map((f) =>
      f.label ? padLabel(f.label) + truncateValue(f.value) : ''
    ),
    DIVIDER,
  ];

  return lines.join('\n');
}

function formatMemorySearch(data: MemorySearchData): string {
  const results = data.results || [];
  const lines = [
    DIVIDER,
    padLabel('QUERY:') + truncateValue(data.query || '[REDACTED]'),
    padLabel('RESULTS:'),
    ...results.slice(0, 3).map((r) => '  • ' + truncateValue(r)),
    ...(results.length > 3 ? ['  ...'] : []),
    DIVIDER,
  ];

  return lines.join('\n');
}

function formatMemorySummary(data: MemorySummaryData): string {
  const fields = [
    { label: 'ATTACKS:', value: data.attacks || '[REDACTED]' },
    { label: 'CONTACTS:', value: data.contacts || '[REDACTED]' },
    { label: 'DOCKING:', value: data.docking || '[REDACTED]' },
    { label: '', value: '' },
    { label: '', value: '' },
    { label: '', value: '' },
  ];

  const lines = [
    DIVIDER,
    ...fields.map((f) =>
      f.label ? padLabel(f.label) + truncateValue(f.value) : ''
    ),
    DIVIDER,
  ];

  return lines.join('\n');
}

/**
 * Formats tool output into ASCII panel text
 * Handles all tool types: baseline, system_intel, threat, pilot, memory
 */
export function ToolOutputFormatter({
  toolType,
  data,
}: ToolOutputFormatterProps) {
  let formatted = '';

  switch (toolType) {
    case 'system_intel':
      formatted = formatSystemIntel(data as SystemIntelData);
      break;
    case 'threat_assessment':
      formatted = formatThreat(data as ThreatAssessmentData);
      break;
    case 'pilot_profile':
      formatted = formatPilotProfile(data as PilotProfileData);
      break;
    case 'memory_search':
      formatted = formatMemorySearch(data as MemorySearchData);
      break;
    case 'memory_summary':
      formatted = formatMemorySummary(data as MemorySummaryData);
      break;
    default:
      formatted = DIVIDER + '\n[UNKNOWN TOOL TYPE]\n' + DIVIDER;
  }

  return (
    <pre style={{ whiteSpace: 'pre-wrap', wordWrap: 'break-word' }}>
      {formatted}
    </pre>
  );
}
```

- [ ] **Step 2: Verify TypeScript**

Run: `cd /opt/eve-frontier/frontend && npx tsc --noEmit src/components/ToolOutputFormatter.tsx`

Expected: No errors

- [ ] **Step 3: Commit**

```bash
cd /opt/eve-frontier
git add frontend/src/components/ToolOutputFormatter.tsx
git commit -m "feat: add ToolOutputFormatter component for all tool output types"
```

---

### Task 8: Create InfoPanel component with animations

**Files:**
- Create: `src/components/InfoPanel.tsx`

**Steps:**

- [ ] **Step 1: Write InfoPanel with animation state management**

```typescript
// src/components/InfoPanel.tsx

import { useState, useEffect } from 'react';
import { ToolType, ToolOutputData } from '../types/terminal';
import { BaselinePanel } from './BaselinePanel';
import { ToolOutputFormatter } from './ToolOutputFormatter';
import '../styles/info-panel.css';

interface InfoPanelProps {
  currentToolType: ToolType | null;
  currentData: ToolOutputData | null;
  isAnimating: boolean;
  onAnimationEnd: () => void;
  useTypingEffect?: boolean;
}

/**
 * Animated visual panel that displays tool outputs with slide transitions
 * - Slide out current content (250ms)
 * - Swap content
 * - Slide in new content (500ms)
 * Total: 750ms animation cycle
 */
export function InfoPanel({
  currentToolType,
  currentData,
  isAnimating,
  onAnimationEnd,
  useTypingEffect = false,
}: InfoPanelProps) {
  const [displayContent, setDisplayContent] = useState<React.ReactNode>(null);
  const [isSliding, setIsSliding] = useState(false);

  useEffect(() => {
    if (!isAnimating || !currentToolType || !currentData) {
      setDisplayContent(getContentComponent(currentToolType, currentData));
      setIsSliding(false);
      return;
    }

    // Start slide-out animation
    setIsSliding(true);

    const slideOutTimer = setTimeout(() => {
      // Swap content
      setDisplayContent(getContentComponent(currentToolType, currentData));

      // Start slide-in animation
      const slideInTimer = setTimeout(() => {
        setIsSliding(false);
        onAnimationEnd();
      }, 500);

      return () => clearTimeout(slideInTimer);
    }, 250);

    return () => clearTimeout(slideOutTimer);
  }, [currentToolType, currentData, isAnimating, onAnimationEnd]);

  const wrapperClass = isSliding ? 'slide-out-right' : '';

  return (
    <div id="visual-area" className={wrapperClass}>
      {displayContent}
    </div>
  );
}

function getContentComponent(
  toolType: ToolType | null,
  data: ToolOutputData | null
): React.ReactNode {
  if (!toolType || !data) {
    return <BaselinePanel data={{
      crudVersion: 'CRUD - Version',
      signature: '[REDACTED]',
      shellName: '[REDACTED]',
      accessLevel: '[REDACTED]',
      assemblySignature: '[REDACTED]',
      location: '[REDACTED]'
    }} />;
  }

  if (toolType === 'baseline') {
    return <BaselinePanel data={data as any} />;
  }

  return <ToolOutputFormatter toolType={toolType} data={data} />;
}
```

- [ ] **Step 2: Verify TypeScript**

Run: `cd /opt/eve-frontier/frontend && npx tsc --noEmit src/components/InfoPanel.tsx`

Expected: No errors

- [ ] **Step 3: Commit**

```bash
cd /opt/eve-frontier
git add frontend/src/components/InfoPanel.tsx
git commit -m "feat: add InfoPanel component with CSS animation support"
```

---

### Task 9: Create VisualArea container component

**Files:**
- Create: `src/components/VisualArea.tsx`

**Steps:**

- [ ] **Step 1: Write VisualArea wrapper component**

```typescript
// src/components/VisualArea.tsx

import { ReactNode } from 'react';
import '../styles/terminal.css';

interface VisualAreaProps {
  children: ReactNode;
}

/**
 * Container for the visual panel area (top 33% of terminal)
 * Provides consistent styling and layout for all panel displays
 */
export function VisualArea({ children }: VisualAreaProps) {
  return (
    <div id="visual-area" style={{
      flex: '0 0 33%',
      padding: '16px',
      borderBottom: '1px solid #5a4a20',
      overflow: 'hidden',
      fontSize: '13px',
      lineHeight: '1.4',
      whiteSpace: 'pre-wrap',
      wordWrap: 'break-word',
    }}>
      {children}
    </div>
  );
}
```

- [ ] **Step 2: Verify TypeScript**

Run: `cd /opt/eve-frontier/frontend && npx tsc --noEmit src/components/VisualArea.tsx`

Expected: No errors

- [ ] **Step 3: Commit**

```bash
cd /opt/eve-frontier
git add frontend/src/components/VisualArea.tsx
git commit -m "feat: add VisualArea container component for panel layout"
```

---

## Chunk 4: Integration

### Task 10: Integrate visual panels into TerminalUI

**Files:**
- Modify: `src/components/TerminalUI.tsx`

**Steps:**

- [ ] **Step 1: Update TerminalUI to use new components**

Find the TerminalUI component and modify the return statement to include the visual panels. Replace the existing JSX structure with:

```typescript
import { InfoPanel } from './InfoPanel';
import { useCharacterData } from '../hooks/useCharacterData';
import { useSSEChat } from '../hooks/useSSEChat';
import { useToolOutput } from '../hooks/useToolOutput';

// Inside TerminalUI component, add these hooks:

const { data: characterData, isLoading: isLoadingCharacter } = useCharacterData(walletAddress);
const { current: toolOutput, queued: queuedOutput, display: displayToolOutput, finishAnimation: finishAnimation } = useToolOutput();
const SERVER_TOKEN = "5740edb0fb25a051db4a932c3622bd69ce47d487bc501f2bde4cb7e19907c454";

const handleSSEMessage = (msg: any) => {
  if (msg.text) {
    addLog(msg.text, 'ai');
  }
  if (msg.tool_result) {
    const toolName = msg.tool_result.tool_name || msg.tool;
    const toolData = msg.tool_result.data || msg.tool_result;
    displayToolOutput(toolName, toolData);
  }
};

useSSEChat({
  serverToken: SERVER_TOKEN,
  onMessage: handleSSEMessage,
});

// Update baseline panel display on character load
useEffect(() => {
  if (characterData && walletAddress) {
    displayToolOutput('baseline', {
      crudVersion: 'CRUD - Version',
      signature: walletAddress,
      shellName: characterData.character?.name || '[REDACTED]',
      accessLevel: '[REDACTED]',
      assemblySignature: '[REDACTED]',
      location: '[REDACTED]',
    });
  }
}, [characterData, walletAddress, displayToolOutput]);

// In the return JSX, add before #chat-history:
<InfoPanel
  currentToolType={toolOutput.toolType}
  currentData={toolOutput.data}
  isAnimating={toolOutput.isAnimating}
  onAnimationEnd={finishAnimation}
/>
```

- [ ] **Step 2: Run TypeScript check**

Run: `cd /opt/eve-frontier/frontend && npx tsc --noEmit`

Expected: No errors

- [ ] **Step 3: Test build**

Run: `cd /opt/eve-frontier/frontend && npm run build`

Expected: Build succeeds with no errors

- [ ] **Step 4: Commit**

```bash
cd /opt/eve-frontier
git add frontend/src/components/TerminalUI.tsx
git commit -m "feat: integrate visual panels and SSE hooks into TerminalUI"
```

---

### Task 11: Update App.tsx and main entry point

**Files:**
- Modify: `src/App.tsx`, `src/main.tsx`, `index.html`

**Steps:**

- [ ] **Step 1: Ensure App.tsx wraps TerminalUI correctly**

Verify `src/App.tsx` has:

```typescript
import { TerminalUI } from './components/TerminalUI'
import './styles/terminal.css'
import './App.css'

export default function App() {
  return <TerminalUI />
}
```

- [ ] **Step 2: Verify index.html references correct root element**

Check `frontend/index.html` has:

```html
<!doctype html>
<html lang="en">
  <head>
    <meta charset="UTF-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1.0" />
    <title>Building AI Terminal</title>
  </head>
  <body>
    <div id="root"></div>
    <script type="module" src="/src/main.tsx"></script>
  </body>
</html>
```

- [ ] **Step 3: Verify Vite config deploys to /static/companion/**

Check `frontend/vite.config.ts`:

```typescript
export default defineConfig({
  plugins: [react()],
  base: '/static/companion/',
  server: {
    host: '0.0.0.0',
    port: 5173,
  },
})
```

- [ ] **Step 4: Build and verify output**

Run: `cd /opt/eve-frontier/frontend && npm run build`

Expected: Build completes, `/frontend/dist/` contains `index.html` and JS bundles

- [ ] **Step 5: Copy built files to static location**

Run: `cp -r /opt/eve-frontier/frontend/dist/* /opt/eve-frontier/static/companion/`

Expected: Files copied successfully

- [ ] **Step 6: Commit**

```bash
cd /opt/eve-frontier
git add frontend/index.html
git add frontend/src/App.tsx
git add frontend/src/main.tsx
git add frontend/vite.config.ts
git commit -m "feat: finalize React app entry point and Vite build configuration"
```

---

## Chunk 5: Final Polish & Testing

### Task 12: Test end-to-end and verify visual parity

**Files:**
- None (testing only)

**Steps:**

- [ ] **Step 1: Start backend server**

```bash
cd /opt/eve-frontier
python main.py
```

Expected: Server starts on http://localhost:8745

- [ ] **Step 2: Open React app in browser**

Navigate to: `http://localhost:8745/`

Expected: React app loads, shows terminal UI

- [ ] **Step 3: Test wallet connection (if DApp Kit works)**

Click connect button in terminal

Expected: Wallet connects, character data fetches, baseline panel displays with SIGNATURE + SHELL_NAME filled

- [ ] **Step 4: Test SSE connection by sending a message**

Type a message and hit enter

Expected: Message sent to backend, SSE connection established, responses stream in

- [ ] **Step 5: Test tool output display**

Trigger a tool output from the backend (via chat command that calls a tool)

Expected: Visual panel updates with animation, shows formatted tool output

- [ ] **Step 6: Verify visual styling matches vanilla**

Compare `/legacy-cli` (vanilla) vs `/` (React)

Check:
- Colors (#c8a560 gold, #000 black)
- Font (Courier New monospace)
- Panel dividers (═══...)
- Layout (33% visual, 67% chat, input at bottom)
- Animation smoothness (250ms slide-out, 500ms slide-in)

Expected: Visuals are identical or very close

- [ ] **Step 7: Final commit with test verification**

```bash
cd /opt/eve-frontier
git add -A
git commit -m "test: verify React terminal visual and functional parity with vanilla version"
```

---

## Summary

**What's been built:**
- ✅ TypeScript types for all tool outputs and SSE messages
- ✅ Custom hooks: useSSEChat, useCharacterData, useToolOutput
- ✅ React components: BaselinePanel, ToolOutputFormatter, InfoPanel, VisualArea
- ✅ CSS animations ported from vanilla
- ✅ TerminalUI integration with all new components
- ✅ Build and deployment configured
- ✅ End-to-end tested

**Result:**
Single React app at `/` with:
- DApp Kit wallet integration
- SSE streaming from backend
- Visual panel with all tool output types
- Pixel-perfect terminal styling
- No legacy CLI—React is the single source of truth

**Next steps after execution:**
- Decomission `/legacy-cli` endpoint from ui.py
- Update documentation to point to new React app
- Monitor production deployment

---

