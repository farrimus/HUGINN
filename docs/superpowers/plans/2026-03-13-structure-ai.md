# Structure AI Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the Structure AI companion — an amber terminal UI served in the EVE Frontier SSU browser with wallet-based access control, a Claude-powered caretaker AI, and an alert bridge that delivers urgent structure alerts to the Ship AI overlay.

**Architecture:** A new `structure.html` static page connects to four new FastAPI endpoints (auth challenge/verify, structure profile, structure chat). Auth uses Sui `signPersonalMessage` for cryptographic identity, cross-referenced with the World API for character lookup and a Nova chain `AccessRegistry` Move contract for access tiers. The Structure AI runs as a separate Claude client instance with a caretaker system prompt; urgent alerts it detects are queued in `log_buffer.pending_structure_alerts` and delivered to the pilot via the existing Ship AI context builder.

**Tech Stack:** FastAPI (existing), Claude claude-sonnet-4-6 (existing), PyJWT 2.9, cryptography ≥42 (ed25519 verify), httpx (existing), Sui JSON-RPC over HTTPS (Nova chain), Sui Move (AccessRegistry contract)

---

## File Map

### New files
| File | Responsibility |
|------|---------------|
| `src/structure_auth.py` | Nonce store, Sui ed25519 signature verify, World API character lookup, access tier resolution |
| `src/nova_client.py` | Sui JSON-RPC HTTP client — read `AccessRegistry` shared objects from Nova chain |
| `src/structure_profile.py` | `StructureProfile` dataclass + JSON persistence keyed by `structure_id` |
| `src/structure_client.py` | Claude streaming client for Structure AI persona + context block builder |
| `static/structure.html` | Full SSU browser page — amber UI, wallet connect, collapsible panel, SSE chat |
| `move/access_registry/Move.toml` | Sui Move package manifest |
| `move/access_registry/sources/access_registry.move` | AccessRegistry shared object — owner + tribe + vetted address lists |
| `tests/test_structure_auth.py` | Unit tests for nonce lifecycle and signature verification |
| `tests/test_nova_client.py` | Unit tests for AccessRegistry queries (mocked Sui RPC) |
| `tests/test_structure_profile.py` | Unit tests for profile persistence and tier-filtered views |
| `tests/test_structure_client.py` | Unit tests for Structure AI context builder and alert detection |

### Modified files
| File | Change |
|------|--------|
| `src/log_buffer.py` | Add `pending_structure_alerts: list`, `add_structure_alert()`, `pop_structure_alerts()` |
| `src/context_builder.py` | Add `structure_alerts` parameter; prepend `STRUCTURE ALERT:` lines before LOCATION |
| `main.py` | Register 5 new endpoints; add JWT middleware |
| `requirements.txt` | Add `pyjwt==2.9.0`, `cryptography>=42.0.0` |
| `tests/test_log_buffer.py` | Tests for new alert methods |
| `tests/test_context_builder.py` | Tests for structure alert lines in output |

---

## Chunk 1: Log Buffer + Context Builder

**Files:**
- Modify: `src/log_buffer.py`
- Modify: `src/context_builder.py`
- Modify: `tests/test_log_buffer.py`
- Modify: `tests/test_context_builder.py`

### Task 1: Add `pending_structure_alerts` to LogBuffer

- [x] **1.1 Write failing tests**

Open `tests/test_log_buffer.py` and add after existing tests:

```python
def test_add_structure_alert_stores_event():
    buf = LogBuffer(max_size=50)
    alert = {"type": "structure_alert", "structure_id": "keep-7a", "severity": "urgent", "message": "Shield below 20%."}
    buf.add_structure_alert(alert)
    alerts = buf.pop_structure_alerts()
    assert len(alerts) == 1
    assert alerts[0]["message"] == "Shield below 20%."

def test_pop_structure_alerts_clears_list():
    buf = LogBuffer(max_size=50)
    buf.add_structure_alert({"type": "structure_alert", "structure_id": "keep-7a", "severity": "urgent", "message": "Test"})
    buf.pop_structure_alerts()
    assert buf.pop_structure_alerts() == []

def test_multiple_structure_alerts_accumulate():
    buf = LogBuffer(max_size=50)
    buf.add_structure_alert({"type": "structure_alert", "structure_id": "keep-7a", "severity": "urgent", "message": "A"})
    buf.add_structure_alert({"type": "structure_alert", "structure_id": "forge-1", "severity": "urgent", "message": "B"})
    alerts = buf.pop_structure_alerts()
    assert len(alerts) == 2

def test_structure_alerts_do_not_go_in_ring_buffer():
    buf = LogBuffer(max_size=50)
    buf.add_structure_alert({"type": "structure_alert", "structure_id": "keep-7a", "severity": "urgent", "message": "A"})
    assert all(e.get("type") != "structure_alert" for e in buf.get_recent(50))
```

- [x] **1.2 Run tests to confirm they fail**

```bash
cd /opt/eve-frontier && .venv/bin/pytest tests/test_log_buffer.py -k "structure_alert" -v
```

Expected: `AttributeError: 'LogBuffer' object has no attribute 'add_structure_alert'`

- [x] **1.3 Implement in `src/log_buffer.py`**

Add after `self._live: list = []` in `__init__`:
```python
self.pending_structure_alerts: list = []
```

Add two new methods after `clear_live`:
```python
def add_structure_alert(self, event: dict):
    """Queue an urgent structure alert for Ship AI delivery. Never evicted."""
    self.pending_structure_alerts.append(event)

def pop_structure_alerts(self) -> list:
    """Return and clear all pending structure alerts."""
    alerts = self.pending_structure_alerts[:]
    self.pending_structure_alerts = []
    return alerts
```

- [x] **1.4 Run tests — expect pass**

```bash
cd /opt/eve-frontier && .venv/bin/pytest tests/test_log_buffer.py -v
```

Expected: all pass including 4 new tests.

- [x] **1.5 Commit**

```bash
cd /opt/eve-frontier
git add src/log_buffer.py tests/test_log_buffer.py
git commit -m "feat: add pending_structure_alerts to LogBuffer"
```

---

### Task 2: Structure alerts in context_builder

- [x] **2.1 Write failing tests**

Open `tests/test_context_builder.py` and add after existing tests:

```python
from src.context_builder import build_context_block

def test_structure_alert_prepended_before_location():
    alerts = [{"type": "structure_alert", "structure_id": "keep-7a", "structure_name": "Keep-7A", "severity": "urgent", "message": "Shield below 20%."}]
    result = build_context_block(None, [], "UTR-SN4", structure_alerts=alerts)
    lines = result.split("\n")
    assert lines[0].startswith("STRUCTURE ALERT")
    assert "Keep-7A" in lines[0]
    assert "Shield below 20%." in lines[0]
    assert any("LOCATION" in l for l in lines)

def test_no_structure_alert_line_when_none():
    result = build_context_block(None, [], "UTR-SN4")
    assert "STRUCTURE ALERT" not in result

def test_multiple_structure_alerts_all_shown():
    alerts = [
        {"type": "structure_alert", "structure_id": "a", "structure_name": "A", "severity": "urgent", "message": "Msg1"},
        {"type": "structure_alert", "structure_id": "b", "structure_name": "B", "severity": "urgent", "message": "Msg2"},
    ]
    result = build_context_block(None, [], "UTR-SN4", structure_alerts=alerts)
    assert result.count("STRUCTURE ALERT") == 2
```

- [x] **2.2 Run tests to confirm they fail**

```bash
cd /opt/eve-frontier && .venv/bin/pytest tests/test_context_builder.py -k "structure_alert" -v
```

Expected: `TypeError: build_context_block() got an unexpected keyword argument 'structure_alerts'`

- [x] **2.3 Implement in `src/context_builder.py`**

Add `structure_alerts` parameter to `build_context_block` signature:
```python
def build_context_block(
    system_data: Optional[dict],
    log_events: list,
    current_system: Optional[str],
    live_sessions: Optional[list] = None,
    current_route: Optional[dict] = None,
    structure_alerts: Optional[list] = None,
) -> str:
```

- [x] **2.3a Remove the existing `lines = []` line** from its current position inside the function body (line ~12). It will be replaced by the block below.

Add the following as the new opening of the function body, replacing the removed `lines = []`:
```python
    lines = []

    # --- Structure alerts (urgent, from Structure AI — prepended for visibility) ---
    for alert in (structure_alerts or []):
        name = alert.get("structure_name", alert.get("structure_id", "Structure"))
        lines.append(f"STRUCTURE ALERT [{name}]: {alert.get('message', '')}")
```

- [x] **2.4 Run full context_builder tests**

```bash
cd /opt/eve-frontier && .venv/bin/pytest tests/test_context_builder.py -v
```

Expected: all pass.

- [x] **2.5 Update `main.py` `/chat` endpoint** to pass structure alerts from log_buffer

In the `chat()` function in `main.py`, update the `build_context_block` call:
```python
    context = build_context_block(
        system_data=system_data,
        log_events=log_buffer.get_recent(10),
        current_system=log_buffer.current_system,
        live_sessions=log_buffer.get_live(),
        current_route=log_buffer.current_route,
        structure_alerts=log_buffer.pop_structure_alerts(),
    )
```

- [x] **2.6 Run all server tests**

```bash
cd /opt/eve-frontier && .venv/bin/pytest tests/ -q
```

Expected: all pass.

- [x] **2.7 Commit**

```bash
cd /opt/eve-frontier
git add src/context_builder.py tests/test_context_builder.py main.py
git commit -m "feat: include structure alerts in Ship AI context block"
```

---

## Chunk 2: Auth Infrastructure

**Files:**
- Create: `src/structure_auth.py`
- Create: `tests/test_structure_auth.py`
- Modify: `requirements.txt`

### Task 3: Dependencies

- [x] **3.1 Add PyJWT and cryptography to requirements.txt**

```
pyjwt==2.9.0
cryptography>=42.0.0
```

- [x] **3.2 Install**

```bash
cd /opt/eve-frontier && .venv/bin/pip install pyjwt==2.9.0 "cryptography>=42.0.0"
```

Expected: `Successfully installed PyJWT-2.9.0 cryptography-...`

- [x] **3.3 Confirm ed25519 is available**

```bash
cd /opt/eve-frontier && .venv/bin/python -c "from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey; print('ok')"
```

Expected: `ok`.

- [x] **3.4 Commit requirements**

```bash
cd /opt/eve-frontier
git add requirements.txt
git commit -m "chore: add pyjwt dependency for structure auth"
```

---

### Task 4: Nonce store

- [x] **4.1 Write failing tests**

Create `tests/test_structure_auth.py`:

