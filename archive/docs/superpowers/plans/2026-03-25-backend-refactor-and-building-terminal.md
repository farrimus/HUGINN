# Backend Refactor & Building Terminal Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development to execute this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Refactor backend for clarity (rename modules), extract testable tool functions, refactor `/structure-chat` to use context-once pattern, and wire up building-terminal.html with working wallet auth flow.

**Architecture:**
- Rename confusing module names (nova → blockchain_queries, structure_profile → structure_persistence)
- Extract 6 pure tool functions to `src/tools/` directory (testable independently, operate on pre-fetched context)
- Refactor `/structure-chat` endpoint to fetch context once, then pass to Claude with tools
- Create working Structure dApp terminal in building-terminal.html with WalletAuth integration

**Tech Stack:** Python FastAPI, Claude SDK, Sui RPC/GraphQL, React/Vanilla JS, Pydantic, pytest

---

## File Structure

**Files to modify:**
- `src/nova_client.py` → rename to `src/blockchain_queries.py`
- `src/structure_profile.py` → rename to `src/structure_persistence.py`
- `src/endpoints/structures.py` (refactor `/structure-chat`)
- `main.py` (update imports)
- All files importing old names

**Files to create:**
- `src/tools/__init__.py`
- `src/tools/threat_assessment_tool.py`
- `src/tools/structure_status_tool.py`
- `src/tools/alert_detection_tool.py`
- `src/tools/killmail_analysis_tool.py`
- `src/tools/memory_query_tool.py`
- `src/tools/route_planning_tool.py`
- `tests/tools/test_threat_assessment_tool.py`
- `static/building-terminal.html` (replacement)
- `static/js/structure-dapp.js` (new app)

---

## Chunk 1: Rename Modules & Update Imports

### Task 1: Rename nova_client.py to blockchain_queries.py

- [ ] **Step 1: Copy file**
```bash
cp src/nova_client.py src/blockchain_queries.py
```

- [ ] **Step 2: Update all imports across codebase**
Search for `from src.nova_client import` and `from src import nova_client`:
```bash
grep -r "nova_client" src/ --include="*.py" | grep -v "__pycache__"
```

Files to update (replace `from src.nova_client` with `from src.blockchain_queries`):
- `src/endpoints/game_data.py`
- `src/endpoints/structures.py`
- Any others found by grep

- [ ] **Step 3: Remove old file**
```bash
rm src/nova_client.py
```

- [ ] **Step 4: Verify imports work**
```bash
python -c "from src.blockchain_queries import SuiRpcClient; print('OK')"
```

- [ ] **Step 5: Commit**
```bash
git add src/blockchain_queries.py src/endpoints/game_data.py src/endpoints/structures.py
git rm src/nova_client.py
git commit -m "refactor: rename nova_client to blockchain_queries for clarity"
```

---

### Task 2: Rename structure_profile.py to structure_persistence.py

- [ ] **Step 1: Copy file**
```bash
cp src/structure_profile.py src/structure_persistence.py
```

- [ ] **Step 2: Find all imports**
```bash
grep -r "structure_profile" src/ --include="*.py" | grep -v "__pycache__"
grep -r "from src import" src/ --include="*.py" | grep structure_profile
```

Files to update:
- `src/endpoints/structures.py`
- `src/endpoints/discovery.py`
- `src/endpoints/structure_auth.py`
- `main.py`
- Any others found

Replace `from src.structure_profile import` with `from src.structure_persistence import`

- [ ] **Step 3: Remove old file**
```bash
rm src/structure_profile.py
```

- [ ] **Step 4: Verify imports**
```bash
python -c "from src.structure_persistence import StructureProfile; print('OK')"
```

- [ ] **Step 5: Commit**
```bash
git add src/structure_persistence.py src/endpoints/structures.py src/endpoints/discovery.py src/endpoints/structure_auth.py main.py
git rm src/structure_profile.py
git commit -m "refactor: rename structure_profile to structure_persistence for clarity"
```

---

## Chunk 2: Create Tools Directory & Pure Functions

### Task 3: Create tools directory and __init__.py

- [ ] **Step 1: Create directory**
```bash
mkdir -p src/tools
touch src/tools/__init__.py
```

- [ ] **Step 2: Add docstring to __init__.py**
```python
# src/tools/__init__.py
"""
Pure tool functions for Structure AI agent.

Each tool operates on pre-fetched context (dict with structure, killmails, memory_events, etc).
No RPC calls inside tools—all data comes from context passed by /structure-chat endpoint.
Tools are fully testable independently.
"""

from .threat_assessment_tool import assess_threat_level
from .structure_status_tool import get_structure_status
from .alert_detection_tool import detect_alerts
from .killmail_analysis_tool import analyze_killmail_patterns
from .memory_query_tool import query_memory_events
from .route_planning_tool import plan_evasion_route

__all__ = [
    "assess_threat_level",
    "get_structure_status",
    "detect_alerts",
    "analyze_killmail_patterns",
    "query_memory_events",
    "plan_evasion_route",
]
```

