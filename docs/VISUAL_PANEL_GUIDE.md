# Visual Info Panel Guide

The visual info panel is the top 33% of the terminal UI that displays contextual information retrieved by AI tools and user commands. It uses smooth animations and ASCII formatting to show real-time game state.

## Architecture

Three-layer design:

```
┌─────────────────────────────────────────────┐
│ BuildingAITerminal (app-building.js)        │
│ - Manages overall terminal state             │
│ - Routes tool results to InfoPanel           │
└──────────────────┬──────────────────────────┘
                   │ displayToolOutput(toolName, data)
                   ↓
┌─────────────────────────────────────────────┐
│ InfoPanel (info-panel.js)                   │
│ - Manages panel state & animations           │
│ - Routes to appropriate formatter            │
│ - Handles slide transitions                  │
└──────────────────┬──────────────────────────┘
                   │ _formatByToolType(type, data)
                   ↓
┌─────────────────────────────────────────────┐
│ ToolOutputFormatter (panel-formatter.js)    │
│ - Converts raw data → ASCII panels           │
│ - Handles truncation & defaults              │
│ - Formats 6 tool output types                │
└─────────────────────────────────────────────┘
```

## Components

### ToolOutputFormatter
Utility class that converts tool output objects into formatted ASCII strings.

**Methods:**
- `formatBaseline(data)` - Landing state with 6 fields
- `formatSystemIntel(data)` - System info (star class, planets, threats, etc.)
- `formatThreat(data)` - Threat assessment (level, aggressor, ship type)
- `formatPilotProfile(data)` - Pilot history (visits, tier, dates)
- `formatMemorySearch(data)` - Search results with bullet list
- `formatMemorySummary(data)` - Activity summary (attacks, contacts, docking)

**Output format:**
- 8 lines: divider + 6 fields + divider
- Left-aligned labels (38 chars padding)
- Right-aligned values
- Empty fields default to `[REDACTED]`
- Long values truncated with ellipsis (...)

**Example:**
```javascript
const formatter = new ToolOutputFormatter();
const output = formatter.formatSystemIntel({
  system: 'UR8-K7K',
  starClass: 'K5V',
  minTemp: '45',
  planets: '8',
  kills24h: '2',
  gates: '3'
});
```

### InfoPanel
State machine that manages panel content, animations, and tool routing.

**State:**
- `currentContent` - Currently displayed text
- `nextContent` - Queued content (if animating)
- `isAnimating` - Flag to prevent animation conflicts

**Public methods:**
- `display(toolType, data)` - Display tool output with animation
- `setContent(content)` - Update content without animating

**Animation sequence (750ms total):**
1. Current content slides right (250ms) → translateX(100%)
2. Content swaps instantly
3. New content slides in from left (500ms) → translateX(-100%) to 0

**Tool type routing:**
```
'baseline' → formatBaseline()
'system_intel' → formatSystemIntel()
'threat_assessment' → formatThreat()
'pilot_profile' → formatPilotProfile()
'memory_search' → formatMemorySearch()
'memory_summary' → formatMemorySummary()
```

**Example:**
```javascript
infoPanel.display('system_intel', {
  system: 'UR8-K7K',
  starClass: 'K5V',
  minTemp: '45',
  planets: '8',
  kills24h: '2',
  gates: '3'
});
```

### BuildingAITerminal Integration
The main app imports InfoPanel and wires tool results to the panel.

**Initialization (in constructor):**
```javascript
const visualArea = document.querySelector('#visual-area');
this.infoPanel = new InfoPanel(visualArea);
```

**Displaying tool results:**
```javascript
displayToolOutput(toolName, toolResult) {
  const toolTypeMap = {
    'assess_threat': 'threat_assessment',
    'get_system_intel': 'system_intel',
    'get_pilot_profile': 'pilot_profile',
    'search_memory': 'memory_search',
    'get_memory_summary': 'memory_summary'
  };
  const formatterType = toolTypeMap[toolName] || toolName;
  this.infoPanel.display(formatterType, toolResult);
}
```

When the backend sends tool results via SSE (`obj.tool_result`), the app automatically calls `displayToolOutput()` to render it.

## Styling