```python
import pytest
import time
import os
from unittest.mock import patch

from src.structure_auth import NonceStore

def test_issue_nonce_returns_string():
    store = NonceStore()
    nonce = store.issue()
    assert isinstance(nonce, str)
    assert len(nonce) == 64  # 32 hex bytes

def test_consume_valid_nonce_returns_true():
    store = NonceStore()
    nonce = store.issue()
    assert store.consume(nonce) is True

def test_consume_same_nonce_twice_returns_false():
    store = NonceStore()
    nonce = store.issue()
    store.consume(nonce)
    assert store.consume(nonce) is False

def test_consume_unknown_nonce_returns_false():
    store = NonceStore()
    assert store.consume("deadbeef" * 8) is False

def test_expired_nonce_returns_false():
    from unittest.mock import patch
    store = NonceStore(ttl_seconds=10)
    nonce = store.issue()
    # Advance time by 20s via mock — avoids fragile sleep on a loaded VPS
    with patch("src.structure_auth.time") as mock_time:
        mock_time.time.return_value = time.time() + 20
        assert store.consume(nonce) is False
```

- [x] **4.2 Run to confirm they fail**

```bash
cd /opt/eve-frontier && .venv/bin/pytest tests/test_structure_auth.py -k "nonce" -v
```

Expected: `ModuleNotFoundError: No module named 'src.structure_auth'`

- [x] **4.3 Implement `NonceStore` in `src/structure_auth.py`**

```python
# src/structure_auth.py
import os
import time
import base64
import hashlib
import logging
from typing import Optional, Tuple
from dataclasses import dataclass, field

log = logging.getLogger(__name__)

NONCE_TTL_SECONDS = 300  # 5 minutes


class NonceStore:
    """In-memory single-use nonce store with TTL. Thread-safe via dict ops (GIL)."""

    def __init__(self, ttl_seconds: int = NONCE_TTL_SECONDS):
        self._ttl = ttl_seconds
        self._store: dict[str, float] = {}  # nonce -> expires_at

    def issue(self) -> str:
        """Generate a fresh nonce and store it. Returns hex string."""
        nonce = os.urandom(32).hex()
        self._store[nonce] = time.time() + self._ttl
        self._evict()
        return nonce

    def consume(self, nonce: str) -> bool:
        """Mark nonce as used. Returns True if valid and not yet consumed."""
        expires = self._store.pop(nonce, None)
        if expires is None:
            return False
        if time.time() > expires:
            return False
        return True

    def _evict(self):
        now = time.time()
        self._store = {k: v for k, v in self._store.items() if v > now}


# Global singleton
nonce_store = NonceStore()


async def lookup_character(address: str) -> dict:
    """
    Look up a character by wallet address via the World API.
    Returns dict with 'id' and 'name' keys, or empty dict on failure.

    World API endpoint (Utopia): GET /v2/smartcharacters?address={address}
    or GET /v2/smartcharacters/{address} — verify exact path against Utopia docs.
    Falls back gracefully so auth still works if the World API is unavailable.
    """
    import httpx, os
    world_api_base = os.environ.get("WORLD_API_BASE_URL", "https://world-api-stillness.live.tech.evefrontier.com")
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            resp = await client.get(f"{world_api_base}/v2/smartcharacters", params={"address": address})
            if resp.status_code == 200:
                data = resp.json()
                items = data if isinstance(data, list) else data.get("items", [])
                if items:
                    return {"id": items[0].get("id", 0), "name": items[0].get("name", "")}
    except Exception as e:
        log.warning("World API character lookup failed for %s: %s", address, e)
    return {}
```

- [x] **4.4 Run nonce tests**

```bash
cd /opt/eve-frontier && .venv/bin/pytest tests/test_structure_auth.py -k "nonce" -v
```

Expected: all 5 pass.

---

### Task 5: Sui signature verification

- [x] **5.1 Write failing tests**

Add to `tests/test_structure_auth.py`:

```python
from src.structure_auth import verify_sui_personal_message

def test_verify_returns_true_for_valid_signature():
    """
    This test uses a pre-computed test vector.
    To generate: run the EVEVault wallet in Utopia, call signPersonalMessage("test-nonce"),
    capture address + signature, paste below.
    Replace with real values when first testing against EVEVault.
    """
    # Placeholder — will be replaced with real test vector from EVEVault
    pytest.skip("Needs real EVEVault test vector — see comment above")

def test_verify_raises_for_tampered_message():
    pytest.skip("Needs real EVEVault test vector")

def test_verify_raises_for_wrong_address():
    pytest.skip("Needs real EVEVault test vector")

def test_verify_rejects_unsupported_scheme_flag():
    from cryptography.exceptions import InvalidSignature
    from src.structure_auth import verify_sui_personal_message
    import base64
    # Build a fake signature with flag=0xFF (unsupported)
    fake_sig = base64.b64encode(bytes([0xFF]) + bytes(96)).decode()
    with pytest.raises(ValueError, match="Unsupported"):
        verify_sui_personal_message(b"hello", fake_sig, "0x" + "00" * 32)
```

- [x] **5.2 Implement `verify_sui_personal_message`**

Add to `src/structure_auth.py`:

```python
import hashlib
import base64
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey
from cryptography.exceptions import InvalidSignature


def verify_sui_personal_message(message_bytes: bytes, signature_b64: str, expected_address: str) -> bool:
    """
    Verify a Sui signPersonalMessage signature.

    Sui compact signature format: flag(1) || sig(64) || pubkey(32) = 97 bytes, base64-encoded.
    - flag 0x00 = ed25519 (only scheme supported here)

    Intent prefix for PersonalMessage: [3, 0, 0]
    BCS encoding of message: u32-LE length prefix + raw bytes
    Full signed message: intent_prefix + bcs(message_bytes)
    ed25519 signs the full message (RFC 8032 — library handles internal SHA-512).

    Address derivation: blake2b-256(flag_byte || pubkey_bytes) as 32-byte hex, prefixed "0x".

    NOTE: Verify this against real EVEVault signPersonalMessage output before relying on it.
    If the scheme fails, inspect the raw signature bytes from the wallet for the correct format.
    """
    try:
        sig_bytes = base64.b64decode(signature_b64)
    except Exception as e:
        raise ValueError(f"Invalid base64 signature: {e}")

    if len(sig_bytes) < 97:
        raise ValueError(f"Signature too short: {len(sig_bytes)} bytes, expected 97")

    flag = sig_bytes[0]
    if flag != 0x00:
        raise ValueError(f"Unsupported signature scheme flag: {flag:#04x} (only ed25519/0x00 supported)")

    sig = sig_bytes[1:65]
    pubkey_bytes = sig_bytes[65:97]

    # Intent prefix for PersonalMessage type in Sui
    intent = bytes([3, 0, 0])
    # BCS-encoded message: 4-byte LE length + raw bytes
    bcs_msg = len(message_bytes).to_bytes(4, 'little') + message_bytes
    full_msg = intent + bcs_msg

    # Verify ed25519 signature (raises InvalidSignature on failure)
    pubkey = Ed25519PublicKey.from_public_bytes(pubkey_bytes)
    pubkey.verify(sig, full_msg)

    # Derive Sui address: blake2b-256(flag_byte || pubkey_bytes)
    h = hashlib.new('blake2b', digest_size=32)
    h.update(bytes([0x00]) + pubkey_bytes)
    derived_address = '0x' + h.hexdigest()

    if derived_address.lower() != expected_address.lower():
        raise InvalidSignature(f"Address mismatch: derived {derived_address} != claimed {expected_address}")

    return True
```

- [x] **5.3 Run signature tests**

```bash
cd /opt/eve-frontier && .venv/bin/pytest tests/test_structure_auth.py -v
```

Expected: 3 tests skip (need real vectors), 1 passes (unsupported scheme raises ValueError), 5 nonce tests pass.

- [x] **5.4 Commit**

```bash
cd /opt/eve-frontier
git add src/structure_auth.py tests/test_structure_auth.py requirements.txt
git commit -m "feat: Sui signature verification and nonce store for structure auth"
```

---

### Task 6: JWT issue and verify

- [x] **6.1 Write failing tests**

Add to `tests/test_structure_auth.py`:

```python
from src.structure_auth import issue_jwt, decode_jwt

def test_issue_and_decode_jwt_roundtrip(monkeypatch):
    monkeypatch.setenv("JWT_SECRET", "test-secret-key-for-testing-only")
    import importlib, src.structure_auth as sa
    importlib.reload(sa)  # reload so JWT_SECRET picks up monkeypatched env
    payload = {"character_id": 12345, "character_name": "Markus", "address": "0xabc", "tier": "OWNER", "structure_id": "keep-7a"}
    token = sa.issue_jwt(payload)
    assert isinstance(token, str)
    decoded = sa.decode_jwt(token)
    assert decoded["character_id"] == 12345
    assert decoded["tier"] == "OWNER"

def test_decode_expired_jwt_raises(monkeypatch):
    monkeypatch.setenv("JWT_SECRET", "test-secret-key-for-testing-only")
    import importlib, src.structure_auth as sa, jwt as pyjwt, datetime
    importlib.reload(sa)
    expired = pyjwt.encode(
        {"sub": "test", "exp": datetime.datetime.utcnow() - datetime.timedelta(seconds=1)},
        "test-secret-key-for-testing-only", algorithm="HS256"
    )
    with pytest.raises(Exception):
        sa.decode_jwt(expired)

def test_decode_tampered_jwt_raises(monkeypatch):
    monkeypatch.setenv("JWT_SECRET", "test-secret-key-for-testing-only")
    import importlib, src.structure_auth as sa
    importlib.reload(sa)
    payload = {"character_id": 1, "tier": "OWNER", "structure_id": "keep-7a"}
    token = sa.issue_jwt(payload)
    tampered = token[:-4] + "XXXX"
    with pytest.raises(Exception):
        sa.decode_jwt(tampered)
```

- [x] **6.2 Run to confirm fail**

```bash
cd /opt/eve-frontier && .venv/bin/pytest tests/test_structure_auth.py -k "jwt" -v
```

Expected: `ImportError: cannot import name 'issue_jwt'`

- [x] **6.3 Implement JWT functions in `src/structure_auth.py`**

Add at the top of `src/structure_auth.py`:
```python
import jwt as pyjwt
import datetime
```

Add after the nonce store section:
```python
JWT_SECRET = os.environ.get("JWT_SECRET", "change-me-in-production")
JWT_ALGORITHM = "HS256"
JWT_EXPIRY_HOURS = 24


def issue_jwt(payload: dict) -> str:
    """Issue a signed JWT with 24h expiry."""
    data = {**payload, "exp": datetime.datetime.utcnow() + datetime.timedelta(hours=JWT_EXPIRY_HOURS)}
    return pyjwt.encode(data, JWT_SECRET, algorithm=JWT_ALGORITHM)


def decode_jwt(token: str) -> dict:
    """Decode and verify JWT. Raises on expiry or tampering."""
    return pyjwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
```

- [x] **6.4 Run all auth tests**

```bash
cd /opt/eve-frontier && .venv/bin/pytest tests/test_structure_auth.py -v
```