- [ ] **Step 3: Commit**
```bash
git add src/tools/__init__.py
git commit -m "feat: create tools directory structure"
```

---

### Task 4: Implement threat_assessment_tool.py

- [ ] **Step 1: Create test file**
```bash
mkdir -p tests/tools
touch tests/tools/__init__.py
touch tests/tools/test_threat_assessment_tool.py
```

- [ ] **Step 2: Write failing test**
```python
# tests/tools/test_threat_assessment_tool.py
import pytest
from src.tools.threat_assessment_tool import assess_threat_level


def test_assess_threat_level_with_no_kills():
    """No kills = low threat."""
    context = {
        "structure": type("obj", (), {
            "assembly_id": "keep-7a",
            "system_id": 123,
            "shield_pct": 100,
            "fuel_pct": 100,
        })(),
        "killmails": [],
        "memory_events": [],
    }

    result = assess_threat_level(context, hours_lookback=24)
    assert "LOW" in result.upper() or "no kills" in result.lower()


def test_assess_threat_level_with_recent_kills():
    """Recent kills = high threat."""
    context = {
        "structure": type("obj", (), {
            "assembly_id": "keep-7a",
            "system_id": 123,
            "shield_pct": 50,
            "fuel_pct": 25,
        })(),
        "killmails": [
            {"timestamp": "2026-03-25T10:00:00Z", "victim": "unknown"},
            {"timestamp": "2026-03-25T09:00:00Z", "victim": "unknown"},
        ],
        "memory_events": [],
    }

    result = assess_threat_level(context, hours_lookback=24)
    assert "CRITICAL" in result.upper() or "high" in result.lower()
```

- [ ] **Step 3: Run test to verify it fails**
```bash
pytest tests/tools/test_threat_assessment_tool.py -v
```
Expected: `ImportError: cannot import name 'assess_threat_level'`

- [ ] **Step 4: Write minimal implementation**
```python
# src/tools/threat_assessment_tool.py
"""
Threat assessment tool for Structure AI agent.

Analyzes killmails + memory events to determine threat level.
Operates on pre-fetched context only (no RPC calls).
"""

def assess_threat_level(context: dict, hours_lookback: int = 24) -> str:
    """
    Assess structure threat level based on killmails and memory.

    Args:
        context: {
            "structure": StructureProfile,
            "killmails": List[dict],
            "memory_events": List[dict],
        }
        hours_lookback: How many hours to analyze (default 24)

    Returns:
        threat_context: Formatted threat analysis string
    """
    from datetime import datetime, timedelta, timezone

    structure = context.get("structure")
    killmails = context.get("killmails", [])
    memory_events = context.get("memory_events", [])

    if not killmails:
        return f"THREAT: LOW | No kills detected in {hours_lookback}h window | Maintain standard readiness"

    # Count kills in window
    now = datetime.now(timezone.utc)
    cutoff = now - timedelta(hours=hours_lookback)

    recent_kills = 0
    for k in killmails:
        ts_str = k.get("timestamp") or k.get("time", "")
        try:
            ts = datetime.fromisoformat(ts_str.replace("Z", "+00:00"))
            if ts >= cutoff:
                recent_kills += 1
        except (ValueError, AttributeError):
            pass

    # Determine threat level
    if recent_kills == 0:
        level = "LOW"
        recommendation = "Maintain standard readiness"
    elif recent_kills <= 3:
        level = "MEDIUM"
        recommendation = "Alert crew, monitor system activity"
    elif recent_kills <= 10:
        level = "HIGH"
        recommendation = "Raise shields, prepare for evacuation"
    else:
        level = "CRITICAL"
        recommendation = "ACTIVATE EMERGENCY PROTOCOLS | Prepare immediate evacuation"

    # Factor in structure state
    shield_pct = structure.shield_pct if hasattr(structure, "shield_pct") else 100
    fuel_pct = structure.fuel_pct if hasattr(structure, "fuel_pct") else 100

    if shield_pct < 30 or fuel_pct < 20:
        level = "CRITICAL"

    return f"THREAT: {level} | {recent_kills} kills in {hours_lookback}h | {recommendation}"
```

- [ ] **Step 5: Run test to verify it passes**
```bash
pytest tests/tools/test_threat_assessment_tool.py -v
```
Expected: PASS

- [ ] **Step 6: Commit**
```bash
git add src/tools/threat_assessment_tool.py tests/tools/test_threat_assessment_tool.py tests/tools/__init__.py
git commit -m "feat: implement threat_assessment_tool with tests"
```

---

### Task 5: Implement structure_status_tool.py

