# Deal Mechanic Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a "deal-with-the-devil" access mechanic: strangers pay (item deposit, SUI coin, or information trade) to receive a time/token-limited PATRON JWT for the Structure AI chat.

**Architecture:** Three new auth endpoints (`/auth/deal/offer`, `/auth/deal/claim`) issue PATRON JWTs backed by server-side `DealStore` (JSON files under `data/deals/`). A `LocationIndex` module indexes `LocationRevealedEvent` on-chain data. SSE generators get keep-alive headers. All Sui queries use existing `nova_client._rpc`. All JWT/nonce/wallet-verify logic reuses existing `structure_auth.py` helpers.

**PATRON expiry design:** `issue_jwt()` always issues 24h JWTs (not changed). PATRON time-limiting is enforced by `DealStore.consume_message()` — it checks both `expires_at` and `messages_remaining`. This means a PATRON JWT is technically valid for 24h at the JWT layer, but `structure_chat` enforces the deal terms server-side before every message. This is intentional for hackathon simplicity. Post-hackathon: pass custom `expiry_hours` to `issue_jwt()`.

**NONE tier → lobby:** NONE tier (unauthenticated strangers) is deliberately routed to `lobby_client.stream()` — the same lobby persona as VETTED. The lobby persona can mention the deal and invite the player to engage. This replaces the current 403.

**Tech Stack:** FastAPI, PyJWT, Sui JSON-RPC via `nova_client._rpc`, existing `nonce_store` + `issue_jwt` + `verify_sui_personal_message` from `src/structure_auth.py`.

---

## Chunk 1: SSE Keep-alive

**Files:**
- Modify: `main.py` (three `event_stream()` generators at lines ~633, ~675, ~962)

### Task 1: Add keep-alive yield to all three SSE generators

- [ ] **Step 1: Write failing test verifying keep-alive appears in ship chat stream**

Add to `tests/test_main.py` (find the existing ship chat test or add alongside):

```python
def test_ship_chat_stream_starts_with_keepalive(client, monkeypatch):
    """SSE stream must yield a keep-alive comment before the first data chunk."""
    from unittest.mock import patch

    chunks = ["Hello", " world"]

    def fake_stream(message, history, context):
        return iter(chunks)

    with patch("main.claude.stream", side_effect=fake_stream), \
         patch("main.world_api.get_system", return_value=None), \
         patch("main.log_buffer.current_system", None):
        resp = client.post(
            "/chat",
            json={"message": "hi", "history": []},
            headers={"X-Server-Token": "test-token"},
        )
    body = resp.text
    assert body.startswith(": keep-alive\n\n"), f"Expected keep-alive first, got: {body[:40]!r}"
```

- [ ] **Step 2: Run test to verify it fails**

```bash
cd /opt/eve-frontier && .venv/bin/pytest tests/test_main.py::test_ship_chat_stream_starts_with_keepalive -v
```
Expected: FAIL (no keep-alive in stream)

- [ ] **Step 3: Add keep-alive to ship chat generator (main.py ~line 633)**

Change:
```python
    def event_stream():
        try:
            for chunk in claude.stream(req.message, req.history, context):
```
To:
```python
    def event_stream():
        yield ": keep-alive\n\n"
        try:
            for chunk in claude.stream(req.message, req.history, context):
```

- [ ] **Step 4: Add keep-alive to structure debug chat generator (main.py ~line 675)**

Change:
```python
    def event_stream():
        try:
            for chunk in structure_client.stream(
```
To:
```python
    def event_stream():
        yield ": keep-alive\n\n"
        try:
            for chunk in structure_client.stream(
```

- [ ] **Step 5: Add keep-alive to structure chat generator (main.py ~line 962)**

Change:
```python
    def event_stream():
        try:
            if tier == "VETTED":
```
To:
```python
    def event_stream():
        yield ": keep-alive\n\n"
        try:
            if tier == "VETTED":
```

- [ ] **Step 6: Run test to verify it passes**

```bash
cd /opt/eve-frontier && .venv/bin/pytest tests/test_main.py::test_ship_chat_stream_starts_with_keepalive -v
```
Expected: PASS

- [ ] **Step 7: Run full suite — no regressions**

```bash
cd /opt/eve-frontier && .venv/bin/pytest tests/ -q
```
Expected: all tests passing (was 91+)

- [ ] **Step 8: Commit**

```bash
git add main.py tests/test_main.py
git commit -m "fix: add SSE keep-alive comment to all three event_stream generators"
```

---

## Chunk 2: DealStore

**Files:**
- Create: `src/deal_store.py`
- Create: `tests/test_deal_store.py`

### Task 2: DealStore — server-side PATRON deal tracking

`DealStore` persists one JSON file per `(address, structure_id)` under `data/deals/`. Tracks `messages_remaining` and `expires_at` (unix timestamp). The `consume_message` method is the hot path — called on every PATRON chat.

- [ ] **Step 1: Write failing tests**

Create `tests/test_deal_store.py`:

