# EVE Frontier Codebase Investigation TODO

**Date:** 2026-03-17
**Based on:** Comprehensive documentation audit (7 docs × src/ + tests)
**Status:** Investigation phase — NO CHANGES without explicit approval per item

---

## Investigation Protocol

For each item:
1. **Read the code** — understand current behavior fully
2. **Check usage** — find ALL callers/references (grep -r)
3. **Verify tests** — confirm test coverage exists
4. **Document findings** — report before proposing changes
5. **Ask before acting** — get approval to fix

---

## 🔴 CRITICAL: Security Issues

### SEC-1: Hardcoded API Tokens in HTML Files

**What to investigate:**
- `static/index.html` line 29 — hardcoded `SERVER_TOKEN = "5740edb0fb25a051db4a932c3622bd69ce47d487bc501f2bde4cb7e19907c454"`
- `static/structure-debug.html` line 207 — identical hardcoded token
- Check if this token is actually valid (matches `.env` or deployed config)
- Search git history: when was this token added, how old is it, was it ever rotated?

**Safety checks before any change:**
- Verify token is NOT in active use on production VPS
- Confirm both files use identical token (same token in 2 places = copy-paste issue)
- Check if token rotation mechanism exists (if not, may be deliberate)
- Test that removing hardcoded tokens doesn't break local dev flow

**What could go wrong:**
- If you remove tokens without replacement, both files become non-functional
- If token IS in active use, removing it breaks deployments
- May need to implement env substitution at build/deploy time (not trivial)

**Investigation steps:**
```bash
# 1. Find token definition
grep -n "5740edb0fb25a051db4a932c3622bd69ce47d487bc501f2bde4cb7e19907c454" /opt/eve-frontier/static/*.html

# 2. Check if it's used anywhere else
grep -r "5740edb0fb25a051db4a932c3622bd69ce47d487bc501f2bde4cb7e19907c454" /opt/eve-frontier/

# 3. Check git history
cd /opt/eve-frontier && git log --all -S "5740edb0" --oneline

# 4. Compare with .env
grep "SERVER_TOKEN\|AUTH" /opt/eve-frontier/.env /opt/eve-frontier/.env.example

# 5. Check deployment config
grep -r "SERVER_TOKEN" /etc/systemd/system/ ~/.openclaw/ 2>/dev/null || echo "No systemd config found"
```

**Report before proceeding:** Token validity, if it's in use, rotation strategy needed?

---

### SEC-2: EventSource Auth Bypass in index.html

**What to investigate:**
- `static/index.html` function `startSSE()` — opens EventSource with token in query param: `EventSource('/chat?token=...')`
- Backend `/chat` endpoint uses `require_token()` which validates `X-Server-Token` header only
- **Key question:** Does backend actually check query params, or is auth completely bypassed?

**Safety checks before any change:**
- Verify `/chat` endpoint handler in `main.py` — trace auth flow completely
- Check if ANY query param validation happens (may be in middleware)
- Test current behavior: can you hit `/chat` WITHOUT token and get response?
- Confirm debug.html uses correct header-based auth (it does per audit)

**What could go wrong:**
- If you "fix" auth by adding query param validation, may break other endpoints that use query params legitimately
- If you switch index.html to fetch() + headers, may break CORS or EventSource behavior
- Changing SSE auth may need corresponding backend changes

**Investigation steps:**
```bash
# 1. Find SSE handler in main.py
grep -n "def.*chat" /opt/eve-frontier/main.py | head -5
grep -n "require_token\|X-Server-Token" /opt/eve-frontier/src/auth.py

# 2. Check if any middleware validates query params
grep -n "query\|params" /opt/eve-frontier/main.py | grep -i "token\|auth"

# 3. Test current behavior (from your VPS)
# Try to hit /chat without token:
curl -s http://localhost:8745/chat -X POST -H "Content-Type: application/json" -d '{"message":"test"}' 2>&1 | head -20

# 4. Examine EventSource API limitations
# Check if there's a reason query param was used instead of headers
grep -B5 -A5 "EventSource" /opt/eve-frontier/static/index.html
```

