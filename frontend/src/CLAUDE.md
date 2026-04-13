# frontend/src/ -- React Components and Hooks

## Component Hierarchy

`main.tsx` -> `App.tsx` -> `EntityProvider` -> `StructureRouter`

StructureRouter dispatches by assembly type (from `useSmartObject()`):
- **TerminalUI** -- SSU / default (primary UI, 475 lines)
- **GateUI** -- SmartGate (landscape 782x686, on-chain transactions)
- **TurretUI** -- SmartTurret (portrait 281x886, button-driven)

## Panel System

TerminalUI layout: InfoPanel (top 33%) | terminal-output (middle, scrolling) | input area (bottom).

InfoPanel hosts tool output with slide animations. ToolOutputFormatter routes by type:

| toolType | Component | What it shows |
|----------|-----------|--------------|
| baseline | BaselinePanel | Session identity, assembly state, fuel |
| gate_info | GateInfoPanel | Gate status and destination |
| huginn_news | HuginnNewsPanel | Signal broadcast |
| network_map | NetworkMapPanel | Connected assemblies, fuel % |
| inventory | InventoryPanel | SSU inventory items |
| asset_map | AssetMapPanel | Character's assemblies across space |
| route | RoutePanel | Planned route with hop-by-hop detail |
| nodes_list | NodesListPanel | Network node table |
| (other) | ToolOutputFormatter | Generic formatted output (threat, intel, memory, build) |

## Inline Components (rendered in terminal-output)

| Trigger | Component |
|---------|-----------|
| /recon | ReconForm |
| /route | TripCalculatorForm |
| /upload | LogUploadPanel |
| /admin | AdminPanel |
| /board | BoardPanel |
| /help | help-grid (inline) |

## Hooks

| Hook | Purpose |
|------|---------|
| useCompanionStream | SSE streaming to POST /companion/stream |
| useSession | Session registration, tier resolution, character enrichment |
| useToolOutput | Animation queue for panel transitions |
| useWatcherAlerts | SSE for SSU state change alerts |
| useTribePosts | SSE for tribe post updates |
| useSystemNames | System name autocomplete (module-level cache) |

## Context

`EntityContext.tsx` -- React Query enrichment layer. Four parallel queries:
1. enrichedAssembly (GET /entity/assembly/{id})
2. networkData (GET /entity/network/{nodeId})
3. inventoryData (GET /entity/inventory/{id}, SSU only)
4. characterAssemblies (Sui GraphQL getCharacterAndOwnedObjects)

Tenant auto-detection: URL `?tenant=` param > assembly package ID mapping > backend config.

## CSS

7 files in `src/styles/`:
- terminal.css -- main layout, CRT scanlines, chat history, forms
- info-panel.css -- panel host, slide animations, nav bar
- panel-lines.css -- line rendering, PanelHr dividers
- panel-formatter.css -- tool output formatting
- gate.css, turret.css -- structure-specific layouts
- splash.css -- ASCII art reveal, loading text

Color scheme: `#d4701a` primary (amber), `#f08030` accent, `#ca6a6a` error, `#6aca6a` success, `#000` background. All monospace (Courier New).

## Tier and Feature System

- `features/tierCapabilities.ts` -- NONE/VETTED/TRIBE/OWNER definitions, per-tier nav items
- `features/featureFlags.ts` -- admin-toggled feature and tool flags, localStorage cache

## Deep Reference

- Full panel rendering pipeline: `docs/FRONTEND_UI.md`
- dapp-kit hooks and utilities: `docs/DAPP_KIT_API.md`
