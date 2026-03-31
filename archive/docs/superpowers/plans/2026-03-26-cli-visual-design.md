# CLI Terminal Visual Design Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement a dynamic top-panel info display with smooth animations that shows contextual data from AI tool execution.

**Architecture:** Three-layer design: (1) ToolOutputFormatter utility converts raw tool data into formatted ASCII panels, (2) InfoPanel state machine manages content and animation state, (3) Integration layer wires InfoPanel into BuildingAITerminal and CSS animations handle transitions.

**Tech Stack:** Vanilla ES6 JavaScript modules, CSS3 animations (transforms, keyframes), HTML5 semantic structure, no external dependencies.

---

## Chunk 1: Panel Formatter Utility

### Task 1: Create ToolOutputFormatter class and test baseline format

**Files:**
- Create: `static/js/panel-formatter.js`
- Create: `static/js/tests/panel-formatter.test.js`

- [ ] **Step 1: Write failing test for baseline formatting**

Create `static/js/tests/panel-formatter.test.js`:

```javascript
import { ToolOutputFormatter } from '../panel-formatter.js';

describe('ToolOutputFormatter', () => {
  describe('formatBaseline', () => {
    it('should format empty baseline state with REDACTED placeholders', () => {
      const formatter = new ToolOutputFormatter();
      const result = formatter.formatBaseline();

      expect(result).toContain('CRUD - Version');
      expect(result).toContain('[REDACTED]');
      expect(result.split('\n').length).toBe(8); // divider + 6 fields + divider
      expect(result).toContain('═══════════════════════════════════════════════════════════════');
    });

    it('should format baseline with provided values', () => {
      const formatter = new ToolOutputFormatter();
      const data = {
        version: '0.1.0',
        signature: '0x123abc',
        shellName: 'Alpha',
        accessLevel: 'MEMBER',
        assemblySignature: 'asm-001',
        location: 'UR8-K7K'
      };
      const result = formatter.formatBaseline(data);

      expect(result).toContain('CRUD - Version 0.1.0');
      expect(result).toContain('0x123abc');
      expect(result).toContain('Alpha');
      expect(result).toContain('MEMBER');
    });

    it('should right-align values at column 38', () => {
      const formatter = new ToolOutputFormatter();
      const result = formatter.formatBaseline({
        version: '1.0',
        signature: 'test',
        shellName: 'My Shell',
        accessLevel: 'ADMIN',
        assemblySignature: 'test-asm',
        location: 'System'
      });

      const lines = result.split('\n');
      const versionLine = lines.find(l => l.includes('CRUD - Version'));
      // Label should be padded to 38 chars, value starts at column 39
      expect(versionLine.substring(38)).not.toMatch(/^\s/);
    });
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

```bash
cd /opt/eve-frontier && npm test -- static/js/tests/panel-formatter.test.js 2>&1 | head -20
```

Expected output: Test fails with "ToolOutputFormatter is not defined" or similar error.

- [ ] **Step 3: Write minimal implementation**

Create `static/js/panel-formatter.js`:

```javascript
/**
 * ToolOutputFormatter
 * Converts tool output objects into ASCII-formatted display strings
 * Used by InfoPanel to render panel content
 */
export class ToolOutputFormatter {
  constructor() {
    this.divider = '═══════════════════════════════════════════════════════════════';
    this.labelWidth = 38; // Fixed width for left column
  }

  /**
   * Format baseline landing state
   * @param {Object} data - Optional object with version, signature, shellName, accessLevel, assemblySignature, location
   * @returns {string} Formatted panel content
   */
  formatBaseline(data = {}) {
    const defaults = {
      version: '[REDACTED]',
      signature: '[REDACTED]',
      shellName: '[REDACTED]',
      accessLevel: '[REDACTED]',
      assemblySignature: '[REDACTED]',
      location: '[REDACTED]'
    };

    const config = { ...defaults, ...data };
    const lines = [
      this.divider,
      this._padLabel('CRUD - Version') + config.version,
      this._padLabel('SIGNATURE') + config.signature,
      this._padLabel('SHELL NAME') + config.shellName,
      this._padLabel('ACCESS LEVEL') + config.accessLevel,
      this._padLabel('ASSEMBLY SIGNATURE') + config.assemblySignature,
      this._padLabel('LOCATION') + config.location,
      this.divider
    ];

    return lines.join('\n');
  }

