# Secure Token Architecture Design

**Date:** 2026-03-17
**Status:** Design specification (pre-implementation)
**Priority:** Post-hackathon (after 2026-03-31)
**Scope:** Redesign API authentication to eliminate hardcoded tokens in client-side code

---

## Problem Statement

**Current state (insecure):**
```
Frontend (browser/overlay)
  ├─ Hardcoded token: const SERVER_TOKEN = "5740edb0..."
  ├─ Token visible in: Browser DevTools, git history, compiled binary
  ├─ Token exposure: Plain text in 4 files
  └─ Security risk: Anyone with token has unlimited API access

Backend (VPS)
  └─ No way to differentiate clients
  └─ No session management
  └─ No token expiration
  └─ No per-user controls
```

**Goals of redesign:**
1. ✅ Remove hardcoded tokens from client-side code
2. ✅ Implement per-session tokens (short-lived, user-specific)
3. ✅ Support multiple client types (browser, overlay, log-agent)
4. ✅ Enable token revocation and expiration
5. ✅ Allow audit logging (who accessed what, when)
6. ✅ Maintain current functionality (no breaking changes)
7. ✅ Keep deployment simple for self-hosted installations

---

## Solution: Session-Based Authentication

### Architecture Overview

```
┌─────────────────────────────────────────────────────────┐
│                    DEPLOYMENT MODEL                     │
└─────────────────────────────────────────────────────────┘

GAMING PC (Chromium in-game browser)
│
├─ Request: GET http://VPS_IP:8745/
│   └─ Server responds: HTML + no token in it
│
├─ Browser calls: POST /auth/session (no auth needed, first call)
│   ├─ Server generates: session_token = random 64-char (expires 24h)
│   └─ Server stores in: {structure_id}/session.json
│
├─ Browser receives: { session_token: "a3f7b8c2...", expires_in: 86400 }
│   └─ Stores in: httpOnly cookie (invisible to JavaScript)
│
└─ Browser sends: Cookie: session_token=a3f7b8c2...
    └─ On every request (automatic, can't be stolen via XSS)

OVERLAY (Windows DLL)
│
├─ At startup: read config/env
│   ├─ Has: SERVER_IP, NOT SERVER_TOKEN
│   └─ Has: STRUCTURE_ID (what structure this overlay belongs to)
│
├─ First chat request:
│   ├─ POST /auth/overlay-session
│   ├─ Payload: { structure_id: "keep-7a", hardware_id: "..." }
│   └─ Server responds: { session_token, expires_in }
│
└─ Store session_token in memory
    └─ Use in every request header: X-Session-Token

LOG AGENT (Windows Python)
│
├─ At startup: read .env.local (not committed to git)
│   ├─ Has: SERVER_IP, SERVER_TOKEN (only here, kept safe)
│   └─ Has: STRUCTURE_ID
│
├─ Authenticate once on startup:
│   ├─ POST /auth/agent-session
│   ├─ Payload: { structure_id, agent_token (from .env.local) }
│   └─ Server responds: { session_token, expires_in }
│
└─ Store session_token in config
    └─ Use in every POST header: X-Session-Token

SERVER (VPS)
│
├─ Receives requests with X-Session-Token header
│   └─ Validates token: exists, not expired, matches structure_id
│
├─ Maintains session store:
│   ├─ data/sessions/ directory
│   ├─ {structure_id}/session_{token}.json
│   └─ Contents: { created_at, expires_at, client_type, client_id }
│
├─ On token expiration:
│   ├─ Delete session file
│   ├─ Client gets 401 Unauthorized
│   └─ Client re-authenticates (automatic retry)
│
└─ Audit log:
    ├─ Log every API call with: timestamp, session_id, structure_id, endpoint
    └─ Enable: "who accessed what, when" forensics
```

---

## Detailed Design

### 1. Session Token Specification

**Format:** 64 character random hex string (256 bits entropy)
```
Example: a3f7b8c2d9e1f4a6b5c8d2e9f1a3b4c5d6e7f8a9b0c1d2e3f4a5b6c7d8e9
```

