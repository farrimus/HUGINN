"""Tests for token-protected endpoint validation."""
import pytest
from fastapi.testclient import TestClient
from unittest.mock import patch, AsyncMock, MagicMock
import jwt as pyjwt
import datetime


@pytest.fixture
def client():
    """FastAPI test client with mocked background tasks."""
    from main import app
    with patch("main.world_api.load_or_build_index", new_callable=AsyncMock), \
         patch("src.ssu_poller.start_background_tasks"):
        with TestClient(app) as c:
            yield c


@pytest.fixture
def token_manager():
    """Mock TokenManager for issuing test tokens."""
    from src.structure_auth import JWT_SECRET as secret

    class MockTokenManager:
        def issue_token(self, agent_id: str) -> str:
            """Issue a JWT token for the given agent ID."""
            payload = {
                "sub": agent_id,
                "exp": datetime.datetime.utcnow() + datetime.timedelta(hours=24),
            }
            return pyjwt.encode(payload, secret, algorithm="HS256")

        def validate_token(self, token: str) -> dict:
            """Validate a JWT token and return its payload."""
            try:
                return pyjwt.decode(token, secret, algorithms=["HS256"])
            except Exception:
                return None

    return MockTokenManager()


def test_protected_endpoint_requires_valid_token(client, token_manager):
    """Protected endpoints reject requests without valid token."""
    # Request without token
    response = client.post("/log/ingest", json={})
    assert response.status_code == 401

    # Request with invalid token
    response = client.post(
        "/log/ingest",
        json={},
        headers={"Authorization": "Bearer invalid_token"}
    )
    assert response.status_code == 401


def test_protected_endpoint_accepts_valid_token(client, token_manager):
    """Protected endpoints accept requests with valid token."""
    # Issue a valid token
    token = token_manager.issue_token("test-agent-001")

    # Request with valid token
    response = client.post(
        "/log/ingest",
        json={
            "type": "test",
            "timestamp": "2026-03-17T00:00:00Z",
            "data": {}
        },
        headers={"Authorization": f"Bearer {token}"}
    )
    # Should NOT be 401 (auth passed; may fail on other validation)
    assert response.status_code != 401
