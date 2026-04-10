# Frontend UI Reference

**Source:** `frontend/src/`
**Entry point:** `frontend/src/main.tsx`
**Viewport:** 787×838px fixed (EVE Frontier in-game Chromium browser)

This document covers the React component architecture, panel rendering system, data flow from AI stream to visual output, CSS architecture, hooks, and state management. For wallet/assembly data fetching, see `docs/DAPP_KIT_API.md`. For build and deploy, see `docs/ARCHITECTURE.md` → Frontend.

---

## Layout Hierarchy

`TerminalUI` is the primary structure UI. Its DOM structure:

```
.terminal-ui                      100% × 100%, flex column, CRT scanlines overlay (::before z-index 100)
├── InfoPanel (#visual-area)      33% height, position: relative, padding: 16px
│   ├── SplashScreen              First load only — overlays InfoPanel, exits via slide-left
│   ├── BaselinePanel             Session identity + assembly state (toolType: 'baseline')
│   ├── GateInfoPanel             Gate structure UI
│   ├── HuginnNewsPanel           Signal broadcast panel
│   ├── ToolOutputFormatter       All other tool output types (routes to sub-panels)
│   └── nav bar                   Tier-filtered command shortcuts, below panel content
├── .terminal-output              flex: 1, overflow-y auto — scrolling log area
│   ├── .terminal-line            One entry per log item
│   │   ├── TripCalculatorForm    type: 'form' — inline route calculator
│   │   ├── help-grid             type: 'help' — /help command output
│   │   ├── BoardPanel            type: 'board' — tribe post board
│   │   ├── AdminPanel            type: 'admin' — feature flag configuration
│   │   ├── ReconForm             type: 'recon' — radius search
│   │   └── LogUploadPanel        type: 'upload' — log file upload
│   └── .feral-flicker            Animated streaming indicator, visible while AI is responding
└── form.terminal-input-area      flex-shrink: 0, no padding (border on input-wrapper)
    └── .input-wrapper            border: 1px, padding: 8px 16px, flex row
        ├── .prompt               '> ' indicator
        ├── .input-field-wrapper  Custom input: fake-input (display) + hidden-input (real)
        └── .submit-btn           Send button
```

`GateUI` and `TurretUI` are alternate structure layouts. `StructureRouter` selects among them based on assembly type from `useSmartObject()`.

---

## Component Map

| Component | Purpose |
|-----------|---------|
| `StructureRouter` | Top-level router: dispatches to GateUI, TurretUI, or TerminalUI based on assembly type |
| `TerminalUI` | Main companion chat UI: commands, SSE chat stream, tool output display |
| `InfoPanel` | Animated panel host — slide-out/swap/slide-in on tool output change |
| `SplashScreen` | Startup HUGINN ASCII art animation |
| `BaselinePanel` | Session identity: assembly, owner, tribe, location, fuel |
| `ToolOutputFormatter` | Routes tool output data to the correct display component |
| `NetworkMapPanel` | Connected assemblies on a network node |
| `InventoryPanel` | SSU inventory: capacity, items sorted by category |
| `AssetMapPanel` | Character-owned assemblies across the tenant |
| `RoutePanel` | Planned route: jumps, LY, fuel, hop-by-hop with EVE XML copy |
| `NodesListPanel` | All network nodes in tenant: fuel, burn rate, hours remaining |
| `GateInfoPanel` | Gate: source/dest systems, status, linked gate info |
| `HuginnNewsPanel` | Huginn signal broadcast header + body |
| `AdminPanel` | Feature flags, tool flags, vetted wallet management |
| `BoardPanel` | Tribe post board with live SSE updates, post/delete |
| `TripCalculatorForm` | Route planning form (ship profile, cargo, fuel) |
| `ReconForm` | Radius search form |
| `LogUploadPanel` | Game client log upload and analysis results |
| `PanelHr` | Edge-to-edge divider line (heavy `═` or light `─`) |

---

## Panel Rendering System

All panel text goes through a two-component pipeline:

### `PanelHr` (`src/components/PanelHr.tsx`)

Renders a single edge-to-edge horizontal rule. Uses negative margins to break out of `#visual-area`'s 16px padding:

```css
.panel-hr { margin: 0 calc(-1 * var(--panel-padding)); border-top: 1px solid var(--c-primary); }
```

`--panel-padding: 16px` is defined on `#visual-area` in `panel-lines.css`. Changing this one value keeps the math correct automatically.

Props: `light?: boolean` — false = heavy line (`═` detection), true = light line (`─` detection).

### `renderPanelLines` (`src/utils/renderPanelLines.tsx`)

Accepts `string | string[]`. Splits if a string. For each line:

- All `═` characters → `<PanelHr />` (heavy, edge-to-edge)
- All `─` characters → `<PanelHr light />` (light, edge-to-edge)
- Anything else → `<div className="panel-text-line">` with `\u00A0` for empty lines