```python
import pytest
import time
import os
import tempfile
from src.deal_store import DealStore, DealRecord


@pytest.fixture
def store(tmp_path):
    return DealStore(base_dir=str(tmp_path))


def test_issue_creates_record(store):
    store.issue("0xabc", "keep-7a", "item")
    rec = store.get("0xabc", "keep-7a")
    assert rec is not None
    assert rec.payment_method == "item"
    assert rec.messages_remaining == 20
    assert rec.expires_at > time.time()


def test_consume_message_decrements(store):
    store.issue("0xabc", "keep-7a", "sui")
    assert store.consume_message("0xabc", "keep-7a") is True
    rec = store.get("0xabc", "keep-7a")
    assert rec.messages_remaining == 19


def test_consume_exhausted_returns_false(store):
    store.issue("0xabc", "keep-7a", "info", messages=1)
    assert store.consume_message("0xabc", "keep-7a") is True
    assert store.consume_message("0xabc", "keep-7a") is False


def test_consume_expired_returns_false(store):
    store.issue("0xabc", "keep-7a", "item", duration_hours=0)
    # expires_at is in the past (0 hours from now)
    rec = store.get("0xabc", "keep-7a")
    # Manually set expires_at to past
    rec.expires_at = time.time() - 1
    store._save(rec)
    assert store.consume_message("0xabc", "keep-7a") is False


def test_get_missing_returns_none(store):
    assert store.get("0xnobody", "keep-7a") is None


def test_issue_overwrites_existing(store):
    store.issue("0xabc", "keep-7a", "item")
    store.issue("0xabc", "keep-7a", "sui", messages=5)
    rec = store.get("0xabc", "keep-7a")
    assert rec.messages_remaining == 5
    assert rec.payment_method == "sui"


def test_path_sanitizes_address(store, tmp_path):
    """Addresses with special chars don't escape the directory."""
    store.issue("0x../../../etc/passwd", "keep-7a", "info")
    for f in os.listdir(tmp_path):
        assert "/" not in f
        assert ".." not in f
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd /opt/eve-frontier && .venv/bin/pytest tests/test_deal_store.py -v
```
Expected: ImportError — `src.deal_store` not found

- [ ] **Step 3: Implement `src/deal_store.py`**

```python
# src/deal_store.py
import os
import re
import json
import time
import logging
from dataclasses import dataclass, asdict
from typing import Optional
import datetime

log = logging.getLogger(__name__)

_DEFAULT_BASE_DIR = os.path.normpath(
    os.path.join(os.path.dirname(__file__), "..", "data", "deals")
)

_SAFE_RE = re.compile(r'[^a-zA-Z0-9_-]')

DEAL_MESSAGES_DEFAULT = 20
DEAL_DURATION_HOURS_DEFAULT = 24


def _safe(s: str) -> str:
    return _SAFE_RE.sub('', s.lower())[:80]


@dataclass
class DealRecord:
    address: str
    structure_id: str
    payment_method: str      # "item" | "sui" | "info"
    messages_remaining: int
    expires_at: float        # unix timestamp
    created_at: str          # ISO8601


class DealStore:
    def __init__(self, base_dir: str = _DEFAULT_BASE_DIR):
        self._base = base_dir

    def _path(self, address: str, structure_id: str) -> str:
        return os.path.join(self._base, f"{_safe(address)}-{_safe(structure_id)}.json")

    def _save(self, rec: DealRecord) -> None:
        os.makedirs(self._base, exist_ok=True)
        try:
            with open(self._path(rec.address, rec.structure_id), "w") as f:
                json.dump(asdict(rec), f)
        except Exception as e:
            log.warning("DealStore._save failed: %s", e)

    def issue(
        self,
        address: str,
        structure_id: str,
        payment_method: str,
        messages: int = DEAL_MESSAGES_DEFAULT,
        duration_hours: int = DEAL_DURATION_HOURS_DEFAULT,
    ) -> DealRecord:
        """Create or overwrite a PATRON deal for this address + structure."""
        rec = DealRecord(
            address=address.lower(),
            structure_id=structure_id,
            payment_method=payment_method,
            messages_remaining=messages,
            expires_at=time.time() + duration_hours * 3600,
            created_at=datetime.datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ"),
        )
        self._save(rec)
        return rec

    def get(self, address: str, structure_id: str) -> Optional[DealRecord]:
        path = self._path(address, structure_id)
        if not os.path.exists(path):
            return None
        try:
            with open(path) as f:
                data = json.load(f)
            return DealRecord(**data)
        except Exception as e:
            log.warning("DealStore.get failed for %s: %s", address[:12], e)
            return None

    def consume_message(self, address: str, structure_id: str) -> bool:
        """
        Decrement messages_remaining and return True if the deal is still valid.
        Returns False if deal is missing, expired, or exhausted.
        """
        rec = self.get(address, structure_id)
        if rec is None:
            return False
        if time.time() > rec.expires_at:
            return False
        if rec.messages_remaining <= 0:
            return False
        rec.messages_remaining -= 1
        self._save(rec)
        return True


# Module-level singleton
deal_store = DealStore()
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
cd /opt/eve-frontier && .venv/bin/pytest tests/test_deal_store.py -v
```
Expected: 8 tests PASS

- [ ] **Step 5: Run full suite — no regressions**

```bash
cd /opt/eve-frontier && .venv/bin/pytest tests/ -q
```

- [ ] **Step 6: Commit**

```bash
git add src/deal_store.py tests/test_deal_store.py
git commit -m "feat: add DealStore for PATRON deal tracking (messages_remaining + expires_at)"
```

---

## Chunk 3: Deal Endpoints

**Files:**
- Modify: `main.py` (add `/auth/deal/offer` + `/auth/deal/claim` endpoints)
- Create: `tests/test_deal_endpoints.py`

Two endpoints:
- `POST /auth/deal/offer` — issues a nonce + returns deal terms (no auth required)
- `POST /auth/deal/claim` — verifies signature + payment proof, issues PATRON JWT

Payment methods:
- `"item"` — server queries chain for recent `ItemDepositedEvent` from the player's wallet
- `"sui"` — player submits a transaction digest; server verifies it sent SUI to VPS address
- `"info"` — player submits structure object IDs; server reads them from chain

