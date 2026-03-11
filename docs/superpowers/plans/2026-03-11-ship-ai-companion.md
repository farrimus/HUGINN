# Ship AI Companion — Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a Python/FastAPI ship AI companion for EVE Frontier with a streaming chat UI, live game data via World API, and event-driven log ingestion from a Windows client agent.

**Architecture:** FastAPI server on port 8745 serves a single-file HTML frontend and four backend modules (Claude API, World API client, log buffer, auth). A separate Windows Python script (log-agent.py) watches EVE Frontier log files and POSTs structured events to the server. Claude receives an assembled context block per message and streams responses via SSE.

**Tech Stack:** Python 3.11+, FastAPI, httpx, anthropic SDK, watchdog (log agent), pytest, plain HTML/CSS/JS (no build step)

**Spec:** `docs/superpowers/specs/2026-03-11-ship-ai-companion-design.md`

---

## Chunk 1: Project Setup + FastAPI Skeleton + Auth

### Task 1: Project structure and dependencies

**Files:**
- Create: `requirements.txt`
- Create: `.env.example`
- Create: `src/__init__.py`
- Create: `tests/__init__.py`

- [ ] **Step 1: Create requirements.txt**

```
fastapi==0.115.0
uvicorn[standard]==0.30.0
httpx==0.27.0
anthropic==0.34.0
python-dotenv==1.0.0
pytest==8.3.0
pytest-asyncio==0.23.0
httpx[test]
```

- [ ] **Step 2: Create .env.example**

```
ANTHROPIC_API_KEY=your-key-here
WORLD_API_BASE_URL=https://api.evefrontier.com
WORLD_API_KEY=
SHIP_TOKEN=change-this-to-a-random-secret
PORT=8745
```

- [ ] **Step 3: Create directory structure**

```bash
mkdir -p /opt/eve-frontier/src
mkdir -p /opt/eve-frontier/static
mkdir -p /opt/eve-frontier/tests
mkdir -p /opt/eve-frontier/log-agent
touch /opt/eve-frontier/src/__init__.py
touch /opt/eve-frontier/tests/__init__.py
```

- [ ] **Step 4: Install dependencies**

```bash
cd /opt/eve-frontier
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

Expected: all packages install without error.

- [ ] **Step 5: Commit**

```bash
git add requirements.txt .env.example src/__init__.py tests/__init__.py
git commit -m "feat: project structure and dependencies"
```

---

### Task 2: FastAPI app skeleton with health check

**Files:**
- Create: `main.py`
- Create: `tests/test_main.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_main.py
from httpx import AsyncClient, ASGITransport
import pytest
from main import app

@pytest.mark.asyncio
async def test_health_check():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
```

- [ ] **Step 2: Run test to verify it fails**

```bash
cd /opt/eve-frontier && source .venv/bin/activate
pytest tests/test_main.py -v
```

Expected: FAIL — `ModuleNotFoundError: No module named 'main'`

- [ ] **Step 3: Write minimal implementation**

```python
# main.py
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from dotenv import load_dotenv
import os

load_dotenv()

app = FastAPI(title="Ship AI Companion")
app.mount("/static", StaticFiles(directory="static"), name="static")

@app.get("/health")
async def health():
    return {"status": "ok"}
```

- [ ] **Step 4: Run test to verify it passes**

```bash
pytest tests/test_main.py -v
```

Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add main.py tests/test_main.py
git commit -m "feat: FastAPI skeleton with health check"
```

---

### Task 3: Auth middleware (X-Ship-Token)

**Files:**
- Create: `src/auth.py`
- Create: `tests/test_auth.py`

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_auth.py
from httpx import AsyncClient, ASGITransport
import pytest
from fastapi import FastAPI
from src.auth import require_token

app = FastAPI()

@app.get("/protected")
async def protected(token_valid=require_token):
    return {"ok": True}

@pytest.mark.asyncio
async def test_valid_token_passes(monkeypatch):
    monkeypatch.setenv("SHIP_TOKEN", "test-secret")
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/protected", headers={"X-Ship-Token": "test-secret"})
    assert response.status_code == 200

@pytest.mark.asyncio
async def test_missing_token_rejected(monkeypatch):
    monkeypatch.setenv("SHIP_TOKEN", "test-secret")
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/protected")
    assert response.status_code == 403

@pytest.mark.asyncio
async def test_wrong_token_rejected(monkeypatch):
    monkeypatch.setenv("SHIP_TOKEN", "test-secret")
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/protected", headers={"X-Ship-Token": "wrong"})
    assert response.status_code == 403

@pytest.mark.asyncio
async def test_no_token_configured_allows_all(monkeypatch):
    monkeypatch.delenv("SHIP_TOKEN", raising=False)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/protected")
    assert response.status_code == 200
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
pytest tests/test_auth.py -v
```

Expected: FAIL — `ModuleNotFoundError: No module named 'src.auth'`

- [ ] **Step 3: Write minimal implementation**

```python
# src/auth.py
import os
from fastapi import Header, HTTPException, Depends

