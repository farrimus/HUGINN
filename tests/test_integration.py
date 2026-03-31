# tests/test_integration.py
import pytest
import asyncio
import datetime
import jwt as pyjwt
from unittest.mock import AsyncMock, patch
from httpx import AsyncClient, ASGITransport
from main import app

def _get_valid_token():
    """Generate a valid JWT token for testing."""
    from src.structure_auth import JWT_SECRET, JWT_ALGORITHM
    payload = {
        "sub": "test-agent",
        "exp": datetime.datetime.utcnow() + datetime.timedelta(hours=24),
    }
    return pyjwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)

@pytest.mark.asyncio
async def test_system_change_triggers_world_api_refresh(monkeypatch):
    from src import world_api as wa_module
    mock_get = AsyncMock(return_value={"name": "Jita", "security": 0.9})
    wa_module.world_api.get_system = mock_get

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post(
            "/log/ingest",
            json={"type": "system_change", "system": "Jita"},
            headers={"Authorization": f"Bearer {_get_valid_token()}"}
        )

    assert response.status_code == 200
    # Give the background task a moment to run
    await asyncio.sleep(0.1)
    mock_get.assert_called_once_with("Jita")

@pytest.mark.asyncio
async def test_non_system_change_does_not_trigger_refresh(monkeypatch):
    from src import world_api as wa_module
    mock_get = AsyncMock(return_value=None)
    wa_module.world_api.get_system = mock_get

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        await client.post(
            "/log/ingest",
            json={"type": "combat", "data": {"damage": 100}},
            headers={"Authorization": f"Bearer {_get_valid_token()}"}
        )

    await asyncio.sleep(0.1)
    mock_get.assert_not_called()
