# EVE Frontier Codebase Implementation Plan

**Date:** 2026-03-17
**Based on:** Complete investigation of 13 issues across all 7 documentation files
**Status:** Ready for subagent-driven-development execution
**Deadline:** Hackathon 2026-03-31 (14 days)

---

## Executive Summary

**Total tasks:** 13 investigation findings → 11 implementation tasks
**Critical:** 3 security issues
**High:** 2 functional issues (broken features)
**Medium:** 4 code quality / cleanup items
**Low:** 2 documentation updates

**Blockers:** SEC-1 requires Markús approval (production token rotation)

---

## Task Priority Matrix

```
Severity × Impact × Effort

🔴 CRITICAL
├─ SEC-1: Token rotation (BLOCKED — needs Markús)
├─ SEC-2: Fix EventSource auth (HIGH impact, LOW effort) ✓
└─ SEC-3: Address validation (HIGH impact, LOW effort) ✓

🟠 HIGH
├─ FIX-1: index.html broken chat (FUNCTIONAL BUG)
└─ FIX-2: Implement SSE keep-alive for /logs/stream (CONSISTENCY)

🟡 MEDIUM
├─ CODE-1: Code quality improvements (imports, errors, locking, naming)
├─ CODE-2: Dead code cleanup (3 functions, 1 unused var, 1 config)
└─ DOC-1: Documentation fixes (get_summary, missing endpoints)

🟢 LOW
└─ DOC-2: Add missing endpoint documentation
```

---

## Execution Order

**Week 1 (Days 1-3): Security & Critical Bugs**
- Task 1: SEC-2 fix (EventSource auth) — HIGH impact, needed for index.html to work
- Task 2: SEC-3 fix (Address validation) — prevent path traversal
- Task 3: Awaiting Markús approval on SEC-1 (token rotation)

**Week 2 (Days 4-7): Functional Fixes & Code Quality**
- Task 4: DOC-1 fix (get_summary return type) — docs only
- Task 5: FIX-2 (SSE keep-alive for /logs/stream) — consistency
- Task 6: CODE-1 (imports, error messages, file locking, naming)

**Week 3 (Days 8-10): Cleanup & Documentation**
- Task 7: CODE-2 (dead code removal)
- Task 8: DOC-2 (missing endpoint docs)

**Week 4 (Days 11-14): Testing & Verification**
- Full integration testing
- Manual smoke tests
- PR review & merge

---

## DETAILED TASK SPECIFICATIONS

### 🔴 CRITICAL TASKS

---

### TASK 1: Fix EventSource Auth Bypass in index.html (SEC-2)

**Status:** Ready to implement
**Severity:** CRITICAL — Ship terminal chat is non-functional
**Effort:** LOW
**Files affected:** 1 (main.py), 1 (index.html)
**Risk:** LOW (auth improvement)

**Problem:**
- `index.html` uses EventSource with query param: `new EventSource('/chat?token=...')`
- EventSource API cannot send custom headers
- `require_token()` only checks `X-Server-Token` header
- Result: Auth fails immediately, `/chat` returns 403

**Solution (Choose One):**

**Option A (Recommended):** Modify `require_token()` to accept query param fallback
- File: `src/auth.py` lines 4-9
- Add `token: str = Query(default="")` parameter
- Check header first, fall back to query param
- Maintains header-priority for fetch() clients

**Option B:** Switch index.html to fetch() with manual SSE parsing
- File: `static/index.html` lines 99-101
- Replace EventSource with fetch() + response.body.getReader()
- Same pattern as debug.html (working reference implementation)
- More explicit control, better error handling

**Specification:**
- If Option A: Add query param fallback to `require_token()`, verify both header and query work
- If Option B: Replace EventSource with fetch() streaming, maintain identical behavior
- Add test: verify `/chat` works with both header and query param auth
- Verify: index.html chat panel functions end-to-end with overlay

**Acceptance criteria:**
- [ ] `/chat` endpoint accepts token via header (existing) AND query param (new)
- [ ] index.html EventSource connects successfully
- [ ] Chat messages stream without 403 errors
- [ ] Test coverage for both auth methods
- [ ] No CORS issues or security regressions

---

### TASK 2: Add Address Format Validation (SEC-3)

**Status:** Ready to implement
**Severity:** CRITICAL — Path traversal risk on Windows
**Effort:** LOW
**Files affected:** 2 (main.py request models, memory_store.py)
**Risk:** LOW (validation only, defense in depth)