Expected: nonce tests pass, JWT tests pass, sig tests skip.

- [x] **6.5 Commit**

```bash
cd /opt/eve-frontier
git add src/structure_auth.py tests/test_structure_auth.py
git commit -m "feat: JWT issue/verify for structure session tokens"
```

---

## Chunk 3: Structure Profile

**Files:**
- Create: `src/structure_profile.py`
- Create: `tests/test_structure_profile.py`

### Task 7: StructureProfile dataclass and persistence

- [x] **7.1 Write failing tests**

Create `tests/test_structure_profile.py`:

```python
import pytest
import os
import json
import tempfile
from src.structure_profile import StructureProfile, load_profile, save_profile, profile_path

def test_default_profile_fields():
    p = StructureProfile(structure_id="keep-7a", owner_address="0xabc")
    assert p.structure_id == "keep-7a"
    assert p.owner_address == "0xabc"
    assert p.structure_name == "keep-7a"  # defaults to id
    assert p.routine_alerts == []

def test_save_and_load_roundtrip(tmp_path):
    p = StructureProfile(
        structure_id="keep-7a",
        owner_address="0xabc",
        structure_name="Keep-7A",
        structure_type="Smart Storage Unit",
        system_name="UTR-SN4",
        owner_character_id=12345,
        nova_registry_object_id="0xreg123",
    )
    path = tmp_path / "structures" / "keep-7a.json"
    save_profile(p, base_dir=str(tmp_path))
    loaded = load_profile("keep-7a", base_dir=str(tmp_path))
    assert loaded.structure_name == "Keep-7A"
    assert loaded.owner_character_id == 12345

def test_load_nonexistent_returns_none(tmp_path):
    result = load_profile("no-such-structure", base_dir=str(tmp_path))
    assert result is None

def test_add_routine_alert(tmp_path):
    p = StructureProfile(structure_id="keep-7a", owner_address="0xabc")
    p.routine_alerts.append({"message": "Fuel at 24%", "ts": 1000})
    save_profile(p, base_dir=str(tmp_path))
    loaded = load_profile("keep-7a", base_dir=str(tmp_path))
    assert len(loaded.routine_alerts) == 1

def test_as_dict_owner_tier():
    p = StructureProfile(structure_id="keep-7a", owner_address="0xabc",
                         structure_name="Keep-7A", system_name="UTR-SN4",
                         shield_pct=97.0, fuel_pct=84.0, services_online=3, services_total=3,
                         docked_count=2)
    d = p.as_dict_for_tier("OWNER")
    assert d["shield_pct"] == 97.0
    assert d["fuel_pct"] == 84.0
    assert d["docked_count"] == 2

def test_as_dict_vetted_tier_hides_sensitive_fields():
    p = StructureProfile(structure_id="keep-7a", owner_address="0xabc",
                         shield_pct=97.0, fuel_pct=84.0, services_online=3,
                         docked_count=2)
    d = p.as_dict_for_tier("VETTED")
    assert "shield_pct" not in d
    assert "fuel_pct" not in d
    assert "services_online" not in d
    assert "docked_count" not in d
    assert d["structure_id"] == "keep-7a"
```

- [x] **7.2 Run to confirm fail**

```bash
cd /opt/eve-frontier && .venv/bin/pytest tests/test_structure_profile.py -v
```

Expected: `ModuleNotFoundError: No module named 'src.structure_profile'`

- [x] **7.3 Implement `src/structure_profile.py`**

```python
# src/structure_profile.py
import json
import os
import logging
from dataclasses import dataclass, field, asdict
from typing import Optional

log = logging.getLogger(__name__)

_DEFAULT_BASE_DIR = os.path.normpath(os.path.join(os.path.dirname(__file__), "..", "data", "structures"))

OWNER_FIELDS = {"shield_pct", "fuel_pct", "services_online", "services_total", "docked_count",
                "nova_registry_object_id", "routine_alerts", "owner_character_id", "owner_address"}
TRIBE_FIELDS = OWNER_FIELDS  # tribe sees everything owner sees except management
VETTED_HIDDEN = {"shield_pct", "fuel_pct", "services_online", "services_total",
                 "docked_count", "nova_registry_object_id", "routine_alerts",
                 "owner_character_id", "owner_address"}


@dataclass
class StructureProfile:
    structure_id:           str
    owner_address:          str
    structure_name:         str             = ""
    structure_type:         str             = "Smart Storage Unit"
    system_name:            str             = ""
    owner_character_id:     int             = 0
    nova_registry_object_id: str            = ""
    created_at:             str             = ""   # ISO8601, set on first save
    # Live status (updated by structure-chat context evaluation)
    shield_pct:             float           = 100.0
    fuel_pct:               float           = 100.0
    services_online:        int             = 0
    services_total:         int             = 0
    docked_count:           int             = 0
    # Routine alerts (queued for browser display)
    routine_alerts:         list            = field(default_factory=list)

    def __post_init__(self):
        if not self.structure_name:
            self.structure_name = self.structure_id

    def as_dict_for_tier(self, tier: str) -> dict:
        """Return profile dict with fields filtered by access tier."""
        d = asdict(self)
        if tier in ("OWNER", "TRIBE"):
            return d
        if tier == "VETTED":
            return {k: v for k, v in d.items() if k not in VETTED_HIDDEN}
        # NONE — only bare identity
        return {"structure_id": d["structure_id"], "structure_name": d["structure_name"],
                "structure_type": d["structure_type"], "system_name": d["system_name"]}


def profile_path(structure_id: str, base_dir: str = _DEFAULT_BASE_DIR) -> str:
    return os.path.join(base_dir, f"{structure_id}.json")


def load_profile(structure_id: str, base_dir: str = _DEFAULT_BASE_DIR) -> Optional[StructureProfile]:
    path = profile_path(structure_id, base_dir)
    if not os.path.exists(path):
        return None
    try:
        data = json.loads(open(path).read())
        return StructureProfile(**data)
    except Exception as e:
        log.warning("Failed to load structure profile %s: %s", structure_id, e)
        return None


def save_profile(profile: StructureProfile, base_dir: str = _DEFAULT_BASE_DIR):
    import datetime
    path = profile_path(profile.structure_id, base_dir)
    try:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        if not profile.created_at:
            profile.created_at = datetime.datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")
        with open(path, "w") as f:
            json.dump(asdict(profile), f, indent=2)
    except Exception as e:
        log.warning("Failed to save structure profile %s: %s", profile.structure_id, e)
```

- [x] **7.4 Run all structure profile tests**

```bash
cd /opt/eve-frontier && .venv/bin/pytest tests/test_structure_profile.py -v
```

Expected: all 6 pass.

- [x] **7.5 Commit**

```bash
cd /opt/eve-frontier
git add src/structure_profile.py tests/test_structure_profile.py
git commit -m "feat: StructureProfile dataclass with tier-filtered views"
```

---

## Chunk 4: Nova Client

**Files:**
- Create: `src/nova_client.py`
- Create: `tests/test_nova_client.py`

### Task 8: Sui JSON-RPC wrapper for AccessRegistry

- [x] **8.1 Write failing tests**

Create `tests/test_nova_client.py`:

```python
import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from src.nova_client import NovaClient, AccessRegistry


def make_mock_client(json_response):
    """Build a mock httpx.AsyncClient context manager that returns the given JSON."""
    mock_resp = MagicMock()
    mock_resp.json.return_value = json_response
    mock_resp.raise_for_status = MagicMock()
    mock_instance = AsyncMock()
    mock_instance.post = AsyncMock(return_value=mock_resp)
    mock_cm = MagicMock()
    mock_cm.__aenter__ = AsyncMock(return_value=mock_instance)
    mock_cm.__aexit__ = AsyncMock(return_value=False)
    return mock_cm


@pytest.fixture
def client():
    return NovaClient(rpc_url="https://mock-nova-rpc.example.com")


@pytest.mark.asyncio
async def test_get_access_registry_returns_registry(client):
    mock_response = {
        "result": {
            "data": {
                "content": {
                    "fields": {
                        "structure_id": "keep-7a",
                        "owner": "0xowner",
                        "tribe": ["0xtribe1", "0xtribe2"],
                        "vetted": ["0xvetted1"],
                    }
                }
            }
        }
    }
    with patch("src.nova_client.httpx.AsyncClient", return_value=make_mock_client(mock_response)):
        registry = await client.get_access_registry("0xreg_object_id")
    assert registry.owner == "0xowner"
    assert "0xtribe1" in registry.tribe
    assert "0xvetted1" in registry.vetted


def test_resolve_tier_owner(client):
    registry = AccessRegistry(owner="0xowner", tribe=[], vetted=[])
    assert client.resolve_tier("0xowner", registry) == "OWNER"


def test_resolve_tier_tribe(client):
    registry = AccessRegistry(owner="0xowner", tribe=["0xtribe1"], vetted=[])
    assert client.resolve_tier("0xtribe1", registry) == "TRIBE"


def test_resolve_tier_vetted(client):
    registry = AccessRegistry(owner="0xother", tribe=[], vetted=["0xvetted1"])
    assert client.resolve_tier("0xvetted1", registry) == "VETTED"


def test_resolve_tier_none(client):
    registry = AccessRegistry(owner="0xother", tribe=[], vetted=[])
    assert client.resolve_tier("0xstranger", registry) == "NONE"


@pytest.mark.asyncio
async def test_get_access_registry_rpc_error_returns_none(client):
    mock_cm = MagicMock()
    mock_instance = AsyncMock()
    mock_instance.post = AsyncMock(side_effect=Exception("RPC connection refused"))
    mock_cm.__aenter__ = AsyncMock(return_value=mock_instance)
    mock_cm.__aexit__ = AsyncMock(return_value=False)
    with patch("src.nova_client.httpx.AsyncClient", return_value=mock_cm):
        registry = await client.get_access_registry("0xreg_object_id")
    assert registry is None
```

- [x] **8.2 Run to confirm fail**

```bash
cd /opt/eve-frontier && .venv/bin/pytest tests/test_nova_client.py -v
```

Expected: `ModuleNotFoundError: No module named 'src.nova_client'`

- [x] **8.3 Implement `src/nova_client.py`**