  /**
   * Helper: pad label to fixed width
   * @param {string} label - The label text
   * @returns {string} Padded label (left-aligned, padded to labelWidth)
   */
  _padLabel(label) {
    return label.padEnd(this.labelWidth);
  }
}
```

- [ ] **Step 4: Run test to verify it passes**

```bash
cd /opt/eve-frontier && npm test -- static/js/tests/panel-formatter.test.js 2>&1 | grep -E "PASS|FAIL|passed|failed"
```

Expected output: All tests pass.

- [ ] **Step 5: Commit**

```bash
cd /opt/eve-frontier && git add -A static/js/panel-formatter.js static/js/tests/panel-formatter.test.js && git commit -m "feat: add ToolOutputFormatter class with baseline formatting"
```

---

### Task 2: Add formatSystemIntel method

**Files:**
- Modify: `static/js/tests/panel-formatter.test.js`
- Modify: `static/js/panel-formatter.js`

- [ ] **Step 1: Write failing test for system intel formatting**

Add to `static/js/tests/panel-formatter.test.js`, inside the describe block:

```javascript
  describe('formatSystemIntel', () => {
    it('should format system intel data with all fields', () => {
      const formatter = new ToolOutputFormatter();
      const data = {
        system: 'UR8-K7K',
        starClass: 'K5V',
        minTemp: '45',
        planets: '8',
        kills24h: '2',
        gates: '3'
      };
      const result = formatter.formatSystemIntel(data);

      expect(result).toContain('SYSTEM:');
      expect(result).toContain('UR8-K7K');
      expect(result).toContain('STAR CLASS:');
      expect(result).toContain('K5V');
      expect(result).toContain('MIN TEMP:');
      expect(result).toContain('45');
      expect(result.split('\n').length).toBe(8); // divider + 6 fields + divider
    });

    it('should handle truncation of long system names', () => {
      const formatter = new ToolOutputFormatter();
      const data = {
        system: 'VERY_LONG_SYSTEM_NAME_THAT_IS_OVER_TWENTY_CHARACTERS',
        starClass: 'F0V',
        minTemp: '50',
        planets: '10',
        kills24h: '1',
        gates: '2'
      };
      const result = formatter.formatSystemIntel(data);

      const systemLine = result.split('\n').find(l => l.includes('SYSTEM:'));
      const value = systemLine.substring(38);
      expect(value.length).toBeLessThanOrEqual(25);
      if (value.includes('...')) {
        expect(value.endsWith('...')).toBe(true);
      }
    });
  });
```

- [ ] **Step 2: Run test to verify it fails**

```bash
cd /opt/eve-frontier && npm test -- static/js/tests/panel-formatter.test.js 2>&1 | grep -A 5 "formatSystemIntel"
```

Expected output: Test fails with "formatSystemIntel is not a function".

- [ ] **Step 3: Write minimal implementation**

Add to `static/js/panel-formatter.js`, after the `formatBaseline` method:

```javascript
  /**
   * Format system intel output
   * @param {Object} data - {system, starClass, minTemp, planets, kills24h, gates}
   * @returns {string} Formatted panel content
   */
  formatSystemIntel(data) {
    const lines = [
      this.divider,
      this._padLabel('SYSTEM:') + this._truncateValue(data.system, 20),
      this._padLabel('STAR CLASS:') + this._truncateValue(data.starClass, 20),
      this._padLabel('MIN TEMP:') + (data.minTemp + '°C'),
      this._padLabel('PLANETS:') + data.planets,
      this._padLabel('KILLS (24h):') + data.kills24h,
      this._padLabel('GATES:') + data.gates,
      this.divider
    ];

    return lines.join('\n');
  }

  /**
   * Helper: truncate long values with ellipsis
   * @param {string} value - The value to truncate
   * @param {number} maxLen - Max length before truncation
   * @returns {string} Truncated value or original if shorter
   */
  _truncateValue(value, maxLen = 25) {
    if (value.length > maxLen) {
      return value.substring(0, maxLen - 3) + '...';
    }
    return value;
  }