All chain queries use `nova_client._rpc`. Signature verification reuses `verify_sui_personal_message`. JWT issuance reuses `issue_jwt`. Nonce lifecycle reuses `nonce_store`.

### Task 3: Pydantic models and `/auth/deal/offer`

- [ ] **Step 1: Write failing test for `/auth/deal/offer`**

Create `tests/test_deal_endpoints.py`:

```python
import pytest
from fastapi.testclient import TestClient
from unittest.mock import patch, AsyncMock


@pytest.fixture
def client():
    from main import app
    # Patch lifespan tasks so we don't start background pollers
    with patch("main.world_api.load_or_build_index", new_callable=AsyncMock), \
         patch("main.start_background_tasks"), \
         patch("main.get_memory_store"):
        with TestClient(app) as c:
            yield c


def test_deal_offer_returns_nonce_and_terms(client):
    resp = client.post("/auth/deal/offer", json={
        "structure_id": "keep-7a",
        "address": "0xabc123",
    })
    assert resp.status_code == 200
    data = resp.json()
    assert "nonce" in data
    assert len(data["nonce"]) == 64
    assert data["structure_id"] == "keep-7a"
    assert data["expires_in_seconds"] == 300
    assert "terms" in data
    assert set(data["terms"]["payment_options"]) == {"item", "sui", "info"}
    assert data["terms"]["messages"] == 20
    assert data["terms"]["duration_hours"] == 24


def test_deal_offer_does_not_require_auth(client):
    """Offer endpoint is public — no X-Server-Token needed."""
    resp = client.post("/auth/deal/offer", json={
        "structure_id": "keep-7a",
        "address": "0xabc",
    })
    assert resp.status_code == 200
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd /opt/eve-frontier && .venv/bin/pytest tests/test_deal_endpoints.py::test_deal_offer_returns_nonce_and_terms tests/test_deal_endpoints.py::test_deal_offer_does_not_require_auth -v
```
Expected: FAIL — endpoint not found (404)

- [ ] **Step 3: Add Pydantic models + `/auth/deal/offer` endpoint to `main.py`**

Add import at top of main.py (after existing deal_store import — add both):
```python
from src.deal_store import deal_store, DEAL_MESSAGES_DEFAULT, DEAL_DURATION_HOURS_DEFAULT
```

Add Pydantic models (near the other auth models, after `VerifyRequest`):
```python
class DealOfferRequest(BaseModel):
    structure_id: str
    address: str


class DealClaimRequest(BaseModel):
    nonce: str
    address: str
    structure_id: str
    signature: str
    payment_method: str          # "item" | "sui" | "info"
    proof: dict = {}             # payment_method-specific evidence
```

Add endpoint (after `/auth/verify`):
```python
@app.post("/auth/deal/offer")
async def deal_offer(req: DealOfferRequest):
    """
    Issue a nonce and return deal terms for PATRON access.
    No auth required — public endpoint for strangers.
    """
    nonce = nonce_store.issue()
    return {
        "nonce": nonce,
        "structure_id": req.structure_id,
        "expires_in_seconds": 300,
        "terms": {
            "messages": DEAL_MESSAGES_DEFAULT,
            "duration_hours": DEAL_DURATION_HOURS_DEFAULT,
            "payment_options": ["item", "sui", "info"],
        },
    }
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
cd /opt/eve-frontier && .venv/bin/pytest tests/test_deal_endpoints.py::test_deal_offer_returns_nonce_and_terms tests/test_deal_endpoints.py::test_deal_offer_does_not_require_auth -v
```
Expected: PASS

### Task 4: `/auth/deal/claim` — all three payment paths

- [ ] **Step 1: Write failing tests for `/auth/deal/claim`**

Add to `tests/test_deal_endpoints.py`:

```python
import base64


def _fake_zklogin_sig():
    """Minimal zkLogin-flagged signature accepted by verify_sui_personal_message."""
    return base64.b64encode(bytes([0x05]) + bytes(96)).decode()


def test_deal_claim_item_payment(client):
    """Item payment: server finds a recent ItemDepositedEvent from the player."""
    fake_events = {
        "result": {
            "data": [
                {
                    "sender": "0xplayer",
                    "type": "0xpkg::ephemeral_inventory::ItemDepositedEvent",
                    "parsedJson": {"sender": "0xplayer", "type_id": 1234, "quantity": 1},
                    "timestampMs": str(int((__import__('time').time() - 30) * 1000)),
                }
            ],
            "hasNextPage": False,
        }
    }

    with patch("src.nova_client.nova_client._rpc", new_callable=AsyncMock, return_value=fake_events), \
         patch("src.structure_auth.verify_sui_personal_message", return_value=True), \
         patch("src.structure_auth.lookup_character", new_callable=AsyncMock, return_value={}):
        # First get a nonce
        offer = client.post("/auth/deal/offer", json={"structure_id": "keep-7a", "address": "0xplayer"})
        nonce = offer.json()["nonce"]

        resp = client.post("/auth/deal/claim", json={
            "nonce": nonce,
            "address": "0xplayer",
            "structure_id": "keep-7a",
            "signature": _fake_zklogin_sig(),
            "payment_method": "item",
            "proof": {},
        })
    assert resp.status_code == 200
    data = resp.json()
    assert data["tier"] == "PATRON"
    assert "token" in data
    assert data["messages_remaining"] == 20


def test_deal_claim_info_payment(client):
    """Info payment: player provides structure IDs; server reads them."""
    fake_obj = {
        "result": {
            "data": {
                "type": "0xpkg::storage_unit::StorageUnit",
                "content": {"fields": {"status": {}}},
            }
        }
    }

    with patch("src.nova_client.nova_client._rpc", new_callable=AsyncMock, return_value=fake_obj), \
         patch("src.structure_auth.verify_sui_personal_message", return_value=True), \
         patch("src.structure_auth.lookup_character", new_callable=AsyncMock, return_value={}):
        offer = client.post("/auth/deal/offer", json={"structure_id": "keep-7a", "address": "0xplayer"})
        nonce = offer.json()["nonce"]

        resp = client.post("/auth/deal/claim", json={
            "nonce": nonce,
            "address": "0xplayer",
            "structure_id": "keep-7a",
            "signature": _fake_zklogin_sig(),
            "payment_method": "info",
            "proof": {"structure_ids": ["0xstruct1"]},
        })
    assert resp.status_code == 200
    assert resp.json()["tier"] == "PATRON"


def test_deal_claim_rejects_invalid_nonce(client):
    with patch("src.structure_auth.verify_sui_personal_message", return_value=True):
        resp = client.post("/auth/deal/claim", json={
            "nonce": "deadbeef" * 8,
            "address": "0xplayer",
            "structure_id": "keep-7a",
            "signature": _fake_zklogin_sig(),
            "payment_method": "info",
            "proof": {"structure_ids": ["0xstruct1"]},
        })
    assert resp.status_code == 400


def test_deal_claim_rejects_no_item_deposit_found(client):
    """Item payment with empty event list → 402."""
    empty_events = {"result": {"data": [], "hasNextPage": False}}

    with patch("src.nova_client.nova_client._rpc", new_callable=AsyncMock, return_value=empty_events), \
         patch("src.structure_auth.verify_sui_personal_message", return_value=True), \
         patch("src.structure_auth.lookup_character", new_callable=AsyncMock, return_value={}):
        offer = client.post("/auth/deal/offer", json={"structure_id": "keep-7a", "address": "0xplayer"})
        nonce = offer.json()["nonce"]

        resp = client.post("/auth/deal/claim", json={
            "nonce": nonce,
            "address": "0xplayer",
            "structure_id": "keep-7a",
            "signature": _fake_zklogin_sig(),
            "payment_method": "item",
            "proof": {},
        })
    assert resp.status_code == 402


def test_deal_claim_rejects_unknown_payment_method(client):
    with patch("src.structure_auth.verify_sui_personal_message", return_value=True), \
         patch("src.structure_auth.lookup_character", new_callable=AsyncMock, return_value={}):
        offer = client.post("/auth/deal/offer", json={"structure_id": "keep-7a", "address": "0xplayer"})
        nonce = offer.json()["nonce"]

        resp = client.post("/auth/deal/claim", json={
            "nonce": nonce,
            "address": "0xplayer",
            "structure_id": "keep-7a",
            "signature": _fake_zklogin_sig(),
            "payment_method": "magic",
            "proof": {},
        })
    assert resp.status_code == 400
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd /opt/eve-frontier && .venv/bin/pytest tests/test_deal_endpoints.py -v -k "claim"
```
Expected: FAIL — endpoint not found

- [ ] **Step 3: Add helper functions + `/auth/deal/claim` to `main.py`**

Add these two env-var reads near the `_STRUCTURE_REGISTRY_MAP` setup (top of main.py, after `load_dotenv()`):
```python
_EVE_FRONTIER_PACKAGE = os.environ.get(
    "EVE_FRONTIER_PACKAGE",
    "0xd12a70c74c1e759445d6f209b01d43d860e97fcf2ef72ccbbd00afd828043f75",
)
_VPS_SUI_ADDRESS = os.environ.get("VPS_SUI_ADDRESS", "")
_ITEM_DEPOSIT_EVENT = f"{_EVE_FRONTIER_PACKAGE}::ephemeral_inventory::ItemDepositedEvent"
_ITEM_DEPOSIT_WINDOW_MS = 600_000  # 10 minutes
```

