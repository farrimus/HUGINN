"""
Integration test for end-to-end token authentication flow.

Tests the complete flow from token request through protected endpoint access,
verifying JWT structure, error handling, and authorization.
"""

import pytest
from httpx import AsyncClient, ASGITransport
from main import app
from src.token_manager import TokenManager
from src.endpoints.auth import token_manager


@pytest.fixture
async def client():
    """Create async test client."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as _client:
        yield _client


@pytest.mark.asyncio
async def test_full_token_flow(client):
    """Full flow: request token, use token, access protected endpoint."""
    # 1. Request token
    response = await client.post("/auth/token", json={"agent_id": "test-agent-001"})
    assert response.status_code == 200
    token = response.json()["access_token"]

    # 2. Use token to access protected endpoint (/log/ingest)
    response = await client.post(
        "/log/ingest",
        json={"type": "test"},
        headers={"Authorization": f"Bearer {token}"}
    )
    # Should not be 401 (authentication passed)
    assert response.status_code != 401

    # 3. Request without token should fail
    response = await client.post("/log/ingest", json={"type": "test"})
    assert response.status_code in [401, 403]


@pytest.mark.asyncio
async def test_token_structure(client):
    """Verify issued token has correct JWT structure."""
    response = await client.post("/auth/token", json={"agent_id": "test-agent"})
    assert response.status_code == 200

    token = response.json()["access_token"]

    # JWT has 3 parts: header.payload.signature
    parts = token.split(".")
    assert len(parts) == 3
    assert all(part for part in parts)  # No empty parts


@pytest.mark.asyncio
async def test_invalid_token_rejected(client):
    """Invalid tokens are rejected with 401."""
    response = await client.post(
        "/log/ingest",
        json={"type": "test"},
        headers={"Authorization": "Bearer invalid.token.here"}
    )
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_malformed_authorization_header(client):
    """Malformed Authorization header returns 401/403."""
    # Missing "Bearer " prefix
    response = await client.post(
        "/log/ingest",
        json={"type": "test"},
        headers={"Authorization": "InvalidToken"}
    )
    assert response.status_code in [401, 403]

    # Empty Authorization header
    response = await client.post(
        "/log/ingest",
        json={"type": "test"},
        headers={"Authorization": ""}
    )
    assert response.status_code in [401, 403]


@pytest.mark.asyncio
async def test_token_response_format(client):
    """Verify token response includes required fields."""
    response = await client.post("/auth/token", json={"agent_id": "test-agent-002"})
    assert response.status_code == 200

    data = response.json()
    assert "access_token" in data
    assert "token_type" in data
    assert "expires_in" in data
    assert data["token_type"] == "Bearer"
    assert data["expires_in"] == 86400  # 24 hours in seconds