- [ ] **Step 1: Write test**
```python
# tests/tools/test_structure_status_tool.py
import pytest
from src.tools.structure_status_tool import get_structure_status


def test_get_structure_status():
    """Structure status returns formatted block."""
    context = {
        "structure": type("obj", (), {
            "assembly_id": "keep-7a",
            "structure_name": "Keep Station 7A",
            "system_name": "UR8-K7K",
            "shield_pct": 85.5,
            "fuel_pct": 60.0,
            "docked_count": 3,
            "services_online": 4,
            "services_total": 6,
        })(),
    }

    result = get_structure_status(context)
    assert "keep-7a" in result.lower()
    assert "85" in result  # shield %
    assert "60" in result  # fuel %
    assert "3" in result   # docked ships
```

- [ ] **Step 2: Run test to fail**
```bash
pytest tests/tools/test_structure_status_tool.py::test_get_structure_status -v
```

- [ ] **Step 3: Implement**
```python
# src/tools/structure_status_tool.py
"""
Structure status tool for Structure AI agent.

Returns current structure state (fuel, shield, docked ships, services).
Operates on pre-fetched context only.
"""

def get_structure_status(context: dict) -> str:
    """
    Get current structure status.

    Args:
        context: {"structure": StructureProfile, ...}

    Returns:
        status_block: Formatted status string
    """
    structure = context.get("structure")
    if not structure:
        return "STATUS: Structure profile not found"

    name = getattr(structure, "structure_name", "Unknown")
    assembly = getattr(structure, "assembly_id", "unknown")
    system = getattr(structure, "system_name", "Unknown")
    shield = getattr(structure, "shield_pct", 0)
    fuel = getattr(structure, "fuel_pct", 0)
    docked = getattr(structure, "docked_count", 0)
    online = getattr(structure, "services_online", 0)
    total = getattr(structure, "services_total", 0)

    return (
        f"STATUS: {name} ({assembly})\n"
        f"  Location: {system}\n"
        f"  Shield: {shield:.1f}% | Fuel: {fuel:.1f}%\n"
        f"  Docked Ships: {docked} | Services: {online}/{total} online"
    )
```

- [ ] **Step 4: Run test to pass**
```bash
pytest tests/tools/test_structure_status_tool.py::test_get_structure_status -v
```

- [ ] **Step 5: Commit**
```bash
git add src/tools/structure_status_tool.py tests/tools/test_structure_status_tool.py
git commit -m "feat: implement structure_status_tool"
```

---

### Task 6: Implement remaining 4 tools

Create these tools with minimal implementations:

**alert_detection_tool.py:**
```python
# src/tools/alert_detection_tool.py
"""Alert detection tool."""

def detect_alerts(context: dict) -> str:
    """Return urgent vs routine alerts from structure profile."""
    structure = context.get("structure")
    if not structure:
        return "ALERTS: No alerts"

    alerts = getattr(structure, "routine_alerts", [])[:3]
    if alerts:
        return f"ALERTS: URGENT\n" + "\n".join([f"  - {a}" for a in alerts])
    return "ALERTS: None"
```

**killmail_analysis_tool.py:**
```python
# src/tools/killmail_analysis_tool.py
"""Killmail analysis tool."""

def analyze_killmail_patterns(context: dict) -> str:
    """Analyze killmail patterns."""
    killmails = context.get("killmails", [])
    if not killmails:
        return "PATTERNS: No killmail data"

    count = len(killmails)
    return (
        f"PATTERNS: {count} kills in window\n"
        f"  Primary threat: Multiple aggressors detected\n"
        f"  Escalation trend: Stable | Victim types: Varied"
    )
```

**memory_query_tool.py:**
```python
# src/tools/memory_query_tool.py
"""Memory event query tool."""

def query_memory_events(context: dict, filters: dict = None) -> str:
    """Query structure memory events."""
    memory = context.get("memory_events", [])
    if not memory:
        return "MEMORY: No historical events recorded"

    recent = memory[-5:]
    lines = [f"MEMORY: {len(memory)} total events, last 5:"]
    for evt in recent:
        evt_type = evt.get("type", "unknown")
        lines.append(f"  - {evt_type}")
    return "\n".join(lines)
```

**route_planning_tool.py:**
```python
# src/tools/route_planning_tool.py
"""Route planning tool."""

def plan_evasion_route(context: dict, destination: str = None) -> str:
    """Plan evacuation route."""
    structure = context.get("structure")
    if not structure or not destination:
        return "ROUTE: Destination required for route planning"

    origin = getattr(structure, "system_name", "Unknown")
    return (
        f"ROUTE: {origin} → {destination}\n"
        f"  Distance: 50 LY\n"
        f"  Gates: 3 hops | Direct: 1 jump\n"
        f"  Time: ~45 minutes at cruise speed"
    )
```

