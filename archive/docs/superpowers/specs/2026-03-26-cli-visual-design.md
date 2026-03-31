# CLI Terminal Visual Design — EVE Frontier Structure AI

**Date:** 2026-03-26
**Scope:** Top info panel (33% viewport) visual design, animations, tool output styling
**Status:** Design approved, ready for implementation

---

## Overview

The Structure AI companion uses a **pure monospace CLI aesthetic**—no browser chrome, no graphical UI. The interface has three sections:

1. **Top 33% (visual-area):** Dynamic info panel that updates via animation
2. **Middle (chat-history):** AI and user message exchange
3. **Bottom (input-field):** User text entry with prompt

This spec covers the **top panel design**, which displays contextual info retrieved by AI tools and user commands.

---

## Design Principles

- **Minimalist ASCII:** No fancy borders unless they serve function
- **Left-aligned labels, right-aligned values:** Maximum readability
- **Persistent state:** Panel stays until next action changes it
- **Smooth animation:** Right-to-left scroll with typing effect
- **Constraint-aware:** 15 lines max, ~125–140 chars per line

---

## Baseline Landing State

Displayed on page load, before wallet connects or tools execute.

```
═══════════════════════════════════════════════════════════════
CRUD - Version [REDACTED]
SIGNATURE:                                  [REDACTED]
SHELL NAME:                                 [REDACTED]
ACCESS LEVEL:                               [REDACTED]
ASSEMBLY SIGNATURE:                         [REDACTED]
LOCATION:                                   [REDACTED]
═══════════════════════════════════════════════════════════════
```

**Fields:**
- **CRUD - Version:** Product name and version (hardcoded or from .env)
- **SIGNATURE:** Wallet address (empty until user connects)
- **SHELL NAME:** Character name (empty until connected)
- **ACCESS LEVEL:** User tier / rank (empty until connected)
- **ASSEMBLY SIGNATURE:** Assembly ID of selected structure (empty until selected)
- **LOCATION:** System name (empty until structure provides data)

**Line count:** 8 lines (2 dividers + 6 fields)

**Visual rules:**
- Horizontal dividers: `═══════════════════════════════════════════════════════════════` (60+ chars)
- Empty value placeholder: `[REDACTED]`
- Label padding: 38 characters to align all values at right edge

---

## Transition Mechanic

### Animation Trigger
Panel updates when:
- User runs a `/` command (e.g., `/scan <system>`)
- AI tool executes (assess_threat, get_system_intel, etc.)
- User navigates (e.g., `/select <structure>`)

### Animation Sequence

1. **Outgoing Panel:** Current content slides **right** off-screen
2. **Incoming Panel:** New content slides **left** on-screen
3. **Text Generation:** New text types/appears **during the slide**
4. **Duration:** 400–600ms smooth ease-out
5. **Persistence:** New panel stays visible until next update

### Implementation Details

**CSS:**
```css
.visual-area {
  transition: transform 500ms ease-out;
}

.visual-area.slide-out-right {
  transform: translateX(100%);
}

.visual-area.slide-in-left {
  transform: translateX(-100%);
  animation: slideInLeft 500ms ease-out forwards;
}

@keyframes slideInLeft {
  from { transform: translateX(-100%); opacity: 0; }
  to { transform: translateX(0); opacity: 1; }
}
```

**JavaScript:**
- Track current panel state (content + animation status)
- Trigger slide-out-right, replace content, trigger slide-in-left
- Use CSS animation for smooth transform
- Simultaneously type text character-by-character during animation (or post-animation, TBD)

---

## Tool Output Designs

### 1. get_system_intel
**Triggered:** User or AI queries system data (e.g., `/scan current-system`)
**Data:** System name, star class, minimum jump temperature, planet count, kills in 24h, gate links

```
═══════════════════════════════════════════════════════════════
SYSTEM:                                    UR8-K7K
STAR CLASS:                                K5V
MIN TEMP:                                  45°C
PLANETS:                                   8
KILLS (24h):                               2
GATES:                                     3
═══════════════════════════════════════════════════════════════
```

**Line count:** 8 lines
**Formatting:** Stacked labels, right-aligned values
**Truncation:** System name and star class may be truncated if >20 chars (use ellipsis)

---

### 2. assess_threat
**Triggered:** AI tool executes threat analysis (triggered by AI or `/threat` command)
**Data:** Threat level, top aggressor corp/pilot, dominant ship type, escalation count

```
═══════════════════════════════════════════════════════════════
THREAT ASSESSMENT
LEVEL:                                     ELEVATED
TOP AGGRESSOR:                             PirateCorp
DOMINANT SHIP:                             Frigate
ESCALATION:                                +2 (24h)
═══════════════════════════════════════════════════════════════
```

**Line count:** 8 lines
**Threat Level values:** CLEAR, LOW, MODERATE, ELEVATED, CRITICAL
**Formatting:** Stacked labels, uppercase values

---

