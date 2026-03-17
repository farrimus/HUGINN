# Security Review & Token Rotation Approval Request

**To:** Markús Þór (@markussimo1)
**From:** Claude Code audit & investigation
**Date:** 2026-03-17
**Deadline:** 2026-03-31 (hackathon)

---

## Executive Summary

Comprehensive codebase audit (7 docs, 13 investigations) identified **3 critical security issues**. Two are ready to fix immediately. One requires your explicit approval.

**SEC-1: Production Token Rotation** — The active API token is hardcoded in 4 source files and visible in git/browser DevTools. Rotation requires coordination and service deployment. **Awaiting your decision.**

---

## Critical Findings

### 1️⃣ SEC-2: EventSource Auth Bypass (READY TO FIX)

**Status:** ✅ Ready for immediate implementation
**Impact:** Ship terminal chat (index.html) is currently non-functional
**Fix:** Modify `/chat` endpoint auth to accept query param OR switch to fetch() streaming
**Effort:** 1-2 hours
**Risk:** Low (auth improvement, adds flexibility)

**Approval:** Not needed (standard security improvement)

---

### 2️⃣ SEC-3: Address Validation Missing (READY TO FIX)

**Status:** ✅ Ready for immediate implementation
**Impact:** Path traversal risk on Windows systems
**Fix:** Add Pydantic validator for Sui address format + hardened sanitization
**Effort:** 1-2 hours
**Risk:** Low (validation-only, defense in depth)

**Approval:** Not needed (standard security hardening)

---

### 3️⃣ SEC-1: Hardcoded Production Token (REQUIRES YOUR DECISION)

**Status:** ⚠️ Blocked pending approval
**Severity:** 🔴 CRITICAL
**Impact:** Active production token exposed in source code

#### Current State

| Item | Value |
|------|-------|
| **Token** | `5740edb0fb25a051db4a932c3622bd69ce47d487bc501f2bde4cb7e19907c454` |
| **Locations** | 4 files (3 HTML, 1 C++ header) |
| **Active?** | **YES** — matches `.env` production token |
| **Visible in** | Git history, browser DevTools, compiled overlay binary |
| **Rotation mechanism** | None exists |
| **Clients affected** | Overlay DLL, web UIs, log agent (Windows PC) |

#### Files Containing Token

1. `/opt/eve-frontier/static/index.html` line 63
2. `/opt/eve-frontier/static/debug.html` line 237
3. `/opt/eve-frontier/static/structure-debug.html` line 207
4. `/opt/eve-frontier/overlay/overlay_ui/config.h` line 6

#### Exposure Risk

**If token is leaked:**
- Full API access to ship AI system (route planning, logs, chat)
- Access to player structure data
- No expiration — permanent access
- Attacker could impersonate legitimate clients

**Reverse engineering risk:**
- overlay.dll is reverse-engineerable (binary analysis tools)
- HTML files are plaintext (browser DevTools)
- Git history is searchable (public/private repo exposure)

#### Rotation Complexity

Rotation requires coordinating across multiple systems:

1. **Generate new token** (simple: `openssl rand -hex 32`)
2. **Update source files** (5 lines):
   - `.env`
   - `overlay_ui/config.h`
   - 3 HTML files
3. **Rebuild overlay.dll** on Windows gaming PC
4. **Deploy overlay** to running game instance
5. **Restart server** (all updates must be atomic — clients can't have mixed old/new tokens)

**Deployment window:** 15-30 minutes of coordinated changes

#### Decision Matrix

| Option | Security | Service Impact | Effort | Recommendation |
|--------|----------|----------------|--------|---|
| **Rotate now** | ✅ Fixes exposure | 30min downtime | Medium | **Best** — before public exposure |
| **Rotate later** | ⚠️ Risk remains | 30min downtime | Medium | **Risky** — token stays exposed |
| **Don't rotate** | ❌ Risk remains | None | Zero | **Not recommended** — active token in git |

---

## What We Need From You

### Decision 1: Approve SEC-1 Token Rotation?

**[ ] YES — Rotate the token**
- Proceed with all implementation tasks (8 total)
- Coordinate overlay rebuild + deployment
- Schedule maintenance window

**[ ] NO — Don't rotate; document risk**
- Still proceed with SEC-2, SEC-3, and other tasks
- Acknowledge token exposure remains
- Note: Will need to rotate before public deployment

### Decision 2: When to Execute?

If you approve rotation:

**Option A:** Rotate now (before other tasks)
- Generate new token → push to git
- Rebuild overlay on Windows
- Deploy + restart server
- Then run subagent-driven-development for all 8 tasks

**Option B:** Schedule rotation separately
- Run 7 other tasks first (non-blocking)
- Schedule token rotation window later
- Can be coordinated independently

---

## What Happens Next

**Once you approve:**

1. I dispatch subagent-driven-development with 8 implementation tasks:
   - SEC-2 (fix EventSource auth)
   - SEC-3 (add address validation)
   - CODE-1 (code quality refactor)
   - CODE-2 (dead code cleanup)
   - FIX-2 (SSE keep-alive)
   - DOC-1 (documentation fix)
   - DOC-2 (missing endpoint docs)
   - SEC-1 (token rotation, if approved)

2. Each task:
   - Implementer subagent (writes code)
   - Spec compliance review
   - Code quality review
   - Automated tests
   - Commit + PR

3. Final code review gate before merge

4. Target completion: 2026-03-24 (1 week before hackathon deadline)

---

## Investigation Findings Summary

All 13 issues investigated, categorized:

- **3 Critical (security):** SEC-1, SEC-2, SEC-3
- **2 High (functional):** FIX-1 (index.html chat), FIX-2 (SSE keep-alive)
- **4 Medium (code quality):** CODE-1 refactoring, CODE-2 cleanup
- **4 Low (documentation):** DOC-1, DOC-2, plus cleanup notes

**Full details:** `/opt/eve-frontier/IMPLEMENTATION_PLAN.md`

---

## Your Options

**RESPOND WITH:**

```
Decision on SEC-1: [YES / NO]
Schedule: [NOW / LATER / OTHER]
Additional notes: [if any]
```

Once confirmed, I'll:
1. Lock in the execution plan
2. Dispatch all subagents
3. Track progress to completion
4. Report status daily until done

---

**Awaiting your decision.** No changes will be made until you approve.
