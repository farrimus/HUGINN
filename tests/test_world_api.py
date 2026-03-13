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