Detection is character-level, not length-based — works at any string length or container width.

Returns `<div className="panel-lines">` containing the mapped elements.

### `ToolOutputFormatter` (`src/components/ToolOutputFormatter.tsx`)

Routes by `toolType` to the correct component or formatter function:

| toolType | Handler |
|----------|---------|
| `baseline` | `BaselinePanel` (separate component, not via ToolOutputFormatter) |
| `system_intel` | `SystemIntelPanel` (inline, with EVE XML copy button) |
| `threat_assessment` | `formatThreat()` → `renderPanelLines()` |
| `pilot_profile` | `formatPilotProfile()` → `renderPanelLines()` |
| `memory_search` | `formatMemorySearch()` → `renderPanelLines()` |
| `memory_summary` | `formatMemorySummary()` → `renderPanelLines()` |
| `network_map` | `NetworkMapPanel` |
| `inventory` | `InventoryPanel` |
| `asset_map` | `AssetMapPanel` |
| `route_planned` | `RoutePanel` |
| `nodes_list` | `NodesListPanel` |
| `build_options` | `BuildOrderPanel` (inline sub-component) |

`NodesListPanel` imports `PanelHr` directly instead of using `renderPanelLines` — it renders line-by-line with interactive `[PRINT]` spans.

---

## AI Tool Output Data Flow

```
POST /companion/stream (SSE)
  │
  ├── { text: "..." }           → onTextChunk → accumulated text buffer → terminal log
  ├── { tool_result: {...} }    → onToolResult → displayToolOutput(toolType, data)
  ├── { done: true }            → onDone → finalize, wind-down feral ticker
  └── { error: "..." }         → onError → log error line
          │
          ▼
    useToolOutput.display(toolType, data)
          │
          ▼
    InfoPanel reads { current, isAnimating }
          │
    isAnimating=true → slide-out (250ms) → swap content → slide-in (500ms)
          │
          ▼
    InfoPanel dispatches to:
      BaselinePanel (toolType='baseline')
      GateInfoPanel (toolType='gate_info')
      HuginnNewsPanel (toolType='huginn_news')
      ToolOutputFormatter (all other types)
          │
          ▼
    Component → renderPanelLines(lines[]) → PanelHr / panel-text-line divs
```

`useToolOutput` queues updates when an animation is already in progress — multiple rapid tool results don't conflict.

---

## Hooks

| Hook | Purpose | Key returns |
|------|---------|------------|
| `useCompanionStream` | Stream AI chat via SSE from `/companion/stream` | `{ sendMessage }` |
| `useToolOutput` | Queue and animate tool output panel updates | `{ current, isAnimating, display, finishAnimation, setDirect, clearQueue }` |
| `useSession` | Multi-stage init: admin config → session register → character/tribe → presence ping | `{ featureFlags, toolFlags, toolRegistry, tier, visitorName, tribeId, characterId, sessionRegistered, sessionTenant }` |
| `useWatcherAlerts` | Persistent SSE to `/watcher/alerts/stream`, auto-reconnect | `onAlert` callback |
| `useTribePosts` | Persistent SSE to `/tribe-posts/{tribeId}/stream`, snapshot + delta events | `{ posts }` |
| `useSystemNames` | Fetch and cache solar system name lookup map | `{ systemNames }` |

`useSession` runs four sequential stages gated by available data:
1. Admin config + tool registry (on mount)
2. Session register (needs wallet + assembly ID)
3. Character name + tribe ID from Sui GraphQL via dapp-kit
4. Tribe presence ping (needs wallet + tribeId)

---

## Context

### `EntityContext` (`src/context/EntityContext.tsx`)

Provides enriched assembly data to all components. Runs four parallel React Query queries:

| Query | Endpoint | Gate condition |
|-------|---------|---------------|
| `enrichedAssembly` | `/entity/assembly/{id}` | assemblyId + tenant |
| `networkData` | `/entity/network/{nodeId}` | assembly has network_node |
| `inventoryData` | `/entity/inventory/{id}` | assemblyId + isSSU |
| `characterAssemblies` | Sui GraphQL (via dapp-kit) | walletAddress |

Stale time: 30s. Tenant is detected from URL `?tenant=` param → assembly package ID → `/config` endpoint, in priority order.

---

## CSS Architecture

Four CSS files, each owning a distinct concern. Do not merge them.

| File | Owns |
|------|------|
| `src/index.css` | CSS variables (color palette, RGB variants), body/root reset, scrollbar hiding |
| `src/styles/terminal.css` | All TerminalUI layout: `.terminal-ui`, `.terminal-output`, `.terminal-input-area`, `.input-wrapper`, line classes, admin panel, recon form, trip calculator, help grid, upload panel |
| `src/styles/panel-lines.css` | Panel rendering: `--panel-padding`, `.panel-lines`, `.panel-text-line`, `.panel-hr`, `.panel-hr-light` |
| `src/styles/info-panel.css` | InfoPanel slide animation, copy button, nav bar |

