# type_names

## Overview
Resolves EVE Frontier type IDs to human-readable names. Loaded once at import time from `data/type_names_all.json`. Single public function: `get_type_name(type_id)` returns a string name or "Unknown" if not found.

## When Should an Agent Use This Module?
- Converting type IDs (int or str) to display names
- Making game items and structures readable in chat
- Formatting inventory, enemy lists, and cargo manifests
- Building context blocks with human-readable item/structure names

## Key API
| Symbol | Type | Purpose | Agent Instruction |
|--------|------|---------|------------------|
| `get_type_name(type_id)` | function | Resolve type_id to human-readable name | Always use instead of raw IDs in prompts/output |

### Function Signature
- **Input:** `type_id` (int, str, or None)
- **Output:** str — human-readable name, or "Unknown" if not found
- **Handles:** None input gracefully (returns "Unknown")

## Critical Gotchas & Pitfalls for Agents
• **Type IDs are strings in the database:** Even if you pass an int, the function converts to str for lookup.
• **Missing IDs return "Unknown":** Never assume a type_id is in the database; always handle gracefully.
• **Load happens once at import:** The JSON is loaded at module import time. Changes to the file require a server restart.
• **No runtime caching:** Function does a dict lookup every call (fast, O(1)), no additional caching layer.

## Architecture
```
Import time:
  Load data/type_names_all.json → _TYPE_NAMES dict {type_id (str) → name (str)}
  ↓
Runtime:
  get_type_name(type_id)
    → if type_id is None: return "Unknown"
    → convert input to str
    → return _TYPE_NAMES.get(str(type_id), "Unknown")
```

## Agent Guidance
**Primary Workflow**
1. Whenever you have a type_id from game data, call `get_type_name(type_id)`
2. Use the returned name in prompts, context, and player messages
3. Never show raw type IDs to players

**Best Practices & Anti-Patterns**
- Always / Call `get_type_name()` for any item/structure type visible to player
- Always / Build lists/summaries using names, not IDs
- Always / Handle None return value (the function always returns a string, never None)
- Never / Assume a type_id exists — the function returns "Unknown" gracefully
- Never / Pre-resolve type_ids outside of context building (resolve as-needed)

**Cross-Module Dependencies**
- Depends on: `data/type_names_all.json` (World API type database export)
- Used by: `context_builder` (inventory, enemies, structures), `claude_client` (readability), `ssu_poller` (inventory display)

## Progressive Disclosure
**Read this main file by default.**

**Load deeper files ONLY when:**
- You need to rebuild type_names.json: check `/docs/ref/ops.md` for World API export script