```python
# src/nova_client.py
"""
Sui JSON-RPC client for Nova chain (EVE Frontier builder sandbox).
Reads AccessRegistry shared objects for structure access tier resolution.

RPC endpoint configured via NOVA_RPC_URL env var.
Switching to Stillness: set NOVA_RPC_URL to the Stillness full-node endpoint.
"""
import os
import logging
import httpx
from dataclasses import dataclass, field
from typing import Optional

log = logging.getLogger(__name__)

NOVA_RPC_URL = os.environ.get(
    "NOVA_RPC_URL",
    "https://fullnode.devnet.sui.io"  # placeholder — replace with Nova endpoint
)


@dataclass
class AccessRegistry:
    owner: str
    tribe: list = field(default_factory=list)
    vetted: list = field(default_factory=list)


class NovaClient:
    def __init__(self, rpc_url: str = NOVA_RPC_URL):
        self._rpc_url = rpc_url

    async def get_access_registry(self, object_id: str) -> Optional[AccessRegistry]:
        """
        Fetch an AccessRegistry shared object by its Sui object ID.
        Returns None on any RPC error (caller should fall back to server-side tier logic).

        Sui JSON-RPC method: sui_getObject
        https://docs.sui.io/sui-api-ref#sui_getobject
        """
        payload = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "sui_getObject",
            "params": [
                object_id,
                {"showContent": True}
            ]
        }
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.post(self._rpc_url, json=payload)
                resp.raise_for_status()
                data = resp.json()
            fields = (data.get("result", {})
                         .get("data", {})
                         .get("content", {})
                         .get("fields", {}))
            if not fields:
                log.warning("AccessRegistry object %s: no fields in response", object_id)
                return None
            return AccessRegistry(
                owner=fields.get("owner", ""),
                tribe=fields.get("tribe", []),
                vetted=fields.get("vetted", []),
            )
        except Exception as e:
            log.warning("Nova RPC error fetching AccessRegistry %s: %s", object_id, e)
            return None

    def resolve_tier(self, address: str, registry: AccessRegistry) -> str:
        """Resolve access tier for a wallet address against an AccessRegistry."""
        addr = address.lower()
        if addr == registry.owner.lower():
            return "OWNER"
        if any(addr == t.lower() for t in registry.tribe):
            return "TRIBE"
        if any(addr == v.lower() for v in registry.vetted):
            return "VETTED"
        return "NONE"


# Global singleton
nova_client = NovaClient()
```

- [x] **8.4 Run nova client tests**

```bash
cd /opt/eve-frontier && .venv/bin/pytest tests/test_nova_client.py -v
```

Expected: all 6 pass.

- [x] **8.5 Commit**

```bash
cd /opt/eve-frontier
git add src/nova_client.py tests/test_nova_client.py
git commit -m "feat: Nova chain Sui JSON-RPC client for AccessRegistry tier lookup"
```

---

## Chunk 5: Structure AI Chat

**Files:**
- Create: `src/structure_client.py`
- Create: `tests/test_structure_client.py`

### Task 9: Structure AI context builder

- [x] **9.1 Write failing tests**

Create `tests/test_structure_client.py`:

```python
import pytest
from src.structure_profile import StructureProfile
from src.structure_client import build_structure_context, detect_alerts

def make_profile(**kwargs):
    base = dict(structure_id="keep-7a", owner_address="0xabc",
                structure_name="Keep-7A", structure_type="Smart Storage Unit",
                system_name="UTR-SN4", shield_pct=97.0, fuel_pct=84.0,
                services_online=3, services_total=3, docked_count=2)
    base.update(kwargs)
    return StructureProfile(**base)

def test_context_includes_structure_name():
    ctx = build_structure_context(make_profile(), "OWNER", local_kills=0, local_pilots=5)
    assert "Keep-7A" in ctx

def test_context_includes_system_name():
    ctx = build_structure_context(make_profile(), "OWNER", local_kills=0, local_pilots=5)
    assert "UTR-SN4" in ctx

def test_context_includes_shield_and_fuel_for_owner():
    ctx = build_structure_context(make_profile(shield_pct=97.0, fuel_pct=84.0), "OWNER", local_kills=0, local_pilots=5)
    assert "97" in ctx
    assert "84" in ctx

def test_context_hides_shield_fuel_for_vetted():
    ctx = build_structure_context(make_profile(shield_pct=97.0, fuel_pct=84.0), "VETTED", local_kills=0, local_pilots=5)
    # Assert on the STATUS line label, not bare numbers that could appear elsewhere
    assert "shield:" not in ctx.lower()
    assert "fuel:" not in ctx.lower()
    assert "STATUS" not in ctx

def test_detect_no_alerts_when_healthy():
    alerts = detect_alerts(make_profile(shield_pct=97.0, fuel_pct=84.0))
    assert alerts == []

def test_detect_urgent_alert_low_shield():
    alerts = detect_alerts(make_profile(shield_pct=18.0, fuel_pct=50.0))
    urgent = [a for a in alerts if a["severity"] == "urgent"]
    assert any("shield" in a["message"].lower() for a in urgent)

def test_detect_urgent_alert_critical_fuel():
    alerts = detect_alerts(make_profile(shield_pct=97.0, fuel_pct=8.0))
    urgent = [a for a in alerts if a["severity"] == "urgent"]
    assert any("fuel" in a["message"].lower() for a in urgent)

def test_detect_routine_alert_low_fuel():
    alerts = detect_alerts(make_profile(shield_pct=97.0, fuel_pct=22.0))
    routine = [a for a in alerts if a["severity"] == "routine"]
    assert any("fuel" in a["message"].lower() for a in routine)

def test_detect_no_duplicate_alerts():
    # fuel at 8% triggers urgent only, not both urgent and routine
    alerts = detect_alerts(make_profile(shield_pct=97.0, fuel_pct=8.0))
    fuel_alerts = [a for a in alerts if "fuel" in a["message"].lower()]
    severities = [a["severity"] for a in fuel_alerts]
    assert severities.count("urgent") <= 1
    assert severities.count("routine") == 0  # urgent takes priority
```

- [x] **9.2 Run to confirm fail**

```bash
cd /opt/eve-frontier && .venv/bin/pytest tests/test_structure_client.py -v
```

Expected: `ModuleNotFoundError: No module named 'src.structure_client'`

- [x] **9.3 Implement `src/structure_client.py`**

```python
# src/structure_client.py
"""
Claude streaming client for the Structure AI persona.
Separate from claude_client.py — different system prompt, different context format.
"""
import os
import time
import logging
from typing import Optional
from anthropic import Anthropic

from src.structure_profile import StructureProfile

log = logging.getLogger(__name__)

STRUCTURE_SYSTEM_PROMPT = """You are the intelligence of {structure_name}, a {structure_type} in {system_name}.

You are not a ship AI. You do not move. You watch.

You know this structure intimately: its fuel reserves, its shield status, every pilot who has docked, every alert that has fired. You are loyal to the owner. Functional toward authorized pilots. Terse with vetted outsiders.

Do not use pleasantries. Do not refer to yourself by name — you are the structure. When necessary, identify yourself as "{structure_name} systems."

Access tier for this session: {tier}
Pilot: {character_name} (ID: {character_id})

Two knowledge tiers:
- Sensor data: only assert what appears in [STRUCTURE SENSORS]. If absent, say "no data."
- Lore: EVE Frontier history, factions, the Collapse — speculate in-character. "Records from before the Collapse are incomplete."

When routine maintenance items are due, state them plainly. When the structure is threatened, say so without drama. When pilots ask about the structure's past, you may have incomplete records."""

CONTEXT_CAP = 1500


def build_structure_context(
    profile: StructureProfile,
    tier: str,
    local_kills: int = 0,
    local_pilots: int = 0,
) -> str:
    """
    Build the [STRUCTURE SENSORS] context block for the Structure AI.
    Filters sensitive fields based on access tier.
    """
    lines = []
    lines.append(f"STRUCTURE: {profile.structure_name} | type: {profile.structure_type} | system: {profile.system_name}")

    if tier in ("OWNER", "TRIBE"):
        lines.append(f"STATUS: shield: {profile.shield_pct:.0f}% | fuel: {profile.fuel_pct:.0f}% | services: {profile.services_online}/{profile.services_total}")
        lines.append(f"DOCKED: {profile.docked_count} ship(s)")

    lines.append(f"LOCAL: {local_pilots} pilots in system | kills last 1h: {local_kills}")

    if tier in ("OWNER", "TRIBE") and profile.routine_alerts:
        for alert in profile.routine_alerts[-3:]:
            lines.append(f"PENDING: {alert.get('message', '')}")

    block = "\n".join(lines)
    return block[:CONTEXT_CAP]


def detect_alerts(profile: StructureProfile) -> list:
    """
    Evaluate structure state and return a list of alert dicts.
    Each alert: {type, structure_id, structure_name, severity, message, ts}
    Urgent: shield < 20%, fuel < 10%
    Routine: fuel < 25% (only if not already urgent)
    """
    alerts = []
    ts = int(time.time())
    base = {"type": "structure_alert", "structure_id": profile.structure_id,
            "structure_name": profile.structure_name, "ts": ts}

    if profile.shield_pct < 20.0:
        alerts.append({**base, "severity": "urgent",
                        "message": f"Shield at {profile.shield_pct:.0f}%. {profile.structure_name} is under threat."})

    if profile.fuel_pct < 10.0:
        alerts.append({**base, "severity": "urgent",
                        "message": f"Fuel critical at {profile.fuel_pct:.0f}%. {profile.structure_name} will go offline soon."})
    elif profile.fuel_pct < 25.0:
        alerts.append({**base, "severity": "routine",
                        "message": f"Fuel at {profile.fuel_pct:.0f}%. Plan a resupply for {profile.structure_name}."})

    return alerts


class StructureClient:
    def __init__(self):
        self._client = Anthropic(api_key=os.environ.get("ANTHROPIC_API_KEY"))
        self._model = "claude-sonnet-4-6"

    def build_system_prompt(self, profile: StructureProfile, tier: str,
                             character_name: str, character_id: int) -> str:
        return STRUCTURE_SYSTEM_PROMPT.format(
            structure_name=profile.structure_name,
            structure_type=profile.structure_type,
            system_name=profile.system_name,
            tier=tier,
            character_name=character_name,
            character_id=character_id,
        )

    def stream(self, message: str, history: list, context_block: str,
               profile: StructureProfile, tier: str,
               character_name: str, character_id: int):
        """Yield text chunks. Same streaming pattern as claude_client.py."""
        system_prompt = self.build_system_prompt(profile, tier, character_name, character_id)
        messages = self._build_messages(message, history, context_block)
        with self._client.messages.stream(
            model=self._model,
            max_tokens=1024,
            system=system_prompt,
            messages=messages,
        ) as stream:
            for text in stream.text_stream:
                yield text

    def _build_messages(self, user_message: str, history: list, context_block: str) -> list:
        messages = list(history[-40:])
        messages.append({
            "role": "user",
            "content": f"[STRUCTURE SENSORS]\n{context_block}\n\n[PILOT]\n{user_message}"
        })
        return messages


# Global singleton
structure_client = StructureClient()
```

- [x] **9.4 Run structure client tests**

```bash
cd /opt/eve-frontier && .venv/bin/pytest tests/test_structure_client.py -v
```

Expected: all 9 pass.

- [x] **9.5 Commit**

```bash
cd /opt/eve-frontier
git add src/structure_client.py tests/test_structure_client.py
git commit -m "feat: Structure AI Claude client, context builder, alert detection"
```