def require_token(x_ship_token: str = Header(default="")):
    expected = os.getenv("SHIP_TOKEN", "")
    if not expected:
        return  # No token configured — open access (local-only mode)
    if x_ship_token != expected:
        raise HTTPException(status_code=403, detail="Invalid token")
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
pytest tests/test_auth.py -v
```

Expected: all 3 PASS

- [ ] **Step 5: Commit**

```bash
git add src/auth.py tests/test_auth.py
git commit -m "feat: X-Ship-Token auth middleware"
```

---

## Chunk 2: Log Buffer

### Task 4: Log buffer + /log/ingest endpoint

**Files:**
- Create: `src/log_buffer.py`
- Create: `tests/test_log_buffer.py`
- Modify: `main.py` — add `/log/ingest` route

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_log_buffer.py
import pytest
from src.log_buffer import LogBuffer

def test_add_event_stores_in_buffer():
    buf = LogBuffer(max_size=50)
    buf.add({"type": "jump", "system": "Jita"})
    assert len(buf.events) == 1

def test_buffer_caps_at_max_size():
    buf = LogBuffer(max_size=3)
    for i in range(5):
        buf.add({"type": "jump", "system": f"System{i}"})
    assert len(buf.events) == 3

def test_buffer_drops_oldest_when_full():
    buf = LogBuffer(max_size=3)
    for i in range(5):
        buf.add({"type": "jump", "system": f"System{i}"})
    assert buf.events[0]["system"] == "System2"

def test_get_recent_returns_last_n():
    buf = LogBuffer(max_size=50)
    for i in range(20):
        buf.add({"type": "event", "index": i})
    recent = buf.get_recent(10)
    assert len(recent) == 10
    assert recent[-1]["index"] == 19

def test_get_recent_returns_all_if_fewer_than_n():
    buf = LogBuffer(max_size=50)
    buf.add({"type": "event", "index": 0})
    assert len(buf.get_recent(10)) == 1

def test_system_change_events_tracked():
    buf = LogBuffer(max_size=50)
    buf.add({"type": "system_change", "system": "Amarr"})
    assert buf.current_system == "Amarr"

def test_current_system_defaults_to_none():
    buf = LogBuffer(max_size=50)
    assert buf.current_system is None

@pytest.fixture(autouse=True)
def reset_global_buffer():
    from src.log_buffer import log_buffer
    log_buffer.events.clear()
    log_buffer.current_system = None
    yield
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
pytest tests/test_log_buffer.py -v
```

Expected: FAIL — `ModuleNotFoundError: No module named 'src.log_buffer'`

- [ ] **Step 3: Write minimal implementation**

```python
# src/log_buffer.py
from collections import deque
from typing import Optional

class LogBuffer:
    def __init__(self, max_size: int = 50):
        self.events: deque = deque(maxlen=max_size)
        self.current_system: Optional[str] = None

    def add(self, event: dict):
        self.events.append(event)
        if event.get("type") == "system_change":
            self.current_system = event.get("system")

    def get_recent(self, n: int = 10) -> list:
        events = list(self.events)
        return events[-n:]

# Global singleton used by the FastAPI app
log_buffer = LogBuffer(max_size=50)
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
pytest tests/test_log_buffer.py -v
```

Expected: all 7 PASS

- [ ] **Step 5: Add /log/ingest route to main.py**

```python
# Add to main.py
from fastapi import Depends
from pydantic import BaseModel
from src.log_buffer import log_buffer
from src.auth import require_token

class LogEvent(BaseModel):
    type: str
    system: str | None = None
    data: dict | None = None

@app.post("/log/ingest", dependencies=[Depends(require_token)])
async def ingest_log(event: LogEvent):
    log_buffer.add(event.model_dump())
    return {"accepted": True}
```

- [ ] **Step 6: Run full test suite**

```bash
pytest tests/ -v
```

Expected: all PASS

- [ ] **Step 7: Commit**

```bash
git add src/log_buffer.py tests/test_log_buffer.py main.py
git commit -m "feat: log buffer and /log/ingest endpoint"
```

---

## Chunk 3: World API Client

### Task 5: World API client with per-endpoint caching

**Files:**
- Create: `src/world_api.py`
- Create: `tests/test_world_api.py`

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_world_api.py
import pytest
import time
from unittest.mock import AsyncMock, patch
from src.world_api import WorldAPIClient

@pytest.mark.asyncio
async def test_get_system_returns_data():
    client = WorldAPIClient(base_url="https://fake.api", api_key="")
    mock_response = {"name": "Jita", "security": 0.9, "kills": []}
    with patch.object(client, "_fetch", return_value=mock_response):
        result = await client.get_system("Jita")
    assert result["name"] == "Jita"