**Problem:**
- Sui addresses received from `/auth/verify` and `/auth/deal/claim` endpoints
- Pydantic models have NO format validation
- `_pilot_path()` sanitization only removes `/` and `..`
- Missing: backslash `\`, colon `:`, control chars, format validation
- Windows path escape possible: `0x123\..\..\windows\system32`

**Solution (TWO PARTS):**

**Part 1: Pydantic Validator (API boundary)**
- File: `main.py`
- Add to `VerifyRequest` class (line ~369)
- Add to `DealClaimRequest` class (line ~383)
- Validator: Address must be `0x` + exactly 64 hex characters
- Format: `^0x[0-9a-fA-F]{64}$`

```python
@field_validator('address')
@classmethod
def validate_address(cls, v: str) -> str:
    if not v or not v.startswith('0x') or len(v) != 66:
        raise ValueError('address must be 0x + 64 hex chars')
    try:
        int(v[2:], 16)
    except ValueError:
        raise ValueError('invalid hex in address')
    return v.lower()
```

**Part 2: Hardened _pilot_path() (defense in depth)**
- File: `src/memory_store.py` lines 38-41
- Validate address format before sanitization
- Remove: `\`, `:`, `.`, `;`, `|`, `?`, `*`, control chars
- Verify: address matches expected format

```python
def _pilot_path(self, address: str) -> str:
    # Format validation
    if not isinstance(address, str) or not address.startswith('0x') or len(address) != 66:
        raise ValueError(f'Invalid address format: {address!r}')

    # Comprehensive sanitization
    safe = address.lower()
    dangerous_chars = '/\\:.;|?*\x00\x01\x02'  # Path seps, special chars, control
    safe = ''.join(c for c in safe if c not in dangerous_chars)

    return os.path.join(self._pilots_dir(), f"{safe}.json")
```

**Specification:**
- Address format: `0x` + 64 hex chars (case-insensitive)
- Validation happens at Pydantic layer (400 on invalid input)
- Additional validation in `_pilot_path()` for defense in depth
- Test with valid/invalid addresses, Windows path escape attempts

**Acceptance criteria:**
- [ ] Pydantic validator rejects non-Sui addresses (400 Bad Request)
- [ ] Valid addresses pass through cleanly
- [ ] `_pilot_path()` validates format and sanitizes thoroughly
- [ ] No path traversal possible with malicious input
- [ ] All existing tests pass
- [ ] New tests: path traversal attempts (Windows + Linux)

---

### TASK 3: Rotate Production Token (SEC-1)

**Status:** BLOCKED — Requires Markús approval
**Severity:** CRITICAL — Active token exposed in source
**Effort:** MEDIUM (requires coordination)
**Files affected:** 4 (3 HTML, 1 C++ config)
**Risk:** HIGH if done wrong (service disruption); MEDIUM if skipped (security)

**Problem:**
- Token `5740edb0fb25a051db4a932c3622bd69ce47d487bc501f2bde4cb7e19907c454` is active production token
- Hardcoded in: `index.html:63`, `debug.html:237`, `structure-debug.html:207`, `overlay_ui/config.h:6`
- Visible in: git history, browser DevTools, compiled overlay binary
- No rotation mechanism exists

**Solution:**
1. **Approval:** Get Markús sign-off (security risk vs service disruption tradeoff)
2. **Generate new token:** `openssl rand -hex 32` (64-char hex)
3. **Update atomically:**
   - `.env` file (1 line)
   - Rebuild `overlay.dll` on Windows with new token in `config.h`
   - Update 3 HTML files (1 line each)
   - Restart server
4. **Deployment order:**
   - Stage 1: Update source files (create PR)
   - Stage 2: Rebuild overlay on Windows
   - Stage 3: Deploy overlay.dll to gaming PC
   - Stage 4: Merge & restart server (all in one atomic operation)

**Specification:**
- New token format: 64-char hex string (0-9a-f lowercase)
- Update locations: `.env`, `overlay_ui/config.h`, 3 HTML files
- No interim exposure: all clients must be updated before rolling out
- Backwards compat: none (token rotation breaks old clients)

**Acceptance criteria:**
- [ ] Markús approves token rotation
- [ ] New token generated and documented (date, reason)
- [ ] All 4 hardcoded instances updated
- [ ] Overlay rebuilt with new token
- [ ] Server restarts and new token validated
- [ ] Old token confirmed invalid
- [ ] No breaking changes to other services

**Note:** This task is BLOCKED until Markús approves. Once approved, coordinate overlay rebuild with Windows gaming PC.

---

### 🟠 HIGH-PRIORITY TASKS

---

### TASK 4: Fix index.html Broken Chat Feature (FIX-1)

**Depends on:** TASK 1 (SEC-2: EventSource auth fix)

**Status:** Blocked by Task 1
**Severity:** HIGH — Feature is currently non-functional
**Effort:** LOW (once auth is fixed)
**Files affected:** 1 (index.html, if Option B chosen in Task 1)
**Risk:** LOW

**Problem:**
- index.html attempts to use EventSource for `/chat` SSE streaming
- Auth fails due to query param token not being validated (TASK 1)
- Ship terminal chat panel shows no messages from Claude

**Solution:**
- Complete TASK 1 first (fix auth)
- If Option B chosen: rewrite EventSource to fetch() streaming (already done in TASK 1)
- If Option A chosen: EventSource will work once auth validates query param

**Specification:**
- index.html must successfully connect to `/chat` endpoint
- Messages must stream in real-time
- Errors must be displayed to user
- Connection recovery on disconnect
- No security issues (token handled securely per TASK 1)

**Acceptance criteria:**
- [ ] index.html chat connects without 403 errors
- [ ] Messages stream from Claude API
- [ ] User can type and send messages
- [ ] Connection handles interruptions gracefully
- [ ] Works in in-game Chromium 122 browser
- [ ] Overlay companion panel mirrors chat

---

### TASK 5: Add SSE Keep-Alive to /logs/stream (FIX-2)

**Status:** Ready to implement
**Severity:** HIGH (consistency, reliability)
**Effort:** LOW
**Files affected:** 1 (main.py)
**Risk:** LOW (SSE improvement)

**Problem:**
- `/logs/stream` endpoint (line 319) does NOT send keep-alive
- Other SSE endpoints (`/chat`, `/structure-debug/chat`, `/structure-chat`) DO send keep-alive
- Inconsistency can cause connection timeouts on proxy/firewall
- Documented as "intentionally missing" but should be consistent

**Solution:**
- Add `yield ": keep-alive\n\n"` at start of `/logs/stream` generator (before first log)
- Match pattern used in other SSE endpoints

```python
async def logs_stream():
    q = await get_log_queue()
    try:
        yield ": keep-alive\n\n"  # ADD THIS LINE
        while True:
            line = await q.get()
            yield f"data: {json.dumps({'line': line})}\n\n"
    except asyncio.CancelledError:
        pass