**Properties:**
- Generated fresh for each client session
- Expires after configurable duration (default: 24 hours for browser, 7 days for agents)
- Can be manually revoked
- Tied to specific structure_id (can't use token from one structure on another)
- Single-use per request is not required (can be reused, unlike CSRF tokens)

**Storage (server-side):**
```
File: data/sessions/{structure_id}/session_{token}.json

{
  "token": "a3f7b8c2...",
  "created_at": "2026-03-17T10:30:00Z",
  "expires_at": "2026-03-18T10:30:00Z",
  "client_type": "browser",  // or "overlay" or "agent"
  "client_id": "gaming-pc-1",
  "last_used": "2026-03-17T10:45:22Z",
  "ip_address": "192.168.1.100",
  "user_agent": "Mozilla/5.0... (Chromium)"
}
```

---

### 2. Three Authentication Flows

#### **Flow 1: In-Game Browser (Least Secure → Session Token)**

**User perspective:**
```
1. User visits: http://192.168.1.100:8745/
2. Page loads: index.html (NO token hardcoded)
3. JavaScript runs: $.ajax("/auth/session", { method: "POST" })
4. Server responds: { session_token: "a3f7b8c2..." }
5. Browser stores: httpOnly cookie (invisible to JavaScript)
6. Browser auto-sends: Cookie header on every request
7. User can now: /chat, /ship-profile, etc. (all protected)
```

**Implementation:**
```python
# main.py - NEW endpoint

@app.post("/auth/session")
async def create_browser_session():
    """
    Create temporary session for in-game browser.

    No authentication needed (in-game browser is already isolated).
    Returns session token in httpOnly cookie.
    """
    session_token = generate_token()  # 64-char random hex

    # Determine structure_id from request context
    # (in-game browser context = current ship's structure)
    structure_id = get_context_structure_id()  # Extract from request

    # Create session file
    session_data = {
        "token": session_token,
        "created_at": now(),
        "expires_at": now() + timedelta(hours=24),
        "client_type": "browser",
        "client_id": request.client.host,  # IP address
        "user_agent": request.headers.get("user-agent", ""),
    }
    save_session(structure_id, session_token, session_data)

    # Return token in httpOnly cookie (cannot be read by JavaScript)
    response = JSONResponse({"status": "authenticated"})
    response.set_cookie(
        "session_token",
        session_token,
        max_age=86400,  # 24 hours
        httponly=True,  # Invisible to JavaScript (XSS-safe)
        secure=False,  # Set to True if HTTPS (http://localhost is exception)
        samesite="Lax"  # CSRF protection
    )
    return response
```

**Browser code (index.html):**
```javascript
// NO hardcoded token
// const SERVER_TOKEN = "5740edb0...";  // DELETE THIS

// On page load
async function initAuth() {
  const response = await fetch('/auth/session', { method: 'POST' });
  // Response includes Set-Cookie header
  // Browser automatically stores cookie
  // No JavaScript access to token!

  // Now use chat/other endpoints
  // Cookie automatically sent on every request
  await sendChat("hello");
}

async function sendChat(message) {
  const response = await fetch('/chat', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    // NO X-Server-Token header needed
    // Cookie sent automatically by browser
    credentials: 'include',  // Include cookies in request
    body: JSON.stringify({ message, history: [] })
  });
  // ...
}
```

---

#### **Flow 2: Overlay DLL (Low Privilege → Session Token)**

**Deployment config:**
```cpp
// overlay_ui/config.h
// NO token hardcoded anymore!
// #define SERVER_TOKEN "5740edb0..."  // DELETE THIS

// Instead, config from .env or command-line:
// OVERLAY_STRUCTURE_ID="keep-7a"
// OVERLAY_SERVER_IP="135.181.95.84:8745"
// OVERLAY_HARDWARE_ID="nvidia-gpu-1"  (unique per gaming PC)
```

**Overlay code (C++):**
```cpp
// On startup
void OverlayInit() {
    // 1. Read config (NOT token)
    std::string server_ip = GetEnvVar("OVERLAY_SERVER_IP");
    std::string structure_id = GetEnvVar("OVERLAY_STRUCTURE_ID");

    // 2. Request session token from server
    HttpResponse resp = http_client.PostJson(
        server_ip + "/auth/overlay-session",
        {
            "structure_id": structure_id,
            "hardware_id": GetHardwareId()
        }
    );

    // 3. Extract session token (lifetime: 7 days)
    session_token = resp["session_token"];

    // 4. Store in memory (NOT in config file)
    g_session_token = session_token;

    // 5. On every chat request, use header:
    // X-Session-Token: a3f7b8c2...
}

void ChatRequest(const std::string& message) {
    http_client.PostJson(
        server_ip + "/chat",
        json{{"message": message}},
        {
            {"X-Session-Token", g_session_token}
        }
    );
}
```

---

#### **Flow 3: Log Agent (Higher Privilege → Session Token)**

**Deployment (Windows .env.local - NEVER committed to git):**
```
# .env.local (on Windows PC only, .gitignore'd)
STRUCTURE_ID=keep-7a
SERVER_URL=http://135.181.95.84:8745

# ONLY place where hard secret is stored:
AGENT_TOKEN=secret-xyz-789  (known only to server + this Windows PC)
```

**Log agent code (Python):**
```python
# log_agent.py

def bootstrap_session():
    """Authenticate once at startup."""
    agent_token = os.getenv("AGENT_TOKEN")
    structure_id = os.getenv("STRUCTURE_ID")

    # Exchange agent_token for session_token
    response = requests.post(
        f"{SERVER_URL}/auth/agent-session",
        json={
            "structure_id": structure_id,
            "agent_token": agent_token,  # Used once
            "hostname": socket.gethostname()
        }
    )

    # Get back: session token + expiry (7 days)
    session_token = response["session_token"]
    expires_in = response["expires_in"]  # 604800 seconds

    # Store in memory (or config for persistence)
    config.session_token = session_token
    config.session_expires = now() + timedelta(seconds=expires_in)

    return session_token

def send_event(event):
    """Send event with session token."""
    headers = {
        "X-Session-Token": config.session_token,
        "Content-Type": "application/json"
    }

    response = requests.post(
        f"{SERVER_URL}/log/ingest",
        json=event,
        headers=headers
    )

    if response.status_code == 401:
        # Token expired, re-authenticate
        bootstrap_session()
        # Retry with new token
        response = requests.post(
            f"{SERVER_URL}/log/ingest",
            json=event,
            headers={"X-Session-Token": config.session_token}
        )

    return response
```

---

### 3. Server-Side Session Management

**New auth module: `src/session_auth.py`**

```python
# src/session_auth.py

import os
import json
from pathlib import Path
from datetime import datetime, timedelta
import secrets

class SessionManager:
    def __init__(self, base_dir: str = "data/sessions"):
        self.base_dir = Path(base_dir)
        self.base_dir.mkdir(parents=True, exist_ok=True)

    def create_session(
        self,
        structure_id: str,
        client_type: str,  # "browser", "overlay", "agent"
        client_id: str = "",
        ttl_hours: int = 24
    ) -> str:
        """Create new session token."""
        token = secrets.token_hex(32)  # 64-char hex

        structure_dir = self.base_dir / structure_id
        structure_dir.mkdir(parents=True, exist_ok=True)

        session_data = {
            "token": token,
            "structure_id": structure_id,
            "client_type": client_type,
            "client_id": client_id,
            "created_at": datetime.utcnow().isoformat() + "Z",
            "expires_at": (datetime.utcnow() + timedelta(hours=ttl_hours)).isoformat() + "Z",
            "last_used": None,
        }

        session_file = structure_dir / f"session_{token}.json"
        session_file.write_text(json.dumps(session_data, indent=2))

        return token

    def validate_session(self, structure_id: str, token: str) -> dict | None:
        """Validate token and return session data."""
        session_file = self.base_dir / structure_id / f"session_{token}.json"

        if not session_file.exists():
            return None

        with open(session_file) as f:
            session = json.load(f)

        expires_at = datetime.fromisoformat(session["expires_at"].rstrip("Z"))
        if datetime.utcnow() > expires_at:
            # Token expired
            session_file.unlink()  # Delete expired session
            return None

        # Update last_used
        session["last_used"] = datetime.utcnow().isoformat() + "Z"
        session_file.write_text(json.dumps(session, indent=2))

        return session

    def revoke_session(self, structure_id: str, token: str):
        """Manually revoke session token."""
        session_file = self.base_dir / structure_id / f"session_{token}.json"
        if session_file.exists():
            session_file.unlink()

# Global instance
session_manager = SessionManager()


# Dependency for FastAPI
def require_session(
    x_session_token: str = Header(default=""),
    request: Request = None
) -> dict:
    """FastAPI dependency - validates session token."""
    if not x_session_token:
        raise HTTPException(status_code=401, detail="Missing session token")

    # Extract structure_id from request context
    structure_id = request.scope.get("structure_id", "")

    session = session_manager.validate_session(structure_id, x_session_token)
    if not session:
        raise HTTPException(status_code=401, detail="Invalid or expired token")

    return session
```

---

### 4. Updated Endpoints

**Old (insecure):**
```python
@app.post("/chat")
async def chat(req: ChatRequest):
    # Anyone with SERVER_TOKEN can call this
    # Token is permanent, no expiration, no per-user controls
```

**New (secure):**
```python
@app.post("/chat")
async def chat(
    req: ChatRequest,
    session: dict = Depends(require_session)
):
    """Chat endpoint with session-based auth."""
    # session = { token, structure_id, client_type, created_at, expires_at }
    # Token is temporary (24h), per-session, per-structure
    # Can audit: who (client_type), when, what structure

    # Log access
    audit_log.write({
        "timestamp": now(),
        "endpoint": "/chat",
        "structure_id": session["structure_id"],
        "client_type": session["client_type"],
        "session_token": session["token"][:8] + "...",  # Don't log full token
    })

    # Normal logic...
```

---

### 5. Deployment Implications

#### **For VPS Administrator (Markús):**

**Setup (one-time):**
```bash
# Create sessions directory
mkdir -p /opt/eve-frontier/data/sessions

# No more hardcoding tokens in .env!
# .env only contains server config, not auth secrets

# Optional: configure session TTLs
SESSION_BROWSER_TTL_HOURS=24
SESSION_OVERLAY_TTL_DAYS=7
SESSION_AGENT_TTL_DAYS=30
```

**Maintenance:**
```bash
# Cleanup expired sessions (cron job)
0 3 * * * find /opt/eve-frontier/data/sessions -name "*.json" -mtime +30 -delete

# Audit logs
tail -f /var/log/openclaw/audit.log

# Revoke specific session (manual intervention)
rm /opt/eve-frontier/data/sessions/{structure_id}/session_{token}.json
```

#### **For End-User Installing on Own Server:**

**Before (complex):**
```bash
# User must:
1. Generate SERVER_TOKEN manually
2. Update 4 files with token (index.html, debug.html, structure-debug.html, .env)
3. Rebuild overlay.dll with token (Windows)
4. Redeploy everything
5. Hope they didn't expose token in git
```

**After (simpler):**
```bash
# User does:
1. Clone repo (no token in any file)
2. Edit .env with server IP (no token)
3. Deploy HTML files (no token)
4. Build overlay (no token in code)
5. On first run: browser/overlay auto-generate sessions

# Result: Much simpler, more secure by default
```

---

### 6. Migration Path (Backwards Compatibility)

**Phase 1: Deploy alongside existing auth**
```python
# Accept BOTH old (X-Server-Token) AND new (X-Session-Token) headers
# Prioritize session token if both present

@app.get("/chat")
async def chat(
    req: ChatRequest,
    session: dict = Depends(require_session_optional),  # New
    x_server_token: str = Header(default="")  # Old
):
    if session:
        # Use session-based auth
    elif x_server_token:
        # Use old token auth (emit deprecation warning)
        log.warning("Old X-Server-Token auth used - please migrate to sessions")
    else:
        raise HTTPException(401)
```

**Phase 2: Deprecation period (1-2 months)**
- Log warnings when old auth is used
- Document migration guide
- Support both simultaneously

**Phase 3: Remove old auth**
- Drop X-Server-Token support
- Require X-Session-Token only

---

## Implementation Plan

### **Pre-Hackathon (Now)**
- ✅ Design complete (this document)
- ✅ Get buy-in (this review with Markús)

### **Post-Hackathon (April 2026)**

**Week 1:**
- [ ] Create `src/session_auth.py` with SessionManager class
- [ ] Add `/auth/session`, `/auth/overlay-session`, `/auth/agent-session` endpoints
- [ ] Update `require_session` dependency
- [ ] Add session cleanup cron job

**Week 2:**
- [ ] Update `static/index.html` to use `/auth/session`
- [ ] Update `static/debug.html` to use `/auth/session`
- [ ] Update `static/structure-debug.html` to use `/auth/session`
- [ ] Remove hardcoded SERVER_TOKEN from all files

**Week 3:**
- [ ] Update `log-agent/log_agent.py` to use `/auth/agent-session`
- [ ] Remove hardcoded SERVER_TOKEN from .env.example (keep AGENT_TOKEN only)
- [ ] Create `.env.local.example` template for end-users
- [ ] Add `.env.local` to .gitignore

**Week 4:**
- [ ] Update `overlay_ui/config.h` to remove hardcoded token
- [ ] Modify overlay to use `/auth/overlay-session`
- [ ] Document overlay deployment (config.h has no secret anymore)
- [ ] Add tests for session auth flows

**Week 5:**
- [ ] Backward compatibility: accept both old and new auth (deprecation warning)
- [ ] Write migration guide for existing installations
- [ ] Update all documentation

**Week 6:**
- [ ] Integration testing across all 3 client types
- [ ] Security review (test exposure, token revocation, expiry)
- [ ] Performance testing (session file I/O overhead)

**Week 7:**
- [ ] Optional: Migrate session storage from JSON files to SQLite (performance improvement)
- [ ] Optional: Add session dashboard (list active sessions, revoke manually)

---

## Security Checklist

- [ ] Session tokens are 256-bit random (64 hex chars)
- [ ] Tokens cannot be guessed or predicted
- [ ] Tokens expire (24h browser, 7d overlay, 30d agent)
- [ ] Expired tokens are automatically deleted
- [ ] Tokens are NOT logged in plain text (only first 8 chars in audit log)
- [ ] Session data includes structure_id (can't use token from one structure on another)
- [ ] Browser tokens are httpOnly cookies (invisible to JavaScript)
- [ ] All requests validate token before processing
- [ ] Token validation checks both: token exists, token not expired, token matches structure_id
- [ ] Audit logs capture: who (client_type), when, what endpoint, what structure
- [ ] No hardcoded secrets in any client-side file
- [ ] AGENT_TOKEN only stored in .env.local (not committed to git)
- [ ] Session files are user-readable only (chmod 600 if on multi-user system)

---

## Performance Considerations

**Current (hardcoded token):**
- ✅ Zero overhead per request
- ❌ Permanent exposure

**New (session-based):**
- ⚠️ Slight overhead: load + validate JSON file per request
- ✅ Sessions expire (auto-cleanup)
- ✅ Can audit all access

**Optimization options (future):**
1. Cache sessions in memory (with TTL)
2. Move to SQLite (faster than JSON files)
3. Use Redis (if deploying at scale)

**For current single-user VPS:** JSON files are fine

---

## FAQ

**Q: What if overlay is offline when token expires?**
A: Overlay stores token in memory. If offline for 7+ days and token expires, overlay reconnects and auto-requests new token. User doesn't need to do anything.

**Q: What if user has multiple gaming PCs?**
A: Each gets its own session token on first connect. Sessions are independent. User can revoke any session manually if a PC is compromised.

**Q: How do I revoke a specific session?**
A: Delete the session file:
```bash
rm /opt/eve-frontier/data/sessions/{structure_id}/session_{token}.json
```

**Q: Can I extend token expiry?**
A: Yes, configure TTL per client type:
```python
SESSION_BROWSER_TTL_HOURS = 24
SESSION_OVERLAY_TTL_DAYS = 7
SESSION_AGENT_TTL_DAYS = 30
```

**Q: Does this change the API for developers?**
A: For web clients: yes (auth endpoint required). For server API: no (token header is same concept, just different auth flow).

---

## Summary

**Current architecture:** Hardcoded tokens → Exposed in 4 places → No expiration → No per-session controls

**New architecture:** Dynamic sessions → No hardcoding → Automatic expiration → Per-client audit trail → Revocable → Secure by default

**Implementation timeline:** ~4-5 weeks post-hackathon

**Benefit:** From "security theater" (rotate tokens) to "real security" (proper auth design)

---

**Ready to implement post-hackathon? This is the blueprint.**
