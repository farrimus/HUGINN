import pytest
from unittest.mock import patch, AsyncMock
from fastapi.testclient import TestClient


@pytest.fixture
def client():
    from main import app
    with patch("main.world_api.load_or_build_index", new_callable=AsyncMock), \
         patch("src.ssu_poller.start_background_tasks"):
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


import base64


def _fake_zklogin_sig():
    """Minimal zkLogin-flagged signature accepted by verify_sui_personal_message."""
    return base64.b64encode(bytes([0x05]) + bytes(96)).decode()


def test_deal_claim_item_payment(client):
    """Item payment: server finds a recent ItemDepositedEvent from the player."""
    import time as _time
    fake_events = {
        "result": {
            "data": [
                {
                    "sender": "0xplayer",
                    "type": "0xpkg::ephemeral_inventory::ItemDepositedEvent",
                    "parsedJson": {"sender": "0xplayer", "type_id": 1234, "quantity": 1},
                    "timestampMs": str(int((_time.time() - 30) * 1000)),
                }
            ],
            "hasNextPage": False,
        }
    }

    with patch("src.blockchain_queries.nova_client._rpc", new_callable=AsyncMock, return_value=fake_events), \
         patch("src.structure_auth.verify_sui_personal_message", return_value=True), \
         patch("src.structure_auth.lookup_character", new_callable=AsyncMock, return_value={}), \
         patch("src.memory_store.MemoryStore.upsert_pilot"):
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

    with patch("src.blockchain_queries.nova_client._rpc", new_callable=AsyncMock, return_value=fake_obj), \
         patch("src.structure_auth.verify_sui_personal_message", return_value=True), \
         patch("src.structure_auth.lookup_character", new_callable=AsyncMock, return_value={}), \
         patch("src.memory_store.MemoryStore.upsert_pilot"), \
         patch("src.memory_store.MemoryStore.append_event"):
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

    with patch("src.blockchain_queries.nova_client._rpc", new_callable=AsyncMock, return_value=empty_events), \
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


def test_structure_chat_patron_consumes_message(client):
    """PATRON tier: deal_store.consume_message called before streaming."""
    import jwt as pyjwt, datetime
    from unittest.mock import patch, MagicMock
    from src.structure_auth import JWT_SECRET as secret

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
         patch("src.memory_store.get_memory_store", return_value=MagicMock(get_summary=lambda: {"text": ""})), \
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
    import jwt as pyjwt, datetime
    from unittest.mock import patch, MagicMock
    from src.structure_auth import JWT_SECRET as secret

    token = pyjwt.encode({
        "address": "0xpatron",
        "character_id": 0,
        "character_name": "Stranger",
        "tier": "PATRON",
        "structure_id": "keep-7a",
        "exp": datetime.datetime.utcnow() + datetime.timedelta(hours=1),
    }, secret, algorithm="HS256")

    with patch("main.deal_store.consume_message", return_value=False):
        resp = client.post(
            "/structure-chat",
            json={"structure_id": "keep-7a", "message": "hi", "history": []},
            headers={"Authorization": f"Bearer {token}"},
        )
    assert resp.status_code == 402


def test_structure_chat_none_tier_goes_to_lobby(client):
    """NONE tier is routed to lobby_client, not 403."""
    import jwt as pyjwt, datetime
    from unittest.mock import patch, MagicMock
    from src.structure_auth import JWT_SECRET as secret

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
         patch("src.memory_store.get_memory_store", return_value=MagicMock(get_summary=lambda: {"text": ""})), \
         patch("main.build_structure_context", return_value="ctx"), \
         patch("main.lobby_client.stream", return_value=iter(["welcome"])) as mock_lobby:
        resp = client.post(
            "/structure-chat",
            json={"structure_id": "keep-7a", "message": "hi", "history": []},
            headers={"Authorization": f"Bearer {token}"},
        )
    assert resp.status_code == 200
    mock_lobby.assert_called_once()