```

**Specification:**
- Keep-alive sent once at connection start (not periodic)
- Prevents firewall/proxy timeout on idle connections
- Matches pattern of other SSE endpoints
- No performance impact (one-time overhead)

**Acceptance criteria:**
- [ ] `/logs/stream` generator yields keep-alive first
- [ ] Tests verify keep-alive is sent
- [ ] Connection stability improves (no timeout during idle)
- [ ] Consistency with other SSE endpoints

---

### 🟡 MEDIUM-PRIORITY TASKS

---

### TASK 6: Code Quality Improvements (CODE-1)

**Status:** Ready to implement
**Severity:** MEDIUM (maintainability, clarity)
**Effort:** LOW
**Files affected:** 2 (main.py, ship_profile.py)
**Risk:** LOW

**Part 1: Move repeated imports to module level (QUAL-1)**

**File:** `main.py`
**Current:** 5 inline imports of `asdict` (lines 168, 221, 685, 734, 743)
**Solution:** Move to module-level imports

```python
# Add to top of main.py (near line 6):
from dataclasses import asdict, fields as dc_fields

# Remove all 5 inline imports (lines 168, 221, 685, 734, 743)
```

**Part 2: Improve error messages in SSE endpoints (QUAL-2)**

**File:** `main.py`
**Current:** Generic "Stream interrupted." (lines 671, 721, 1223)
**Solution:** Include exception type name

```python
# Line 671: /chat endpoint
except Exception as e:
    yield f"data: {json.dumps({'error': f'Stream error: {type(e).__name__}'})}\n\n"

# Line 721: /structure-debug/chat endpoint
except Exception as e:
    yield f"data: {json.dumps({'error': f'Stream error: {type(e).__name__}'})}\n\n"

# Line 1223: /structure-chat endpoint
except Exception as e:
    yield f"data: {json.dumps({'error': f'Stream error: {type(e).__name__}'})}\n\n"
```

**Part 3: Add file locking to alert saving (QUAL-3)**

**File:** `src/structure_profile.py` lines 92-104
**Current:** No locking; concurrent writes possible
**Solution:** Add `fcntl` file locking

```python
import fcntl
import os