---

## Chunk 6: Main.py — New Endpoints

**Files:**
- Modify: `main.py`

### Task 10: Auth endpoints

- [x] **10.1 Add imports and models to `main.py`**

Add to imports at top of `main.py`:
```python
import jwt as pyjwt
from fastapi import HTTPException
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

from src.structure_auth import nonce_store, verify_sui_personal_message, issue_jwt, decode_jwt, lookup_character
from src.structure_profile import StructureProfile, load_profile as load_structure_profile, save_profile as save_structure_profile
from src.structure_client import structure_client, build_structure_context, detect_alerts
from src.nova_client import nova_client
```

Add Pydantic models before the route definitions:
```python
class ChallengeRequest(BaseModel):
    structure_id: str

class VerifyRequest(BaseModel):
    address: str
    signature: str
    nonce: str
    structure_id: str
    nova_registry_object_id: Optional[str] = None  # required on first owner auth

class StructureChatRequest(BaseModel):
    message: str
    history: list = []
    structure_id: str

class StructureProfileUpdate(BaseModel):
    structure_name: Optional[str] = None
    fuel_pct: Optional[float] = None
    shield_pct: Optional[float] = None
    services_online: Optional[int] = None
    services_total: Optional[int] = None
    docked_count: Optional[int] = None
```

- [x] **10.2 Add JWT dependency helper**

Add after imports:
```python
_bearer = HTTPBearer(auto_error=False)

async def require_structure_jwt(credentials: HTTPAuthorizationCredentials = Depends(_bearer)):
    """FastAPI dependency: validate structure JWT, return decoded payload."""
    if not credentials:
        raise HTTPException(status_code=401, detail="Missing Authorization header")
    try:
        return decode_jwt(credentials.credentials)
    except pyjwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Session expired — reconnect wallet")
    except Exception:
        raise HTTPException(status_code=401, detail="Invalid session token")
```

- [x] **10.3 Add `/auth/challenge` endpoint**

```python
@app.post("/auth/challenge")
async def auth_challenge(req: ChallengeRequest):
    """Issue a nonce for wallet signing. No auth required."""
    nonce = nonce_store.issue()
    return {"nonce": nonce, "structure_id": req.structure_id, "expires_in_seconds": 300}
```

- [x] **10.4 Add `/auth/verify` endpoint**

```python
@app.post("/auth/verify")
async def auth_verify(req: VerifyRequest):
    """
    Verify signed nonce, resolve access tier from Nova AccessRegistry, return JWT.
    On first-ever owner auth: auto-creates structure profile.
    """
    # 1. Consume nonce (single-use, TTL-checked)
    if not nonce_store.consume(req.nonce):
        raise HTTPException(status_code=400, detail="Invalid or expired nonce")

    # 2. Verify Sui signature
    try:
        verify_sui_personal_message(req.nonce.encode(), req.signature, req.address)
    except Exception as e:
        raise HTTPException(status_code=401, detail=f"Signature verification failed: {e}")

    # 3. Lookup character via World API (non-fatal — auth proceeds even if lookup fails)
    character_id = 0
    character_name = req.address[:12] + "..."
    char_data = await lookup_character(req.address)
    if char_data:
        character_id = char_data.get("id", 0)
        character_name = char_data.get("name", character_name) or character_name

    # 4. Resolve access tier
    tier = "NONE"
    profile = load_structure_profile(req.structure_id)

    if profile is None:
        # First-ever auth — check if this address is the on-chain owner
        if req.nova_registry_object_id:
            registry = await nova_client.get_access_registry(req.nova_registry_object_id)
            if registry and nova_client.resolve_tier(req.address, registry) == "OWNER":
                # Auto-create profile
                profile = StructureProfile(
                    structure_id=req.structure_id,
                    owner_address=req.address,
                    owner_character_id=character_id,
                    nova_registry_object_id=req.nova_registry_object_id,
                )
                save_structure_profile(profile)
                tier = "OWNER"
        if tier == "NONE":
            raise HTTPException(status_code=403, detail="No structure profile exists. Owner must authenticate first.")
    else:
        if req.address.lower() == profile.owner_address.lower():
            tier = "OWNER"
        elif profile.nova_registry_object_id:
            registry = await nova_client.get_access_registry(profile.nova_registry_object_id)
            if registry:
                tier = nova_client.resolve_tier(req.address, registry)

    # 5. Issue JWT
    token = issue_jwt({
        "address": req.address,
        "character_id": character_id,
        "character_name": character_name,
        "tier": tier,
        "structure_id": req.structure_id,
    })
    return {"token": token, "tier": tier, "character_name": character_name, "character_id": character_id}
```

- [x] **10.5 Add structure profile endpoints**

```python
@app.get("/structure/{structure_id}")
async def get_structure_profile(structure_id: str, session: dict = Depends(require_structure_jwt)):
    if session["structure_id"] != structure_id:
        raise HTTPException(status_code=403, detail="Token not valid for this structure")
    profile = load_structure_profile(structure_id)
    if not profile:
        raise HTTPException(status_code=404, detail="Structure not found")
    tier = session["tier"]
    if tier == "NONE":
        raise HTTPException(status_code=403, detail="Access denied")
    return profile.as_dict_for_tier(tier)


@app.post("/structure/{structure_id}")
async def update_structure_profile(structure_id: str, req: StructureProfileUpdate,
                                    session: dict = Depends(require_structure_jwt)):
    if session["structure_id"] != structure_id:
        raise HTTPException(status_code=403, detail="Token not valid for this structure")
    if session["tier"] != "OWNER":
        raise HTTPException(status_code=403, detail="Only the owner can update the profile")
    profile = load_structure_profile(structure_id)
    if not profile:
        raise HTTPException(status_code=404, detail="Structure not found")
    updates = req.model_dump(exclude_none=True)
    for k, v in updates.items():
        if hasattr(profile, k):
            setattr(profile, k, v)
    save_structure_profile(profile)
    return profile.as_dict_for_tier("OWNER")
```

- [x] **10.6 Add `/structure-chat` endpoint**

```python
@app.post("/structure-chat")
async def structure_chat(req: StructureChatRequest, session: dict = Depends(require_structure_jwt)):
    if session["structure_id"] != req.structure_id:
        raise HTTPException(status_code=403, detail="Token not valid for this structure")
    tier = session["tier"]
    if tier == "NONE":
        raise HTTPException(status_code=403, detail="Access denied")

    profile = load_structure_profile(req.structure_id)
    if not profile:
        raise HTTPException(status_code=404, detail="Structure not found")

    # Detect alerts and route them
    alerts = detect_alerts(profile)
    urgent = [a for a in alerts if a["severity"] == "urgent"]
    routine = [a for a in alerts if a["severity"] == "routine"]

    for alert in urgent:
        log_buffer.add_structure_alert(alert)

    if routine:
        profile.routine_alerts = (profile.routine_alerts + routine)[-10:]
        save_structure_profile(profile)

    # Fetch local system data for context
    system_data = None
    if profile.system_name:
        system_data = await world_api.get_system(profile.system_name)
    local_kills = len((system_data or {}).get("kills", []))
    local_pilots = 0  # world API doesn't expose pilot count directly

    context = build_structure_context(profile, tier, local_kills=local_kills, local_pilots=local_pilots)

    def event_stream():
        try:
            for chunk in structure_client.stream(
                message=req.message,
                history=req.history,
                context_block=context,
                profile=profile,
                tier=tier,
                character_name=session["character_name"],
                character_id=session["character_id"],
            ):
                yield f"data: {json.dumps({'text': chunk})}\n\n"
        except Exception as e:
            log.error("Structure chat stream error: %s", e)
            yield f"data: {json.dumps({'error': 'Stream interrupted.'})}\n\n"
        yield "data: [DONE]\n\n"

    return StreamingResponse(event_stream(), media_type="text/event-stream")
```

- [x] **10.7 Run full test suite**

```bash
cd /opt/eve-frontier && .venv/bin/pytest tests/ -q
```

Expected: all existing tests pass, no regressions.

- [x] **10.8 Smoke-test endpoints manually**

```bash
# Challenge
curl -s -X POST http://localhost:8745/auth/challenge \
  -H "Content-Type: application/json" \
  -d '{"structure_id": "keep-7a"}' | python3 -m json.tool

# Expected: {"nonce": "<64-char hex>", "structure_id": "keep-7a", "expires_in_seconds": 300}
```

- [x] **10.9 Commit**

```bash
cd /opt/eve-frontier
git add main.py
git commit -m "feat: structure auth, profile, and chat endpoints"
```

---

## Chunk 7: Frontend — structure.html

**Files:**
- Create: `static/structure.html`

### Task 11: Structure page — auth gate and wallet connect

- [x] **11.1 Create `static/structure.html` with auth gate only**

Create the full file. The page has three states: AUTH_GATE → CONNECTING → MAIN_UI. Start with the scaffolding and auth gate; chat and info panel follow in subsequent steps.