**Report before proceeding:** Is auth actually bypassed? What's the intended auth flow?

---

### SEC-3: Path Traversal Risk in memory_store.py

**What to investigate:**
- `src/memory_store.py` line 40: `_pilot_path()` function sanitization
- Current code: `safe = address.lower().replace("/", "").replace("..", "")`
- **Problem:** Only removes `/` and `..`, doesn't validate Sui address format
- Sui addresses SHOULD be: `0x` + 64 hex chars (e.g., `0x442f...`)

**Safety checks before any change:**
- Verify all callers of `_pilot_path()` — what input types are passed?
- Check if invalid addresses ever reach this function in practice
- Confirm Sui address format requirement (is it always 0x + 64 hex?)
- Look for existing validation elsewhere in codebase

**What could go wrong:**
- If you add strict validation, may reject legitimate edge cases
- If format varies (some addresses shorter?), validation breaks them
- May need to update callers to validate BEFORE calling _pilot_path()

**Investigation steps:**
```bash
# 1. Find all calls to _pilot_path()
grep -n "_pilot_path\|pilot_path" /opt/eve-frontier/src/memory_store.py

# 2. Trace back to callers
grep -rn "_pilot_path\|/pilots/" /opt/eve-frontier/src/ /opt/eve-frontier/tests/ | grep -v ".pyc"

# 3. Check Sui address format in codebase
grep -r "0x[a-f0-9]\{64\}\|Sui.*address" /opt/eve-frontier/src/ | head -10

# 4. Look for existing address validation
grep -n "validate.*address\|address.*format" /opt/eve-frontier/src/*.py

# 5. Check test data for address examples
grep -r "0x" /opt/eve-frontier/tests/ | grep -i address | head -5
```

**Report before proceeding:** What addresses are actually used? What format validation exists elsewhere?

---

## ❌ INACCURACIES: Fix Documentation

### DOC-1: structure-ai.md — get_summary() Return Type

**What to investigate:**
- `docs/ref/structure-ai.md` line 268 claims: `get_summary() → str`
- `src/memory_store.py` line 147 returns: `dict` with keys `{"last_updated": str|None, "text": str}`
- `main.py` line 1165-1166 shows caller extracts `.get("text", "")`

**Safety checks:**
- This is purely documentation, NOT code that needs fixing
- Just need to verify actual return type in memory_store.py
- Check if any code assumes string return (would be a bug)

**Investigation steps:**
```bash
# 1. Read the actual function
grep -A 20 "def get_summary" /opt/eve-frontier/src/memory_store.py

# 2. Find all callers
grep -rn "get_summary\|\.get.*text" /opt/eve-frontier/src/ /opt/eve-frontier/main.py

# 3. Verify return type in all cases
grep -B 5 "get_summary()" /opt/eve-frontier/main.py
```

**Action:** Update docs only. Current code is correct; docs are wrong.

---

### DOC-2: ops.md — SSE Keep-Alive Documentation

**What to investigate:**
- `docs/ref/ops.md` previously stated: "Not yet implemented"
- Audit found: Already implemented in all 3 event_stream functions (`main.py` lines 657, 700, 1192)
- Each sends: `yield ": keep-alive\n\n"` at stream start (NOT periodically every 15-20s as doc suggested)

**Safety checks:**
- Docs were already updated (2026-03-17 update mentioned "Resolved")
- Verify actual implementation matches update

**Investigation steps:**
```bash
# Confirm keep-alive is sent
grep -n "keep-alive" /opt/eve-frontier/main.py
```

**Action:** Docs already updated. Verify no further changes needed.

---

## 🗑️ DEAD CODE: Safe to Remove (After Verification)

### DEAD-1: _extract_fuel_pct() in ssu_poller.py