def save_profile(profile: StructureProfile, base_dir: str = _DEFAULT_BASE_DIR):
    import datetime
    path = profile_path(profile.structure_id, base_dir)
    try:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        if not profile.created_at:
            profile.created_at = datetime.datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")

        # File locking for concurrent access safety
        with open(path, "w") as f:
            fcntl.flock(f.fileno(), fcntl.LOCK_EX)  # Exclusive lock
            try:
                json.dump(asdict(profile), f, indent=2)
            finally:
                fcntl.flock(f.fileno(), fcntl.LOCK_UN)  # Unlock
    except ValueError:
        raise
    except Exception as e:
        log.warning("Failed to save structure profile %s: %s", profile.structure_id, e)
```

**Part 4: Rename ambiguous parameter (QUAL-4)**

**File:** `src/ship_profile.py` line 84
**Current:** `def jump_range_at_temp(self, temp: float)`
**Solution:** Rename `temp` → `safe_jump_temp`

```python
def jump_range_at_temp(self, safe_jump_temp: float) -> float:
    """Jump range in LY at a given safe_jump_temp (system ambient temperature)."""
    if safe_jump_temp >= NO_JUMP_TEMP:
        return 0.0
    c_eff = self.specific_heat * (1.0 + self.adaptive_level * 0.02)
    return ((T_MAX - safe_jump_temp) * c_eff * self.hull_mass) / (HEAT_CONSTANT * self._current_mass)