### CSS (`static/styles/info-panel.css`)
- Transitions: 250ms ease-out for slide-out
- Animations: 500ms ease-out for slide-in
- Colors inherited from terminal theme (#c8a560 gold, #000 black)

### HTML structure
```html
<div class="terminal-screen">
  <div id="visual-area"></div>  <!-- 33% height, InfoPanel renders here -->
  <div id="chat-history"></div> <!-- 67% flex, chat messages -->
  <input id="input-field" />     <!-- Bottom, user input -->
</div>
```

## Usage Examples

### Trigger panel update from console
```javascript
// System intel
window.buildingAI.infoPanel.display('system_intel', {
  system: 'UR8-K7K',
  starClass: 'K5V',
  minTemp: '45',
  planets: '8',
  kills24h: '2',
  gates: '3'
});

// Threat assessment
window.buildingAI.infoPanel.display('threat_assessment', {
  level: 'ELEVATED',
  topAggressor: 'PirateCorp',
  dominantShip: 'Frigate',
  escalation: '+2'
});
```

### Enable optional typing effect
```javascript
window.buildingAI.infoPanel.useTypingEffect = true;
window.buildingAI.infoPanel.display('baseline', {});
// Text will type out character-by-character at 20ms intervals
```

### Queue animations
If animations are running, `display()` calls queue the next content:
```javascript
infoPanel.display('system_intel', data1);
// Animation running...
infoPanel.display('threat_assessment', data2);
// data2 queued, displays after data1 animation completes
```

## Adding New Tool Output Formats

1. **Add test** in `static/js/tests/panel-formatter.test.js`
2. **Implement formatter** in `static/js/panel-formatter.js`
   - Method name: `format<ToolName>(data = {})`
   - Return: 8-line ASCII string with dividers
   - Include defaults for all fields
   - Use `_padLabel()` and `_truncateValue()` helpers
3. **Add routing** in `info-panel.js` `_formatByToolType()`
   - Add switch case mapping tool type → formatter
4. **Wire in BuildingAITerminal** `displayToolOutput()`
   - Add tool name → formatter type mapping

Example:
```javascript
// 1. Test
describe('formatNewTool', () => {
  it('should format new tool data', () => {
    const formatter = new ToolOutputFormatter();
    const result = formatter.formatNewTool({ field1: 'value1' });
    expect(result).toContain('FIELD1:');
    expect(result.split('\n').length).toBe(8);
  });
});

// 2. Implementation
formatNewTool(data = {}) {
  const defaults = { field1: '[REDACTED]' };
  const config = { ...defaults, ...data };
  const lines = [
    this.divider,
    this._padLabel('FIELD1:') + config.field1,
    // ... more fields ...
    this.divider
  ];
  return lines.join('\n');
}

// 3. Routing (info-panel.js)
case 'new_tool':
  return this.formatter.formatNewTool(data);

// 4. Integration (app-building.js)
'get_new_tool': 'new_tool',
```

## Testing

**Unit tests:** `npm test` (17 tests covering all formatters and animations)

**Manual testing:**
1. Load http://135.181.95.84:8745/legacy-cli
2. Open browser console (F12)
3. Trigger display: `window.buildingAI.infoPanel.display('system_intel', {...})`
4. Watch animations in the top panel

**What to verify:**
- Baseline displays on page load
- Formatting is correct (labels padded, values aligned)
- Long values truncate with ellipsis
- Empty fields show `[REDACTED]`
- Animations are smooth (slide out 250ms, slide in 500ms)
- Multiple rapid calls queue properly
- No console errors

## Performance

- **Animation latency:** < 5ms (negligible)
- **Content swap:** Instant (pre-rendered during slide-out)
- **Text rendering:** Native browser (no virtual DOM)
- **Memory:** ~50KB for all modules + styles

Animations use CSS transforms (GPU-accelerated), not layout recalculation.

## Troubleshooting

**Panel doesn't update:**
- Check console for errors (F12, Console tab)
- Verify `window.buildingAI.infoPanel` exists
- Check that tool type is in the `_formatByToolType()` switch

**Animation doesn't appear:**
- Hard refresh browser (Ctrl+Shift+R)
- Check CSS file loads (DevTools Network → info-panel.css)
- Verify `#visual-area.slide-out-right` has `transform: translateX(100%)`

**Text looks garbled:**
- Verify monospace font is applied (should be Courier New)
- Check line-height is 1.4
- Ensure `white-space: pre` is set for visual-area

**Missing formatter:**
- Verify method exists in `ToolOutputFormatter` class
- Check routing in `_formatByToolType()` switch
- Confirm tool name mapping in `displayToolOutput()`