Add the claim endpoint (after `/auth/deal/offer`):
```python
@app.post("/auth/deal/claim")
async def deal_claim(req: DealClaimRequest):
    """
    Verify wallet signature + payment proof, issue PATRON JWT.

    payment_method="item": server queries suix_queryEvents for a recent
        ItemDepositedEvent from req.address on this SSU. No proof field needed.
    payment_method="sui": req.proof must contain {"tx_digest": "0x..."}.
        Server calls sui_getTransactionBlock to verify sender==req.address
        and receiver==VPS_SUI_ADDRESS.
    payment_method="info": req.proof must contain {"structure_ids": ["0x..."]}.
        Server reads each via sui_getObject and stores them in memory.
    """
    # 1. Consume nonce
    if not nonce_store.consume(req.nonce):
        raise HTTPException(status_code=400, detail="Invalid or expired nonce")

    # 2. Verify wallet signature (reuse existing helper)
    try:
        verify_sui_personal_message(req.nonce.encode(), req.signature, req.address)
    except Exception as e:
        log.warning("deal_claim: signature failed for %s: %s", req.address, e)
        raise HTTPException(status_code=401, detail="Signature verification failed")

    # 3. Verify payment
    if req.payment_method == "item":
        await _verify_item_deposit(req.address, req.structure_id)
    elif req.payment_method == "sui":
        await _verify_sui_payment(req.address, req.proof)
    elif req.payment_method == "info":
        await _process_info_trade(req.address, req.structure_id, req.proof)
    else:
        raise HTTPException(status_code=400, detail=f"Unknown payment_method: {req.payment_method!r}")

    # 4. Lookup character (non-fatal)
    character_id = 0
    character_name = req.address[:12] + "..."
    char_data = await lookup_character(req.address)
    if char_data:
        character_id = char_data.get("id", 0)
        character_name = char_data.get("name", character_name) or character_name

    # 5. Issue deal record + PATRON JWT
    rec = deal_store.issue(req.address, req.structure_id, req.payment_method)
    token = issue_jwt({
        "address": req.address,
        "character_id": character_id,
        "character_name": character_name,
        "tier": "PATRON",
        "structure_id": req.structure_id,
    })

    # 6. Upsert pilot profile (same as /auth/verify)
    from src.memory_store import get_memory_store
    mem = get_memory_store(req.structure_id)
    mem.upsert_pilot(
        address=req.address,
        character_name=character_name,
        character_id=character_id,
        tier="PATRON",
    )

    return {
        "token": token,
        "tier": "PATRON",
        "character_name": character_name,
        "character_id": character_id,
        "messages_remaining": rec.messages_remaining,
        "expires_at": rec.expires_at,
    }


async def _verify_item_deposit(address: str, structure_id: str) -> None:
    """Query suix_queryEvents for a recent ItemDepositedEvent from address.
    Raises HTTPException 402 if no qualifying event found.
    """
    import time as _time
    try:
        result = await nova_client._rpc("suix_queryEvents", [
            {"MoveEventType": _ITEM_DEPOSIT_EVENT},
            None,   # cursor = latest page
            50,     # limit
            True,   # descending (newest first)
        ])
    except Exception as e:
        log.warning("_verify_item_deposit: RPC failed: %s", e)
        raise HTTPException(status_code=502, detail="Chain query failed — try again")

    events = result.get("result", {}).get("data") or []
    cutoff_ms = (_time.time() - _ITEM_DEPOSIT_WINDOW_MS / 1000) * 1000

    for event in events:
        sender = event.get("sender", "").lower()
        ts_ms = int(event.get("timestampMs") or 0)
        if sender == address.lower() and ts_ms >= cutoff_ms:
            return  # found a qualifying deposit

    raise HTTPException(
        status_code=402,
        detail="No recent item deposit found. Drag any item into the SSU within 10 minutes of requesting a deal, then claim.",
    )


async def _verify_sui_payment(address: str, proof: dict) -> None:
    """Verify a SUI coin transfer to VPS address.
    proof must contain {"tx_digest": "0x..."}.
    Raises HTTPException 402 if verification fails.
    """
    if not _VPS_SUI_ADDRESS:
        raise HTTPException(status_code=503, detail="SUI payment not configured on this structure")

    tx_digest = proof.get("tx_digest", "")
    if not tx_digest:
        raise HTTPException(status_code=400, detail="proof.tx_digest required for sui payment")

    try:
        result = await nova_client._rpc("sui_getTransactionBlock", [
            tx_digest,
            {"showInput": True, "showEffects": False, "showBalanceChanges": True},
        ])
    except Exception as e:
        log.warning("_verify_sui_payment: RPC failed: %s", e)
        raise HTTPException(status_code=502, detail="Chain query failed — try again")

    tx_data = result.get("result", {})
    if not tx_data:
        raise HTTPException(status_code=402, detail="Transaction not found on chain")

    # Check sender
    sender = (tx_data.get("transaction", {})
                     .get("data", {})
                     .get("sender", "")).lower()
    if sender != address.lower():
        raise HTTPException(status_code=402, detail="Transaction sender does not match your address")

    # Check balance changes: VPS address received SUI
    balance_changes = tx_data.get("balanceChanges") or []
    vps_received = any(
        bc.get("owner", {}).get("AddressOwner", "").lower() == _VPS_SUI_ADDRESS.lower()
        and int(bc.get("amount", 0)) > 0
        for bc in balance_changes
    )
    if not vps_received:
        raise HTTPException(status_code=402, detail="Transaction does not show SUI sent to this structure's address")


async def _process_info_trade(address: str, structure_id: str, proof: dict) -> None:
    """Player provides structure object IDs as payment.
    Server reads each from chain, stores what it learns.
    Raises HTTPException 400 if no structure_ids provided.
    """
    structure_ids = proof.get("structure_ids") or []
    if not structure_ids:
        raise HTTPException(status_code=400, detail="proof.structure_ids required for info payment")

    from src.memory_store import get_memory_store
    mem = get_memory_store(structure_id)
    learned = []
    for obj_id in structure_ids[:5]:  # cap at 5 to limit RPC calls
        try:
            result = await nova_client._rpc("sui_getObject", [
                obj_id,
                {"showContent": True, "showType": True}
            ])
            data = result.get("result", {}).get("data", {})
            type_str = data.get("type", "unknown")
            learned.append({"object_id": obj_id, "type": type_str})
        except Exception as e:
            log.debug("_process_info_trade: could not read %s: %s", obj_id[:12], e)

    # Store in memory even if chain reads partially failed
    mem.append_event("info_trade", 0, {
        "address": address,
        "structures_offered": structure_ids,
        "structures_read": learned,
    })
    log.info("info_trade: %s offered %d structures, read %d", address[:12], len(structure_ids), len(learned))
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
cd /opt/eve-frontier && .venv/bin/pytest tests/test_deal_endpoints.py -v
```
Expected: all tests PASS

- [ ] **Step 5: Run full suite**

```bash
cd /opt/eve-frontier && .venv/bin/pytest tests/ -q
```