@pytest.mark.asyncio
async def test_cache_returns_cached_result():
    client = WorldAPIClient(base_url="https://fake.api", api_key="")
    mock_response = {"name": "Jita"}
    with patch.object(client, "_fetch", return_value=mock_response) as mock_fetch:
        await client.get_system("Jita")
        await client.get_system("Jita")
    assert mock_fetch.call_count == 1  # second call hit cache

@pytest.mark.asyncio
async def test_cache_expires_after_ttl():
    client = WorldAPIClient(base_url="https://fake.api", api_key="", cache_ttl=0.1)
    mock_response = {"name": "Jita"}
    with patch.object(client, "_fetch", return_value=mock_response) as mock_fetch:
        await client.get_system("Jita")
        time.sleep(0.2)
        await client.get_system("Jita")
    assert mock_fetch.call_count == 2  # cache expired

@pytest.mark.asyncio
async def test_different_systems_cached_independently():
    client = WorldAPIClient(base_url="https://fake.api", api_key="")
    with patch.object(client, "_fetch", return_value={"name": "X"}) as mock_fetch:
        await client.get_system("Jita")
        await client.get_system("Amarr")
    assert mock_fetch.call_count == 2

@pytest.mark.asyncio
async def test_returns_none_on_api_error():
    client = WorldAPIClient(base_url="https://fake.api", api_key="")
    with patch.object(client, "_fetch", side_effect=Exception("timeout")):
        result = await client.get_system("Jita")
    assert result is None
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
pytest tests/test_world_api.py -v
```

Expected: FAIL — `ModuleNotFoundError: No module named 'src.world_api'`

- [ ] **Step 3: Write minimal implementation**

```python
# src/world_api.py
import os
import time
import httpx
from typing import Optional

class WorldAPIClient:
    def __init__(self, base_url: str = None, api_key: str = None, cache_ttl: float = 30.0):
        self.base_url = base_url or os.getenv("WORLD_API_BASE_URL", "https://api.evefrontier.com")
        self.api_key = api_key if api_key is not None else os.getenv("WORLD_API_KEY", "")
        self.cache_ttl = cache_ttl
        self._cache: dict = {}  # key -> (data, timestamp)

    def _cache_key(self, endpoint: str, params: dict) -> str:
        return f"{endpoint}:{sorted(params.items())}"

    def _get_cached(self, key: str) -> Optional[dict]:
        if key not in self._cache:
            return None
        data, ts = self._cache[key]
        if time.time() - ts > self.cache_ttl:
            del self._cache[key]
            return None
        return data

    async def _fetch(self, endpoint: str, params: dict = None) -> dict:
        headers = {"Authorization": f"Bearer {self.api_key}"} if self.api_key else {}
        async with httpx.AsyncClient() as client:
            response = await client.get(f"{self.base_url}{endpoint}", params=params or {}, headers=headers, timeout=10.0)
            response.raise_for_status()
            return response.json()

    async def _cached_fetch(self, endpoint: str, params: dict = None) -> Optional[dict]:
        key = self._cache_key(endpoint, params or {})
        cached = self._get_cached(key)
        if cached is not None:
            return cached
        try:
            data = await self._fetch(endpoint, params)
            self._cache[key] = (data, time.time())
            return data
        except Exception:
            return None

    async def get_system(self, system_name: str) -> Optional[dict]:
        return await self._cached_fetch("/v1/system", {"name": system_name})

    async def get_killmails(self, system_name: str) -> list:
        # Returns [] on empty or fetch error — never None
        result = await self._cached_fetch("/v1/killmails", {"system": system_name})
        if result is None:
            return []
        return result if isinstance(result, list) else []

# Global singleton
world_api = WorldAPIClient()
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
pytest tests/test_world_api.py -v
```

Expected: all 5 PASS

- [ ] **Step 5: Commit**

```bash
git add src/world_api.py tests/test_world_api.py
git commit -m "feat: World API client with per-endpoint TTL cache"
```

---

## Chunk 4: Claude API + Context Builder

### Task 6: Context builder

**Files:**
- Create: `src/context_builder.py`
- Create: `tests/test_context_builder.py`

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_context_builder.py
from src.context_builder import build_context_block

def test_empty_inputs_produce_minimal_block():
    block = build_context_block(system_data=None, log_events=[], current_system=None)
    assert "CURRENT SYSTEM" in block
    assert "unknown" in block.lower()

def test_system_data_included():
    system_data = {"name": "Jita", "security": 0.9}
    block = build_context_block(system_data=system_data, log_events=[], current_system="Jita")
    assert "Jita" in block
    assert "0.9" in block

def test_log_events_included():
    events = [
        {"type": "jump", "system": "Jita", "timestamp": "12:00"},
        {"type": "combat", "target": "Rogue Drone", "damage": 450},
    ]
    block = build_context_block(system_data=None, log_events=events, current_system=None)
    assert "jump" in block
    assert "combat" in block

def test_context_block_under_500_tokens_approx():
    # Rough check: 500 tokens ~ 375 words ~ 2000 chars
    system_data = {"name": "Jita", "security": 0.9, "kills": list(range(100))}
    events = [{"type": "event", "data": "x" * 100} for _ in range(20)]
    block = build_context_block(system_data=system_data, log_events=events, current_system="Jita")
    assert len(block) <= 2000

def test_killmails_summarised_not_dumped():
    system_data = {"name": "Jita", "kills": [{"victim": f"Player{i}"} for i in range(50)]}
    block = build_context_block(system_data=system_data, log_events=[], current_system="Jita")
    assert "Player49" not in block  # not dumping all 50
    assert "kill" in block.lower()
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
pytest tests/test_context_builder.py -v
```