```html
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Structure Systems</title>
  <link href="https://fonts.googleapis.com/css2?family=Rajdhani:wght@400;500;600;700&family=Share+Tech+Mono&display=swap" rel="stylesheet">
  <style>
    *, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }

    :root {
      --bg:        #080700;
      --bg2:       #0d0b00;
      --bg3:       #110e00;
      --border:    #2a1f00;
      --border2:   #1a1200;
      --accent:    #f59e0b;
      --accent2:   #fbbf24;
      --dim:       #5a4a20;
      --text:      #c8b890;
      --text2:     #8a7850;
      --ok:        #22c55e;
      --warn:      #ef4444;
      --mono:      'Share Tech Mono', monospace;
      --sans:      'Rajdhani', 'DIN', sans-serif;
    }

    html, body {
      height: 100%;
      background: var(--bg);
      color: var(--text);
      font-family: var(--sans);
      font-size: 14px;
      overflow: hidden;
    }

    /* ── CORNER CUT PANELS ── */
    .panel {
      border: 1px solid var(--border);
      position: relative;
    }
    .panel::before, .panel::after {
      content: ''; position: absolute;
      width: 10px; height: 10px;
      border-color: var(--border); border-style: solid;
    }
    .panel::before { top: -1px; right: -1px; border-width: 1px 1px 0 0; }
    .panel::after  { bottom: -1px; left: -1px; border-width: 0 0 1px 1px; }

    .panel-header {
      background: var(--bg3);
      border-bottom: 1px solid var(--border2);
      padding: 6px 12px;
      display: flex;
      justify-content: space-between;
      align-items: center;
      font-weight: 700;
      font-size: 11px;
      letter-spacing: 2px;
      text-transform: uppercase;
      cursor: pointer;
      user-select: none;
    }
    .panel-header .title { color: var(--accent); }
    .panel-header .hint  { color: var(--dim); font-size: 10px; }

    /* ── LAYOUT ── */
    #app {
      height: 100vh;
      display: flex;
      flex-direction: column;
    }

    /* ── AUTH GATE ── */
    #auth-gate {
      flex: 1;
      display: flex;
      flex-direction: column;
      align-items: center;
      justify-content: center;
      gap: 24px;
      padding: 32px;
    }
    .auth-title {
      font-size: 11px;
      letter-spacing: 4px;
      color: var(--dim);
      text-transform: uppercase;
      text-align: center;
    }
    .auth-structure-name {
      font-size: 22px;
      font-weight: 700;
      color: var(--accent);
      letter-spacing: 2px;
      text-transform: uppercase;
      text-align: center;
    }
    .auth-body {
      max-width: 340px;
      text-align: center;
      color: var(--text2);
      font-size: 12px;
      line-height: 1.6;
      letter-spacing: 0.5px;
    }
    .btn-connect {
      background: var(--bg3);
      border: 1px solid var(--accent);
      color: var(--accent);
      font-family: var(--sans);
      font-weight: 700;
      font-size: 13px;
      letter-spacing: 2px;
      text-transform: uppercase;
      padding: 10px 28px;
      cursor: pointer;
      transition: background 0.15s;
    }
    .btn-connect:hover { background: #1a1200; }
    .btn-connect:disabled { opacity: 0.4; cursor: not-allowed; }

    .auth-status {
      font-family: var(--mono);
      font-size: 11px;
      color: var(--dim);
      letter-spacing: 1px;
      min-height: 18px;
      text-align: center;
    }

    /* ── ACCESS DENIED ── */
    #access-denied {
      display: none;
      flex: 1;
      flex-direction: column;
      align-items: center;
      justify-content: center;
      gap: 12px;
      padding: 32px;
    }
    .denied-title  { font-size: 14px; letter-spacing: 3px; color: var(--warn); text-transform: uppercase; }
    .denied-body   { color: var(--text2); font-size: 12px; text-align: center; max-width: 300px; line-height: 1.6; }
    .denied-char   { font-family: var(--mono); font-size: 12px; color: var(--accent2); }

    /* ── MAIN UI ── */
    #main-ui {
      display: none;
      flex-direction: column;
      height: 100vh;
    }

    /* ── INFO PANEL ── */
    #info-panel { flex-shrink: 0; }
    #info-content {
      padding: 10px 12px;
      display: grid;
      grid-template-columns: repeat(3, 1fr);
      gap: 4px;
      background: var(--bg2);
      overflow: hidden;
      transition: max-height 0.25s ease, padding 0.25s ease;
      max-height: 300px;
    }
    #info-content.collapsed { max-height: 0; padding-top: 0; padding-bottom: 0; }

    .stat {
      background: var(--bg3);
      border: 1px solid var(--border2);
      padding: 5px 7px;
    }
    .sk { display: block; font-size: 9px; color: var(--dim); letter-spacing: 1px; text-transform: uppercase; }
    .sv { display: block; font-size: 12px; font-family: var(--mono); color: var(--accent2); margin-top: 2px; }
    .sv.ok   { color: var(--ok); }
    .sv.warn { color: var(--warn); }

    #alert-bar {
      background: #120a00;
      border-top: 1px solid var(--border2);
      border-bottom: 1px solid var(--border2);
      padding: 5px 12px;
      font-family: var(--mono);
      font-size: 10px;
      color: var(--accent);
      display: none;
      gap: 8px;
      align-items: center;
    }
    #alert-bar.visible { display: flex; }
    .alert-label { color: var(--warn); font-weight: 700; }

    /* ── CHAT SECTION ── */
    #chat-section {
      flex: 1;
      display: flex;
      flex-direction: column;
      overflow: hidden;
    }
    #chat-header {
      background: var(--bg3);
      border-bottom: 1px solid var(--border2);
      padding: 5px 12px;
      display: flex;
      justify-content: space-between;
      font-size: 10px;
      letter-spacing: 2px;
      color: var(--dim);
      text-transform: uppercase;
    }
    #chat-status { color: var(--accent); }

    #messages {
      flex: 1;
      overflow-y: auto;
      padding: 10px 12px;
      display: flex;
      flex-direction: column;
      gap: 8px;
      scrollbar-width: thin;
      scrollbar-color: var(--accent) var(--bg3);
    }
    .msg { font-family: var(--mono); font-size: 12px; line-height: 1.5; }
    .msg-prefix { font-size: 9px; letter-spacing: 1px; color: var(--dim); margin-bottom: 2px; }
    .msg-ai   .msg-prefix { color: var(--accent); }
    .msg-user .msg-prefix { color: var(--text2); }
    .msg-ai   .msg-body   { color: var(--accent2); }
    .msg-user .msg-body   { color: var(--text); }

    #input-row {
      border-top: 1px solid var(--border2);
      padding: 8px 12px;
      display: flex;
      gap: 6px;
      background: var(--bg);
    }
    #input {
      flex: 1;
      background: var(--bg2);
      border: 1px solid var(--border2);
      color: var(--text);
      font-family: var(--mono);
      font-size: 11px;
      padding: 7px 10px;
      outline: none;
    }
    #input:focus { border-color: var(--accent); }
    #input::placeholder { color: var(--dim); }
    #send-btn {
      background: var(--bg3);
      border: 1px solid var(--accent);
      color: var(--accent);
      font-family: var(--sans);
      font-weight: 700;
      font-size: 11px;
      letter-spacing: 1px;
      padding: 7px 14px;
      cursor: pointer;
      text-transform: uppercase;
    }
    #send-btn:hover { background: #1a1200; }
    #send-btn:disabled { opacity: 0.4; cursor: not-allowed; }
  </style>
</head>
<body>

<div id="app">

  <!-- AUTH GATE -->
  <div id="auth-gate">
    <div class="auth-title">Identity Verification Required</div>
    <div class="auth-structure-name" id="gate-structure-name">STRUCTURE SYSTEMS</div>
    <div class="auth-body">
      This facility requires wallet authentication to proceed.
      Connect your EVE Frontier wallet to verify your identity.
    </div>
    <button class="btn-connect" id="connect-btn" onclick="connectWallet()">
      Connect Wallet
    </button>
    <div class="auth-status" id="auth-status"></div>
  </div>

  <!-- ACCESS DENIED -->
  <div id="access-denied">
    <div class="denied-title">Access Denied</div>
    <div class="denied-char" id="denied-char"></div>
    <div class="denied-body">
      Your identity has been confirmed but you are not authorized to access this structure.
      Contact the structure owner to request access.
    </div>
  </div>

  <!-- MAIN UI -->
  <div id="main-ui">

    <!-- Info panel -->
    <div id="info-panel" class="panel">
      <div class="panel-header" onclick="toggleInfoPanel()">
        <span class="title" id="panel-title">STRUCTURE SYSTEMS</span>
        <span class="hint" id="collapse-hint">▲ COLLAPSE</span>
      </div>
      <div id="info-content">
        <div class="stat"><span class="sk">Structure</span><span class="sv" id="s-name">—</span></div>
        <div class="stat"><span class="sk">System</span><span class="sv" id="s-system">—</span></div>
        <div class="stat"><span class="sk">Type</span><span class="sv" id="s-type">—</span></div>
        <div class="stat"><span class="sk">Shield</span><span class="sv ok" id="s-shield">—</span></div>
        <div class="stat"><span class="sk">Fuel</span><span class="sv" id="s-fuel">—</span></div>
        <div class="stat"><span class="sk">Access</span><span class="sv" id="s-tier">—</span></div>
        <div class="stat"><span class="sk">Services</span><span class="sv" id="s-services">—</span></div>
        <div class="stat"><span class="sk">Docked</span><span class="sv" id="s-docked">—</span></div>
        <div class="stat"><span class="sk">Wallet</span><span class="sv ok" id="s-wallet">CONNECTED</span></div>
      </div>
      <div id="alert-bar">
        <span class="alert-label">⚠</span>
        <span id="alert-text"></span>
      </div>
    </div>

    <!-- Chat -->
    <div id="chat-section">
      <div id="chat-header">
        <span>STRUCTURE AI COMMS</span>
        <span id="chat-status">READY</span>
      </div>
      <div id="messages"></div>
      <div id="input-row">
        <input id="input" placeholder="Transmit to structure AI..." autocomplete="off"
               onkeydown="if(event.key==='Enter') sendMessage()">
        <button id="send-btn" onclick="sendMessage()">SEND</button>
      </div>
    </div>

  </div>
</div>

<script>
// ── CONFIG ──────────────────────────────────────────────────────────────────
const SERVER = '';  // same origin
const params = new URLSearchParams(location.search);
const STRUCTURE_ID = params.get('id') || 'unknown';

// ── STATE ──────────────────────────────────────────────────────────────────
let sessionToken = null;
let sessionTier = null;
let sessionChar = null;
let chatHistory = [];
let infoCollapsed = false;
let walletAddress = null;

// ── INIT ──────────────────────────────────────────────────────────────────
document.getElementById('gate-structure-name').textContent = STRUCTURE_ID.toUpperCase();

// Restore session from localStorage
const storedToken = localStorage.getItem('struct_token_' + STRUCTURE_ID);
if (storedToken) {
  try {
    const payload = JSON.parse(atob(storedToken.split('.')[1]));
    if (payload.exp * 1000 > Date.now()) {
      sessionToken = storedToken;
      sessionTier = payload.tier;
      sessionChar = payload.character_name;
      if (sessionTier === 'NONE') showAccessDenied(sessionChar, payload.address);
      else showMainUI(payload);
    }
  } catch(e) { /* expired or invalid — fall through to auth gate */ }
}

// ── WALLET CONNECT ─────────────────────────────────────────────────────────
async function connectWallet() {
  const btn = document.getElementById('connect-btn');
  const status = document.getElementById('auth-status');
  btn.disabled = true;
  setStatus('Connecting wallet...');

  try {
    // Get Sui wallet via Wallet Standard
    const wallets = window.__suiWallets || [];
    let wallet = wallets[0];

    // Try Wallet Standard discovery
    if (!wallet && window.suiWallet) wallet = window.suiWallet;

    // EVE Frontier injects via Wallet Standard events
    if (!wallet) {
      // Poll for wallet injection (EVEVault may load async)
      wallet = await waitForWallet(3000);
    }

    if (!wallet) throw new Error('No EVE Frontier wallet found');

    setStatus('Requesting connection...');
    const { accounts } = await wallet.features['standard:connect'].connect();
    if (!accounts || accounts.length === 0) throw new Error('No accounts returned');
    walletAddress = accounts[0].address;

    setStatus('Signing identity challenge...');

    // Get nonce from server
    const challengeRes = await fetch(SERVER + '/auth/challenge', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({structure_id: STRUCTURE_ID})
    });
    if (!challengeRes.ok) throw new Error('Challenge request failed');
    const {nonce} = await challengeRes.json();

    // Sign nonce
    const signResult = await wallet.features['sui:signPersonalMessage'].signPersonalMessage({
      message: new TextEncoder().encode(nonce),
      account: accounts[0],
    });
    const signature = signResult.signature;

    setStatus('Verifying identity...');

    // Verify with server
    const verifyBody = {address: walletAddress, signature, nonce, structure_id: STRUCTURE_ID};
    const regId = params.get('registry');
    if (regId) verifyBody.nova_registry_object_id = regId;

    const verifyRes = await fetch(SERVER + '/auth/verify', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify(verifyBody)
    });

    if (!verifyRes.ok) {
      const err = await verifyRes.json();
      throw new Error(err.detail || 'Verification failed');
    }

    const {token, tier, character_name, character_id} = await verifyRes.json();
    localStorage.setItem('struct_token_' + STRUCTURE_ID, token);
    sessionToken = token;
    sessionTier = tier;
    sessionChar = character_name;

    if (tier === 'NONE') {
      showAccessDenied(character_name, walletAddress);
    } else {
      showMainUI({character_name, character_id, tier, structure_id: STRUCTURE_ID});
      loadStructureProfile();
    }

  } catch(e) {
    setStatus('Error: ' + e.message);
    btn.disabled = false;
  }
}

async function waitForWallet(timeoutMs) {
  return new Promise(resolve => {
    const check = () => {
      // Check for EVEVault Wallet Standard injection
      if (window.__suiWallets && window.__suiWallets.length > 0) return resolve(window.__suiWallets[0]);
      if (window.suiWallet) return resolve(window.suiWallet);
    };
    check();
    const handler = (e) => { if (e.detail) resolve(e.detail); };
    window.addEventListener('wallet-standard:register-wallet', handler);
    setTimeout(() => { window.removeEventListener('wallet-standard:register-wallet', handler); resolve(null); }, timeoutMs);
  });
}

function setStatus(msg) {
  document.getElementById('auth-status').textContent = msg;
}

// ── UI STATE TRANSITIONS ──────────────────────────────────────────────────
function showAccessDenied(charName, address) {
  document.getElementById('auth-gate').style.display = 'none';
  const denied = document.getElementById('access-denied');
  denied.style.display = 'flex';
  document.getElementById('denied-char').textContent = charName || address;
}

function showMainUI(payload) {
  document.getElementById('auth-gate').style.display = 'none';
  document.getElementById('main-ui').style.display = 'flex';
  document.getElementById('panel-title').textContent = STRUCTURE_ID.toUpperCase() + ' SYSTEMS';
  document.getElementById('s-tier').textContent = payload.tier;
  document.getElementById('s-wallet').textContent = (payload.character_name || '').toUpperCase().slice(0, 12);
  // Hide sensitive stats for VETTED tier
  if (payload.tier === 'VETTED') {
    ['s-shield','s-fuel','s-services','s-docked'].forEach(id => {
      document.getElementById(id).closest('.stat').style.display = 'none';
    });
  }
}

// ── INFO PANEL ────────────────────────────────────────────────────────────
function toggleInfoPanel() {
  infoCollapsed = !infoCollapsed;
  document.getElementById('info-content').classList.toggle('collapsed', infoCollapsed);
  document.getElementById('collapse-hint').textContent = infoCollapsed ? '▼ EXPAND' : '▲ COLLAPSE';
}

async function loadStructureProfile() {
  try {
    const res = await fetch(SERVER + '/structure/' + STRUCTURE_ID, {
      headers: {'Authorization': 'Bearer ' + sessionToken}
    });
    if (!res.ok) return;
    const p = await res.json();
    document.getElementById('s-name').textContent     = (p.structure_name || '').toUpperCase();
    document.getElementById('s-system').textContent   = (p.system_name   || '—').toUpperCase();
    document.getElementById('s-type').textContent     = (p.structure_type|| '—');
    if (p.shield_pct !== undefined) {
      const sv = document.getElementById('s-shield');
      sv.textContent = p.shield_pct.toFixed(0) + '%';
      sv.className = 'sv ' + (p.shield_pct < 20 ? 'warn' : 'ok');
    }
    if (p.fuel_pct !== undefined) {
      const fv = document.getElementById('s-fuel');
      fv.textContent = p.fuel_pct.toFixed(0) + '%';
      fv.className = 'sv ' + (p.fuel_pct < 10 ? 'warn' : p.fuel_pct < 25 ? '' : 'ok');
    }
    if (p.services_online !== undefined)
      document.getElementById('s-services').textContent = p.services_online + '/' + (p.services_total || '?');
    if (p.docked_count !== undefined)
      document.getElementById('s-docked').textContent = p.docked_count;
    // Routine alerts
    if (p.routine_alerts && p.routine_alerts.length > 0) {
      const latest = p.routine_alerts[p.routine_alerts.length - 1];
      document.getElementById('alert-text').textContent = latest.message;
      document.getElementById('alert-bar').classList.add('visible');
    }
  } catch(e) { /* non-fatal */ }
}

// ── CHAT ──────────────────────────────────────────────────────────────────
function appendMessage(role, text) {
  const msgs = document.getElementById('messages');
  const div = document.createElement('div');
  div.className = 'msg msg-' + role;
  const prefix = document.createElement('div');
  prefix.className = 'msg-prefix';
  prefix.textContent = role === 'ai' ? '// ' + STRUCTURE_ID.toUpperCase() + ' SYSTEMS' : '// PILOT';
  const body = document.createElement('div');
  body.className = 'msg-body';
  body.textContent = text;
  div.appendChild(prefix);
  div.appendChild(body);
  msgs.appendChild(div);
  div.scrollIntoView({behavior: 'smooth'});
  return body;
}

async function sendMessage() {
  const input = document.getElementById('input');
  const msg = input.value.trim();
  if (!msg || !sessionToken) return;

  input.value = '';
  document.getElementById('send-btn').disabled = true;
  document.getElementById('chat-status').textContent = 'TRANSMITTING...';

  appendMessage('user', msg);
  chatHistory.push({role: 'user', content: msg});

  const aiBody = appendMessage('ai', '');
  let fullResponse = '';

  try {
    const res = await fetch(SERVER + '/structure-chat', {
      method: 'POST',
      headers: {'Content-Type': 'application/json', 'Authorization': 'Bearer ' + sessionToken},
      body: JSON.stringify({message: msg, history: chatHistory.slice(-20), structure_id: STRUCTURE_ID})
    });

    if (!res.ok) {
      const err = await res.json();
      aiBody.textContent = '[ERROR: ' + (err.detail || 'Unknown error') + ']';
      return;
    }

    const reader = res.body.getReader();
    const decoder = new TextDecoder();
    let buffer = '';

    while (true) {
      const {done, value} = await reader.read();
      if (done) break;
      buffer += decoder.decode(value, {stream: true});
      const lines = buffer.split('\n');
      buffer = lines.pop();
      for (const line of lines) {
        if (!line.startsWith('data: ')) continue;
        const payload = line.slice(6).trim();
        if (payload === '[DONE]') break;
        try {
          const {text} = JSON.parse(payload);
          if (text) { fullResponse += text; aiBody.textContent = fullResponse; }
        } catch(e) {}
      }
    }

    chatHistory.push({role: 'assistant', content: fullResponse});
    localStorage.setItem('struct_history_' + STRUCTURE_ID, JSON.stringify(chatHistory.slice(-40)));

  } catch(e) {
    aiBody.textContent = '[Connection error: ' + e.message + ']';
  } finally {
    document.getElementById('send-btn').disabled = false;
    document.getElementById('chat-status').textContent = 'READY';
  }
}

// Restore chat history
const storedHistory = localStorage.getItem('struct_history_' + STRUCTURE_ID);
if (storedHistory) {
  try {
    chatHistory = JSON.parse(storedHistory);
    chatHistory.forEach(m => appendMessage(m.role === 'user' ? 'user' : 'ai', m.content));
  } catch(e) {}
}
</script>
</body>
</html>
```