- [ ] **Step 6: Commit**

```bash
git add main.py tests/test_deal_endpoints.py
git commit -m "feat: add /auth/deal/offer and /auth/deal/claim endpoints (item, sui, info payment)"
```

---

## Chunk 4: PATRON tier + NONE → Lobby routing in structure_chat

**Files:**
- Modify: `main.py` (structure_chat endpoint, ~lines 908–993)
- Modify: `tests/test_deal_endpoints.py` (add structure_chat PATRON test)

### Task 5: Route PATRON through structure_client; route NONE to lobby

- [ ] **Step 1: Write failing tests**

Add to `tests/test_deal_endpoints.py`:

```python
def test_structure_chat_patron_consumes_message(client):
    """PATRON tier: deal_store.consume_message called; response streams."""
    from unittest.mock import patch, MagicMock
    import jwt as pyjwt, datetime, os

    secret = os.environ.get("JWT_SECRET", "change-me-in-production")
    token = pyjwt.encode({
        "address": "0xpatron",
        "character_id": 0,
        "character_name": "Stranger",
        "tier": "PATRON",
        "structure_id": "keep-7a",
        "exp": datetime.datetime.utcnow() + datetime.timedelta(hours=1),
    }, secret, algorithm="HS256")

    mock_profile = MagicMock()
    mock_profile.system_id = 0
    mock_profile.routine_alerts = []

    with patch("main.load_structure_profile", return_value=mock_profile), \
         patch("main.detect_alerts", return_value=[]), \
         patch("main.get_memory_store", return_value=MagicMock(get_summary=lambda: {"text": ""})), \
         patch("main.build_structure_context", return_value="ctx"), \
         patch("main.deal_store.consume_message", return_value=True) as mock_consume, \
         patch("main.structure_client.stream", return_value=iter(["hello"])):
        resp = client.post(
            "/structure-chat",
            json={"structure_id": "keep-7a", "message": "hi", "history": []},
            headers={"Authorization": f"Bearer {token}"},
        )
    assert resp.status_code == 200
    mock_consume.assert_called_once_with("0xpatron", "keep-7a")


def test_structure_chat_patron_exhausted_returns_402(client):
    import jwt as pyjwt, datetime, os
    secret = os.environ.get("JWT_SECRET", "change-me-in-production")
    token = pyjwt.encode({
        "address": "0xpatron",
        "character_id": 0,
        "character_name": "Stranger",
        "tier": "PATRON",
        "structure_id": "keep-7a",
        "exp": datetime.datetime.utcnow() + datetime.timedelta(hours=1),
    }, secret, algorithm="HS256")

    mock_profile = MagicMock()
    mock_profile.system_id = 0
    mock_profile.routine_alerts = []

    with patch("main.load_structure_profile", return_value=mock_profile), \
         patch("main.detect_alerts", return_value=[]), \
         patch("main.get_memory_store", return_value=MagicMock(get_summary=lambda: {"text": ""})), \
         patch("main.deal_store.consume_message", return_value=False):
        resp = client.post(
            "/structure-chat",
            json={"structure_id": "keep-7a", "message": "hi", "history": []},
            headers={"Authorization": f"Bearer {token}"},
        )
    assert resp.status_code == 402


def test_structure_chat_none_tier_goes_to_lobby(client):
    """NONE tier no longer returns 403 — routed to lobby_client."""
    import jwt as pyjwt, datetime, os
    secret = os.environ.get("JWT_SECRET", "change-me-in-production")
    token = pyjwt.encode({
        "address": "0xstranger",
        "character_id": 0,
        "character_name": "Stranger",
        "tier": "NONE",
        "structure_id": "keep-7a",
        "exp": datetime.datetime.utcnow() + datetime.timedelta(hours=1),
    }, secret, algorithm="HS256")

    mock_profile = MagicMock()
    mock_profile.system_id = 0
    mock_profile.routine_alerts = []

    with patch("main.load_structure_profile", return_value=mock_profile), \
         patch("main.detect_alerts", return_value=[]), \
         patch("main.get_memory_store", return_value=MagicMock(get_summary=lambda: {"text": ""})), \
         patch("main.build_structure_context", return_value="ctx"), \
         patch("main.lobby_client.stream", return_value=iter(["welcome"])) as mock_lobby:
        resp = client.post(
            "/structure-chat",
            json={"structure_id": "keep-7a", "message": "hi", "history": []},
            headers={"Authorization": f"Bearer {token}"},
        )
    assert resp.status_code == 200
    mock_lobby.assert_called_once()
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd /opt/eve-frontier && .venv/bin/pytest tests/test_deal_endpoints.py -v -k "patron or none_tier"
```
Expected: FAIL — PATRON gets 403 (NONE branch), or wrong routing

- [ ] **Step 3: Modify `structure_chat` in `main.py`**

The `deal_store` import is already there from Task 3.

In `structure_chat`, make two changes:

**Change 1:** Replace the tier check block (right after `tier = session["tier"]`, before `profile = load_structure_profile(...)`):

Replace:
```python
    tier = session["tier"]
    if tier == "NONE":
        raise HTTPException(status_code=403, detail="Access denied")

    profile = load_structure_profile(req.structure_id)
```
With:
```python
    tier = session["tier"]

    # PATRON: consume one message token before any expensive work.
    # DealStore enforces both messages_remaining and expires_at.
    # (JWT itself has a 24h expiry — deal terms are enforced server-side.)
    if tier == "PATRON":
        if not deal_store.consume_message(session["address"], req.structure_id):
            raise HTTPException(
                status_code=402,
                detail="Deal exhausted or expired. Visit /auth/deal/offer to make a new deal.",
            )
    # NONE: falls through — routed to lobby_client in event_stream below.

    profile = load_structure_profile(req.structure_id)
```