### 3. get_pilot_profile
**Triggered:** AI or user queries pilot data (e.g., `/profile <pilot_address>`)
**Data:** Pilot name, visit count, first visit date, last visit date, access tier

```
═══════════════════════════════════════════════════════════════
PILOT PROFILE
NAME:                                      John Thorne
VISITS:                                    42
FIRST SEEN:                                2026-01-15
LAST SEEN:                                 2026-03-20
TIER:                                      PATRON
═══════════════════════════════════════════════════════════════
```

**Line count:** 8 lines
**Tier values:** NONE, MEMBER, PATRON, TRUSTED, HOSTILE
**Formatting:** Stacked labels, dates YYYY-MM-DD

---

### 4. search_memory
**Triggered:** AI or user searches structure memory (e.g., `/search pirate`)
**Data:** Search keyword, lookback period, matched events (up to 5 shown, capped at ~3–5 lines)

```
═══════════════════════════════════════════════════════════════
SEARCH: "pirate" (7 days)
  • 2026-03-20 attack: contact at gate
  • 2026-03-18 contact: 3 x frigate
  • 2026-03-15 attack: docking attempt
═══════════════════════════════════════════════════════════════
```

**Line count:** 6–9 lines (1 header + results)
**Formatting:** Bullet list with date, event type, summary
**Truncation:** Event summaries limited to ~50 chars; if >5 results, show top 5 with "... and X more"

---

### 5. get_memory_summary
**Triggered:** AI queries activity summary (triggered by AI internally or `/summary` command)
**Data:** Activity tallies (attacks, contacts, docking events), key insight

```
═══════════════════════════════════════════════════════════════
ACTIVITY SUMMARY (7 days)
ATTACKS:                                   3
CONTACTS:                                  12
DOCKING:                                   45
KEY: Increased frigate activity targeting corvettes
═══════════════════════════════════════════════════════════════
```

**Line count:** 8 lines
**Formatting:** Stacked labels for tallies, free-form text for key insight
**Key field:** Optional; omit if empty

---

### 6. radius_search → Chat Area (Not Top Panel)
**Note:** radius_search output is **too large** for the top panel (15-line limit). Instead:
- Trigger displays in **chat history** as scrollable results
- User can scroll naturally to see all systems, categories, rankings
- Top panel can show a **summary line** like: `SCAN: UR8-K7K ±100 LY | 847 systems found`

---

## Technical Specifications

### Viewport & Layout
- **Max height:** 828px
- **Top panel height:** 33% (~273px)
- **Font:** Courier New, 13px, line-height 1.4
- **Chars per line:** ~125–140 (varies by browser zoom)
- **Max lines in panel:** ~15 (varies by line-height)
- **Colors:** #c8a560 (gold text), #000 (black bg), #5a4a20 (dark separator)

### Animation Timing
- **Duration:** 400–600ms (CSS transition or JS animation)
- **Easing:** ease-out (smooth deceleration)
- **Text generation:** Types in during slide (or immediately if slow animation)
- **FPS target:** Smooth 60fps; avoid jank on lower-end hardware

### Content Constraints
- **Divider line length:** 63 characters (═══...═══)
- **Label max width:** 38 characters (left column)
- **Value max width:** 25 characters (right column, overflow handled by truncation + ellipsis)
- **Bullet points:** 2-space indent for readability

### Styling Rules
1. All labels are **uppercase** for EVE universe aesthetic
2. Empty fields show `[REDACTED]` (not null, not blank)
3. Dates use **YYYY-MM-DD** format
4. Numbers are right-aligned in values
5. Threat level and tier strings are **uppercase**
6. Dividers use **═══** (box drawing characters, U+2550)

---

## Implementation Roadmap

1. **Phase 1:** Build panel state manager (current content, animation state)
2. **Phase 2:** Implement CSS + JS animation (slide-in-left, slide-out-right)
3. **Phase 3:** Add text-typing effect during animation
4. **Phase 4:** Connect to backend tool execution (receive data, update panel)
5. **Phase 5:** Test with real tool outputs; adjust truncation/formatting as needed
6. **Phase 6:** Refine animation timing based on visual feedback

---

## Future Enhancements

- **Color coding by threat level:** Use ANSI colors for threat assessment (red=critical, yellow=elevated, etc.)
- **ASCII art decorations:** Add subtle corner decorations or section dividers for fancy panels
- **Icon prefixes:** Add ASCII symbols before key fields (★ for tier, ◆ for threat, etc.)
- **Smooth text transition:** Stagger character appearance across slide animation
- **Panel history:** Allow user to scroll back through previous panel states

---

## Questions & Decisions Deferred

- **Text typing speed:** Characters per millisecond during slide animation (TBD after first implementation)
- **Truncation fallback:** If value > 25 chars, use ellipsis or shorten? (Recommend ellipsis)
- **Dynamic field count:** Some tools may have variable field counts—should panel height shrink, or add blank lines?
- **Error states:** How to display tool failures (e.g., "assess_threat: timeout") in panel format?