Expected: FAIL — `ModuleNotFoundError`

- [ ] **Step 3: Write minimal implementation**

```python
# src/context_builder.py
from typing import Optional

def build_context_block(
    system_data: Optional[dict],
    log_events: list,
    current_system: Optional[str],
) -> str:
    lines = []

    # Current system
    system_name = current_system or (system_data or {}).get("name", "unknown")
    lines.append(f"CURRENT SYSTEM: {system_name}")

    if system_data:
        security = system_data.get("security")
        if security is not None:
            lines.append(f"SECURITY: {security:.1f}")
        kills = system_data.get("kills", [])
        if kills:
            lines.append(f"RECENT KILLS IN SYSTEM: {min(len(kills), 5)} recorded")

    # Recent log events (last 10, truncated to avoid bloat)
    if log_events:
        lines.append("RECENT EVENTS:")
        for event in log_events[-10:]:
            event_type = event.get("type", "unknown")
            # Format each event type cleanly
            if event_type == "jump":
                lines.append(f"  - jumped to {event.get('system', '?')}")
            elif event_type == "combat":
                lines.append(f"  - combat: {event.get('damage', '?')} dmg vs {event.get('target', '?')}")
            elif event_type == "system_change":
                lines.append(f"  - entered system {event.get('system', '?')}")
            elif event_type == "docking":
                lines.append(f"  - docked at {event.get('location', '?')}")
            else:
                lines.append(f"  - {event_type}")

    block = "\n".join(lines)
    # Hard cap: truncate to ~2000 chars if somehow over
    return block[:2000]
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
pytest tests/test_context_builder.py -v
```

Expected: all 5 PASS

- [ ] **Step 5: Commit**

```bash
git add src/context_builder.py tests/test_context_builder.py
git commit -m "feat: context builder with 2000-char cap"
```

---

### Task 7: Claude API client with streaming

**Files:**
- Create: `src/claude_client.py`
- Create: `tests/test_claude_client.py`
- Modify: `main.py` — add `/chat` SSE endpoint

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_claude_client.py
import pytest
from unittest.mock import patch, MagicMock
from src.claude_client import ClaudeClient, SYSTEM_PROMPT

def test_system_prompt_contains_identity():
    assert "ship" in SYSTEM_PROMPT.lower()
    assert "computer" in SYSTEM_PROMPT.lower() or "unit" in SYSTEM_PROMPT.lower()

def test_system_prompt_does_not_contain_name():
    # The AI has no name — no proper noun identifier
    assert "my name is" not in SYSTEM_PROMPT.lower()
    assert "i am called" not in SYSTEM_PROMPT.lower()

def test_build_messages_includes_history():
    client = ClaudeClient(api_key="fake")
    history = [
        {"role": "user", "content": "where am i"},
        {"role": "assistant", "content": "Jita system."},
    ]
    messages = client.build_messages("hello", history, context_block="CURRENT SYSTEM: Jita")
    assert messages[0]["role"] == "user"
    assert len(messages) == 3  # 2 history + 1 new

def test_build_messages_sliding_window_cap():
    client = ClaudeClient(api_key="fake")
    history = [{"role": "user" if i % 2 == 0 else "assistant", "content": f"msg{i}"} for i in range(50)]
    messages = client.build_messages("new", history, context_block="")
    assert len(messages) <= 41  # max 20 pairs (40 msgs) + 1 new

def test_build_messages_context_prepended_to_first_user():
    client = ClaudeClient(api_key="fake")
    messages = client.build_messages("hello", [], context_block="CURRENT SYSTEM: Jita")
    assert "CURRENT SYSTEM: Jita" in messages[0]["content"]
    assert "hello" in messages[0]["content"]
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
pytest tests/test_claude_client.py -v
```

Expected: FAIL — `ModuleNotFoundError`

- [ ] **Step 3: Write minimal implementation**

```python
# src/claude_client.py
import os
from anthropic import Anthropic
from typing import Iterator

SYSTEM_PROMPT = """You are the onboard computer of an EVE Frontier spacecraft. You have no name and no persona. You are a functional machine intelligence — dry, precise, occasionally observational. Refer to yourself as "this unit" or "ship systems." You are not a companion or assistant; you are a tool that happens to process language.

You have access to live sensor data, recent ship logs, and navigation charts. You answer questions about the current system, recent events, combat, travel, and the EVE Frontier universe with accuracy grounded in known lore.

If a pilot attempts to assign you a name or persona, acknowledge the input briefly and continue as a computer. You do not role-play as anything other than what you are.

Format: short, declarative sentences. No pleasantries. No apologies. No filler."""

