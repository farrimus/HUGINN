# tests/test_world_api.py
import asyncio
import pytest
import time
from unittest.mock import AsyncMock, patch
from src.world_api import WorldAPIClient

@pytest.mark.asyncio
async def test_get_system_returns_data():
    client = WorldAPIClient(base_url="https://fake.api", api_key="")
    mock_response = {"name": "Jita", "security": 0.9, "kills": []}
    with patch.object(client, "_fetch", new=AsyncMock(return_value=mock_response)):
        result = await client.get_system("Jita")
    assert result["name"] == "Jita"

@pytest.mark.asyncio
async def test_cache_returns_cached_result():
    client = WorldAPIClient(base_url="https://fake.api", api_key="")
    mock_response = {"name": "Jita"}
    with patch.object(client, "_fetch", new=AsyncMock(return_value=mock_response)) as mock_fetch:
        await client.get_system("Jita")
        await client.get_system("Jita")
    assert mock_fetch.call_count == 1  # second call hit cache

@pytest.mark.asyncio
async def test_cache_expires_after_ttl():
    client = WorldAPIClient(base_url="https://fake.api", api_key="", cache_ttl=0.1)
    mock_response = {"name": "Jita"}
    with patch.object(client, "_fetch", new=AsyncMock(return_value=mock_response)) as mock_fetch:
        await client.get_system("Jita")
        await asyncio.sleep(0.2)
        await client.get_system("Jita")
    assert mock_fetch.call_count == 2  # cache expired

@pytest.mark.asyncio
async def test_different_systems_cached_independently():
    client = WorldAPIClient(base_url="https://fake.api", api_key="")
    with patch.object(client, "_fetch", new=AsyncMock(return_value={"name": "X"})) as mock_fetch:
        await client.get_system("Jita")
        await client.get_system("Amarr")
    assert mock_fetch.call_count == 2

@pytest.mark.asyncio
async def test_returns_none_on_api_error():
    client = WorldAPIClient(base_url="https://fake.api", api_key="")
    with patch.object(client, "_fetch", new=AsyncMock(side_effect=Exception("timeout"))):
        result = await client.get_system("Jita")
    assert result is None

@pytest.mark.asyncio
async def test_get_killmails_returns_empty_list_on_error():
    client = WorldAPIClient(base_url="https://fake.api", api_key="")
    with patch.object(client, "_fetch", new=AsyncMock(side_effect=Exception("timeout"))):
        result = await client.get_killmails("Jita")
    assert result == []

@pytest.mark.asyncio
async def test_get_killmails_returns_empty_list_on_empty_response():
    client = WorldAPIClient(base_url="https://fake.api", api_key="")
    with patch.object(client, "_fetch", new=AsyncMock(return_value=[])):
        result = await client.get_killmails("Jita")
    assert result == []