**What to investigate:**
- `src/ssu_poller.py` lines 217-234: function marked "Deprecated"
- Comment says: "no longer called internally"
- **Question:** Is it called by external code? (even though comment says no)

**Safety checks before removal:**
- Search all files for ANY reference to this function
- Check if external processes call this module
- Verify tests don't depend on it
- Confirm it's NOT exported as API

**What could go wrong:**
- If external consumers call this, removing breaks them (unlikely but must verify)
- Tests might reference it (unlikely but check)

**Investigation steps:**
```bash
# 1. Find exact function
grep -n "def _extract_fuel_pct" /opt/eve-frontier/src/ssu_poller.py

# 2. Search for ALL references
grep -rn "_extract_fuel_pct\|extract_fuel" /opt/eve-frontier/

# 3. Check if it's in __all__ or public API
grep -n "__all__\|extract_fuel" /opt/eve-frontier/src/ssu_poller.py | head -5

# 4. Check if documented in any README/CODEBASE.md
grep -r "_extract_fuel_pct\|extract_fuel" /opt/eve-frontier/docs/
```

**Action:** If zero references found, safe to delete.

---

### DEAD-2: get_system_by_id() in world_api.py

**What to investigate:**
- `src/world_api.py` line 243: function exists, never called
- Audit found: Only used in unit tests

**Safety checks:**
- Confirm no production code calls this
- Check if it's documented as public API
- Verify tests still pass if removed

**Investigation steps:**
```bash
# 1. Find function
grep -n "def get_system_by_id" /opt/eve-frontier/src/world_api.py

# 2. Search for calls
grep -rn "get_system_by_id" /opt/eve-frontier/

# 3. If only in tests, check if test actually verifies it
grep -B 5 -A 10 "get_system_by_id" /opt/eve-frontier/tests/test_world_api.py
```

**Action:** If only in tests, consider if test is still relevant. If not, remove function AND test.

---

### DEAD-3: format_pilot_line() in memory_store.py

**What to investigate:**
- `src/memory_store.py` lines 197-209: constructs pilot context line
- Defined but never called anywhere
- **Question:** Was this planned for system prompts but abandoned?

**Safety checks:**
- Verify it's not referenced anywhere
- Check git blame to see when added and why
- Determine if it was incomplete feature work

**Investigation steps:**
```bash
# 1. Find function
grep -n "def format_pilot_line" /opt/eve-frontier/src/memory_store.py

# 2. Search for any references
grep -rn "format_pilot_line" /opt/eve-frontier/

# 3. Check git history
cd /opt/eve-frontier && git log -p -S "format_pilot_line" | head -50
```

**Action:** If no references, determine if it was abandoned feature. If so, remove OR add TODO explaining intent.

---

### DEAD-4: debugTimer variable in debug.html

**What to investigate:**
- `static/debug.html` line 239: `let debugTimer = null;`
- Declared but never assigned or used

**Safety checks:**
- Confirm it's not used anywhere in HTML
- Check if it's set by inline scripts or external files
- Verify removing it doesn't break auto-refresh

**Investigation steps:**
```bash
# 1. Find variable declaration
grep -n "debugTimer" /opt/eve-frontier/static/debug.html

# 2. Check all uses
grep -n "debugTimer" /opt/eve-frontier/static/*.html /opt/eve-frontier/static/*.js 2>/dev/null
```

**Action:** If unused, remove the line.

---

### DEAD-5: current_mass field in ship_profile.py

**What to investigate:**
- `src/ship_profile.py` line 59: field marked "legacy; not used in calculations"
- Still persisted to JSON and accepted in requests
- Never read from in calculations

**Safety checks:**
- Verify it's not used in any formulas
- Check if removing it breaks existing ship_profile.json files
- Confirm clients aren't sending it

**What could go wrong:**
- Old ship_profile.json files might have this field; removing it breaks backwards compat
- Clients might be sending it (would need migration)

