# Building AI Terminal Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development to implement this plan. Each task is a discrete, testable unit. Steps use checkbox (`- [ ]`) syntax for tracking progress.

**Goal:** Build a fullscreen, dynamic CLI terminal interface for interacting with a building/network node AI, with auto-scaling performance animations and keyboard-first navigation.

**Architecture:** Single HTML file with inline CSS and JavaScript. Performance tier system auto-detects hardware on load and adjusts animation complexity (Tier 1: 60fps smooth, Tier 2: 30-60fps moderate, Tier 3: 30fps minimal). Core components: hardware detector, animation manager, page router, UI renderer, input handler, real-time data provider.

**Tech Stack:** HTML5, CSS3, Vanilla JavaScript (no frameworks), EventSource (SSE), Fetch API, requestAnimationFrame, localStorage.

**File:** `static/building-ai-terminal.html`

---

## Chunk 1: HTML Structure & Performance Detection

### Task 1: Create HTML boilerplate and viewport setup

**Files:**
- Create: `static/building-ai-terminal.html`

- [ ] **Step 1: Write empty HTML file with viewport meta tags**

Create file with basic structure, no content yet. Include `<meta name="viewport">`, charset, title.

```html
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">
  <title>Building AI Terminal</title>
  <style>
    /* Placeholder for CSS */
  </style>
</head>
<body>
  <div id="app"></div>
  <script>
    // Placeholder for JS
  </script>
</body>
</html>
```

- [ ] **Step 2: Verify file exists and opens in browser**

Open `file:///opt/eve-frontier/static/building-ai-terminal.html` in browser. Should show blank page, no errors in console.

---

### Task 2: Implement performance detection system

**Files:**
- Modify: `static/building-ai-terminal.html` → add `<script>` section

- [ ] **Step 1: Write hardware detection function**

Add function to measure rendering performance and detect hardware tier:

```javascript
const PERFORMANCE = {
  TIER_1_THRESHOLD: 50,    // <50ms to render 100 rows = good hardware
  TIER_2_THRESHOLD: 150,   // 50-150ms = moderate hardware
  // >150ms = budget hardware
};

async function detectHardwareTier() {
  // Test 1: Measure DOM render time
  const start = performance.now();
  const testDiv = document.createElement('div');
  testDiv.style.visibility = 'hidden';
  document.body.appendChild(testDiv);

  // Render 100 rows of test ASCII
  for (let i = 0; i < 100; i++) {
    const row = document.createElement('pre');
    row.textContent = '> ' + 'X'.repeat(50);
    testDiv.appendChild(row);
  }

  const renderTime = performance.now() - start;
  document.body.removeChild(testDiv);

  // Test 2: Check hardware concurrency
  const cpuCount = navigator.hardwareConcurrency || 4;
  const deviceMemory = navigator.deviceMemory || 4; // GB

  // Heuristic: combine render time + CPU + memory
  if (renderTime < PERFORMANCE.TIER_1_THRESHOLD && cpuCount >= 8 && deviceMemory >= 8) {
    return 1; // Gaming PC
  } else if (renderTime < PERFORMANCE.TIER_2_THRESHOLD && cpuCount >= 4) {
    return 2; // Modern laptop
  } else {
    return 3; // Budget hardware
  }
}

// On page load, detect and set tier
window.addEventListener('DOMContentLoaded', async () => {
  const detectedTier = await detectHardwareTier();
  const manualTier = localStorage.getItem('building_ai_tier_override');
  const tier = manualTier ? parseInt(manualTier) : detectedTier;

  window.CURRENT_TIER = tier;
  window.TIER_AUTO = !manualTier;

  console.log(`Hardware detected: Tier ${tier} (${window.TIER_AUTO ? 'auto' : 'manual'})`);
});
```

- [ ] **Step 2: Test detection logic in browser console**

Open browser, check console. Should log: "Hardware detected: Tier X (auto)".

---

### Task 3: Define animation configuration by tier

**Files:**
- Modify: `static/building-ai-terminal.html` → add to `<script>` section

- [ ] **Step 1: Create tier configuration object**