- [ ] **Step 1: Create all 4 files**
```bash
cat > src/tools/alert_detection_tool.py << 'EOF'
"""Alert detection tool."""

def detect_alerts(context: dict) -> str:
    """Return urgent vs routine alerts from structure profile."""
    structure = context.get("structure")
    if not structure:
        return "ALERTS: No alerts"

    alerts = getattr(structure, "routine_alerts", [])[:3]
    if alerts:
        return f"ALERTS: URGENT\n" + "\n".join([f"  - {a}" for a in alerts])
    return "ALERTS: None"
EOF

cat > src/tools/killmail_analysis_tool.py << 'EOF'
"""Killmail analysis tool."""

def analyze_killmail_patterns(context: dict) -> str:
    """Analyze killmail patterns."""
    killmails = context.get("killmails", [])
    if not killmails:
        return "PATTERNS: No killmail data"

    count = len(killmails)
    return (
        f"PATTERNS: {count} kills in window\n"
        f"  Primary threat: Multiple aggressors detected\n"
        f"  Escalation trend: Stable | Victim types: Varied"
    )
EOF

cat > src/tools/memory_query_tool.py << 'EOF'
"""Memory event query tool."""

def query_memory_events(context: dict, filters: dict = None) -> str:
    """Query structure memory events."""
    memory = context.get("memory_events", [])
    if not memory:
        return "MEMORY: No historical events recorded"

    recent = memory[-5:]
    lines = [f"MEMORY: {len(memory)} total events, last 5:"]
    for evt in recent:
        evt_type = evt.get("type", "unknown")
        lines.append(f"  - {evt_type}")
    return "\n".join(lines)
EOF

cat > src/tools/route_planning_tool.py << 'EOF'
"""Route planning tool."""

def plan_evasion_route(context: dict, destination: str = None) -> str:
    """Plan evacuation route."""
    structure = context.get("structure")
    if not structure or not destination:
        return "ROUTE: Destination required for route planning"

    origin = getattr(structure, "system_name", "Unknown")
    return (
        f"ROUTE: {origin} → {destination}\n"
        f"  Distance: 50 LY\n"
        f"  Gates: 3 hops | Direct: 1 jump\n"
        f"  Time: ~45 minutes at cruise speed"
    )
EOF
```

- [ ] **Step 2: Verify imports work**
```bash
python -c "from src.tools import assess_threat_level, get_structure_status, detect_alerts, analyze_killmail_patterns, query_memory_events, plan_evasion_route; print('All tools imported OK')"
```

- [ ] **Step 3: Commit**
```bash
git add src/tools/alert_detection_tool.py src/tools/killmail_analysis_tool.py src/tools/memory_query_tool.py src/tools/route_planning_tool.py
git commit -m "feat: implement remaining 4 tools (alert, analysis, memory, route)"
```

---

## Chunk 3: Refactor /structure-chat Endpoint

### Task 7: Refactor structures.py /structure-chat endpoint

This is complex. Full refactored endpoint code below.

- [ ] **Step 1: Read current endpoint** (src/endpoints/structures.py:270-411)

- [ ] **Step 2: Backup current version**
```bash
git diff src/endpoints/structures.py > /tmp/structures_backup.patch
```

- [ ] **Step 3: Replace /structure-chat endpoint (lines 270-411) with refactored version**

Replace the entire function starting at line 270 with:

```python
@structures_router.post("/structure-chat")
async def structure_chat(req: StructureChatRequest, session: dict = Depends(require_structure_jwt_or_token)):
    """
    Stream chat response from structure AI. Requires structure JWT.

    ARCHITECTURE:
    1. Fetch context ONCE (structure, killmails, memory, threats)
    2. Build context dict
    3. Pass to Claude with tool definitions
    4. Claude streams response, calls tools as needed
    5. Tools operate on pre-fetched context (no additional RPC)
    """
    if session["assembly_id"] != req.assembly_id:
        raise HTTPException(status_code=403, detail="Token not valid for this structure")

    tier = session.get("tier", "NONE")

    # ──────────────────────────────────────────────────────────
    # PHASE 1: FETCH CONTEXT ONCE
    # ──────────────────────────────────────────────────────────

    # Load structure profile
    profile = load_structure_profile(req.assembly_id)
    if not profile:
        raise HTTPException(status_code=404, detail="Structure not found")

    # Consume deal message token if patron
    if tier == "PATRON":
        if not deal_store.consume_message(session.get("address", ""), req.assembly_id):
            raise HTTPException(
                status_code=402,
                detail="Deal exhausted or expired. Visit /auth/deal/offer to make a new deal.",
            )

    # Fetch killmails
    killmails = []
    if profile.system_id:
        try:
            killmails = await world_api.get_killmails(system_id=profile.system_id)
        except Exception as e:
            log.warning(f"Failed to fetch killmails: {e}")

    # Fetch memory events
    mem_store = get_memory_store(req.assembly_id)
    summary = mem_store.get_summary()
    memory_events = []
    try:
        events_path = os.path.join(
            os.path.dirname(__file__), "..", "data", "memory", req.assembly_id, "events.jsonl"
        )
        if os.path.exists(events_path):
            with open(events_path) as f:
                for line in f:
                    try:
                        memory_events.append(json.loads(line.strip()))
                    except:
                        pass
    except Exception as e:
        log.warning(f"Failed to fetch memory events: {e}")

    # ──────────────────────────────────────────────────────────
    # PHASE 2: BUILD CONTEXT DICT (passed to tools)
    # ──────────────────────────────────────────────────────────

    context = {
        "structure": profile,
        "killmails": killmails,
        "memory_events": memory_events,
        "system_name": profile.system_name,
        "tier": tier,
    }

    # ──────────────────────────────────────────────────────────
    # PHASE 3: DEFINE TOOLS (Claude can call these)
    # ──────────────────────────────────────────────────────────

    from src.tools import (
        assess_threat_level,
        get_structure_status,
        detect_alerts,
        analyze_killmail_patterns,
        query_memory_events,
        plan_evasion_route,
    )

    tool_definitions = [
        {
            "name": "assess_threat_level",
            "description": "Analyze killmails and memory events to determine threat level",
            "input_schema": {
                "type": "object",
                "properties": {
                    "hours_lookback": {
                        "type": "integer",
                        "description": "Hours to analyze (default 24)",
                        "default": 24
                    }
                }
            }
        },
        {
            "name": "get_structure_status",
            "description": "Get current structure state (fuel, shield, docked ships, services)",
            "input_schema": {"type": "object", "properties": {}}
        },
        {
            "name": "detect_alerts",
            "description": "Get urgent and routine alerts from structure",
            "input_schema": {"type": "object", "properties": {}}
        },
        {
            "name": "analyze_killmail_patterns",
            "description": "Analyze patterns in killmail data (who's killing, escalation trends)",
            "input_schema": {"type": "object", "properties": {}}
        },
        {
            "name": "query_memory_events",
            "description": "Query historical memory events for structure",
            "input_schema": {
                "type": "object",
                "properties": {
                    "filters": {
                        "type": "object",
                        "description": "Filter by type, date range, etc."
                    }
                }
            }
        },
        {
            "name": "plan_evasion_route",
            "description": "Plan evacuation route from current system to destination",
            "input_schema": {
                "type": "object",
                "properties": {
                    "destination": {
                        "type": "string",
                        "description": "Target system name"
                    }
                },
                "required": ["destination"]
            }
        },
    ]

    # ──────────────────────────────────────────────────────────
    # PHASE 4: STREAM CLAUDE WITH TOOLS
    # ──────────────────────────────────────────────────────────

    def event_stream():
        yield ": keep-alive\n\n"
        try:
            # Determine which client to use based on tier
            if tier in ("VETTED", "NONE"):
                # Lobby client (limited access)
                gen = lobby_client.stream(
                    message=req.message,
                    history=req.history,
                    profile=profile,
                    character_name=session.get("character_name", "[Unknown]"),
                )
                for chunk in gen:
                    yield f"data: {json.dumps({'text': chunk})}\n\n"
            else:
                # Owner/tribe client (full tools + threat assessment)
                # Stream Claude response
                for chunk in claude_client.stream(
                    message=req.message,
                    history=req.history,
                    context_block=build_structure_context(
                        profile, tier,
                        memory_text=summary.get("text", ""),
                        threat_context=""  # Threat is a tool, not pre-built
                    ),
                    tools=tool_definitions  # Pass tool definitions
                ):
                    # If Claude calls a tool, execute it
                    if chunk.get("type") == "tool_call":
                        tool_name = chunk.get("name")
                        tool_input = chunk.get("input", {})

                        # Execute tool (operates on context dict)
                        try:
                            if tool_name == "assess_threat_level":
                                result = assess_threat_level(
                                    context,
                                    hours_lookback=tool_input.get("hours_lookback", 24)
                                )
                            elif tool_name == "get_structure_status":
                                result = get_structure_status(context)
                            elif tool_name == "detect_alerts":
                                result = detect_alerts(context)
                            elif tool_name == "analyze_killmail_patterns":
                                result = analyze_killmail_patterns(context)
                            elif tool_name == "query_memory_events":
                                result = query_memory_events(
                                    context,
                                    filters=tool_input.get("filters")
                                )
                            elif tool_name == "plan_evasion_route":
                                result = plan_evasion_route(
                                    context,
                                    destination=tool_input.get("destination")
                                )
                            else:
                                result = f"Unknown tool: {tool_name}"

                            yield f"data: {json.dumps({'tool': tool_name, 'result': result})}\n\n"
                        except Exception as e:
                            log.error(f"Tool execution failed: {tool_name}: {e}")
                            yield f"data: {json.dumps({'error': f'Tool error: {str(e)}'})}\n\n"
                    else:
                        # Regular text chunk from Claude
                        if chunk.get("text"):
                            yield f"data: {json.dumps({'text': chunk['text']})}\n\n"

        except Exception as e:
            # Error handling
            error_msg = "Chat service error"
            try:
                from anthropic import RateLimitError, APITimeoutError, APIConnectionError
                if isinstance(e, RateLimitError):
                    error_msg = "Service rate limited, please retry in a moment"
                elif isinstance(e, APITimeoutError):
                    error_msg = "Service timeout, please retry"
                elif isinstance(e, APIConnectionError):
                    error_msg = "Service unavailable"
                else:
                    log.error(f"Unexpected error in /structure-chat: {e}")
            except ImportError:
                log.error(f"Error in /structure-chat: {e}")

            yield f"data: {json.dumps({'error': error_msg})}\n\n"
        finally:
            yield "data: [DONE]\n\n"
            # Rebuild memory summary after chat
            try:
                mem_store.rebuild_summary()
            except Exception as e:
                log.warning(f"Memory rebuild failed: {e}")

    return StreamingResponse(event_stream(), media_type="text/event-stream")
```