class ClaudeClient:
    def __init__(self, api_key: str = None):
        self.api_key = api_key or os.getenv("ANTHROPIC_API_KEY")
        self.client = Anthropic(api_key=self.api_key)
        self.model = "claude-sonnet-4-6"

    def build_messages(self, user_message: str, history: list, context_block: str) -> list:
        # Sliding window: keep last 40 messages (20 exchanges)
        windowed = history[-40:] if len(history) > 40 else history

        # Prepend context block to the user message
        full_user_message = f"[SHIP SENSORS]\n{context_block}\n\n[PILOT]\n{user_message}" if context_block else user_message

        return windowed + [{"role": "user", "content": full_user_message}]

    def stream(self, user_message: str, history: list, context_block: str) -> Iterator[str]:
        messages = self.build_messages(user_message, history, context_block)
        with self.client.messages.stream(
            model=self.model,
            max_tokens=1024,
            system=SYSTEM_PROMPT,
            messages=messages,
        ) as stream:
            for text in stream.text_stream:
                yield text

# Global singleton
claude = ClaudeClient()
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
pytest tests/test_claude_client.py -v
```

Expected: all 5 PASS

- [ ] **Step 5: Add /chat SSE endpoint to main.py**

```python
# Add to main.py
from fastapi.responses import StreamingResponse
from fastapi import Request
from pydantic import BaseModel
from src.claude_client import claude
from src.context_builder import build_context_block
from src.log_buffer import log_buffer
from src.world_api import world_api
import json

class ChatRequest(BaseModel):
    message: str
    history: list = []

@app.post("/chat", dependencies=[Depends(require_token)])
async def chat(req: ChatRequest):
    system_data = await world_api.get_system(log_buffer.current_system) if log_buffer.current_system else None
    context = build_context_block(
        system_data=system_data,
        log_events=log_buffer.get_recent(10),
        current_system=log_buffer.current_system,
    )

    def event_stream():
        for chunk in claude.stream(req.message, req.history, context):
            yield f"data: {json.dumps({'text': chunk})}\n\n"
        yield "data: [DONE]\n\n"

    return StreamingResponse(event_stream(), media_type="text/event-stream")
