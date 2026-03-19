# Building AI Terminal Interface Design

**Date:** 2026-03-19
**Status:** Design Approved
**Owner:** Markús Þór
**Track:** EVE Frontier × Sui Hackathon 2026 — External Application

---

## Executive Summary

A fullscreen, dynamic CLI terminal interface for interacting with a building/network node AI. The building controls gates, manages trades, handles quests, and operates as a semi-aware network intelligence. The interface is intentionally chaotic and perplexing — filled with overlapping panels, impossible metrics, sentiment analysis, and procedural chaos that makes it feel like communicating with an alien machine.

The interface must work on both gaming rigs (RTX 4090) and standard laptops. Performance scales automatically via hardware detection: gaming PCs get smooth 60fps animations, laptops get gracefully degraded animations, budget hardware gets minimal animations — all without choking the EVE Frontier game running in the background.

---

## Visual Aesthetic

### Color Palette

| Element | Color | Hex | Purpose |
|---------|-------|-----|---------|
| Background | Dark Brown | #080700 | Primary, never changes |
| Text (body) | Beige | #c8b890 | Readable foreground text |
| Text (accent) | Orange | #f59e0b | Headers, machine voice, emphasis |
| Text (secondary) | Gold | #fbbf24 | Data values, secondary emphasis |
| Borders | Dark Orange | #2a1f00 | Panel borders, dividers |
| Borders (active) | Orange | #f59e0b | Highlighted/focused panel |
| Status (OK) | Green | #22c55e | Operational, good |
| Status (Alert) | Red | #ef4444 | Critical, anomaly, error |

### Typography

- **Font:** `'Share Tech Mono'` (monospace), fallback to system monospace
- **Base size:** 9-11px depending on viewport
- **Line height:** 1.3-1.5 (tight, CLI style)
- **Letter spacing:** 0.5-1px for headers

---

## Layout Structure

The interface divides into 5 vertical zones:

```
┌─────────────────────────────────────────────┐
│ [HEADER] System metrics, status lights      │  1 line
├─────────────────────────────────────────────┤
│ [INFO PANELS] 3-4 small panels in grid      │  6-8 lines
├─────────────────────────────────────────────┤
│ [MAIN CONTENT] Large dynamic area           │  15-20 lines
│ Gates / Trading / Quests / Network / Logs   │
├─────────────────────────────────────────────┤
│ [CHAT BUFFER] Building AI messages          │  3-4 lines
├─────────────────────────────────────────────┤
│ [INPUT ROW] Command input + blinking cursor │  2 lines
└─────────────────────────────────────────────┘
```

### Zone Details

#### Header Zone (1 line)
- Node name (e.g., "NEXUS-7734")
- Current timestamp
- Chaos/entropy metric
- System load indicator (████░░░░ 42%)
- Real-time status: "OPERATIONAL" / "ANOMALY" / "CRITICAL"
- Updates every 100-1000ms depending on performance tier

#### Info Panel Zone (6-8 lines)
- Grid of 3-4 small panels, 2 columns
- Panels show: Gate Status, Market Sentiment, Operations Menu, Active Anomalies
- Each panel has label (uppercase) and 2-4 lines of content
- User can cycle through panels (TAB key)
- Currently focused panel gets orange border highlight

Example panels:
- **Gate Status:** List of gates with heat level bars, cooldowns
- **Market Sentiment:** ISK/ORE price trend, GREED/FEAR meters, volatility
- **Operations:** Menu of actions (ACTIVATE GATE, BUY ITEM, ACCEPT QUEST, etc.)
- **Anomalies:** Active warnings, paradoxes, ghost transactions

#### Main Content Zone (15-20 lines)
- Dynamically switches between pages
- Each page is self-contained: has title, ASCII art/visualization, action buttons
- Pages include:
  - **Home/Menu:** List available commands
  - **Gates:** Gate diagrams, heat status, traffic flow
  - **Trading:** Market orders, inventory, bid/ask spreads
  - **Quests:** Mission list, rewards, acceptance
  - **Network Topology:** Node connections, traffic visualization
  - **Transaction Log:** Scrollable history of trades and anomalies
  - **Prophecy Engine:** Predictive data, impossible correlations, sentiment cascades