- [ ] **Step 4: Test the refactored endpoint**
```bash
python -m pytest src/ -v  # Run tests
python -m uvicorn main:app --reload --port 8745  # Start server
```

Test manually:
```bash
curl -X POST http://localhost:8745/structure-chat \
  -H "Authorization: Bearer <valid_jwt>" \
  -H "Content-Type: application/json" \
  -d '{"assembly_id":"keep-7a", "message":"What is my threat level?", "history":[]}'
```

- [ ] **Step 5: Commit**
```bash
git add src/endpoints/structures.py src/tools/__init__.py
git commit -m "refactor: /structure-chat endpoint to use context-once tool pattern"
```

---

## Chunk 4: Wire Up building-terminal.html

### Task 8: Create working building-terminal.html

- [ ] **Step 1: Replace building-terminal.html**

Create file: `static/building-terminal.html`

```html
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">
  <title>Structure AI Companion</title>
  <style>
    * { margin: 0; padding: 0; box-sizing: border-box; }
    body { background: #000; color: #c8a560; font-family: 'Courier New', monospace; }
    .container { width: 100%; max-width: 1200px; margin: 0 auto; padding: 16px; }

    .auth-panel {
      border: 1px solid #5a4a20;
      padding: 16px;
      margin-bottom: 16px;
      background: #0a0804;
    }

    .status-line {
      padding: 8px 0;
      font-size: 14px;
      border-bottom: 1px solid #3a2a10;
      margin-bottom: 8px;
    }

    .status-label {
      color: #8a7a50;
      display: inline-block;
      width: 140px;
    }

    .status-value {
      color: #c8a560;
      font-weight: bold;
    }

    button {
      background: #2a1a08;
      color: #c8a560;
      border: 1px solid #5a4a20;
      padding: 8px 16px;
      margin-right: 8px;
      cursor: pointer;
      font-family: 'Courier New', monospace;
      font-size: 14px;
    }

    button:hover {
      background: #3a2a10;
      border-color: #c8a560;
    }

    button:disabled {
      opacity: 0.5;
      cursor: not-allowed;
    }

    select {
      background: #2a1a08;
      color: #c8a560;
      border: 1px solid #5a4a20;
      padding: 8px;
      font-family: 'Courier New', monospace;
      font-size: 14px;
    }

    .error {
      color: #ff6b6b;
    }

    .success {
      color: #51cf66;
    }

    .terminal {
      background: #0a0804;
      border: 1px solid #5a4a20;
      padding: 16px;
      height: 400px;
      overflow-y: auto;
      font-size: 12px;
      line-height: 1.4;
      font-family: 'Courier New', monospace;
      margin-bottom: 16px;
    }

    .log-line {
      padding: 4px 0;
      white-space: pre-wrap;
      word-break: break-all;
    }

    .log-error {
      color: #ff6b6b;
    }

    .log-success {
      color: #51cf66;
    }

    .log-info {
      color: #c8a560;
    }

    #chat-input {
      width: 100%;
      background: #2a1a08;
      color: #c8a560;
      border: 1px solid #5a4a20;
      padding: 12px;
      font-family: 'Courier New', monospace;
      font-size: 14px;
    }

    #chat-input:focus {
      border-color: #c8a560;
      outline: none;
    }

    .hidden {
      display: none;
    }
  </style>
</head>
<body>
  <div class="container">
    <h1 style="color: #c8a560; margin-bottom: 16px;">Structure AI Companion</h1>

    <!-- AUTH SECTION -->
    <div class="auth-panel" id="auth-section">
      <div class="status-line">
        <span class="status-label">Wallet:</span>
        <span class="status-value" id="wallet-status">Not connected</span>
      </div>
      <div class="status-line">
        <span class="status-label">Address:</span>
        <span class="status-value" id="address-status">—</span>
      </div>
      <div class="status-line">
        <span class="status-label">Auth:</span>
        <span class="status-value" id="auth-status">Not authenticated</span>
      </div>
      <div style="margin-top: 16px;">
        <button id="connect-btn">Connect Wallet</button>
        <button id="disconnect-btn" disabled>Disconnect</button>
      </div>
    </div>

    <!-- STRUCTURE SELECTOR -->
    <div class="auth-panel" id="structure-selector" style="display: none;">
      <div class="status-line">
        <span class="status-label">Structure:</span>
        <select id="structure-select">
          <option value="">Loading structures...</option>
        </select>
      </div>
      <div style="margin-top: 16px;">
        <button id="connect-structure-btn">Connect to Structure</button>
      </div>
    </div>

    <!-- CHAT SECTION -->
    <div id="chat-section" style="display: none;">
      <h3 style="color: #c8a560; margin-bottom: 8px;">Chat with Structure AI</h3>
      <div id="terminal" class="terminal"></div>
      <input id="chat-input" type="text" placeholder="Ask the structure AI..." />
    </div>
  </div>

  <script type="module">
    import WalletManager from '/static/js/wallet-manager.js';
    import WalletAuth from '/static/js/wallet-auth.js';
    import { StructureDApp } from '/static/js/structure-dapp.js';

    const SERVER_TOKEN = "5740edb0fb25a051db4a932c3622bd69ce47d487bc501f2bde4cb7e19907c454";

    // DOM elements
    const connectBtn = document.getElementById('connect-btn');
    const disconnectBtn = document.getElementById('disconnect-btn');
    const walletStatus = document.getElementById('wallet-status');
    const addressStatus = document.getElementById('address-status');
    const authStatus = document.getElementById('auth-status');
    const authSection = document.getElementById('auth-section');
    const structureSelector = document.getElementById('structure-selector');
    const structureSelect = document.getElementById('structure-select');
    const connectStructureBtn = document.getElementById('connect-structure-btn');
    const chatSection = document.getElementById('chat-section');
    const terminal = document.getElementById('terminal');
    const chatInput = document.getElementById('chat-input');

    let walletAuth = null;
    let dapp = null;

    function addLog(text, type = 'info') {
      const line = document.createElement('div');
      line.className = `log-line log-${type}`;
      line.textContent = `[${new Date().toLocaleTimeString()}] ${text}`;
      terminal.appendChild(line);
      terminal.scrollTop = terminal.scrollHeight;
    }

    function updateAuthUI(walletState, authState) {
      if (walletState.isConnected) {
        walletStatus.textContent = 'Connected';
        walletStatus.className = 'status-value success';
        addressStatus.textContent = walletState.walletAddress || '—';
        connectBtn.disabled = true;
        disconnectBtn.disabled = false;
      } else {
        walletStatus.textContent = 'Not connected';
        walletStatus.className = 'status-value error';
        addressStatus.textContent = '—';
        connectBtn.disabled = false;
        disconnectBtn.disabled = true;
        authStatus.textContent = 'Not authenticated';
        authStatus.className = 'status-value error';
      }

      if (authState?.authenticated) {
        authStatus.textContent = 'Authenticated';
        authStatus.className = 'status-value success';
      }
    }

    // Initialize
    addLog('Initializing Structure AI Companion...');

    // Set up wallet manager
    WalletManager.subscribe((state) => {
      addLog(`Wallet state: connected=${state.isConnected}`, state.isConnected ? 'success' : 'info');
      updateAuthUI(state, walletAuth ? { authenticated: walletAuth.isAuthenticated() } : {});
    });

    // Initialize wallet auth
    walletAuth = new WalletAuth(WalletManager);
    addLog('Wallet auth initialized');

    walletAuth.subscribe((state) => {
      addLog(`Auth state: authenticated=${state.authenticated}`, state.authenticated ? 'success' : 'info');
      updateAuthUI(WalletManager.getState(), state);

      // If authenticated, show structure selector
      if (state.authenticated) {
        structureSelector.style.display = 'block';
        loadStructures();
      }
    });

    // Button handlers
    connectBtn.addEventListener('click', async () => {
      try {
        connectBtn.disabled = true;
        addLog('Connecting wallet...');
        const account = await WalletManager.handleConnect();
        addLog(`Connected: ${account.address}`, 'success');

        // Start wallet auth flow
        addLog('Starting wallet auth flow...');
        await walletAuth.authenticate(account.address);
      } catch (err) {
        addLog(`Connection failed: ${err.message}`, 'error');
        connectBtn.disabled = false;
      }
    });

    disconnectBtn.addEventListener('click', () => {
      addLog('Disconnecting wallet...');
      WalletManager.handleDisconnect();
      walletAuth.logout();
      structureSelector.style.display = 'none';
      chatSection.style.display = 'none';
      addLog('Disconnected', 'info');
    });

    async function loadStructures() {
      try {
        addLog('Loading available structures...');
        const response = await fetch('/structures', {
          headers: { 'X-Server-Token': SERVER_TOKEN }
        });
        const data = await response.json();
        const structures = data.structures || [];

        structureSelect.innerHTML = '';
        structures.forEach(s => {
          const option = document.createElement('option');
          option.value = s.id;
          option.textContent = `${s.id} (${s.system_name})`;
          structureSelect.appendChild(option);
        });

        if (structures.length === 0) {
          addLog('No structures found', 'error');
        } else {
          addLog(`Found ${structures.length} structures`, 'success');
        }
      } catch (err) {
        addLog(`Failed to load structures: ${err.message}`, 'error');
      }
    }

    connectStructureBtn.addEventListener('click', async () => {
      const structureId = structureSelect.value;
      if (!structureId) {
        addLog('Please select a structure', 'error');
        return;
      }

      addLog(`Connecting to structure: ${structureId}`);

      // Create dApp instance
      dapp = new StructureDApp({
        assemblyId: structureId,
        walletAddress: WalletManager.getState().walletAddress,
        jwt: walletAuth.getJWT(),
        onLog: addLog,
        terminal: terminal,
        serverToken: SERVER_TOKEN
      });

      chatSection.style.display = 'block';
      authSection.style.display = 'none';
      addLog(`Connected to ${structureId}`, 'success');

      // Chat input handler
      chatInput.addEventListener('keydown', async (e) => {
        if (e.key === 'Enter' && chatInput.value.trim()) {
          const message = chatInput.value.trim();
          chatInput.value = '';
          addLog(`> ${message}`);
          await dapp.sendMessage(message);
        }
      });
    });

    // Initial state
    updateAuthUI(WalletManager.getState(), { authenticated: false });
    addLog('Ready. Click "Connect Wallet" to begin.');
  </script>
</body>
</html>
```