```

**Specification:**
- Move 5 duplicate imports to module level (no circular dependencies)
- Enhance 3 error messages with exception type (helps debugging)
- Add fcntl file locking to profile saving (prevents race conditions)
- Rename parameter for clarity (improves code readability)

**Acceptance criteria:**
- [ ] No inline imports of `asdict` remain
- [ ] Error messages include exception type
- [ ] File locking prevents concurrent write corruption
- [ ] Parameter name matches its semantic meaning
- [ ] All tests pass
- [ ] No performance regression

---

### TASK 7: Clean Up Dead Code (CODE-2)

**Status:** Ready to implement
**Severity:** MEDIUM (maintenance, code clarity)
**Effort:** LOW
**Files affected:** 4 (ssu_poller.py, world_api.py, memory_store.py, debug.html, .env.example)
**Risk:** LOW (verified zero callers)

**Part 1: Delete `_extract_fuel_pct()` function**

**File:** `src/ssu_poller.py` lines 217-234
**Status:** Marked deprecated, zero callers, no tests
**Action:** Delete entire function

**Part 2: Delete `get_system_by_id()` function**

**File:** `src/world_api.py` line 243
**Status:** Zero callers in production, misleading test name
**Action:** Delete function; remove misleading test name from `test_galaxy_db.py` line 22

**Part 3: Delete `format_pilot_line()` method**

**File:** `src/memory_store.py` lines 197-209
**Status:** Abandoned feature, zero callers, no tests
**Action:** Delete entire method; update docs if it's mentioned

**Part 4: Delete unused variable**

**File:** `static/debug.html` line 239
**Status:** `let debugTimer = null;` declared but never used
**Action:** Delete the line

**Part 5: Delete unused config variable**

**File:** `.env.example` line 7
**Status:** `NOVA_ACCESS_REGISTRY_PACKAGE=0x0` never loaded
**Action:** Delete the line; add comment explaining old config

**Specification:**
- Verify zero references for each item (grep results from investigation)
- Ensure no tests depend on deleted code
- Update documentation if functions are mentioned
- Preserve backward compatibility for `.env` (config is not used at runtime)

**Acceptance criteria:**
- [ ] All 4 dead functions removed
- [ ] All 2 unused variables/configs removed
- [ ] All tests pass (no new failures)
- [ ] Grep confirms zero references to deleted code
- [ ] Documentation updated if needed
- [ ] No breaking changes

---

### 🟢 LOW-PRIORITY TASKS

---

### TASK 8: Fix Documentation (DOC-1 + DOC-2)

**Status:** Ready to implement
**Severity:** LOW (documentation accuracy)
**Effort:** LOW
**Files affected:** 2 (structure-ai.md, ship-ai.md, ops.md)
**Risk:** NONE (docs only)

**Part 1: Fix get_summary() return type (DOC-1)**

**File:** `docs/ref/structure-ai.md` line 283
**Current:** Claims `get_summary() → str`
**Actual:** Returns `dict` with keys `{"last_updated": str|None, "text": str}`
**Fix:**

```markdown
| Method | Behavior |
|--------|----------|
| `get_summary() → dict` | Returns `{"last_updated": ISO8601 timestamp or None, "text": str}`. Text is summary content, empty string if missing. |
```

**Part 2: Clarify SSE keep-alive in ops.md (DOC-2a)**

**File:** `docs/ref/ops.md` line 116
**Current:** Claims keep-alive only in "three `event_stream()` generators"
**Problem:** 4 SSE endpoints total; `/logs/stream` uses `generate()` instead
**Fix:** Clarify after TASK 5 adds keep-alive

```markdown
| SSE keep-alive | All four SSE endpoints (`/chat`, `/structure-debug/chat`, `/structure-chat`, `/logs/stream`) yield `: keep-alive\n\n` once at connection start. |
```

**Part 3: Add missing endpoints to ship-ai.md (DOC-2b)**

**File:** `docs/ref/ship-ai.md` endpoint table (lines 15-31)
**Current:** Missing `/logs/stream` and `/route/clear`
**Fix:** Add rows to endpoint table

```markdown
| Endpoint | Method | Purpose | Auth |
|----------|--------|---------|------|
| `/logs/stream` | GET | SSE stream of server logs; for debugging | Token |
| `/route/clear` | POST | Clear active route | Token |
```

**Specification:**
- Update structure-ai.md to show actual return type
- Clarify ops.md SSE coverage after Task 5
- Add missing endpoint documentation to ship-ai.md

**Acceptance criteria:**
- [ ] structure-ai.md documents correct return type
- [ ] ops.md SSE documentation is accurate and complete
- [ ] ship-ai.md endpoint table includes all public endpoints
- [ ] Examples match actual behavior
- [ ] No broken links or references

---

## Task Dependencies

```
SEC-1 (Blocked)          [Awaiting Markús]
├─ FIX-1 (Fix index.html chat) [Depends on SEC-2]
│  └─ SEC-2 (Fix EventSource auth) ✓ Ready
│
SEC-3 (Path validation) ✓ Ready
QUAL-1,2,3,4 (Code improvements) ✓ Ready (QUAL-3 suggests adding file locking)
CODE-2 (Dead code cleanup) ✓ Ready
FIX-2 (SSE keep-alive) ✓ Ready
DOC-1,2 (Documentation) ✓ Ready (DOC-2a depends on FIX-2 completion)
```

**Execution Path (no blocking):**
1. Start: SEC-2, SEC-3, CODE-1, CODE-2, FIX-2, DOC-1 (parallel)
2. Then: FIX-1 (depends on SEC-2)
3. Then: DOC-2 finalization (after FIX-2 confirmed)
4. Blocked: SEC-1 (awaiting approval)

---

## Testing Strategy

**Unit Tests:**
- Add tests for address validation (Pydantic + _pilot_path)
- Verify dead code removal doesn't break imports
- Test file locking under concurrent writes
- Test ErrorSource auth with both header and query param

**Integration Tests:**
- End-to-end chat with fixed auth
- Keep-alive behavior on /logs/stream
- Profile saving under concurrent requests
- Path traversal attempts (security regression)

**Manual/Smoke Tests:**
- In-game browser chat (index.html)
- Debug console (debug.html)
- Structure debug panel (structure-debug.html)
- Overlay companion panel
- Windows gaming PC deployment (if on Windows)

---

## Risk Assessment

| Task | Risk | Mitigation |
|------|------|-----------|
| SEC-2 (EventSource auth) | Low | Add tests for both auth methods |
| SEC-3 (Address validation) | Low | Defense in depth (Pydantic + _pilot_path) |
| SEC-1 (Token rotation) | High | Coordinate with Markús; atomic deployment |
| FIX-1 (Chat fix) | Low | Depends on SEC-2; test end-to-end |
| CODE-1 (Refactoring) | Low | No logic changes; only structure/messages |
| CODE-2 (Dead code) | Low | Verified zero references; test suite checks |
| FIX-2 (Keep-alive) | Low | Single line change; backward compatible |
| DOC-1,2 (Docs) | None | Documentation only |

---

## Success Criteria

- [ ] All 3 critical security issues addressed (SEC-1 pending approval)
- [ ] index.html chat functional end-to-end
- [ ] Zero dead code references in codebase
- [ ] All tests pass (unit + integration)
- [ ] Code review approved (no security regressions)
- [ ] Documentation accurate and complete
- [ ] Manual smoke tests pass (all 4 UI endpoints working)
- [ ] Ready for hackathon deployment (2026-03-31)

---

## Notes

**For Markús:**
- SEC-1 requires your explicit approval before execution
- Token rotation impacts all clients (overlay, web UIs, log agent)
- Consider scheduling during low-activity window
- New token must be generated securely and not logged

**For Subagent Execution:**
- Use subagent-driven-development workflow (implementer → spec reviewer → quality reviewer)
- Each task should be self-contained and testable
- Tests must pass 100% before marking complete
- Code review gate before merge

---

**Ready for execution. Awaiting Markús approval for SEC-1; can proceed with all others in parallel.**