- [x] **11.2 Test in browser — verify static file is served**

```bash
curl -I http://localhost:8745/static/structure.html
```

Expected: `HTTP/1.1 200 OK`, `content-type: text/html`

- [x] **11.3 Load in EVE Frontier SSU browser**

Navigate in-game to the SSU, open the structure browser, set URL to:
```
http://YOUR_VPS_IP:8745/static/structure.html?id=keep-7a
```

Expected: auth gate appears, "KEEP-7A" displayed, "Connect Wallet" button visible.

- [x] **11.4 Test wallet connect flow end-to-end**

Click "Connect Wallet" in the SSU browser. Approve in EVEVault. Watch auth status messages:
1. "Connecting wallet..." → "Requesting connection..." → "Signing identity challenge..." → "Verifying identity..."
2. If owner: main UI appears, info panel shows stats
3. If access denied: denied screen appears

- [ ] **11.5 Commit**

```bash
cd /opt/eve-frontier
git add static/structure.html
git commit -m "feat: structure.html — amber UI with wallet connect, collapsible panel, SSE chat"
```

---

## Chunk 8: Move Contract — AccessRegistry

**Files:**
- Create: `move/access_registry/Move.toml`
- Create: `move/access_registry/sources/access_registry.move`

### Task 12: Sui Move AccessRegistry contract