```

- [ ] **Step 4: Run test to verify it passes**

```bash
cd /opt/eve-frontier && npm test -- static/js/tests/panel-formatter.test.js 2>&1 | grep -E "PASS|FAIL|passed|failed"
```

Expected output: All tests pass.

- [ ] **Step 5: Commit**

```bash
cd /opt/eve-frontier && git add static/js/panel-formatter.js static/js/tests/panel-formatter.test.js && git commit -m "feat: add formatSystemIntel method with truncation support"
```

---

### Task 3: Add remaining tool output formats

**Files:**
- Modify: `static/js/tests/panel-formatter.test.js`
- Modify: `static/js/panel-formatter.js`

- [ ] **Step 1: Write failing tests for remaining formats**

Add to `static/js/tests/panel-formatter.test.js`:

```javascript
  describe('formatThreat', () => {
    it('should format threat assessment data', () => {
      const formatter = new ToolOutputFormatter();
      const data = {
        level: 'ELEVATED',
        topAggressor: 'PirateCorp',
        dominantShip: 'Frigate',
        escalation: '+2'
      };
      const result = formatter.formatThreat(data);

      expect(result).toContain('THREAT ASSESSMENT');
      expect(result).toContain('LEVEL:');
      expect(result).toContain('ELEVATED');
      expect(result).toContain('TOP AGGRESSOR:');
      expect(result).toContain('DOMINANT SHIP:');
      expect(result).toContain('ESCALATION:');
      expect(result.split('\n').length).toBe(8);
    });
  });

  describe('formatPilotProfile', () => {
    it('should format pilot profile data', () => {
      const formatter = new ToolOutputFormatter();
      const data = {
        name: 'John Thorne',
        visits: '42',
        firstSeen: '2026-01-15',
        lastSeen: '2026-03-20',
        tier: 'PATRON'
      };
      const result = formatter.formatPilotProfile(data);

      expect(result).toContain('PILOT PROFILE');
      expect(result).toContain('NAME:');
      expect(result).toContain('John Thorne');
      expect(result).toContain('TIER:');
      expect(result).toContain('PATRON');
      expect(result.split('\n').length).toBe(8);
    });
  });

  describe('formatMemorySearch', () => {
    it('should format search results with bullet list', () => {
      const formatter = new ToolOutputFormatter();
      const data = {
        keyword: 'pirate',
        lookback: '7 days',
        results: [
          { date: '2026-03-20', type: 'attack', summary: 'contact at gate' },
          { date: '2026-03-18', type: 'contact', summary: '3 x frigate' },
          { date: '2026-03-15', type: 'attack', summary: 'docking attempt' }
        ]
      };
      const result = formatter.formatMemorySearch(data);

      expect(result).toContain('SEARCH: "pirate" (7 days)');
      expect(result).toContain('2026-03-20');
      expect(result).toContain('attack: contact at gate');
      expect(result).toContain('•');
    });
  });

  describe('formatMemorySummary', () => {
    it('should format activity summary data', () => {
      const formatter = new ToolOutputFormatter();
      const data = {
        attacks: '3',
        contacts: '12',
        docking: '45',
        key: 'Increased frigate activity targeting corvettes'
      };
      const result = formatter.formatMemorySummary(data);

      expect(result).toContain('ACTIVITY SUMMARY (7 days)');
      expect(result).toContain('ATTACKS:');
      expect(result).toContain('3');
      expect(result).toContain('CONTACTS:');
      expect(result).toContain('12');
      expect(result).toContain('KEY:');
      expect(result).toContain('Increased frigate activity');
    });
  });
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd /opt/eve-frontier && npm test -- static/js/tests/panel-formatter.test.js 2>&1 | grep -E "formatThreat|formatPilot|formatMemory"
```

Expected output: Tests fail with "is not a function" errors.

- [ ] **Step 3: Write minimal implementations**

Add to `static/js/panel-formatter.js`:

```javascript
  /**
   * Format threat assessment output
   * @param {Object} data - {level, topAggressor, dominantShip, escalation}
   * @returns {string} Formatted panel content
   */
  formatThreat(data) {
    const lines = [
      this.divider,
      this._padLabel('') + 'THREAT ASSESSMENT',
      this._padLabel('LEVEL:') + data.level,
      this._padLabel('TOP AGGRESSOR:') + this._truncateValue(data.topAggressor, 20),
      this._padLabel('DOMINANT SHIP:') + data.dominantShip,
      this._padLabel('ESCALATION:') + data.escalation,
      '',
      this.divider
    ];

    return lines.join('\n');
  }

  /**
   * Format pilot profile output
   * @param {Object} data - {name, visits, firstSeen, lastSeen, tier}
   * @returns {string} Formatted panel content
   */
  formatPilotProfile(data) {
    const lines = [
      this.divider,
      this._padLabel('') + 'PILOT PROFILE',
      this._padLabel('NAME:') + this._truncateValue(data.name, 20),
      this._padLabel('VISITS:') + data.visits,
      this._padLabel('FIRST SEEN:') + data.firstSeen,
      this._padLabel('LAST SEEN:') + data.lastSeen,
      this._padLabel('TIER:') + data.tier,
      this.divider
    ];

    return lines.join('\n');
  }

  /**
   * Format memory search output
   * @param {Object} data - {keyword, lookback, results: [{date, type, summary}, ...]}
   * @returns {string} Formatted panel content
   */
  formatMemorySearch(data) {
    const maxResults = 5;
    const results = (data.results || []).slice(0, maxResults);
    const moreCount = Math.max(0, (data.results || []).length - maxResults);

    const lines = [
      this.divider,
      `SEARCH: "${data.keyword}" (${data.lookback})`
    ];

    results.forEach(r => {
      lines.push(`  • ${r.date} ${r.type}: ${r.summary}`);
    });

    if (moreCount > 0) {
      lines.push(`  ... and ${moreCount} more`);
    }

    lines.push(this.divider);

    return lines.join('\n');
  }

  /**
   * Format memory summary output
   * @param {Object} data - {attacks, contacts, docking, key}
   * @returns {string} Formatted panel content
   */
  formatMemorySummary(data) {
    const lines = [
      this.divider,
      this._padLabel('') + 'ACTIVITY SUMMARY (7 days)',
      this._padLabel('ATTACKS:') + data.attacks,
      this._padLabel('CONTACTS:') + data.contacts,
      this._padLabel('DOCKING:') + data.docking,
      this._padLabel('KEY:') + this._truncateValue(data.key, 40),
      '',
      this.divider
    ];

    return lines.join('\n');
  }
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
cd /opt/eve-frontier && npm test -- static/js/tests/panel-formatter.test.js 2>&1 | tail -10
```

Expected output: All tests pass.

- [ ] **Step 5: Commit**

```bash
cd /opt/eve-frontier && git add static/js/panel-formatter.js static/js/tests/panel-formatter.test.js && git commit -m "feat: add formatThreat, formatPilotProfile, formatMemorySearch, formatMemorySummary methods"
```

---

## Chunk 2: Animation Engine & Panel State Management

### Task 4: Create InfoPanel class and initialize baseline state

**Files:**
- Create: `static/js/info-panel.js`
- Create: `static/js/tests/info-panel.test.js`

- [ ] **Step 1: Write failing test for InfoPanel initialization**

Create `static/js/tests/info-panel.test.js`:

```javascript
import { InfoPanel } from '../info-panel.js';