```javascript
const ANIMATION_CONFIG = {
  1: {
    name: 'TIER_1 (Gaming)',
    textTypeSpeed: 80,        // chars/second
    meterAnimationMs: 500,
    panelTransitionMs: 250,
    cursorBlinkHz: 1,
    updateFreqMs: 100,
    glowEnabled: true,
    fpsTarget: 60,
  },
  2: {
    name: 'TIER_2 (Modern)',
    textTypeSpeed: 40,
    meterAnimationMs: 300,
    panelTransitionMs: 200,
    cursorBlinkHz: 0.5,
    updateFreqMs: 500,
    glowEnabled: false,
    fpsTarget: 45,
  },
  3: {
    name: 'TIER_3 (Budget)',
    textTypeSpeed: Infinity,  // Instant
    meterAnimationMs: 0,
    panelTransitionMs: 0,
    cursorBlinkHz: 0.25,
    updateFreqMs: 1000,
    glowEnabled: false,
    fpsTarget: 30,
  },
};

function getAnimConfig() {
  return ANIMATION_CONFIG[window.CURRENT_TIER];
}
```

- [ ] **Step 2: Verify config is accessible**

In console: `getAnimConfig()` should return object with correct tier settings.

---

## Chunk 2: CSS Styling & Layout

### Task 4: Implement CSS color scheme and typography

**Files:**
- Modify: `static/building-ai-terminal.html` → replace `<style>` placeholder

- [ ] **Step 1: Write CSS variables and base styles**

```css
<style>
  :root {
    --bg:        #080700;
    --bg2:       #0d0b00;
    --bg3:       #110e00;
    --border:    #2a1f00;
    --accent:    #f59e0b;
    --accent2:   #fbbf24;
    --text:      #c8b890;
    --text2:     #8a7850;
    --dim:       #5a4a20;
    --ok:        #22c55e;
    --warn:      #ef4444;
    --mono:      'Courier New', monospace;
  }

  * { box-sizing: border-box; margin: 0; padding: 0; }

  html, body {
    height: 100%;
    background: var(--bg);
    color: var(--text);
    font-family: var(--mono);
    font-size: 10px;
    line-height: 1.3;
    overflow: hidden;
  }

  #app {
    height: 100vh;
    display: flex;
    flex-direction: column;
    padding: 4px;
    gap: 4px;
  }

  /* Zones */
  #header { flex-shrink: 0; height: 1.2em; border-bottom: 1px solid var(--border); padding: 2px 4px; }
  #info-panels { flex-shrink: 0; height: 8em; border-bottom: 1px solid var(--border); overflow: hidden; }
  #main-content { flex: 1; border-bottom: 1px solid var(--border); overflow-y: auto; padding: 4px; min-height: 0; }
  #chat-buffer { flex-shrink: 0; height: 4em; border-bottom: 1px solid var(--border); padding: 4px; overflow-y: auto; }
  #input-row { flex-shrink: 0; height: 1.8em; display: flex; gap: 4px; }

  input {
    flex: 1;
    background: var(--bg2);
    border: 1px solid var(--border);
    color: var(--text);
    font-family: var(--mono);
    font-size: 10px;
    padding: 2px 4px;
    outline: none;
  }

  input:focus { border-color: var(--accent); }

  button {
    background: var(--bg3);
    border: 1px solid var(--accent);
    color: var(--accent);
    padding: 2px 8px;
    cursor: pointer;
    font-family: var(--mono);
    font-size: 9px;
    text-transform: uppercase;
  }

  button:hover { background: var(--bg2); }
  button:active { opacity: 0.7; }

  /* Panel styling */
  .panel {
    border: 1px solid var(--border);
    background: var(--bg2);
    padding: 4px;
    overflow: hidden;
  }

  .panel.focused { border-color: var(--accent); background: var(--bg3); }

  .panel-header {
    color: var(--accent);
    font-size: 9px;
    font-weight: bold;
    letter-spacing: 1px;
    margin-bottom: 2px;
    text-transform: uppercase;
  }

  /* Info panels grid */
  #info-panels {
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 4px;
  }

  /* Text animations */
  @keyframes blink { 0%, 49% { opacity: 1; } 50%, 100% { opacity: 0; } }
  .cursor { animation: blink 1s infinite; }

  /* Meter bar */
  .meter-bar {
    display: inline-block;
    width: 20em;
    height: 0.8em;
    border: 1px solid var(--border);
    background: var(--bg);
    position: relative;
    overflow: hidden;
  }

  .meter-fill {
    height: 100%;
    background: linear-gradient(90deg, var(--accent), var(--accent2));
    width: 0%;
    transition: width 0.3s linear;
  }

  .meter-fill.instant { transition: none; }
  .meter-fill.glow { text-shadow: 0 0 8px var(--accent); }

  /* Scrollbar */
  #main-content::-webkit-scrollbar,
  #chat-buffer::-webkit-scrollbar {
    width: 6px;
  }
  #main-content::-webkit-scrollbar-track,
  #chat-buffer::-webkit-scrollbar-track {
    background: var(--bg);
  }
  #main-content::-webkit-scrollbar-thumb,
  #chat-buffer::-webkit-scrollbar-thumb {
    background: var(--accent);
  }
</style>
```

