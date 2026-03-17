import pytest
from httpx import AsyncClient, ASGITransport
from main import app
from src.token_manager import TokenManager
import tempfile
import os

@pytest.fixture
async def client():
    """Create async test client."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as _client:
        yield _client

@pytest.mark.asyncio
async def test_auth_token_endpoint(client):
    """POST /auth/token with valid agent_id returns JWT token."""
    response = await client.post("/auth/token", json={"agent_id": "test-agent-001"})

    assert response.status_code == 200
    data = response.json()
    assert "access_token" in data
    assert "token_type" in data
    assert data["token_type"] == "Bearer"
    assert "expires_in" in data

@pytest.mark.asyncio
async def test_auth_token_requires_agent_id(client):
    """POST /auth/token without agent_id returns 422 (Pydantic validation error)."""
    response = await client.post("/auth/token", json={})
    assert response.status_code == 422

@pytest.mark.asyncio
async def test_auth_token_empty_string(client):
    """POST /auth/token with empty agent_id returns 400."""
    response = await client.post("/auth/token", json={"agent_id": ""})
    assert response.status_code in [400, 422]

@pytest.mark.asyncio
async def test_auth_token_whitespace_only(client):
    """POST /auth/token with whitespace-only agent_id returns 400."""
    response = await client.post("/auth/token", json={"agent_id": "   "})
    assert response.status_code in [400, 422]

@pytest.mark.asyncio
async def test_auth_token_format(client):
    """Returned token is valid JWT format."""
    response = await client.post("/auth/token", json={"agent_id": "test-agent-001"})
    assert response.status_code == 200
    data = response.json()
    token = data["access_token"]
    # JWT has 3 parts separated by dots
    assert token.count(".") == 2
    assert len(token) > 50  # Valid JWT tokens are reasonably long