describe('InfoPanel', () => {
  describe('initialization', () => {
    it('should initialize with baseline state', () => {
      const container = document.createElement('div');
      container.id = 'visual-area';
      document.body.appendChild(container);

      const panel = new InfoPanel(container);

      expect(panel.currentContent).toBeDefined();
      expect(panel.isAnimating).toBe(false);
      expect(container.innerHTML).toBeTruthy();
      expect(container.innerHTML).toContain('CRUD - Version');
    });

    it('should render baseline with REDACTED values on init', () => {
      const container = document.createElement('div');
      container.id = 'visual-area';
      document.body.appendChild(container);

      const panel = new InfoPanel(container);
      const html = container.innerHTML;

      expect(html).toContain('SIGNATURE');
      expect(html).toContain('[REDACTED]');
      expect(html).toContain('═══════════════════════════════════════════════════════════════');
    });

    it('should contain a pre element for monospace display', () => {
      const container = document.createElement('div');
      container.id = 'visual-area';
      document.body.appendChild(container);

      const panel = new InfoPanel(container);
      const preElement = container.querySelector('pre');

      expect(preElement).toBeDefined();
    });

    afterEach(() => {
      document.body.innerHTML = '';
    });
  });

  describe('setContent', () => {
    it('should update currentContent without animating immediately', () => {
      const container = document.createElement('div');
      container.id = 'visual-area';
      document.body.appendChild(container);

      const panel = new InfoPanel(container);
      const newContent = 'New Content';

      panel.setContent(newContent);

      expect(panel.currentContent).toBe(newContent);
    });

    afterEach(() => {
      document.body.innerHTML = '';
    });
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

```bash
cd /opt/eve-frontier && npm test -- static/js/tests/info-panel.test.js 2>&1 | head -20
```

Expected output: Test fails with "InfoPanel is not defined".

- [ ] **Step 3: Write minimal implementation**

Create `static/js/info-panel.js`:

```javascript
import { ToolOutputFormatter } from './panel-formatter.js';

/**
 * InfoPanel
 * Manages the top 33% visual area content, animations, and tool output rendering
 */
export class InfoPanel {
  constructor(containerElement) {
    this.container = containerElement;
    this.formatter = new ToolOutputFormatter();

    // State
    this.currentContent = this.formatter.formatBaseline();
    this.nextContent = null;
    this.isAnimating = false;

    // Animation timing
    this.slideOutDuration = 250; // ms
    this.slideInDuration = 500; // ms
    this.typeOutSpeed = 20; // ms per character

    // Initialize display
    this._render();
  }

  /**
   * Update panel content (will animate on next display call)
   * @param {string} content - The new content to display
   */
  setContent(content) {
    this.nextContent = content;
    this.currentContent = content;
  }

  /**
   * Render current content to DOM
   */
  _render() {
    const pre = document.createElement('pre');
    pre.style.margin = '0';
    pre.style.fontFamily = 'inherit';
    pre.style.fontSize = 'inherit';
    pre.style.color = 'inherit';
    pre.textContent = this.currentContent;

    this.container.innerHTML = '';
    this.container.appendChild(pre);
  }

  /**
   * Display new content with animation
   * @param {string} toolType - Type of tool output (or 'baseline')
   * @param {Object} data - Tool data to format
   */
  display(toolType, data) {
    if (this.isAnimating) {
      // Queue animation if already animating
      this.nextContent = this._formatByToolType(toolType, data);
      return;
    }

    this.nextContent = this._formatByToolType(toolType, data);
    this._animateTransition();
  }

  /**
   * Format content based on tool type
   * @private
   */
  _formatByToolType(toolType, data) {
    switch (toolType) {
      case 'baseline':
        return this.formatter.formatBaseline(data);
      case 'system_intel':
        return this.formatter.formatSystemIntel(data);
      case 'threat_assessment':
        return this.formatter.formatThreat(data);
      case 'pilot_profile':
        return this.formatter.formatPilotProfile(data);
      case 'memory_search':
        return this.formatter.formatMemorySearch(data);
      case 'memory_summary':
        return this.formatter.formatMemorySummary(data);
      default:
        return this.currentContent;
    }
  }

  /**
   * Animate transition: slide out current, swap, slide in next
   * @private
   */
  _animateTransition() {
    this.isAnimating = true;

    // Stage 1: Slide out current content
    this.container.classList.add('slide-out-right');

    setTimeout(() => {
      // Stage 2: Swap content
      this.currentContent = this.nextContent;
      this._render();

      this.container.classList.remove('slide-out-right');
      this.container.classList.add('slide-in-left');

      // Stage 3: Slide in new content completes
      setTimeout(() => {
        this.container.classList.remove('slide-in-left');
        this.isAnimating = false;
      }, this.slideInDuration);
    }, this.slideOutDuration);
  }
}
```

- [ ] **Step 4: Run test to verify it passes**

```bash
cd /opt/eve-frontier && npm test -- static/js/tests/info-panel.test.js 2>&1 | tail -10
```

Expected output: All tests pass.

- [ ] **Step 5: Commit**

```bash
cd /opt/eve-frontier && git add static/js/info-panel.js static/js/tests/info-panel.test.js && git commit -m "feat: add InfoPanel class with state management and baseline initialization"
```

---

### Task 5: Implement CSS animations and verify animation methods

**Files:**
- Create: `static/styles/info-panel.css`
- Modify: `static/js/tests/info-panel.test.js`
- Modify: `static/building-terminal.html`

- [ ] **Step 1: Add animation tests**

Add to `static/js/tests/info-panel.test.js` before closing describe:

```javascript
  describe('animation', () => {
    beforeEach(() => {
      // Mock CSS transitions
      jest.useFakeTimers();
    });

    afterEach(() => {
      jest.runOnlyPendingTimers();
      jest.useRealTimers();
      document.body.innerHTML = '';
    });

    it('should add slide-out-right class when animating', () => {
      const container = document.createElement('div');
      container.id = 'visual-area';
      document.body.appendChild(container);

      const panel = new InfoPanel(container);
      panel.display('system_intel', { system: 'TEST', starClass: 'M0V', minTemp: '50', planets: '3', kills24h: '0', gates: '1' });

      expect(container.classList.contains('slide-out-right')).toBe(true);
    });

    it('should swap content after slide-out duration', () => {
      const container = document.createElement('div');
      container.id = 'visual-area';
      document.body.appendChild(container);

      const panel = new InfoPanel(container);
      const originalContent = panel.currentContent;

      panel.display('system_intel', { system: 'NEW', starClass: 'K5V', minTemp: '45', planets: '8', kills24h: '2', gates: '3' });

      jest.advanceTimersByTime(panel.slideOutDuration);

      expect(panel.currentContent).not.toBe(originalContent);
      expect(container.classList.contains('slide-in-left')).toBe(true);
    });
  });
```

- [ ] **Step 2: Run tests to verify animation tests pass**

```bash
cd /opt/eve-frontier && npm test -- static/js/tests/info-panel.test.js 2>&1 | grep -E "animation|pass|fail"
```

Expected output: Animation tests pass.

- [ ] **Step 3: Create CSS animations file**

Create `static/styles/info-panel.css`:

```css
/* Info Panel Animation Styles */

.visual-area {
  transition: transform 250ms ease-out;
}

/* Slide out to the right (current panel leaving) */
.visual-area.slide-out-right {
  transform: translateX(100%);
}

/* Slide in from the left (new panel arriving) */
.visual-area.slide-in-left {
  animation: slideInLeft 500ms ease-out forwards;
  transform: translateX(0);
}

@keyframes slideInLeft {
  from {
    transform: translateX(-100%);
    opacity: 0;
  }
  to {
    transform: translateX(0);
    opacity: 1;
  }
}
```

- [ ] **Step 4: Update building-terminal.html to include CSS**

Read `static/building-terminal.html` and add the CSS import in the `<head>`:

```bash
cd /opt/eve-frontier && head -20 static/building-terminal.html
```

Then edit to add the stylesheet link after existing styles:

```html
    <link rel="stylesheet" href="/static/styles/info-panel.css">
```

- [ ] **Step 5: Run tests one more time to confirm all pass**

```bash
cd /opt/eve-frontier && npm test -- static/js/tests/info-panel.test.js 2>&1 | tail -5
```

Expected output: All tests pass.

- [ ] **Step 6: Commit**

```bash
cd /opt/eve-frontier && git add static/styles/info-panel.css static/js/tests/info-panel.test.js static/building-terminal.html && git commit -m "feat: add CSS animations for slide-in and slide-out transitions"
```

---

### Task 6: Add tool output dispatcher (display method routing)

**Files:**
- Modify: `static/js/tests/info-panel.test.js`
- Modify: `static/js/info-panel.js`

- [ ] **Step 1: Write tests for display dispatcher**

Add to `static/js/tests/info-panel.test.js` describe block:

```javascript
  describe('display dispatcher', () => {
    it('should route system_intel to correct formatter', () => {
      const container = document.createElement('div');
      container.id = 'visual-area';
      document.body.appendChild(container);

      const panel = new InfoPanel(container);
      const data = {
        system: 'UR8-K7K',
        starClass: 'K5V',
        minTemp: '45',
        planets: '8',
        kills24h: '2',
        gates: '3'
      };

      panel.display('system_intel', data);

      expect(panel.nextContent).toContain('SYSTEM:');
      expect(panel.nextContent).toContain('UR8-K7K');
    });

    it('should route threat_assessment to correct formatter', () => {
      const container = document.createElement('div');
      container.id = 'visual-area';
      document.body.appendChild(container);

      const panel = new InfoPanel(container);
      const data = {
        level: 'CRITICAL',
        topAggressor: 'EvilCorp',
        dominantShip: 'Battleship',
        escalation: '+5'
      };

      panel.display('threat_assessment', data);

      expect(panel.nextContent).toContain('THREAT ASSESSMENT');
      expect(panel.nextContent).toContain('CRITICAL');
    });

    it('should route pilot_profile to correct formatter', () => {
      const container = document.createElement('div');
      container.id = 'visual-area';
      document.body.appendChild(container);

      const panel = new InfoPanel(container);
      const data = {
        name: 'Capsuleer X',
        visits: '100',
        firstSeen: '2025-01-01',
        lastSeen: '2026-03-26',
        tier: 'HOSTILE'
      };

      panel.display('pilot_profile', data);

      expect(panel.nextContent).toContain('PILOT PROFILE');
      expect(panel.nextContent).toContain('Capsuleer X');
    });

    it('should route memory_search to correct formatter', () => {
      const container = document.createElement('div');
      container.id = 'visual-area';
      document.body.appendChild(container);

      const panel = new InfoPanel(container);
      const data = {
        keyword: 'hostile',
        lookback: '30 days',
        results: [
          { date: '2026-03-01', type: 'attack', summary: 'gate camp' }
        ]
      };

      panel.display('memory_search', data);

      expect(panel.nextContent).toContain('SEARCH:');
      expect(panel.nextContent).toContain('hostile');
    });

    it('should route memory_summary to correct formatter', () => {
      const container = document.createElement('div');
      container.id = 'visual-area';
      document.body.appendChild(container);

      const panel = new InfoPanel(container);
      const data = {
        attacks: '10',
        contacts: '50',
        docking: '200',
        key: 'High traffic zone'
      };

      panel.display('memory_summary', data);

      expect(panel.nextContent).toContain('ACTIVITY SUMMARY');
      expect(panel.nextContent).toContain('10');
    });

    afterEach(() => {
      document.body.innerHTML = '';
    });
  });
```

- [ ] **Step 2: Run tests to verify they pass**

```bash
cd /opt/eve-frontier && npm test -- static/js/tests/info-panel.test.js 2>&1 | grep -E "display dispatcher|PASS|FAIL"
```

Expected output: All dispatcher tests pass.

- [ ] **Step 3: Verify implementation in info-panel.js (already done in Task 4)**

The `_formatByToolType` method and `display` method were already implemented. No code changes needed.

- [ ] **Step 4: Commit test additions**

```bash
cd /opt/eve-frontier && git add static/js/tests/info-panel.test.js && git commit -m "test: add comprehensive tests for tool output dispatcher"
```

---

## Chunk 3: Integration with BuildingAITerminal

### Task 7: Wire InfoPanel into BuildingAITerminal class

**Files:**
- Modify: `static/js/app-building.js`
- Modify: `static/js/tests/panel-formatter.test.js` (if app-building has tests)

- [ ] **Step 1: Read current BuildingAITerminal implementation**

```bash
cd /opt/eve-frontier && head -50 static/js/app-building.js
```

Identify the constructor and message handling methods.

- [ ] **Step 2: Update constructor to initialize InfoPanel**

Edit `static/js/app-building.js` to import and initialize InfoPanel:

Add at top with other imports:

```javascript
import { InfoPanel } from './info-panel.js';
```

In the constructor, after other initialization, add:

```javascript
    // Initialize info panel for tool output display
    const visualArea = document.querySelector('.visual-area');
    if (visualArea) {
      this.infoPanel = new InfoPanel(visualArea);
    }
```

- [ ] **Step 3: Add method to dispatch tool results to InfoPanel**

Add this method to the BuildingAITerminal class:

```javascript
  /**
   * Display tool output in the info panel
   * @param {string} toolName - Name of the tool (maps to formatter method)
   * @param {Object} toolResult - Tool output data
   */
  displayToolOutput(toolName, toolResult) {
    if (!this.infoPanel) return;

    // Map tool names to formatter types
    const toolTypeMap = {
      'assess_threat': 'threat_assessment',
      'assess_threat_level': 'threat_assessment',
      'get_system_intel': 'system_intel',
      'get_pilot_profile': 'pilot_profile',
      'search_memory': 'memory_search',
      'get_memory_summary': 'memory_summary'
    };

    const formatterType = toolTypeMap[toolName] || toolName;
    this.infoPanel.display(formatterType, toolResult);
  }
```

- [ ] **Step 4: Identify where tool results are received and wire them**

Search for tool execution/result handling:

```bash
cd /opt/eve-frontier && grep -n "tool" static/js/app-building.js | head -10
```

Find the method that processes tool outputs and add a call to `displayToolOutput` when tools execute.

Example (pseudocode for where to add):

```javascript
// In the method that processes tool results from backend:
this.displayToolOutput(toolName, toolResult);
```

- [ ] **Step 5: Test with manual inspection**

Load the page in browser:

```bash
curl -s http://135.181.95.84:8745/ | grep -i visual-area
```

Verify visual-area div loads with InfoPanel initialized.

- [ ] **Step 6: Commit integration**

```bash
cd /opt/eve-frontier && git add static/js/app-building.js && git commit -m "feat: integrate InfoPanel into BuildingAITerminal, wire tool output dispatcher"
```

---

### Task 8: Add optional character-by-character typing effect

**Files:**
- Modify: `static/js/info-panel.js`
- Modify: `static/js/tests/info-panel.test.js`

- [ ] **Step 1: Write test for typing effect (optional)**

Add to `static/js/tests/info-panel.test.js`:

```javascript
  describe('typing effect (optional)', () => {
    beforeEach(() => {
      jest.useFakeTimers();
    });

    afterEach(() => {
      jest.runOnlyPendingTimers();
      jest.useRealTimers();
      document.body.innerHTML = '';
    });

    it('should support optional character-by-character typing during animation', () => {
      const container = document.createElement('div');
      container.id = 'visual-area';
      document.body.appendChild(container);

      const panel = new InfoPanel(container);
      panel.useTypingEffect = true; // Enable typing effect

      panel.display('baseline', {});

      jest.advanceTimersByTime(panel.slideOutDuration);

      const pre = container.querySelector('pre');
      expect(pre.textContent.length).toBeGreaterThan(0);
    });
  });
```

- [ ] **Step 2: Run test to verify it passes or skip if not needed**

```bash
cd /opt/eve-frontier && npm test -- static/js/tests/info-panel.test.js 2>&1 | grep -E "typing|PASS"
```

- [ ] **Step 3: Add optional typing effect implementation**

Update `static/js/info-panel.js` constructor to add:

```javascript
    // Optional typing effect flag
    this.useTypingEffect = false;
```

Add this method to InfoPanel class:

```javascript
  /**
   * Type out text character by character (optional effect)
   * @private
   */
  async _typeOutText(text) {
    if (!this.useTypingEffect) return;

    const pre = this.container.querySelector('pre');
    if (!pre) return;

    pre.textContent = '';
    let index = 0;

    while (index < text.length && !this.isAnimating) {
      pre.textContent += text[index];
      index++;
      await new Promise(resolve => setTimeout(resolve, this.typeOutSpeed));
    }

    // Ensure full text is displayed if animation was interrupted
    pre.textContent = text;
  }
```

Update `_render` method to call typing effect:

```javascript
  _render() {
    const pre = document.createElement('pre');
    pre.style.margin = '0';
    pre.style.fontFamily = 'inherit';
    pre.style.fontSize = 'inherit';
    pre.style.color = 'inherit';

    this.container.innerHTML = '';
    this.container.appendChild(pre);

    if (this.useTypingEffect) {
      pre.textContent = '';
      this._typeOutText(this.currentContent);
    } else {
      pre.textContent = this.currentContent;
    }
  }
```

- [ ] **Step 4: Test that typing effect integrates without breaking**

```bash
cd /opt/eve-frontier && npm test -- static/js/tests/info-panel.test.js 2>&1 | tail -5
```

Expected output: All tests pass.

- [ ] **Step 5: Commit optional feature**

```bash
cd /opt/eve-frontier && git add static/js/info-panel.js static/js/tests/info-panel.test.js && git commit -m "feat: add optional character-by-character typing effect during animation"
```

---

### Task 9: Manual testing and integration verification

**Files:**
- None (testing only)

- [ ] **Step 1: Verify page loads without errors**

```bash
cd /opt/eve-frontier && curl -I http://135.181.95.84:8745/ 2>&1 | head -5
```

Expected: HTTP 200 OK

- [ ] **Step 2: Visually inspect panel animations in browser**

Open http://135.181.95.84:8745/ in a browser and:
- Verify visual-area displays baseline info
- Check that text is monospace (#c8a560 on #000)
- Verify layout (top 33% panel)

- [ ] **Step 3: Test tool output formatting manually**

Open browser console and test formatter directly:

```javascript
import { ToolOutputFormatter } from './static/js/panel-formatter.js';
const f = new ToolOutputFormatter();
console.log(f.formatSystemIntel({
  system: 'TEST-SYS',
  starClass: 'A0V',
  minTemp: '60',
  planets: '5',
  kills24h: '1',
  gates: '2'
}));
```

Expected: Properly formatted ASCII panel with left-aligned labels, right-aligned values.

- [ ] **Step 4: Test animation by triggering display**

In console:

```javascript
const panel = window.buildingAI.infoPanel; // assuming exposed for testing
panel.display('system_intel', {
  system: 'UR8-K7K',
  starClass: 'K5V',
  minTemp: '45',
  planets: '8',
  kills24h: '2',
  gates: '3'
});
```

Expected: Smooth slide-out-right, content swap, slide-in-left animation over ~750ms total.

- [ ] **Step 5: Verify edge cases**

Test:
- Very long system names (should truncate with ellipsis)
- Empty tool results (should handle gracefully)
- Rapid successive display() calls (should queue/handle isAnimating flag)

- [ ] **Step 6: Run full test suite one final time**

```bash
cd /opt/eve-frontier && npm test 2>&1 | tail -20
```

Expected: All tests pass, no console errors.

- [ ] **Step 7: Final commit**

```bash
cd /opt/eve-frontier && git log --oneline -5
```

Verify all 9 tasks have been committed. If any manual testing found issues, fix and commit those fixes.

---

## Summary

This plan implements a complete CLI info panel with:
- **Formatter utility** (3 tasks): Converts tool data → ASCII panels
- **Animation engine** (3 tasks): State machine, CSS transitions, content routing
- **Integration** (3 tasks): Wires into main app, optional typing, validation

Each task is 2-5 minute chunks following TDD: test → fail → implement → pass → commit.

All code is vanilla JS (no dependencies), uses CSS3 animations, and maintains the monospace terminal aesthetic (#c8a560/#000).