**Investigation steps:**
```bash
# 1. Find field definition
grep -n "current_mass" /opt/eve-frontier/src/ship_profile.py

# 2. Find all reads
grep -n "current_mass" /opt/eve-frontier/src/ship_profile.py | grep -v "# legacy"

# 3. Check persisted data
head -20 /opt/eve-frontier/data/ship_profile.json

# 4. Check if tests depend on it
grep -n "current_mass" /opt/eve-frontier/tests/test_ship_profile.py
```

**Action:** If truly unused, requires migration script to clean existing data before removal.

---

### DEAD-6: NOVA_ACCESS_REGISTRY_PACKAGE in .env.example

**What to investigate:**
- `.env.example` includes: `NOVA_ACCESS_REGISTRY_PACKAGE=...`
- Audit found: Not referenced in any source code
- **Question:** Is it legacy config or used somewhere?

**Safety checks:**
- Grep entire src/ directory for references
- Check if it's used by Move contracts or external systems
- Verify it was never needed

**Investigation steps:**
```bash
# 1. Find in .env.example
grep "NOVA_ACCESS_REGISTRY_PACKAGE" /opt/eve-frontier/.env.example

# 2. Search entire codebase
grep -rn "NOVA_ACCESS_REGISTRY_PACKAGE" /opt/eve-frontier/

# 3. Check Move contract
grep -r "REGISTRY_PACKAGE" /opt/eve-frontier/move/
```

**Action:** If not referenced, remove from .env.example with comment explaining why.

---

## ⚠️ CODE QUALITY: Investigate & Document

### QUAL-1: Repeated asdict Import in main.py

**What to investigate:**
- `main.py` lines 678, 727, 736: `from dataclasses import asdict` imported inside 3 endpoint functions
- Should be at module level with other imports (line 6)

**Safety checks:**
- Verify moving import to module level doesn't change behavior
- Confirm no circular imports would result
- Check that all three endpoints actually need asdict

**Investigation steps:**
```bash
# 1. Find all imports at top
head -20 /opt/eve-frontier/main.py

# 2. Find inline imports
grep -n "from dataclasses import asdict" /opt/eve-frontier/main.py

# 3. Check each endpoint
grep -B 2 "from dataclasses import asdict" /opt/eve-frontier/main.py
```

**Action:** Move import to module level. Trivial, safe change.

---

### QUAL-2: Vague Error Message in main.py

**What to investigate:**
- `main.py` line 713: stream error returns generic "Stream interrupted."
- Should include exception type or details for debugging

**Safety checks:**
- Verify what exceptions could occur here
- Check if more detailed message would expose sensitive info
- Confirm clients handle detailed messages correctly

**Investigation steps:**
```bash
# 1. Find error handling
grep -B 10 -A 2 "Stream interrupted" /opt/eve-frontier/main.py

# 2. Check what exceptions could occur
grep -B 15 "Stream interrupted" /opt/eve-frontier/main.py | grep -i "except\|try"
```

**Action:** Add exception type to error message. Safe improvement.

---

### QUAL-3: Missing File Locking in Alert Saving

**What to investigate:**
- `main.py` lines 689-690: routine alerts saved to JSON without file locking
- Concurrent updates could overwrite each other

**Safety checks:**
- Check if routine alerts are actually saved concurrently
- Verify this is actually a problem (low traffic = unlikely to hit)
- Determine if file locking would cause performance issues

**Investigation steps:**
```bash
# 1. Find alert saving code
grep -n "routine_alerts\|\.json" /opt/eve-frontier/main.py | grep -i "save\|write"

# 2. Check how often routine alerts are updated
grep -rn "routine_alerts\|detect_alerts" /opt/eve-frontier/src/

# 3. Check if there's any existing locking pattern in codebase
grep -rn "fcntl.flock\|FileLock\|Lock" /opt/eve-frontier/
```

**Action:** If concurrent saves are possible, add file locking. Otherwise document why it's safe.

---

### QUAL-4: Naming Ambiguity in ship_profile.py

