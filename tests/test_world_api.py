# tests/test_world_api.py
import asyncio
import pytest
import time
from unittest.mock import AsyncMock, patch
from src.world_api import WorldAPIClient

# ------------------------------------------------------------------
# System index tests
# ------------------------------------------------------------------

@pytest.mark.asyncio
async def test_build_system_index_populates_name_to_id():
    client = WorldAPIClient(base_url="https://fake.api")
    mock_page = {
        "data": [
            {"id": 1001, "name": "Jita"},
            {"id": 1002, "name": "Amarr"},
        ],
        "metadata": {"total": 2, "limit": 1000, "offset": 0}
    }
    with patch.object(client, "_fetch", new=AsyncMock(return_value=mock_page)), \
         patch.object(client, "save_index_to_disk"):
        count = await client.build_system_index()
    assert count == 2
    assert client.resolve_system_id("Jita") == 1001
    assert client.resolve_system_id("Amarr") == 1002

@pytest.mark.asyncio
async def test_build_system_index_case_insensitive():
    client = WorldAPIClient(base_url="https://fake.api")
    mock_page = {
        "data": [{"id": 1001, "name": "Jita"}],
        "metadata": {"total": 1, "limit": 1000, "offset": 0}
    }
    with patch.object(client, "_fetch", new=AsyncMock(return_value=mock_page)), \
         patch.object(client, "save_index_to_disk"):
        await client.build_system_index()
    assert client.resolve_system_id("JITA") == 1001
    assert client.resolve_system_id("jita") == 1001

@pytest.mark.asyncio
async def test_build_system_index_paginates():
    client = WorldAPIClient(base_url="https://fake.api")
    page1 = {
        "data": [{"id": 1001, "name": "Jita"}],
        "metadata": {"total": 2, "limit": 1, "offset": 0}
    }
    page2 = {
        "data": [{"id": 1002, "name": "Amarr"}],
        "metadata": {"total": 2, "limit": 1, "offset": 1}
    }
    with patch.object(client, "_fetch", new=AsyncMock(side_effect=[page1, page2])), \
         patch.object(client, "save_index_to_disk"):
        count = await client.build_system_index()
    assert count == 2

@pytest.mark.asyncio
async def test_resolve_system_id_returns_none_when_not_indexed():
    client = WorldAPIClient(base_url="https://fake.api")
    assert client.resolve_system_id("Nonexistent") is None

# ------------------------------------------------------------------
# get_system tests
# ------------------------------------------------------------------

@pytest.mark.asyncio
async def test_get_system_returns_data_by_name():
    client = WorldAPIClient(base_url="https://fake.api")
    client._system_index = {"jita": 1001}
    mock_data = {"id": 1001, "name": "Jita", "gateLinks": []}
    with patch.object(client, "_fetch", new=AsyncMock(return_value=mock_data)):
        result = await client.get_system("Jita")
    assert result["id"] == 1001
    assert result["name"] == "Jita"

@pytest.mark.asyncio
async def test_get_system_returns_none_if_not_in_index():
    client = WorldAPIClient(base_url="https://fake.api")
    client._system_index = {}
    result = await client.get_system("Unknown System")
    assert result is None

@pytest.mark.asyncio
async def test_get_system_cache_hit_skips_fetch():
    client = WorldAPIClient(base_url="https://fake.api")
    client._system_index = {"jita": 1001}
    mock_data = {"id": 1001, "name": "Jita"}
    with patch.object(client, "_fetch", new=AsyncMock(return_value=mock_data)) as mock_fetch:
        await client.get_system("Jita")
        await client.get_system("Jita")
    assert mock_fetch.call_count == 1

@pytest.mark.asyncio
async def test_get_system_cache_expires():
    client = WorldAPIClient(base_url="https://fake.api", cache_ttl=0.1)
    client._system_index = {"jita": 1001}
    mock_data = {"id": 1001, "name": "Jita"}
    with patch.object(client, "_fetch", new=AsyncMock(return_value=mock_data)) as mock_fetch:
        await client.get_system("Jita")
        await asyncio.sleep(0.2)
        await client.get_system("Jita")
    assert mock_fetch.call_count == 2

@pytest.mark.asyncio
async def test_get_system_returns_none_on_api_error():
    client = WorldAPIClient(base_url="https://fake.api")
    client._system_index = {"jita": 1001}
    with patch.object(client, "_fetch", new=AsyncMock(side_effect=Exception("timeout"))):
        result = await client.get_system("Jita")
    assert result is None

# ------------------------------------------------------------------
# DEPLOYMENT_ENV switching tests
# ------------------------------------------------------------------

import os

def test_utopia_env_sets_base_url():
    from src.world_api import WorldAPIClient
    with patch.dict(os.environ, {"DEPLOYMENT_ENV": "utopia", "WORLD_API_BASE_URL": ""}):
        client = WorldAPIClient()
        assert "utopia" in client.base_url

def test_stillness_env_sets_base_url():
    from src.world_api import WorldAPIClient
    with patch.dict(os.environ, {"DEPLOYMENT_ENV": "stillness", "WORLD_API_BASE_URL": ""}):
        client = WorldAPIClient()
        assert "stillness" in client.base_url

def test_world_api_env_default_is_utopia():
    """When DEPLOYMENT_ENV is unset, default must be utopia (hackathon default)."""
    from src.world_api import WorldAPIClient
    env_without_overrides = {k: v for k, v in os.environ.items()
                             if k not in ("DEPLOYMENT_ENV", "WORLD_API_BASE_URL")}
    with patch.dict(os.environ, env_without_overrides, clear=True):
        client = WorldAPIClient()
        assert "utopia" in client.base_url

def test_base_url_override_takes_precedence():
    from src.world_api import WorldAPIClient
    with patch.dict(os.environ, {"WORLD_API_BASE_URL": "http://custom", "DEPLOYMENT_ENV": "utopia"}):
        client = WorldAPIClient()
        assert client.base_url == "http://custom"

@pytest.mark.asyncio
async def test_get_killmails_returns_list():
    from src.world_api import WorldAPIClient
    client = WorldAPIClient(base_url="http://fake")
    with patch.object(client, "_fetch", new_callable=AsyncMock) as mock_fetch:
        mock_fetch.return_value = [
            {"id": 1, "time": "2026-03-15T12:00:00Z", "victimName": "Pilot A",
             "victimShip": "Frigate", "attackers": [], "totalValue": 1000000}
        ]
        result = await client.get_killmails(system_id=30000142)
        assert isinstance(result, list)
        mock_fetch.assert_called_once()
        call_args = mock_fetch.call_args
        assert "30000142" in str(call_args)

@pytest.mark.asyncio
async def test_get_killmails_wraps_dict_response():
    """API may return {"data": [...]} instead of a bare list."""
    from src.world_api import WorldAPIClient
    client = WorldAPIClient(base_url="http://fake")
    with patch.object(client, "_fetch", new_callable=AsyncMock) as mock_fetch:
        mock_fetch.return_value = {"data": [{"id": 99}], "total": 1}
        result = await client.get_killmails(system_id=30000142)
        assert isinstance(result, list)
        assert result[0]["id"] == 99

@pytest.mark.asyncio
async def test_get_killmails_returns_empty_on_error():
    from src.world_api import WorldAPIClient
    client = WorldAPIClient(base_url="http://fake")
    with patch.object(client, "_fetch", new_callable=AsyncMock, side_effect=Exception("timeout")):
        result = await client.get_killmails(system_id=30000142)
        assert result == []
