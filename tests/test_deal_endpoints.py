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