**Change 2:** In the `event_stream()` inner function, replace:
```python
            if tier == "VETTED":
```
With:
```python
            if tier in ("VETTED", "NONE"):
```
This routes both VETTED and NONE to `lobby_client.stream()`. PATRON, OWNER, TRIBE go to `structure_client.stream()`.

- [ ] **Step 4: Run tests to verify they pass**

```bash
cd /opt/eve-frontier && .venv/bin/pytest tests/test_deal_endpoints.py -v -k "patron or none_tier"
```
Expected: PASS

- [ ] **Step 5: Run full suite**

```bash
cd /opt/eve-frontier && .venv/bin/pytest tests/ -q
```

- [ ] **Step 6: Commit**

```bash
git add main.py tests/test_deal_endpoints.py
git commit -m "feat: PATRON tier consumes deal message; NONE tier routed to lobby instead of 403"
```

---

## Chunk 5: LocationIndex

**Files:**
- Create: `src/location_index.py`
- Create: `tests/test_location_index.py`
- Modify: `main.py` (add `POST /admin/rebuild-location-index` endpoint)

`LocationIndex` queries all `LocationRevealedEvent` events from the EVE Frontier package, stores `{assembly_id: {solarsystem, x, y, z, location_hash}}` in `data/location_index.json`. The admin endpoint triggers a rebuild. The index is read by the deal mechanic's info-trade flow (future enrichment) and eventually by the AI context.

### Task 6a: LocationIndex — load/get/persist (no network)

- [ ] **Step 1: Write failing tests for load/get/get_all**

Create `tests/test_location_index.py`:

```python
import pytest
import json
import os
from unittest.mock import AsyncMock, patch


@pytest.fixture
def index(tmp_path):
    from src.location_index import LocationIndex
    return LocationIndex(path=str(tmp_path / "location_index.json"))


def _make_event(assembly_id, solarsystem, x, y, z, location_hash="0xhash"):
    return {
        "parsedJson": {
            "assembly_id": assembly_id,
            "solarsystem": solarsystem,
            "x": x,
            "y": y,
            "z": z,
            "location_hash": location_hash,
        }
    }


def _rpc_page(events, has_next=False, next_cursor=None):
    return {
        "result": {
            "data": events,
            "hasNextPage": has_next,
            "nextCursor": next_cursor,
        }
    }


@pytest.mark.asyncio
async def test_rebuild_stores_events(index):
    page = _rpc_page([
        _make_event("0xassem1", "UTR-SN4", 100, 200, 300),
        _make_event("0xassem2", "I.59R.8J2", 400, 500, 600),
    ])
    with patch("src.location_index.nova_client._rpc", new_callable=AsyncMock, return_value=page):
        await index.rebuild()
    assert index.get("0xassem1") == {"solarsystem": "UTR-SN4", "x": 100, "y": 200, "z": 300, "location_hash": "0xhash"}
    assert index.get("0xassem2") is not None


@pytest.mark.asyncio
async def test_rebuild_persists_to_disk(index, tmp_path):
    page = _rpc_page([_make_event("0xassem1", "UTR-SN4", 1, 2, 3)])
    with patch("src.location_index.nova_client._rpc", new_callable=AsyncMock, return_value=page):
        await index.rebuild()
    # Reload from disk
    from src.location_index import LocationIndex
    index2 = LocationIndex(path=str(tmp_path / "location_index.json"))
    index2.load()
    assert index2.get("0xassem1") is not None


@pytest.mark.asyncio
async def test_rebuild_paginates(index):
    page1 = _rpc_page([_make_event("0xassem1", "SYS1", 1, 2, 3)], has_next=True, next_cursor="cursor1")
    page2 = _rpc_page([_make_event("0xassem2", "SYS2", 4, 5, 6)], has_next=False)

    call_count = 0
    async def mock_rpc(method, params):
        nonlocal call_count
        call_count += 1
        return page1 if call_count == 1 else page2

    with patch("src.location_index.nova_client._rpc", side_effect=mock_rpc):
        await index.rebuild()
    assert index.get("0xassem1") is not None
    assert index.get("0xassem2") is not None
    assert call_count == 2


def test_get_missing_returns_none(index):
    assert index.get("0xunknown") is None


def test_get_all_empty(index):
    assert index.get_all() == []


@pytest.mark.asyncio
async def test_rebuild_rpc_error_is_logged_not_raised(index):
    with patch("src.location_index.nova_client._rpc", new_callable=AsyncMock, side_effect=Exception("timeout")):
        # Should not raise
        await index.rebuild()
    assert index.get_all() == []
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd /opt/eve-frontier && .venv/bin/pytest tests/test_location_index.py -v
```
Expected: ImportError — `src.location_index` not found

- [ ] **Step 3: Implement `src/location_index.py`**