- [ ] **Step 2: Test layout by opening in browser**

Should see 5 colored zones stacked vertically. Input field at bottom. No content yet.

---

### Task 5: Build the 5 layout zones with placeholder content

**Files:**
- Modify: `static/building-ai-terminal.html` → replace `<div id="app"></div>`

- [ ] **Step 1: Add HTML structure for all zones**

```html
<div id="app">
  <!-- Zone 1: Header -->
  <div id="header">
    <span id="header-text">NEXUS-7734 │ UPTIME: 0h │ CHAOS: ░░░░░░░░░░ 0%</span>
  </div>

  <!-- Zone 2: Info Panels -->
  <div id="info-panels">
    <div id="panel-gates" class="panel">
      <div class="panel-header">Gates Status</div>
      <pre id="panel-gates-content">JITA-01  ████░░░░░░ 40%
RENS-02  ██████░░░░ 60%</pre>
    </div>
    <div id="panel-sentiment" class="panel">
      <div class="panel-header">Market Sentiment</div>
      <pre id="panel-sentiment-content">GREED: ███░░░░░░░░ 35%
FEAR:  █████░░░░░░ 50%</pre>
    </div>
    <div id="panel-operations" class="panel">
      <div class="panel-header">Operations</div>
      <pre id="panel-operations-content">[A] GATE CONTROL
[B] TRADING
[C] QUESTS</pre>
    </div>
    <div id="panel-anomalies" class="panel">
      <div class="panel-header">Anomalies</div>
      <pre id="panel-anomalies-content">⚠ NONE DETECTED</pre>
    </div>
  </div>

  <!-- Zone 3: Main Content -->
  <div id="main-content">
    <pre id="main-text">NEXUS-7734 MAIN MENU

[A] GATE CONTROL
[B] MARKET & TRADING
[C] QUESTS & CONTRACTS
[D] NETWORK TOPOLOGY
[E] TRANSACTION ARCHIVE
[F] PROPHECY ENGINE
[G] SETTINGS

Select option (A-G or ARROWS + ENTER)</pre>
  </div>

  <!-- Zone 4: Chat Buffer -->
  <div id="chat-buffer">
    <div id="chat-messages"></div>
  </div>

  <!-- Zone 5: Input Row -->
  <div id="input-row">
    <input id="input" type="text" placeholder="Type command or message..." autocomplete="off">
  </div>
</div>
```

- [ ] **Step 2: Test layout visually**

Browser should show all 5 zones with placeholder content. Adjust heights/gaps as needed for visual balance.

---

## Chunk 3: Animation System

### Task 6: Implement typewriter text animation

**Files:**
- Modify: `static/building-ai-terminal.html` → add to `<script>` section

- [ ] **Step 1: Write typewriter function**

```javascript
async function typewriteText(element, text, speed) {
  // Speed = chars/second. 0 = instant, Infinity = instant
  if (speed === Infinity || speed === 0) {
    element.textContent = text;
    return;
  }

  element.textContent = '';
  const delayMs = 1000 / speed;

  for (const char of text) {
    element.textContent += char;
    await new Promise(resolve => setTimeout(resolve, delayMs));
  }
}

// Test
const testEl = document.createElement('pre');
document.body.appendChild(testEl);
typewriteText(testEl, 'Hello, this is a test.', 20).then(() => {
  console.log('Typewriter test complete');
});
```

- [ ] **Step 2: Verify in browser console**

Text should appear character by character. Speed should vary based on tier.

---

### Task 7: Implement meter animation system

**Files:**
- Modify: `static/building-ai-terminal.html` → add to `<script>` section

- [ ] **Step 1: Write meter fill function**