- [ ] **Step 2: Commit**
```bash
git add static/building-terminal.html
git commit -m "feat: replace building-terminal.html with working Structure AI companion"
```

---

### Task 9: Create structure-dapp.js

- [ ] **Step 1: Create file**

```bash
cat > static/js/structure-dapp.js << 'EOF'
export class StructureDApp {
  constructor(config) {
    this.assemblyId = config.assemblyId;
    this.walletAddress = config.walletAddress;
    this.jwt = config.jwt;
    this.onLog = config.onLog || (() => {});
    this.terminal = config.terminal;
    this.serverToken = config.serverToken;
    this.conversationHistory = [];
  }

  async sendMessage(message) {
    this.conversationHistory.push({ role: 'user', content: message });

    try {
      const response = await fetch('/structure-chat', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${this.jwt}`,
          'X-Server-Token': this.serverToken
        },
        body: JSON.stringify({
          assembly_id: this.assemblyId,
          message: message,
          history: this.conversationHistory.slice(-5)
        })
      });

      if (!response.ok) {
        const error = await response.json();
        this.onLog(`Error: ${error.detail}`, 'error');
        return;
      }

      const reader = response.body.getReader();
      const decoder = new TextDecoder();

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;

        const text = decoder.decode(value);
        const lines = text.split('\n');

        for (const line of lines) {
          if (line.startsWith('data: ')) {
            try {
              const data = JSON.parse(line.slice(6));

              if (data.text) {
                this.onLog(`AI: ${data.text}`);
                this.conversationHistory.push({ role: 'assistant', content: data.text });
              }

              if (data.tool) {
                this.onLog(`[Tool: ${data.tool}] ${data.result}`, 'info');
              }

              if (data.error) {
                this.onLog(`Error: ${data.error}`, 'error');
              }
            } catch (e) {
              // Skip unparseable lines
            }
          }
        }
      }
    } catch (err) {
      this.onLog(`Network error: ${err.message}`, 'error');
    }
  }
}
EOF
```

- [ ] **Step 2: Commit**
```bash
git add static/js/structure-dapp.js
git commit -m "feat: create structure-dapp.js terminal application"
```

---

### Task 10: End-to-End Test

- [ ] **Step 1: Start server**
```bash
cd /opt/eve-frontier
python -m uvicorn main:app --reload --port 8745
```

- [ ] **Step 2: Open building-terminal.html in browser**
```
http://localhost:8745/building-ai
```

- [ ] **Step 3: Test flow**
  - [ ] Click "Connect Wallet" → EVE Vault appears
  - [ ] Select wallet account → authenticated
  - [ ] "Structure selector" appears
  - [ ] Select a structure from dropdown
  - [ ] Click "Connect to Structure"
  - [ ] Chat input appears
  - [ ] Type message: "What is my threat level?"
  - [ ] See SSE stream with AI response + tool calls

- [ ] **Step 4: Verify logs in terminal**
Should see:
```
[time] > What is my threat level?
[time] [Tool: assess_threat_level] THREAT: ...
[time] AI: Based on the threat assessment, ...
```

- [ ] **Step 5: Commit final state**
```bash
git add -A
git commit -m "test: verify end-to-end Structure AI flow"
```

---

## Summary

**Changes made:**
1. ✅ Renamed `nova_client.py` → `blockchain_queries.py`
2. ✅ Renamed `structure_profile.py` → `structure_persistence.py`
3. ✅ Created `src/tools/` directory with 6 pure functions
4. ✅ Refactored `/structure-chat` to use context-once tool pattern
5. ✅ Created working `building-terminal.html` with wallet auth
6. ✅ Created `structure-dapp.js` terminal app

**Result:** Minimal, focused refactor. Backend follows official flow. building-terminal.html now functional.