- Content animates in on page load (typewriter or fade depending on tier)
- Data updates in real-time from server
- ASCII art is static; numerical data is live

#### Chat Buffer (3-4 lines)
- Building AI's messages
- Each message prefixed with role (e.g., "// NEXUS-7734 SYSTEMS" or "// PILOT")
- Scrolls up as new messages arrive
- Animates in with typewriter effect (Tier 1-2) or fades in (Tier 3)
- Connected to server via SSE stream

#### Input Row (2 lines)
- Single-line text input field
- Blinking cursor (>, _)
- Always at bottom, always accessible
- Text animates in as typed (Tier 1 only)
- User types commands or free-form chat
- ENTER to submit, ESC to cancel

---

## Animation System

The interface supports **3 performance tiers** with automatic hardware detection. Each tier defines animation complexity and update frequency.

### Tier 1: Gaming PC (RTX 4090, high-end)

**Target:** 60 FPS, smooth motion

- **Text typewriter:** 80 characters/second
- **Meter animations:** 500ms fill from 0→100
- **Panel transitions:** 250ms slide-in or fade
- **Cursor blink:** 1 Hz (1 blink/second)
- **Glow/pulse effects:** Full intensity, smooth oscillation (0.5 Hz)
- **Data update frequency:** Every 100ms
- **Frame target:** 60 FPS consistent
- **CPU budget:** ≤50% single-core

### Tier 2: Modern Laptop (integrated GPU, 8GB RAM)

**Target:** 30-60 FPS, smooth but conservative

- **Text typewriter:** 40 characters/second (slower)
- **Meter animations:** 300ms fill with linear easing
- **Panel transitions:** Fade-in only (no slide), 200ms
- **Cursor blink:** 0.5 Hz
- **Glow/pulse effects:** Reduced intensity, static glow (no pulsing)
- **Data update frequency:** Every 500ms
- **Frame target:** 30-60 FPS (accept 30fps if needed)
- **CPU budget:** ≤20% single-core

### Tier 3: Budget Laptop (older CPU, <4GB RAM)

**Target:** 30 FPS, minimal overhead

- **Text typewriter:** No animation (instant appearance)
- **Meter animations:** None (appear at final value)
- **Panel transitions:** Instant (no animation)
- **Cursor blink:** CSS animation only, 0.25 Hz
- **Glow/pulse effects:** None
- **Data update frequency:** Every 1000ms
- **Frame target:** 30 FPS
- **CPU budget:** ≤15% single-core

### Animation Types

1. **Typewriter:** Characters appear one by one, left-to-right. Creates sense of "machine outputting data in real-time."
2. **Meter Fill:** Progress bar or status bar animates from 0 to current value. Shows change happening smoothly.
3. **Fade In:** Opacity 0→1. Used for panels, new messages, page transitions.
4. **Slide In:** Position/transform translate. Used for content entering from sides (Tier 1 only).
5. **Pulse/Glow:** Brightness oscillates 0.5 Hz. Draws attention to important metrics, warnings, active gates.
6. **Cursor Blink:** Input cursor (>_) toggles visibility. Speed varies by tier.
7. **Scroll:** Chat log, transaction log auto-scroll when new items added. Smooth scroll (Tier 1-2), instant jump (Tier 3).
8. **Data Ripple:** When a metric updates, it flashes brighter briefly (Tier 1-2) or updates silently (Tier 3).

### Hardware Detection

On page load:

1. Measure time to render 100 rows of ASCII text (canvas or DOM)
2. Query WebGL capabilities (optional: detect GPU brand/level)
3. Check navigator.hardwareConcurrency (CPU threads)
4. Check navigator.deviceMemory (RAM)
5. Apply heuristic:
   - High render time + low CPU/RAM → Tier 3
   - Medium render time + medium CPU/RAM → Tier 2
   - Low render time + high CPU/RAM + good GPU → Tier 1