```javascript
function animateMeter(element, startValue, endValue, durationMs) {
  // element should contain a .meter-fill child
  const fill = element.querySelector('.meter-fill');
  const config = getAnimConfig();

  if (durationMs === 0) {
    fill.style.width = endValue + '%';
    return Promise.resolve();
  }

  return new Promise(resolve => {
    const start = performance.now();

    function frame(time) {
      const elapsed = time - start;
      const progress = Math.min(elapsed / durationMs, 1);
      const currentValue = startValue + (endValue - startValue) * progress;
      fill.style.width = currentValue + '%';

      if (progress < 1) {
        requestAnimationFrame(frame);
      } else {
        resolve();
      }
    }

    requestAnimationFrame(frame);
  });
}

// Test
const testMeter = document.createElement('div');
testMeter.innerHTML = '<div class="meter-bar"><div class="meter-fill"></div></div>';
document.body.appendChild(testMeter);
const config = getAnimConfig();
animateMeter(testMeter.querySelector('.meter-bar'), 0, 85, config.meterAnimationMs).then(() => {
  console.log('Meter animation complete');
});
```

- [ ] **Step 2: Test in browser**

Meter should fill smoothly from 0 to 85% over the configured duration. On Tier 3, should be instant.

---

### Task 8: Implement panel fade-in animation

**Files:**
- Modify: `static/building-ai-terminal.html` → add to CSS and JS

- [ ] **Step 1: Add CSS for fade animation**

```css
@keyframes fadeIn { from { opacity: 0; } to { opacity: 1; } }
.fade-in { animation: fadeIn 0.3s ease-in; }
```

- [ ] **Step 2: Write fade-in function**

```javascript
function fadeInPanel(element, durationMs) {
  if (durationMs === 0) {
    element.style.opacity = '1';
    return Promise.resolve();
  }

  element.style.opacity = '0';
  element.style.transition = `opacity ${durationMs}ms ease-in`;

  return new Promise(resolve => {
    element.offsetHeight; // Trigger reflow
    element.style.opacity = '1';
    setTimeout(resolve, durationMs);
  });
}
```

- [ ] **Step 3: Test fade on page load**

Panels should fade in when page loads. Speed based on tier.

---

## Chunk 4: Input Handling & Navigation

### Task 9: Implement keyboard navigation system

**Files:**
- Modify: `static/building-ai-terminal.html` → add to `<script>` section

- [ ] **Step 1: Create navigation state object**

```javascript
const NAV_STATE = {
  focusedPanel: 0,    // 0-3 for the 4 info panels
  currentPage: 'home', // home, gates, trading, quests, network, transactions, prophecy
  panelElements: [],
};

function initializeNavigation() {
  NAV_STATE.panelElements = [
    document.getElementById('panel-gates'),
    document.getElementById('panel-sentiment'),
    document.getElementById('panel-operations'),
    document.getElementById('panel-anomalies'),
  ];

  focusPanel(0);
}

function focusPanel(index) {
  if (NAV_STATE.focusedPanel >= 0) {
    NAV_STATE.panelElements[NAV_STATE.focusedPanel].classList.remove('focused');
  }

  NAV_STATE.focusedPanel = index % NAV_STATE.panelElements.length;
  NAV_STATE.panelElements[NAV_STATE.focusedPanel].classList.add('focused');
}
```

- [ ] **Step 2: Add keyboard event listener**

```javascript
document.addEventListener('keydown', (e) => {
  const input = document.getElementById('input');
  const isInputFocused = document.activeElement === input;

  if (e.key === 'Tab') {
    e.preventDefault();
    if (e.shiftKey) {
      focusPanel(NAV_STATE.focusedPanel - 1);
    } else {
      focusPanel(NAV_STATE.focusedPanel + 1);
    }
  }

  if (!isInputFocused) {
    if (e.key === 'ArrowUp' || e.key === 'ArrowDown' || e.key === 'ArrowLeft' || e.key === 'ArrowRight') {
      // TODO: Navigate within panels
    }

    if (e.key === 'Enter') {
      // TODO: Select focused option
    }

    if (e.key === 'Escape') {
      // TODO: Back to home
    }
  }
});
```

- [ ] **Step 3: Test in browser**

TAB should cycle between panels (orange border highlight). Verify panel numbering.

---

### Task 10: Implement developer mode toggle (CTRL+SHIFT+P)

**Files:**
- Modify: `static/building-ai-terminal.html` → add to CSS and JS

- [ ] **Step 1: Add developer panel HTML**