**What to investigate:**
- `src/ship_profile.py` line 84-89: `jump_range_at_temp(temp)` parameter
- Parameter name `temp` could mean "temporary" or "temperature"
- Callers pass `safe_jump_temp` from systems data

**Safety checks:**
- Verify all callers understand the parameter correctly
- Check if renaming would break anything
- Look for similar naming issues elsewhere

**Investigation steps:**
```bash
# 1. Find function
grep -B 3 -A 10 "def jump_range_at_temp" /opt/eve-frontier/src/ship_profile.py

# 2. Find all callers
grep -rn "jump_range_at_temp" /opt/eve-frontier/

# 3. Check what they pass
grep -B 5 "jump_range_at_temp" /opt/eve-frontier/src/route_engine.py
```

**Action:** Consider renaming parameter to `safe_jump_temp` for clarity. Safe change with grep-replace.

---

## 📋 UNDOCUMENTED FEATURES: Document Only

### UNDOC-1: /logs/stream SSE Endpoint

**What to investigate:**
- `main.py` line 312: `/logs/stream` endpoint exists and works
- Not mentioned in ui.md or ship-ai.md
- Used by debug.html but not documented

**Safety checks:**
- This is read-only, no risk to document it
- Just need to verify current behavior

**Investigation steps:**
```bash
# 1. Find endpoint
grep -B 5 -A 20 "logs/stream" /opt/eve-frontier/main.py

# 2. Check implementation
grep -A 30 "@app.get.*logs/stream" /opt/eve-frontier/main.py
```

**Action:** Add to docs (read-only, low risk).

---

### UNDOC-2: /route/clear and /route/activate Endpoints

**What to investigate:**
- `main.py` lines 439, 449: `/route/clear` and `/route/activate` exist
- Mentioned in structure-debug.md and overlay but not in ship-ai.md or ui.md

**Safety checks:**
- Verify behavior matches documentation
- Check test coverage

**Investigation steps:**
```bash
# 1. Find endpoints
grep -n "route/clear\|route/activate" /opt/eve-frontier/main.py

# 2. Verify implementation
grep -B 2 -A 15 "@app.post.*route" /opt/eve-frontier/main.py | grep -A 15 "clear\|activate"
```

**Action:** Add to ship-ai.md docs (already works, just needs documentation).

---

### UNDOC-3: get_player_structures_in_system() Parameter Doesn't Filter

**What to investigate:**
- `src/ssu_poller.py` lines 531-537: function accepts `system_name` parameter but doesn't use it
- Comment explains: "location is not available on-chain"
- But ship-ai.md claims it filters by system

**Safety checks:**
- Verify parameter is truly unused (it is)
- Confirm comment explains why (it does)
- Check if removing parameter would break callers

**Investigation steps:**
```bash
# 1. Find function
grep -B 5 -A 15 "def get_player_structures_in_system" /opt/eve-frontier/src/ssu_poller.py

# 2. Find callers
grep -rn "get_player_structures_in_system" /opt/eve-frontier/

# 3. Check if system_name is ever used
grep -A 15 "def get_player_structures_in_system" /opt/eve-frontier/src/ssu_poller.py | grep "system_name"
```

**Action:** Either remove parameter (if no external callers) OR document that filtering is not possible.

---

## 🔍 INVESTIGATION COMPLETION CHECKLIST

Before recommending ANY changes:

- [ ] All investigation steps completed for each item
- [ ] All findings documented with code references
- [ ] All callers/references identified (grep results)
- [ ] Test coverage verified
- [ ] Git history checked (when was code added, why)
- [ ] Backwards compatibility assessed
- [ ] Risk of production breakage evaluated
- [ ] Alternative approaches considered

**Report format for each finding:**
```
[ITEM-ID] Title
Status: [Under investigation / Ready to fix / Blocked]
Findings:
  - Finding 1
  - Finding 2
Risk level: [Low/Medium/High]
Recommendation: [Action or block reason]
Approved by: [Markús approval needed]
```

---

**Next step:** Begin investigation. Report findings before proposing code changes.
