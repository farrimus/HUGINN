# HUGINN Tool System — Builder's Guide

How to add tools, change behavior, and understand what each piece does.

---

## How it all fits together

A player message triggers this sequence:

```
Player sends message
  │
  ▼
companion.py: builds context string (structure, system, pilot, inventory, tier)
  │
  ▼
ai_tools.py: get_tools_for_claude()
  → reads tools.yaml → uses description from YAML if present, else falls back to hardcoded
  → filters out tools blocked for this tier (tier_capabilities.py)
  │
  ▼
Claude API call: system=companion.md, messages=[context + message], tools=[tool list]
  │
  ├── Claude calls a tool
  │     │
  │     ▼
  │   ai_tools.py: execute_tool_structured()
  │     → Python handler runs → returns {text, structured}
  │     │
  │     ▼
  │   companion.py: prepends response_guidance from tools.yaml to the text
  │     → Claude receives: "{response_guidance}\n\n{tool text result}"
  │     → If structured data present AND tool is in _TOOL_TO_PANEL:
  │         → frontend receives a panel event with the structured data (bypasses Claude)
  │     │
  │     └── loop: Claude may call more tools before writing to player
  │
  ▼
Claude writes response → player sees it
```

---

## What lives where

| What | File | Notes |
|------|------|-------|
| Tool registration + input schema | `src/ai_tools.py` | Python only — defines what parameters Claude can pass |
| Tool handler (the actual logic) | `src/ai_tools.py` | Returns `{text, structured}` |
| Description Claude sees (pre-call) | `prompts/tools.yaml` → `src/ai_tools.py` | YAML takes precedence; Python is fallback |
| Guidance Claude follows (post-call) | `prompts/tools.yaml` | Prepended to tool result |
| Empty-result string | `prompts/tools.yaml` | Only for `assess_threat` and `query_intel` |
| Tier access control | `src/tier_capabilities.py` | Which tiers can call which tools |
| Panel wiring (optional) | `src/endpoints/companion.py` → `_TOOL_TO_PANEL` | Only needed if tool should show a panel |

---

## Adding a new tool — full checklist

### 1. Register the tool in `src/ai_tools.py`

Inside `_register_default_tools()`, call `self.register_tool()`:

```python
self.register_tool(
    name="my_tool",
    category="info",            # logical grouping only, for readability
    description="Fallback description used if tools.yaml has no entry.",
    input_schema={
        "type": "object",
        "properties": {
            "my_param": {
                "type": "string",
                "description": "What this param does."
            },
        },
        "required": ["my_param"]
    },
    handler=self._tool_my_tool,
    default_enabled=True,       # False = not enabled by default (tier still gates it)
)
```

### 2. Write the handler

```python
def _tool_my_tool(self, inputs: dict, context: dict = None) -> dict:
    param = inputs.get("my_param", "")

    # Do work...
    result_text = f"Result for {param}: ..."
    result_data = {"param": param, "value": 42}  # or None if no panel needed

    return {
        "text": result_text,       # Claude reads this
        "structured": result_data, # Frontend panel reads this (None if no panel)
    }
```

**Return contract:**
- `text` — always a string. This is what Claude receives and uses to write its response.
- `structured` — any JSON-serializable dict, or `None`. Only used if you wire a frontend panel (step 5).
- On error: return `{"text": "[my_tool: description of failure]", "structured": None}`. Never raise.

### 3. Add to tier access in `src/tier_capabilities.py`

Add the tool name to the `tools` list for every tier that should have access:

```python
"TRIBE": {
    "tools": [
        # ... existing tools ...
        "my_tool",
    ],
},
"OWNER": {
    "tools": [
        # ... existing tools ...
        "my_tool",
    ],
},
```

A tool not listed in a tier's `tools` list is invisible to Claude for that tier. This is the primary access gate — `default_enabled` in ai_tools.py is a documentation hint only.

### 4. Add to `prompts/tools.yaml`

```yaml
my_tool:
  description: |
    Full description Claude reads before deciding to call this tool.
    What the tool does, when to use it, when NOT to use it.
    Name key parameters if Claude routinely gets them wrong.
  response_guidance: |
    Lead with X. Mention Y only if Z. Maximum N lines.
    Do not narrate the tool call.
  # no_result: only works for assess_threat and query_intel — skip for other tools
```