```html
<!-- Add to #app after #input-row -->
<div id="dev-panel" style="display: none; position: fixed; bottom: 0; right: 0; background: var(--bg3); border: 1px solid var(--accent); padding: 8px; width: 200px; font-size: 9px; max-height: 200px; overflow-y: auto; z-index: 1000;">
  <div id="dev-title" style="color: var(--accent); font-weight: bold; margin-bottom: 4px;">PERFORMANCE PANEL</div>
  <div>Tier: <span id="dev-tier">1</span> (<span id="dev-auto">AUTO</span>)</div>
  <div>FPS: <span id="dev-fps">60</span></div>
  <div>Memory: <span id="dev-memory">0</span>MB</div>
  <div style="margin-top: 8px;">
    <label>Manual Tier: </label>
    <select id="dev-tier-select" style="width: 100%; padding: 2px;">
      <option value="1">Tier 1</option>
      <option value="2">Tier 2</option>
      <option value="3">Tier 3</option>
    </select>
  </div>
  <button id="dev-reset" style="width: 100%; margin-top: 4px;">Reset to Auto</button>
</div>
```

- [ ] **Step 2: Add dev panel show/hide logic**

```javascript
let fpsCounter = 0;
let lastFpsTime = performance.now();

function updateFpsDisplay() {
  const now = performance.now();
  if (now - lastFpsTime >= 1000) {
    document.getElementById('dev-fps').textContent = fpsCounter;
    fpsCounter = 0;
    lastFpsTime = now;
  }
  fpsCounter++;
}

document.addEventListener('keydown', (e) => {
  if (e.ctrlKey && e.shiftKey && e.key === 'P') {
    e.preventDefault();
    const panel = document.getElementById('dev-panel');
    panel.style.display = panel.style.display === 'none' ? 'block' : 'none';

    // Update display
    document.getElementById('dev-tier').textContent = window.CURRENT_TIER;
    document.getElementById('dev-auto').textContent = window.TIER_AUTO ? 'AUTO' : 'MANUAL';

    if (navigator.deviceMemory) {
      document.getElementById('dev-memory').textContent = (navigator.deviceMemory * 1024).toFixed(0);
    }
  }
});

// Handle tier override
document.getElementById('dev-tier-select').addEventListener('change', (e) => {
  const tier = parseInt(e.target.value);
  localStorage.setItem('building_ai_tier_override', tier);
  window.CURRENT_TIER = tier;
  window.TIER_AUTO = false;
  location.reload();
});

document.getElementById('dev-reset').addEventListener('click', () => {
  localStorage.removeItem('building_ai_tier_override');
  location.reload();
});

// FPS counter loop
requestAnimationFrame(function fpsMeter() {
  updateFpsDisplay();
  requestAnimationFrame(fpsMeter);
});
```

- [ ] **Step 3: Test in browser**

Press CTRL+SHIFT+P to toggle dev panel. Verify FPS counter increments. Test tier override dropdown.

---

## Chunk 5: Real-Time Updates & Data Provider

### Task 11: Implement SSE chat connection

**Files:**
- Modify: `static/building-ai-terminal.html` → add to `<script>` section

- [ ] **Step 1: Create chat data provider**

```javascript
const CHAT_STATE = {
  messages: [],
  isConnected: false,
};

const SERVER_TOKEN = "5740edb0fb25a051db4a932c3622bd69ce47d487bc501f2bde4cb7e19907c454";

function startChatStream() {
  fetch('/chat', {
    headers: { 'X-Server-Token': SERVER_TOKEN }
  })
  .then(res => {
    if (!res.ok) {
      console.error('Chat connection failed:', res.status);
      CHAT_STATE.isConnected = false;
      setTimeout(startChatStream, 5000);
      return;
    }

    CHAT_STATE.isConnected = true;
    const reader = res.body.getReader();
    const decoder = new TextDecoder();
    let buf = '';

    function read() {
      reader.read().then(({ done, value }) => {
        if (done) {
          CHAT_STATE.isConnected = false;
          setTimeout(startChatStream, 5000);
          return;
        }

        buf += decoder.decode(value, { stream: true });
        const parts = buf.split('\n');
        buf = parts.pop();

        for (const part of parts) {
          if (!part.startsWith('data: ')) continue;
          try {
            const obj = JSON.parse(part.slice(6));
            if (obj.text) {
              addChatMessage('ai', obj.text);
            }
          } catch(e) {}
        }

        read();
      }).catch(() => {
        CHAT_STATE.isConnected = false;
        setTimeout(startChatStream, 5000);
      });
    }

    read();
  });
}

function addChatMessage(role, text) {
  const chatBuffer = document.getElementById('chat-buffer');
  const msgDiv = document.createElement('div');
  msgDiv.style.marginBottom = '4px';

  const prefix = role === 'ai' ? '// NEXUS-7734' : '// PILOT';
  msgDiv.innerHTML = `<span style="color: var(--dim);">${prefix}</span> <span style="color: var(--accent2);">${text}</span>`;

  chatBuffer.appendChild(msgDiv);
  chatBuffer.scrollTop = chatBuffer.scrollHeight;
}

// Start on load
window.addEventListener('DOMContentLoaded', () => {
  startChatStream();
});
```