### Color variables (`src/index.css`)

| Variable | Value | Use |
|----------|-------|-----|
| `--c-primary` | `#d4701a` | Main text, borders, dividers |
| `--c-primary-rgb` | `212, 112, 26` | Text-shadow glow calculations |
| `--c-accent` | `#f08030` | AI responses, highlights |
| `--c-accent-rgb` | `240, 128, 48` | Accent glow |
| `--c-muted` | `#8a4818` | Labels, secondary text |
| `--c-dim` | `#5a2e0c` | Placeholders, very faint |
| `--c-border` | `#3d1e08` | Subtle internal borders |
| `--c-error` | `#ca6a6a` | Errors, warnings |
| `--c-error-rgb` | `202, 106, 106` | Error glow |
| `--c-success` | `#6aca6a` | Success states |
| `--c-bg-hover` | `#1a0800` | Hover background |

Text-shadow glow pattern: `0 0 6px rgba(var(--c-primary-rgb), 0.6)` — applied to all content text and panel-hr borders for consistent glow.

Window frame: `box-shadow: inset 0 0 144px rgba(0,0,0,0.54), inset 0 0 0 1px var(--c-primary)` on `.terminal-ui`.

---

## Tier and Feature System

### Tiers (`src/features/tierCapabilities.ts`)

| Tier | Who | Nav access |
|------|-----|-----------|
| `NONE` | Unregistered guest | recon, route, upload |
| `VETTED` | Vouched wallet | recon, route, upload |
| `TRIBE` | Structure tribe member | + network, inventory, assets, nodes, signal, board, tribe, courier, watches |
| `OWNER` | Structure owner | All + admin, signal broadcast |

`getActiveNavItemsForTier(tier, flags, features)` computes the nav bar items shown in InfoPanel.

### Feature flags (`src/features/featureFlags.ts`)

Features defined in `FEATURES` object. Each has `label`, `nav` (nav button label or null), `command`, `defaultOn`. Flags are fetched from `/admin/config` at session init and cached in `localStorage`. Disabled features hide nav items and block their commands. Tool flags control which AI tools are available per session.

---

## Types (`src/types/terminal.ts`)

The `ToolType` union lists all valid tool output types:

```
'baseline' | 'system_intel' | 'threat_assessment' | 'pilot_profile' |
'memory_search' | 'memory_summary' | 'network_map' | 'inventory' |
'asset_map' | 'route_planned' | 'nodes_list' | 'build_options' |
'gate_info' | 'huginn_news'
```

Each tool type has a corresponding data interface (e.g. `SystemIntelData`, `NetworkMapData`). All interfaces are in `terminal.ts`. `ToolOutputFormatter` and `InfoPanel` receive `data: any` and cast to the specific type after switching on `toolType`.

---

## Constants and Utilities

### `src/constants/dividers.ts`

```
DIVIDER  — 84 × '═'  (heavy panel border, calibrated to 787px viewport)
SUBDIV   — 84 × '─'  (light panel border)
```

Push these strings into `lines[]` arrays in panel components. `renderPanelLines` detects them and renders `PanelHr` components. Do not render them directly in `<pre>` blocks.

### `src/utils/formatters.ts`

| Function | Purpose |
|----------|---------|
| `pad(s, len)` | Left-pad string to width |
| `padR(s, len)` | Right-pad (right-aligned numbers) |
| `fmtNum(n)` | Thousands-separator formatting |
| `fmtVol(n)` | Volume to 2 decimal places |
| `copyText(text)` | Clipboard write via textarea + execCommand (HTTP-safe fallback) |

### `src/utils/baselineBuilder.ts`

`buildBaselineData()` — pure function, assembles `BaselinePanelData` from session state and enriched assembly data. Call this when constructing the baseline panel payload.

### `src/utils/assemblyUtils.ts`

| Export | Purpose |
|--------|---------|
| `TYPE_LABEL` | Assembly type → short label (NODE, SSU, GATE, TURT, MFG, REF) |
| `TYPE_PRIORITY` | Sort order for asset lists |
| `statusRank()` | ONLINE=0, OFFLINE=1, DESTROYED=2 |
| `applyNetworkFilter()` | Filter connected assemblies by portable type IDs |

---

## Adding a New Tool Output Type

1. Add the type name to the `ToolType` union in `src/types/terminal.ts`
2. Add a data interface to `terminal.ts`
3. Add a case in `ToolOutputFormatter` — either a formatter function → `renderPanelLines()` or a new panel component
4. If adding a new component, use `renderPanelLines(lines)` for output and `PanelHr` directly for any manual line-by-line rendering
5. Push `DIVIDER` and `SUBDIV` strings into the `lines[]` array as needed — do not render raw `<pre>` text