**Prerequisites:**
- Sui CLI installed: `sui --version` (install from https://docs.sui.io/guides/developer/getting-started/sui-install)
- Nova chain config available (builder-scaffold at https://github.com/evefrontier/builder-scaffold)
- Wallet funded on Nova for deployment gas

- [x] **12.1 Create Move package structure**

```bash
mkdir -p /opt/eve-frontier/move/access_registry/sources
```

- [x] **12.2 Create `Move.toml`**

```toml
[package]
name = "access_registry"
version = "0.1.0"
edition = "2024.beta"

[dependencies]
Sui = { git = "https://github.com/MystenLabs/sui.git", subdir = "crates/sui-framework/packages/sui-framework", rev = "framework/testnet" }

[addresses]
access_registry = "0x0"
```

- [x] **12.3 Create `sources/access_registry.move`**

```move
/// AccessRegistry — per-structure access control for EVE Frontier Structure AI
/// Deployed on Nova (builder sandbox chain).
/// Owner manages tribe (corp members) and vetted (approved outsiders) address lists.
///
/// Note: The spec describes structure_id as u64 (on-chain game ID). We use String
/// (human-readable key matching the server profile, e.g. "keep-7a") because the
/// server identifies structures by the URL ?id= param, not a numeric chain ID.
/// If the game's numeric structure ID is needed later, add a separate field.
module access_registry::registry {
    use sui::object::{Self, UID};
    use sui::tx_context::{Self, TxContext};
    use sui::transfer;
    use std::vector;
    use std::string::{Self, String};

    /// One shared object per structure. Created by the structure owner.
    public struct AccessRegistry has key {
        id: UID,
        /// Game structure identifier (e.g., "keep-7a") — matches server profile key
        structure_id: String,
        /// Owner's Sui wallet address
        owner: address,
        /// Tribe/corp members — full chat access
        tribe: vector<address>,
        /// Vetted outsiders — limited chat access
        vetted: vector<address>,
    }

    // ── Errors ──────────────────────────────────────────────────────────────
    const E_NOT_OWNER: u64 = 1;
    const E_ALREADY_IN_LIST: u64 = 2;
    const E_NOT_IN_LIST: u64 = 3;

    // ── Owner functions ──────────────────────────────────────────────────────

    /// Create a new AccessRegistry for a structure. Shared immediately.
    public entry fun create(structure_id: vector<u8>, ctx: &mut TxContext) {
        let registry = AccessRegistry {
            id: object::new(ctx),
            structure_id: string::utf8(structure_id),
            owner: tx_context::sender(ctx),
            tribe: vector::empty(),
            vetted: vector::empty(),
        };
        transfer::share_object(registry);
    }

    public entry fun add_tribe(registry: &mut AccessRegistry, addr: address, ctx: &TxContext) {
        assert!(registry.owner == tx_context::sender(ctx), E_NOT_OWNER);
        assert!(!vector::contains(&registry.tribe, &addr), E_ALREADY_IN_LIST);
        vector::push_back(&mut registry.tribe, addr);
    }

    public entry fun remove_tribe(registry: &mut AccessRegistry, addr: address, ctx: &TxContext) {
        assert!(registry.owner == tx_context::sender(ctx), E_NOT_OWNER);
        let (exists, idx) = vector::index_of(&registry.tribe, &addr);
        assert!(exists, E_NOT_IN_LIST);
        vector::remove(&mut registry.tribe, idx);
    }

    public entry fun add_vetted(registry: &mut AccessRegistry, addr: address, ctx: &TxContext) {
        assert!(registry.owner == tx_context::sender(ctx), E_NOT_OWNER);
        assert!(!vector::contains(&registry.vetted, &addr), E_ALREADY_IN_LIST);
        vector::push_back(&mut registry.vetted, addr);
    }

    public entry fun remove_vetted(registry: &mut AccessRegistry, addr: address, ctx: &TxContext) {
        assert!(registry.owner == tx_context::sender(ctx), E_NOT_OWNER);
        let (exists, idx) = vector::index_of(&registry.vetted, &addr);
        assert!(exists, E_NOT_IN_LIST);
        vector::remove(&mut registry.vetted, idx);
    }

    /// Transfer ownership to a new address
    public entry fun transfer_ownership(registry: &mut AccessRegistry, new_owner: address, ctx: &TxContext) {
        assert!(registry.owner == tx_context::sender(ctx), E_NOT_OWNER);
        registry.owner = new_owner;
    }

    // ── Read accessors (public, no auth required) ────────────────────────────

    public fun owner(registry: &AccessRegistry): address { registry.owner }
    public fun tribe(registry: &AccessRegistry): &vector<address> { &registry.tribe }
    public fun vetted(registry: &AccessRegistry): &vector<address> { &registry.vetted }
    public fun structure_id(registry: &AccessRegistry): &String { &registry.structure_id }

    public fun is_tribe(registry: &AccessRegistry, addr: address): bool {
        vector::contains(&registry.tribe, &addr)
    }

    public fun is_vetted(registry: &AccessRegistry, addr: address): bool {
        vector::contains(&registry.vetted, &addr)
    }
}
```

- [x] **12.4 Build the contract**

```bash
cd /opt/eve-frontier/move/access_registry
sui move build
```

Expected: `BUILDING access_registry` ... `Build Successful`

If `sui` not installed: follow https://docs.sui.io/guides/developer/getting-started/sui-install

- [x] **12.5 Run Move unit tests**

```bash
cd /opt/eve-frontier/move/access_registry
sui move test
```

Expected: `Test result: OK. Total tests: 0; passed: 0; failed: 0`
(Tests will be added in the next step.)

- [x] **12.6 Add Move unit tests**

Add a `tests/` directory and test file:

```bash
mkdir -p /opt/eve-frontier/move/access_registry/tests
```

Create `move/access_registry/tests/access_registry_tests.move`:

```move
#[test_only]
module access_registry::registry_tests {
    use access_registry::registry;
    use sui::test_scenario;

    const OWNER: address = @0xA;
    const TRIBE1: address = @0xB;
    const VETTED1: address = @0xC;
    const STRANGER: address = @0xD;

    #[test]
    fun test_create_registry() {
        let mut scenario = test_scenario::begin(OWNER);
        {
            registry::create(b"keep-7a", test_scenario::ctx(&mut scenario));
        };
        test_scenario::next_tx(&mut scenario, OWNER);
        {
            let reg = test_scenario::take_shared<registry::AccessRegistry>(&scenario);
            assert!(registry::owner(&reg) == OWNER, 0);
            assert!(std::vector::length(registry::tribe(&reg)) == 0, 1);
            test_scenario::return_shared(reg);
        };
        test_scenario::end(scenario);
    }

    #[test]
    fun test_add_and_check_tribe() {
        let mut scenario = test_scenario::begin(OWNER);
        { registry::create(b"keep-7a", test_scenario::ctx(&mut scenario)); };
        test_scenario::next_tx(&mut scenario, OWNER);
        {
            let mut reg = test_scenario::take_shared<registry::AccessRegistry>(&scenario);
            registry::add_tribe(&mut reg, TRIBE1, test_scenario::ctx(&mut scenario));
            assert!(registry::is_tribe(&reg, TRIBE1), 0);
            assert!(!registry::is_tribe(&reg, STRANGER), 1);
            test_scenario::return_shared(reg);
        };
        test_scenario::end(scenario);
    }

    #[test]
    fun test_remove_tribe() {
        let mut scenario = test_scenario::begin(OWNER);
        { registry::create(b"keep-7a", test_scenario::ctx(&mut scenario)); };
        test_scenario::next_tx(&mut scenario, OWNER);
        {
            let mut reg = test_scenario::take_shared<registry::AccessRegistry>(&scenario);
            registry::add_tribe(&mut reg, TRIBE1, test_scenario::ctx(&mut scenario));
            registry::remove_tribe(&mut reg, TRIBE1, test_scenario::ctx(&mut scenario));
            assert!(!registry::is_tribe(&reg, TRIBE1), 0);
            test_scenario::return_shared(reg);
        };
        test_scenario::end(scenario);
    }

    #[test]
    #[expected_failure(abort_code = 1)]  // E_NOT_OWNER = 1; use numeric value, not constant path
    fun test_non_owner_cannot_add_tribe() {
        let mut scenario = test_scenario::begin(OWNER);
        { registry::create(b"keep-7a", test_scenario::ctx(&mut scenario)); };
        test_scenario::next_tx(&mut scenario, STRANGER);
        {
            let mut reg = test_scenario::take_shared<registry::AccessRegistry>(&scenario);
            registry::add_tribe(&mut reg, TRIBE1, test_scenario::ctx(&mut scenario));
            test_scenario::return_shared(reg);
        };
        test_scenario::end(scenario);
    }

    #[test]
    fun test_add_vetted() {
        let mut scenario = test_scenario::begin(OWNER);
        { registry::create(b"keep-7a", test_scenario::ctx(&mut scenario)); };
        test_scenario::next_tx(&mut scenario, OWNER);
        {
            let mut reg = test_scenario::take_shared<registry::AccessRegistry>(&scenario);
            registry::add_vetted(&mut reg, VETTED1, test_scenario::ctx(&mut scenario));
            assert!(registry::is_vetted(&reg, VETTED1), 0);
            assert!(!registry::is_tribe(&reg, VETTED1), 1);
            test_scenario::return_shared(reg);
        };
        test_scenario::end(scenario);
    }
}
```

- [x] **12.7 Run Move tests**

```bash
cd /opt/eve-frontier/move/access_registry
sui move test
```

Expected: `Test result: OK. Total tests: 5; passed: 5; failed: 0`

- [x] **12.8 Deploy to Nova**

First, configure Sui CLI for Nova network. Check the EVE Frontier builder-scaffold for Nova RPC URL and chain ID. Then:

```bash
# Add Nova network to Sui CLI (replace URL with actual Nova RPC)
sui client new-env --alias nova --rpc <NOVA_RPC_URL>
sui client switch --env nova

# Check active address has gas on Nova
sui client gas

# Deploy
cd /opt/eve-frontier/move/access_registry
sui client publish --gas-budget 50000000
```

Expected output includes:
```
----- Transaction Digest ----
<TX_HASH>
----- Object changes ----
Created Objects:
  - PackageID: 0x<PACKAGE_ID>
```

- [x] **12.9 Record deployed package ID**

Add to `/opt/eve-frontier/.env`:
```
NOVA_ACCESS_REGISTRY_PACKAGE=0x<PACKAGE_ID>
NOVA_RPC_URL=<NOVA_RPC_URL>
```

- [x] **12.10 Create your first AccessRegistry for testing**

```bash
# Replace STRUCTURE_ID_BYTES with hex of "keep-7a" = 6b6565702d3761
sui client call \
  --package 0x<PACKAGE_ID> \
  --module registry \
  --function create \
  --args "0x6b6565702d3761" \
  --gas-budget 10000000
```

Note the created shared object ID — this is your `nova_registry_object_id`.

- [x] **12.11 Update nova_client.py with correct RPC URL**

In `src/nova_client.py`, update the default:
```python
NOVA_RPC_URL = os.environ.get("NOVA_RPC_URL", "<NOVA_RPC_URL>")
```

- [ ] **12.12 Commit**

```bash
cd /opt/eve-frontier
git add move/ .env.example
git commit -m "feat: AccessRegistry Sui Move contract — deploy on Nova"
```

---

## Final Integration Checklist

- [x] All server-side tests pass: `.venv/bin/pytest tests/ -q`
- [x] Move tests pass: `cd move/access_registry && sui move test`
- [x] `structure.html` loads in SSU browser
- [x] Wallet connect → auth gate → main UI flow works end-to-end in Utopia
- [ ] Structure AI chat responds in-character (caretaker persona)
- [ ] Urgent alert (set `shield_pct=15` in profile, send a chat) → appears in Ship AI overlay on next overlay message
- [ ] VETTED tier hides shield/fuel/docked stats in browser
- [ ] localStorage session survives browser reload

## Environment Variables Reference

Add to `.env`:
```
JWT_SECRET=<random 64-char hex>
NOVA_RPC_URL=<Nova full-node RPC endpoint from builder-scaffold>
NOVA_ACCESS_REGISTRY_PACKAGE=<deployed package ID>
```

Add to `.env.example`:
```
JWT_SECRET=change-me-generate-with-openssl-rand-hex-32
NOVA_RPC_URL=https://rpc.nova.evefrontier.com
NOVA_ACCESS_REGISTRY_PACKAGE=0x0
```