### 5. (Optional) Wire a frontend panel in `src/endpoints/companion.py`

If the tool should render a visual panel (not just chat text), add it to `_TOOL_TO_PANEL`:

```python
_TOOL_TO_PANEL = {
    # existing entries...
    "my_tool": "my_panel_type",   # must match a ToolType in frontend/src/types/terminal.ts
}
```

When this is present and `structured` is non-null, the frontend receives a `tool_result` SSE event with the panel data. Claude still gets the `text` version independently.

---

## How `response_guidance` interacts with tool output

Claude receives:
```
{response_guidance from tools.yaml}

{raw text from handler}
```

This means:
- Guidance cannot add data that the handler didn't return. If you want Claude to say something, the handler must produce it in `text`.
- Guidance can suppress or reorder — "lead with X", "omit Y if Z", "maximum 4 lines".
- The `structured` field never goes through Claude. It goes directly to the frontend panel.

Common failure modes:
- **Claude says the wrong thing** → fix `response_guidance`
- **Claude doesn't call the tool** → fix `description` (trigger conditions, "use this when...")
- **Claude calls the wrong tool** → add "Do not use for X — use `other_tool` instead" to `description`
- **Claude says it has no data but it does** → fix `description` (add explicit trigger before saying you have no data)
- **Response is verbose or off-tone** → fix `response_guidance` (state format, cap line count)
- **Data is missing from the response** → fix the handler. Guidance cannot invent data.

---

## How the `no_result` field works

Only two tools check for it: `assess_threat` and `query_intel`. Both have explicit code in `src/ai_tools.py` that substitutes this string when the tool returns empty. For all other tools, the field is ignored.

To add `no_result` support to a new tool, the handler must explicitly load and check it:

```python
from src.prompt_loader import load_tool_prompts
no_result = load_tool_prompts().get("my_tool", {}).get("no_result", "")
if not results:
    return {"text": no_result or "No results found.", "structured": None}
```

---

## Tier access — how the filter works

`tier_capabilities.py` defines a `tools` list per tier (NONE, VETTED, TRIBE, OWNER). At request time:

1. All registered tool names are collected from `ai_tools.tools`
2. `blocked_tools(tier, all_names)` returns names not in that tier's list
3. Blocked names + any `disabled_tools` from the request are passed to `get_tools_for_claude(disabled=...)`
4. `get_tools_for_claude` simply skips any tool in the disabled set

Result: Claude never sees blocked tools in its tool list and cannot call them.

**Minimal access design:** Add a new tool to OWNER only first. Promote to other tiers once behavior is validated.

---

## Live vs restart

| What changed | Restart needed? |
|---|---|
| `prompts/tools.yaml` — any field | No — loaded per request |
| `prompts/companion.md` | Yes — loaded once at module import |
| `src/ai_tools.py` — handler logic | Yes |
| `src/ai_tools.py` — tool registration | Yes |
| `src/tier_capabilities.py` | Yes |
| `src/endpoints/companion.py` | Yes |

---

## Minimal working tool (no panel, text only)

The absolute minimum to add a working tool:

**`src/ai_tools.py`** — register + handler:
```python
self.register_tool(
    name="ping_system",
    category="info",
    description="Check if a named system is in the galaxy database.",
    input_schema={"type": "object", "properties": {
        "system_name": {"type": "string", "description": "System name to look up."}
    }, "required": ["system_name"]},
    handler=self._tool_ping_system,
)

def _tool_ping_system(self, inputs, context=None):
    name = inputs.get("system_name", "")
    from src.galaxy_db import galaxy_db
    sys = galaxy_db.get_system(name)
    if not sys:
        return {"text": f"System '{name}' not found in galaxy database.", "structured": None}
    return {"text": f"{name}: found (region {sys.get('regionName','?')})", "structured": None}
```

**`src/tier_capabilities.py`** — add `"ping_system"` to whichever tiers need it.

**`prompts/tools.yaml`** — optional but recommended:
```yaml
ping_system:
  description: Check if a solar system name is valid and known to this unit's database.
  response_guidance: State found or not found in one line. Include region if found.
```

That is the complete set of changes.