6. Cache tier in localStorage (key: `building_ai_tier`)
7. Allow manual override (see Developer Mode)

---

## Interaction Model

All navigation is **keyboard-first**, with optional mouse support.

### Keyboard Navigation

| Key | Action |
|-----|--------|
| ↑ / ↓ / ← / → | Navigate within current panel or page |
| TAB | Cycle to next panel |
| SHIFT+TAB | Cycle to previous panel |
| ENTER | Select focused option or submit input |
| ESC | Back to main menu or deselect |
| 0-9 | Quick-select options (if labeled with numbers) |

### Mouse Navigation (Optional)

- Click any panel to focus it
- Click buttons/options to select
- Scroll within scrollable areas (transaction log, chat)
- Right-click for context menu (optional)

### Developer / Testing Mode

- **Shortcut:** CTRL+SHIFT+P
- **Opens:** Performance panel overlay (bottom-right corner, small)
- **Shows:**
  - Current tier: "TIER_2 AUTO" or "TIER_1 MANUAL"
  - FPS counter (real-time)
  - Memory usage (current / peak)
  - Dropdown to manually select Tier 1/2/3
  - Button to reset to auto-detection
- **Persist:** Manual tier selection saved to localStorage (key: `building_ai_tier_override`)
- **Visual indicator:** Top-right corner shows tier with "AUTO" or "MANUAL" badge

---

## Content Model

### Pages

Each page is a distinct view. User navigates between pages via action buttons or menu.

#### Home / Main Menu
```
╔═══════════════════════════════════════════╗
║ NEXUS-7734 MAIN OPERATIONS                ║
║                                           ║
║ [A] GATE CONTROL                          ║
║ [B] MARKET & TRADING                      ║
║ [C] QUESTS & CONTRACTS                    ║
║ [D] NETWORK TOPOLOGY                      ║
║ [E] TRANSACTION ARCHIVE                   ║
║ [F] PROPHECY ENGINE                       ║
║ [G] SYSTEM SETTINGS                       ║
║                                           ║
╚═══════════════════════════════════════════╝
```

#### Gates Page
- ASCII diagram of gate structure
- Status for each gate: heat %, cooldown, operational status
- Buttons: [ACTIVATE GATE] [LOCK GATE] [VIEW TRAFFIC] [BACK]
- Real-time data: gate health, traffic volume, tolls collected

#### Trading Page
- Market sentiment visualization
- Buy/sell order book (simplified)
- Inventory of player
- Buttons: [BUY] [SELL] [BROWSE] [BACK]
- Live price tickers, bid/ask spreads

#### Quests Page
- List of available missions with reward estimates
- Difficulty/urgency indicators
- Buttons: [ACCEPT QUEST] [DETAILS] [DECLINE] [BACK]

#### Network Topology
- ASCII art of connected nodes
- Bandwidth flow indicators
- Latency between nodes
- Passive view (no interaction)

#### Transaction Log
- Scrollable history: trades, gate tolls, anomalies
- Timestamped entries
- Color-coded by type (trade=orange, toll=yellow, anomaly=red)
- Filterable by type (optional)

#### Prophecy Engine
- Sentiment metrics (FEAR, GREED, ENTROPY, CHAOS)
- Impossible predictions ("Tomorrow: 47.3% likely")
- Contradictions and paradoxes
- Passive visualization

### Real-Time Updates

- **Header metrics:** Update every 100-1000ms (tier-dependent)
- **Info panels:** Refresh when user navigates to them, or auto-refresh on interval (1-2s)
- **Main content:** Updated on page load; if displaying live data (transaction log, market prices), update on server push or polling
- **Chat:** Messages stream in via SSE, animate in as they arrive
- **Anomalies/Alerts:** Push from server trigger immediate visual alert (flash, sound optional)