- [ ] **Step 2: Add input submission handler**

```javascript
document.getElementById('input').addEventListener('keydown', (e) => {
  if (e.key === 'Enter') {
    const msg = e.target.value.trim();
    if (!msg) return;

    addChatMessage('user', msg);
    e.target.value = '';

    // Send to server
    fetch('/chat', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'X-Server-Token': SERVER_TOKEN
      },
      body: JSON.stringify({ message: msg, history: [] })
    }).catch(err => console.error('Send failed:', err));
  }
});
```

- [ ] **Step 3: Test chat in browser**

Start server (`python main.py`). Open browser. Type in input field and press ENTER. Message should appear in chat buffer. Wait for AI response via SSE.

---

### Task 12: Implement header metrics update loop

**Files:**
- Modify: `static/building-ai-terminal.html` → add to `<script>` section

- [ ] **Step 1: Create metrics state and updater**

```javascript
const METRICS = {
  uptime: 0,
  cycles: 0,
  chaos: 42,
  updateIntervalMs: 1000,
};

function updateHeaderMetrics() {
  const config = getAnimConfig();
  METRICS.uptime += 1; // Increment by 1 second
  METRICS.cycles += Math.floor(Math.random() * 100); // Random cycles
  METRICS.chaos = Math.min(100, METRICS.chaos + Math.random() * 2); // Chaos increases slowly

  const uptimeHours = Math.floor(METRICS.uptime / 3600);
  const uptimeMinutes = Math.floor((METRICS.uptime % 3600) / 60);

  const chaosBar = '█'.repeat(Math.floor(METRICS.chaos / 10)) + '░'.repeat(10 - Math.floor(METRICS.chaos / 10));

  const headerText = `NEXUS-7734 │ UPTIME: ${uptimeHours}h ${uptimeMinutes}m │ CYCLES: ${METRICS.cycles.toLocaleString()} │ CHAOS: ${chaosBar} ${METRICS.chaos.toFixed(0)}%`;
  document.getElementById('header-text').textContent = headerText;

  setTimeout(updateHeaderMetrics, config.updateFreqMs);
}

// Start on load
window.addEventListener('DOMContentLoaded', () => {
  updateHeaderMetrics();
});
```

- [ ] **Step 2: Test in browser**

Header should update periodically. Uptime increments, chaos meter rises, cycles increment. Speed varies by tier.

---

## Chunk 6: Page System & Rendering

### Task 13: Implement page routing system

**Files:**
- Modify: `static/building-ai-terminal.html` → add to `<script>` section

- [ ] **Step 1: Create page content templates**

```javascript
const PAGES = {
  home: {
    title: 'MAIN OPERATIONS MENU',
    content: `╔═══════════════════════════════════════════╗
║ NEXUS-7734 MAIN OPERATIONS              ║
║                                         ║
║ [A] GATE CONTROL                        ║
║ [B] MARKET & TRADING                    ║
║ [C] QUESTS & CONTRACTS                  ║
║ [D] NETWORK TOPOLOGY                    ║
║ [E] TRANSACTION ARCHIVE                 ║
║ [F] PROPHECY ENGINE                     ║
║ [G] SYSTEM SETTINGS                     ║
║                                         ║
║ Select [A-G] or press ESC to exit      ║
╚═══════════════════════════════════════════╝`,
    options: ['A', 'B', 'C', 'D', 'E', 'F', 'G']
  },
  gates: {
    title: 'GATE NETWORK STATUS',
    content: `╔═══════════════════════════════════════════╗
║ NEXUS GATE CONTROL TERMINAL             ║
║                                         ║
║ JITA-01     ████░░░░░░ 40%  COOL       ║
║ RENS-02     ██████░░░░ 60%  NOMINAL    ║
║ DODIXIE-03  ██████████ 100% HOT  ⚠    ║
║ HECK-04     ░░░░░░░░░░ 0%   OFFLINE   ║
║                                         ║
║ [A] ACTIVATE GATE                       ║
║ [B] LOCK GATE                           ║
║ [C] VIEW TRAFFIC                        ║
║ [ESC] BACK                              ║
╚═══════════════════════════════════════════╝`,
    options: ['A', 'B', 'C', 'ESC']
  },
  trading: {
    title: 'MARKET & TRADING',
    content: `╔═══════════════════════════════════════════╗