```python
# src/location_index.py
"""
Indexes LocationRevealedEvent from the EVE Frontier package.
Each event pairs an assembly_id with real-world coordinates.
Persisted to data/location_index.json; rebuilt on demand via admin endpoint.
"""
import os
import json
import logging
from typing import Optional

log = logging.getLogger(__name__)

_DEFAULT_PATH = os.path.normpath(
    os.path.join(os.path.dirname(__file__), "..", "data", "location_index.json")
)

_EVE_FRONTIER_PACKAGE = os.environ.get(
    "EVE_FRONTIER_PACKAGE",
    "0xd12a70c74c1e759445d6f209b01d43d860e97fcf2ef72ccbbd00afd828043f75",
)
_LOCATION_EVENT_TYPE = f"{_EVE_FRONTIER_PACKAGE}::location::LocationRevealedEvent"


try:
    from src.nova_client import nova_client
except Exception:  # pragma: no cover
    nova_client = None  # type: ignore[assignment]


class LocationIndex:
    def __init__(self, path: str = _DEFAULT_PATH):
        self._path = path
        self._data: dict = {}  # {assembly_id: {solarsystem, x, y, z, location_hash}}

    def load(self) -> None:
        """Load index from disk if it exists."""
        if not os.path.exists(self._path):
            return
        try:
            with open(self._path) as f:
                self._data = json.load(f)
            log.info("LocationIndex: loaded %d entries", len(self._data))
        except Exception as e:
            log.warning("LocationIndex.load failed: %s", e)

    def _save(self) -> None:
        try:
            os.makedirs(os.path.dirname(self._path), exist_ok=True)
            with open(self._path, "w") as f:
                json.dump(self._data, f, indent=2)
        except Exception as e:
            log.warning("LocationIndex._save failed: %s", e)

    async def rebuild(self) -> int:
        """
        Fetch all LocationRevealedEvent pages from chain, rebuild index.
        Returns number of entries indexed.
        """
        new_data: dict = {}
        cursor = None

        try:
            while True:
                result = await nova_client._rpc("suix_queryEvents", [
                    {"MoveEventType": _LOCATION_EVENT_TYPE},
                    cursor,
                    50,
                    False,  # ascending — process oldest first
                ])
                page = result.get("result", {})
                events = page.get("data") or []
                for event in events:
                    parsed = event.get("parsedJson") or {}
                    assembly_id = parsed.get("assembly_id")
                    if not assembly_id:
                        continue
                    new_data[assembly_id] = {
                        "solarsystem": parsed.get("solarsystem", ""),
                        "x": parsed.get("x"),
                        "y": parsed.get("y"),
                        "z": parsed.get("z"),
                        "location_hash": parsed.get("location_hash", ""),
                    }
                if not page.get("hasNextPage"):
                    break
                cursor = page.get("nextCursor")
        except Exception as e:
            log.warning("LocationIndex.rebuild failed: %s", e)
            return 0

        self._data = new_data
        self._save()
        log.info("LocationIndex: rebuilt with %d entries", len(self._data))
        return len(self._data)

    def get(self, assembly_id: str) -> Optional[dict]:
        return self._data.get(assembly_id)

    def get_all(self) -> list:
        return [{"assembly_id": k, **v} for k, v in self._data.items()]


# Module-level singleton.
# load() only reads data/location_index.json from disk — no network call.
# rebuild() is the network call; it is only invoked by the admin endpoint.
location_index = LocationIndex()
location_index.load()
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
cd /opt/eve-frontier && .venv/bin/pytest tests/test_location_index.py -v
```
Expected: 7 tests PASS

- [ ] **Step 5: Add admin endpoint to `main.py`**

Add import at top (alongside `nova_client` import):
```python
from src.location_index import location_index
```

Add endpoint (after `/admin/rebuild-index`):
```python
@app.post("/admin/rebuild-location-index", dependencies=[Depends(require_token)])
async def rebuild_location_index():
    """Rebuild LocationRevealedEvent index from chain. Requires X-Server-Token."""
    count = await location_index.rebuild()
    return {"entries_indexed": count}
```

- [ ] **Step 6: Run full suite**

```bash
cd /opt/eve-frontier && .venv/bin/pytest tests/ -q
```
Expected: all tests pass

- [ ] **Step 7: Commit**

```bash
git add src/location_index.py tests/test_location_index.py main.py
git commit -m "feat: add LocationIndex (LocationRevealedEvent indexer) + admin rebuild endpoint"
```

---

## Final verification

- [ ] **Run full test suite**

```bash
cd /opt/eve-frontier && .venv/bin/pytest tests/ -v
```
Expected: 115+ tests passing (previous baseline 91 + new tests across 3 new test files)

- [ ] **Smoke-test deal flow manually**

```bash
# Get a deal offer
curl -s -X POST http://localhost:8745/auth/deal/offer \
  -H "Content-Type: application/json" \
  -d '{"structure_id":"keep-7a","address":"0xtest"}' | jq

# Trigger location index rebuild
curl -s -X POST -H "X-Server-Token: $SERVER_TOKEN" \
  http://localhost:8745/admin/rebuild-location-index | jq
```

- [ ] **Update `.env.example`**

Add:
```
# Deal mechanic
VPS_SUI_ADDRESS=0x9a3e...       # VPS deployer wallet — receives SUI payments
EVE_FRONTIER_PACKAGE=0xd12a70c74c1e759445d6f209b01d43d860e97fcf2ef72ccbbd00afd828043f75
```

- [ ] **Update `docs/ref/ops.md`**

Add to Known Gaps table (resolve existing entries if they apply):
```
| Deal mechanic | PATRON JWT issued server-side; no on-chain enforcement | Post-hackathon |
| LUX token payment | LUX CoinType not yet located in EVE contracts — deferred | Medium |
```

Add new config vars to the Server `.env` section.

- [ ] **Final commit**

```bash
git add .env.example docs/ref/ops.md
git commit -m "docs: add VPS_SUI_ADDRESS + EVE_FRONTIER_PACKAGE to .env.example; update ops.md"
```