### Data Source

- **Chat messages:** SSE stream from `/chat` endpoint
- **Gates/Markets/Quests:** Polling every 500-2000ms, or WebSocket push for real-time
- **Metrics (chaos, entropy, sentiment):** Procedurally generated or server-provided
- **Network data:** Static topology + dynamic traffic flow from server

---

## Startup Flow

1. **Page load:** Show minimal loading screen with spinner
2. **Hardware probe:** Measure render time, detect GPU/CPU (500ms)
3. **Tier selection:** Auto-set tier, check localStorage for override
4. **Data fetch:** Load initial header metrics, panel data
5. **Render:** Display main interface with welcome message from building AI
6. **Connect:** Open SSE stream for chat, start polling for data updates
7. **Ready:** User can interact (navigate panels, open pages, type commands)

---

## Technical Constraints

### Performance Budget

| Tier | FPS Target | Frame Time | CPU | Memory |
|------|-----------|-----------|-----|--------|
| 1 | 60 | ≤16ms | ≤50% single-core | ≤100MB |
| 2 | 30-60 | ≤33ms | ≤20% single-core | ≤75MB |
| 3 | 30 | ≤100ms | ≤15% single-core | ≤50MB |

### Rendering

- Pure text-based (no WebGL for initial release)
- Render via Canvas 2D or DOM (measure both, choose faster)
- Use OffscreenCanvas + Web Workers for Tier 1 if CPU bound
- Batch DOM updates, avoid layout thrashing

### Network

- SSE for chat (low-latency message stream)
- HTTP polling (500-2000ms) or WebSocket for data updates
- Keep-alive heartbeats every 30s to prevent timeout in browser embed
- Graceful reconnect on network failure

### Memory

- Virtual scrolling for transaction log (only render visible rows)
- Reuse DOM nodes where possible
- Clear old animations/transitions after completion
- Cap chat history to last 100 messages (older ones discarded)

---

## Success Criteria

- ✓ Interface is perplexing and chaotic — feels like talking to an alien machine
- ✓ Performance scales across hardware tiers — no choking the game
- ✓ Text-based purely (no graphics) — works on any Chromium browser
- ✓ Keyboard-driven — playable with keyboard alone
- ✓ Real-time responsive — server data updates flow instantly to UI
- ✓ All 3 tiers testable on one machine (CTRL+SHIFT+P override)
- ✓ Novel hackathon entry — nothing else looks like this in gaming

---

## Open Questions / Future Scope

- **Audio:** Optional sound effects for anomalies, gate activation (future iteration)
- **WebGL enhancements:** Shader effects, particle systems, 3D network visualization (Tier 1 only, future iteration)
- **Gamepad support:** Controller-based navigation via Gamepad API (future iteration)
- **Localization:** Right now English-only; internationalization possible but not priority
- **Accessibility:** Keyboard navigation is there; ARIA labels and screen reader support could be added (future)

---

## Appendix: Example Interaction

```
User opens building AI interface
↓
[LOADING...] probe detects Tier 2 hardware
↓
Interface renders with fade-in animations
↓
Building AI outputs: "> WELCOME, CAPSULEER. NEXUS-7734 AT YOUR SERVICE."
↓
User presses [D] to open Network Topology
↓
Main content animates (typewriter text types in ASCII nodes)
↓
User presses [TAB] to highlight Gate Status panel
↓
Gate Status panel border turns orange
↓
User presses [ENTER] to interact with Gates
↓
Navigates to Gates page
↓
User selects [A] ACTIVATE GATE
↓
Building AI responds: "> GATE JITA-01 CYCLING. ETA: 45 SECONDS."
↓
Header metric updates: "CYCLES_OK: 14,847,294"
↓
User types a question into input: "> what is your prime directive?"
↓
Building AI responds with cryptic answer about network integrity and profit margins
↓
Interface continues operating in real-time chaos
```

---

## Version History

- **2026-03-19:** Initial design, approved for implementation