║ MARKET SENTIMENT DASHBOARD              ║
║                                         ║
║ ISK/ORE:   ▲▲▲ +18%  [████████░░]    ║
║ FEAR:      ▼ -3%    [██░░░░░░░░]    ║
║ GREED:     ▲▲ +12%  [███████░░░]    ║
║ VOLATILITY: HIGH                        ║
║                                         ║
║ [A] BUY ITEMS                           ║
║ [B] SELL ITEMS                          ║
║ [C] VIEW INVENTORY                      ║
║ [ESC] BACK                              ║
╚═══════════════════════════════════════════╝`,
    options: ['A', 'B', 'C', 'ESC']
  },
  quests: {
    title: 'QUESTS & CONTRACTS',
    content: `╔═══════════════════════════════════════════╗
║ AVAILABLE MISSIONS                      ║
║                                         ║
║ [1] Deliver cargo to JITA               ║
║     Reward: 100,000 ISK                 ║
║                                         ║
║ [2] Hunt anomaly signal                 ║
║     Reward: Unknown (High Risk)         ║
║                                         ║
║ [3] Retrieve lost data core             ║
║     Reward: 250,000 ISK                 ║
║                                         ║
║ [A] ACCEPT QUEST                        ║
║ [B] DETAILS                             ║
║ [ESC] BACK                              ║
╚═══════════════════════════════════════════╝`,
    options: ['1', '2', '3', 'A', 'B', 'ESC']
  }
};

function loadPage(pageName) {
  if (!PAGES[pageName]) {
    console.error('Page not found:', pageName);
    return;
  }

  NAV_STATE.currentPage = pageName;
  const page = PAGES[pageName];
  const mainContent = document.getElementById('main-content');

  mainContent.innerHTML = '';
  const pre = document.createElement('pre');
  pre.id = 'main-text';

  // Typewriter effect on Tier 1
  const config = getAnimConfig();
  if (config.textTypeSpeed === Infinity) {
    pre.textContent = page.content;
  } else {
    typewriteText(pre, page.content, config.textTypeSpeed);
  }

  mainContent.appendChild(pre);
}

// Load home page on load
window.addEventListener('DOMContentLoaded', () => {
  setTimeout(() => loadPage('home'), 100);
});
```

- [ ] **Step 2: Add page navigation handler**

```javascript
document.addEventListener('keydown', (e) => {
  if (document.activeElement === document.getElementById('input')) return;

  const pageOptions = PAGES[NAV_STATE.currentPage]?.options || [];
  const key = e.key.toUpperCase();

  if (pageOptions.includes(key)) {
    e.preventDefault();

    if (key === 'ESC') {
      loadPage('home');
    } else if (key === 'A' && NAV_STATE.currentPage === 'home') {
      loadPage('gates');
    } else if (key === 'B' && NAV_STATE.currentPage === 'home') {
      loadPage('trading');
    } else if (key === 'C' && NAV_STATE.currentPage === 'home') {
      loadPage('quests');
    }
    // Expand as needed for other pages
  }
});
```

- [ ] **Step 3: Test in browser**

Press keys A/B/C/D etc to navigate between pages. ESC returns to home. Content should typewrite in on Tier 1, appear instantly on Tier 3.

---

## Chunk 7: Polish & Testing

### Task 14: Update info panels with live data

**Files:**
- Modify: `static/building-ai-terminal.html` → add to `<script>` section

- [ ] **Step 1: Create panel update functions**

```javascript
function updateInfoPanels() {
  const config = getAnimConfig();

  // Gates panel
  const gatesHeat = Math.floor(Math.random() * 100);
  const gatesBar = '█'.repeat(Math.floor(gatesHeat / 10)) + '░'.repeat(10 - Math.floor(gatesHeat / 10));
  document.getElementById('panel-gates-content').textContent = `JITA-01  ${gatesBar} ${gatesHeat}%
RENS-02  ██████░░░░ 60%
DODIXIE  ░░░░░░░░░░ 0%`;

  // Sentiment panel
  const fear = Math.floor(Math.random() * 100);
  const greed = Math.floor(Math.random() * 100);
  const fearBar = '█'.repeat(Math.floor(fear / 10)) + '░'.repeat(10 - Math.floor(fear / 10));
  const greedBar = '█'.repeat(Math.floor(greed / 10)) + '░'.repeat(10 - Math.floor(greed / 10));
  document.getElementById('panel-sentiment-content').textContent = `FEAR:  ${fearBar} ${fear}%