```

- [ ] **Step 6: Run full test suite**

```bash
pytest tests/ -v
```

Expected: all PASS

- [ ] **Step 7: Commit**

```bash
git add src/claude_client.py tests/test_claude_client.py main.py
git commit -m "feat: Claude client with streaming and /chat SSE endpoint"
```

---

## Chunk 5: Frontend

### Task 8: Chat UI (index.html)

**Files:**
- Create: `static/index.html`

No unit tests for the frontend — manual test by opening in browser.

- [ ] **Step 1: Create static/index.html**

```html
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Ship Systems</title>
<style>
  * { box-sizing: border-box; margin: 0; padding: 0; }
  body {
    background: #0a0d0f;
    color: #7fb38a;
    font-family: 'Courier New', Courier, monospace;
    font-size: 13px;
    height: 100vh;
    display: flex;
    flex-direction: column;
  }
  #header {
    padding: 8px 12px;
    border-bottom: 1px solid #1e2d22;
    display: flex;
    justify-content: space-between;
    align-items: center;
    color: #4a7a52;
    font-size: 11px;
    letter-spacing: 0.1em;
  }
  #header span { text-transform: uppercase; }
  #minimize-btn {
    cursor: pointer;
    background: none;
    border: 1px solid #1e2d22;
    color: #4a7a52;
    padding: 2px 8px;
    font-family: inherit;
    font-size: 11px;
  }
  #minimize-btn:hover { border-color: #7fb38a; color: #7fb38a; }
  #messages {
    flex: 1;
    overflow-y: auto;
    padding: 12px;
    display: flex;
    flex-direction: column;
    gap: 10px;
  }
  .msg { max-width: 90%; line-height: 1.5; }
  .msg.ai { color: #7fb38a; align-self: flex-start; }
  .msg.ai::before { content: '> '; color: #4a7a52; }
  .msg.user { color: #a0c4a8; align-self: flex-end; text-align: right; }
  .msg.user::before { content: 'PILOT: '; color: #4a7a52; }
  .msg.error { color: #8b3a3a; align-self: center; font-size: 11px; }
  #input-row {
    display: flex;
    border-top: 1px solid #1e2d22;
    padding: 8px;
    gap: 8px;
  }
  #input {
    flex: 1;
    background: #0d1214;
    border: 1px solid #1e2d22;
    color: #7fb38a;
    font-family: inherit;
    font-size: 13px;
    padding: 6px 10px;
    outline: none;
  }
  #input:focus { border-color: #4a7a52; }
  #send-btn {
    background: none;
    border: 1px solid #1e2d22;
    color: #4a7a52;
    font-family: inherit;
    font-size: 11px;
    padding: 6px 14px;
    cursor: pointer;
    text-transform: uppercase;
    letter-spacing: 0.1em;
  }
  #send-btn:hover:not(:disabled) { border-color: #7fb38a; color: #7fb38a; }
  #send-btn:disabled { opacity: 0.4; cursor: default; }
  #status { font-size: 10px; color: #2d4a32; padding: 4px 12px; }
</style>
</head>
<body>
<div id="header">
  <span>SHIP SYSTEMS // ONLINE</span>
  <button id="minimize-btn" onclick="toggleMinimize()">—</button>
</div>
<div id="messages"></div>
<div id="status" id="status-bar">READY</div>
<div id="input-row">
  <input id="input" type="text" placeholder="Enter query..." autocomplete="off" />
  <button id="send-btn" onclick="sendMessage()">SEND</button>
</div>

<script>
const params = new URLSearchParams(window.location.search);
const isIngame = params.get('mode') === 'ingame';
const token = ''; // Set via env/config if auth enabled

if (isIngame) document.getElementById('minimize-btn').style.display = 'none';

let history = [];
let minimized = false;

function toggleMinimize() {
  minimized = !minimized;
  document.getElementById('messages').style.display = minimized ? 'none' : 'flex';
  document.getElementById('input-row').style.display = minimized ? 'none' : 'flex';
  document.getElementById('minimize-btn').textContent = minimized ? '□' : '—';
}

document.getElementById('input').addEventListener('keydown', e => {
  if (e.key === 'Enter') sendMessage();
});

function addMessage(text, type) {
  const div = document.createElement('div');
  div.className = `msg ${type}`;
  div.textContent = text;
  const msgs = document.getElementById('messages');
  msgs.appendChild(div);
  msgs.scrollTop = msgs.scrollHeight;
  return div;
}

function setStatus(text) {
  document.getElementById('status').textContent = text;
}

async function sendMessage() {
  const input = document.getElementById('input');
  const msg = input.value.trim();
  if (!msg) return;
  input.value = '';
  document.getElementById('send-btn').disabled = true;

  addMessage(msg, 'user');
  const aiDiv = addMessage('', 'ai');
  setStatus('PROCESSING...');

  const headers = { 'Content-Type': 'application/json' };
  if (token) headers['X-Ship-Token'] = token;

  try {
    const response = await fetch('/chat', {
      method: 'POST',
      headers,
      body: JSON.stringify({ message: msg, history })
    });

    if (!response.ok) throw new Error(`HTTP ${response.status}`);

    const reader = response.body.getReader();
    const decoder = new TextDecoder();
    let fullText = '';

    while (true) {
      const { done, value } = await reader.read();
      if (done) break;
      const chunk = decoder.decode(value);
      const lines = chunk.split('\n');
      for (const line of lines) {
        if (!line.startsWith('data: ')) continue;
        const data = line.slice(6);
        if (data === '[DONE]') break;
        try {
          const parsed = JSON.parse(data);
          fullText += parsed.text;
          aiDiv.textContent = fullText;
          document.getElementById('messages').scrollTop = document.getElementById('messages').scrollHeight;
        } catch (_) {}
      }
    }

    history.push({ role: 'user', content: msg });
    history.push({ role: 'assistant', content: fullText });
    if (history.length > 40) history = history.slice(-40);
    setStatus('READY');
  } catch (err) {
    addMessage(`COMM ERROR: ${err.message}`, 'error');
    setStatus('ERROR');
  }
  document.getElementById('send-btn').disabled = false;
}
</script>
</body>
</html>
```

- [ ] **Step 2: Manual smoke test**

```bash
cd /opt/eve-frontier && source .venv/bin/activate
uvicorn main:app --port 8745
```

Open `http://localhost:8745/static/index.html` in a browser. Verify:
- Dark terminal UI renders correctly
- Minimize button visible (overlay mode, no `?mode=ingame` param)
- Input and send button present
- No JS console errors

- [ ] **Step 3: Commit**

```bash
git add static/index.html
git commit -m "feat: ship terminal chat UI"
```

---

## Chunk 6: Log Agent (Windows Client)

### Task 9: Log agent — Gamelogs watcher

**Files:**
- Create: `log-agent/requirements.txt`
- Create: `log-agent/.env.example`
- Create: `log-agent/log_agent.py`
- Create: `log-agent/parsers.py`
- Create: `log-agent/tests/test_parsers.py`

- [ ] **Step 1: Create log-agent/requirements.txt**

```
watchdog==4.0.0
requests==2.32.0
python-dotenv==1.0.0
pytest==8.3.0
```

- [ ] **Step 2: Create log-agent/.env.example**

```
SERVER_URL=http://your-vps-ip:8745
SHIP_TOKEN=change-this-to-match-server
LOG_BASE_PATH=C:\Users\Markus\Documents\Frontier\logs
```

- [ ] **Step 3: Write failing parser tests**

```python
# log-agent/tests/test_parsers.py
import pytest
from parsers import parse_gamelog_line, parse_chatlog_line

def test_parse_combat_line():
    line = "[ 2026.03.11 14:23:01 ] (combat) 450 to Rogue Drone - Railgun II - Hits"
    event = parse_gamelog_line(line)
    assert event is not None
    assert event["type"] == "combat"
    assert event["damage"] == 450
    assert "Rogue Drone" in event["target"]

def test_parse_mining_line():
    line = "[ 2026.03.11 14:25:00 ] (mining) 150 units of Veldspar mined"
    event = parse_gamelog_line(line)
    assert event is not None
    assert event["type"] == "mining"

def test_unrecognised_line_returns_none():
    line = "[ 2026.03.11 14:00:00 ] (notify) Some irrelevant notification"
    event = parse_gamelog_line(line)
    assert event is None

def test_parse_system_change_from_local_chat():
    line = "[ 2026.03.11 14:30:00 ] Channel changed to Jita"
    event = parse_chatlog_line(line)
    assert event is not None
    assert event["type"] == "system_change"
    assert event["system"] == "Jita"

def test_parse_regular_chat_returns_none():
    line = "[ 2026.03.11 14:31:00 ] Pilot_Name > hello"
    event = parse_chatlog_line(line)
    assert event is None
```

- [ ] **Step 4: Run tests to verify they fail**

```bash
cd /opt/eve-frontier/log-agent
pip install -r requirements.txt
pytest tests/test_parsers.py -v
```

Expected: FAIL — `ModuleNotFoundError: No module named 'parsers'`

- [ ] **Step 5: Write minimal parsers.py**

```python
# log-agent/parsers.py
import re
from typing import Optional

# Adjust these patterns once the exact log format is confirmed from real logs.
COMBAT_RE = re.compile(r'\(combat\)\s+(\d+)\s+to\s+(.+?)\s+-')
MINING_RE = re.compile(r'\(mining\)')
SYSTEM_CHANGE_RE = re.compile(r'Channel changed to (.+)')

def parse_gamelog_line(line: str) -> Optional[dict]:
    m = COMBAT_RE.search(line)
    if m:
        return {"type": "combat", "damage": int(m.group(1)), "target": m.group(2).strip()}
    if MINING_RE.search(line):
        return {"type": "mining", "raw": line.strip()}
    return None

def parse_chatlog_line(line: str) -> Optional[dict]:
    m = SYSTEM_CHANGE_RE.search(line)
    if m:
        return {"type": "system_change", "system": m.group(1).strip()}
    return None
```

- [ ] **Step 6: Run tests to verify they pass**

```bash
pytest tests/test_parsers.py -v
```

Expected: all 5 PASS

- [ ] **Step 7: Write log_agent.py**

```python
# log-agent/log_agent.py
import os
import time
import requests
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler
from parsers import parse_gamelog_line, parse_chatlog_line
from dotenv import load_dotenv

load_dotenv()

SERVER_URL = os.getenv("SERVER_URL", "http://localhost:8745")
SHIP_TOKEN = os.getenv("SHIP_TOKEN", "")
LOG_BASE = os.getenv("LOG_BASE_PATH", r"C:\Users\Markus\Documents\Frontier\logs")
GAMELOG_DIR = os.path.join(LOG_BASE, "Gamelogs")
CHATLOG_DIR = os.path.join(LOG_BASE, "Chatlogs")

def validate_paths():
    for path in [GAMELOG_DIR, CHATLOG_DIR]:
        if not os.path.isdir(path):
            raise FileNotFoundError(f"Log directory not found: {path}")

def send_event(event: dict):
    headers = {"X-Ship-Token": SHIP_TOKEN} if SHIP_TOKEN else {}
    try:
        requests.post(f"{SERVER_URL}/log/ingest", json=event, headers=headers, timeout=5)
    except Exception as e:
        print(f"[agent] failed to send event: {e}")

class LogFileHandler(FileSystemEventHandler):
    def __init__(self, parser_fn):
        self._file_positions = {}
        self.parser_fn = parser_fn

    def on_modified(self, event):
        if event.is_directory:
            return
        path = event.src_path
        pos = self._file_positions.get(path, 0)
        try:
            with open(path, "r", encoding="utf-8", errors="ignore") as f:
                f.seek(pos)
                new_lines = f.readlines()
                self._file_positions[path] = f.tell()
            for line in new_lines:
                parsed = self.parser_fn(line)
                if parsed:
                    print(f"[agent] sending: {parsed}")
                    send_event(parsed)
        except Exception as e:
            print(f"[agent] error reading {path}: {e}")

if __name__ == "__main__":
    validate_paths()
    print(f"[agent] watching {GAMELOG_DIR} and {CHATLOG_DIR}")

    observer = Observer()
    observer.schedule(LogFileHandler(parse_gamelog_line), GAMELOG_DIR, recursive=False)
    observer.schedule(LogFileHandler(parse_chatlog_line), CHATLOG_DIR, recursive=False)
    observer.start()

    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        observer.stop()
    observer.join()
```

- [ ] **Step 8: Commit**

```bash
git add log-agent/
git commit -m "feat: Windows log agent with gamelog and chatlog parsers"
```

---

## Chunk 7: Integration + System Change Refresh

### Task 10: System-change triggered World API refresh

**Files:**
- Modify: `main.py` — trigger World API fetch on system_change event
- Create: `tests/test_integration.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_integration.py
import pytest
from unittest.mock import AsyncMock, patch
from httpx import AsyncClient, ASGITransport
from main import app
import os

@pytest.mark.asyncio
async def test_system_change_triggers_world_api_refresh(monkeypatch):
    monkeypatch.setenv("SHIP_TOKEN", "")  # disable auth for test
    from src import world_api as wa_module
    mock_fetch = AsyncMock(return_value={"name": "Jita", "security": 0.9})
    wa_module.world_api.get_system = mock_fetch

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post("/log/ingest", json={"type": "system_change", "system": "Jita"})

    assert response.status_code == 200
    mock_fetch.assert_called_once_with("Jita")

@pytest.mark.asyncio
async def test_non_system_change_does_not_call_world_api(monkeypatch):
    monkeypatch.setenv("SHIP_TOKEN", "")
    from src import world_api as wa_module
    mock_fetch = AsyncMock(return_value=None)
    wa_module.world_api.get_system = mock_fetch

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        await client.post("/log/ingest", json={"type": "combat", "damage": 100})

    mock_fetch.assert_not_called()
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
pytest tests/test_integration.py -v
```

Expected: FAIL — system change does not yet trigger World API fetch

- [ ] **Step 3: Update /log/ingest in main.py to trigger refresh**

```python
# Update the ingest endpoint in main.py
@app.post("/log/ingest", dependencies=[Depends(require_token)])
async def ingest_log(event: LogEvent):
    log_buffer.add(event.model_dump())
    if event.type == "system_change" and event.system:
        # Fire-and-forget: refresh world data for the new system
        import asyncio
        asyncio.create_task(world_api.get_system(event.system))
    return {"accepted": True}
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
pytest tests/test_integration.py -v
```

Expected: all PASS

- [ ] **Step 5: Run full test suite**

```bash
pytest tests/ -v
```

Expected: all PASS

- [ ] **Step 6: Commit**

```bash
git add main.py tests/test_integration.py
git commit -m "feat: system_change event triggers World API prefetch"
```

---

### Task 11: End-to-end smoke test and service file

**Files:**
- Create: `/etc/systemd/system/ship-ai.service`
- Create: `start.sh`

- [ ] **Step 1: Create start.sh**

```bash
#!/bin/bash
cd /opt/eve-frontier
source .venv/bin/activate
uvicorn main:app --host 0.0.0.0 --port 8745
```

```bash
chmod +x start.sh
```

- [ ] **Step 2: Manual end-to-end smoke test**

```bash
cp .env.example .env
# Edit .env: add real ANTHROPIC_API_KEY, set SHIP_TOKEN
./start.sh
```

In a browser, open `http://localhost:8745/static/index.html`.
Send a message. Verify streamed response appears token by token in the UI.
Check `GET /health` returns `{"status": "ok"}`.

- [ ] **Step 3: Create systemd service (requires root)**

```ini
# /etc/systemd/system/ship-ai.service
[Unit]
Description=EVE Frontier Ship AI Companion
After=network.target

[Service]
Type=simple
WorkingDirectory=/opt/eve-frontier
ExecStart=/opt/eve-frontier/.venv/bin/uvicorn main:app --host 0.0.0.0 --port 8745
EnvironmentFile=/opt/eve-frontier/.env
Restart=on-failure
RestartSec=5

[Install]
WantedBy=multi-user.target
```

```bash
systemctl daemon-reload
systemctl enable ship-ai
systemctl start ship-ai
systemctl status ship-ai
```

Expected: service shows `active (running)`.

- [ ] **Step 4: Final commit**

```bash
git add start.sh
git commit -m "feat: start script and systemd service for ship AI"
```

---

## Notes for Implementer

- **Log regex patterns** in `log-agent/parsers.py` are based on a guessed format. Before running the agent, open a real EVE Frontier gamelog file and adjust the regex patterns to match actual log line format.
- **World API endpoints** (`/v1/system`, `/v1/killmails`) are placeholders — check https://docs.evefrontier.com for real endpoint paths and response shapes, then update `src/world_api.py` accordingly.
- **SHIP_TOKEN** in `.env` must match on both server and log agent. If running locally only (no public port), leave it blank.
- **Log agent runs on Windows.** Install Python on the gaming PC, `pip install -r log-agent/requirements.txt`, copy `.env.example` to `.env`, fill in server URL and token, then `python log_agent.py`.