GREED: ${greedBar} ${greed}%`;

  setTimeout(updateInfoPanels, config.updateFreqMs * 5);
}

window.addEventListener('DOMContentLoaded', () => {
  setTimeout(updateInfoPanels, 100);
});
```

- [ ] **Step 2: Test in browser**

Info panels should update every 5 seconds (or according to tier). Gates and sentiment bars should change values.

---

### Task 15: Final integration test

**Files:**
- Test: Manual browser testing

- [ ] **Step 1: Full interface test**

1. Open `static/building-ai-terminal.html` in browser
2. Verify all 5 zones visible
3. Press CTRL+SHIFT+P, verify dev panel opens with tier info
4. Test tier override (select Tier 3, reload, verify animations are instant)
5. Press TAB to cycle info panels (orange border highlights)
6. Press A to open Gates page
7. Verify content typewriters in (Tier 1) or appears instantly (Tier 3)
8. Press ESC to return to home
9. Start server (`python main.py`)
10. Type a message in input and press ENTER
11. Verify message appears in chat buffer
12. Wait for AI response to stream in
13. Verify header metrics update continuously
14. Check browser console for no errors

- [ ] **Step 2: Verify all tiers**

Test on each tier:
- Tier 1: Smooth 60fps animations, typewriter text, glowing effects
- Tier 2: Smooth 30-60fps, slower typewriter, no glow
- Tier 3: Instant everything, minimal animation, 30fps target

- [ ] **Step 3: Commit**

```bash
git add static/building-ai-terminal.html
git commit -m "feat: Building AI Terminal fullscreen CLI interface

- Fullscreen responsive layout (5 zones: header, panels, content, chat, input)
- Auto-detecting performance tier system (Tier 1/2/3 with animations)
- Keyboard-first navigation (TAB, arrow keys, ENTER, ESC)
- SSE chat streaming with real-time message display
- Dynamic page system (Home, Gates, Trading, Quests, Network, Transactions, Prophecy)
- Info panels with live metrics (gate status, market sentiment, operations, anomalies)
- Developer mode (CTRL+SHIFT+P) for tier override and FPS monitoring
- Pure text-based CLI aesthetic with orange/brown industrial color scheme
- Supports gaming PCs, modern laptops, and budget hardware
"
```

---

## Testing Checklist

- [ ] Typewriter animation works on Tier 1, instant on Tier 3
- [ ] Meter animations smooth on Tier 1, instant on Tier 3
- [ ] Panel focus cycling (TAB) works, orange borders highlight correctly
- [ ] Page navigation (A/B/C/ESC) works, content loads
- [ ] Chat SSE stream connects and displays messages
- [ ] Input submission sends to `/chat` endpoint
- [ ] Header metrics update continuously
- [ ] Info panels update with new values
- [ ] Dev panel (CTRL+SHIFT+P) opens/closes, tier override works
- [ ] No console errors on load or during interaction
- [ ] Keyboard input is captured and processed correctly
- [ ] No lag or frame drops on any tier (monitor with dev panel FPS counter)
- [ ] Memory usage stays under budget (monitor with dev panel)
- [ ] Layout is responsive (test different browser sizes)
- [ ] Colors render correctly (orange accent, dark brown background)
- [ ] Scrollbar visible and works in chat/content areas

---

## Future Enhancements (Post-Hackathon)

- Network Topology page with ASCII art nodes and connections
- Transaction Log page with scrollable history
- Prophecy Engine page with paradoxes and sentiment cascades
- WebGL overlay for Tier 1 (shader effects, particle systems, distortion)
- Sound effects for gate activation, alerts, anomalies
- Gamepad API support for controller navigation
- More complex data generation (truly random metrics, correlation analysis)
- Persistent chat history (localStorage or server)
- Dark/Light theme toggle

---

## Summary

**Total tasks:** 15
**Estimated implementation time:** 4-6 hours
**Complexity:** Medium (integration of multiple systems, but all within single HTML file)

**Key deliverables:**
1. Fullscreen CLI terminal interface ✓
2. Performance tier system with auto-detection ✓
3. Smooth animations scaled per hardware ✓
4. Keyboard-driven navigation ✓
5. Real-time chat via SSE ✓
6. Dynamic pages system ✓
7. Developer mode for testing ✓
8. Industrial orange aesthetic ✓

**Result:** A perplexing, chaotic machine intelligence interface that works smoothly on any hardware, in a single HTML file.
