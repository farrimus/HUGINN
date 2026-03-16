# tests/test_blockchain_client.py
"""Tests for BlockchainClient — REST wrapper over the EVE Frontier blockchain gateway."""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
import httpx

from src.blockchain_client import BlockchainClient


def _make_client() -> BlockchainClient:
    return BlockchainClient(base_url="https://test.gateway.example", cache_ttl=120.0)


# ---------------------------------------------------------------------------
# get_assembly
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_get_assembly_returns_none_on_network_error():
    """ConnectError → None returned, no exception raised."""
    client = _make_client()
    mock_http = AsyncMock()
    mock_http.is_closed = False
    mock_http.get = AsyncMock(side_effect=httpx.ConnectError("DNS failure"))
    client._http = mock_http

    result = await client.get_assembly("0xabc")
    assert result is None


@pytest.mark.asyncio
async def test_get_assembly_returns_none_on_http_error():
    """Non-2xx response → None returned."""
    client = _make_client()
    mock_resp = MagicMock()
    mock_resp.raise_for_status = MagicMock(
        side_effect=httpx.HTTPStatusError("404", request=MagicMock(), response=MagicMock(status_code=404))
    )
    mock_http = AsyncMock()
    mock_http.is_closed = False
    mock_http.get = AsyncMock(return_value=mock_resp)
    client._http = mock_http

    result = await client.get_assembly("0xabc")
    assert result is None


@pytest.mark.asyncio
async def test_get_assembly_cached_on_second_call():
    """Second call with same ID returns cached result without hitting network."""
    client = _make_client()
    payload = {"assemblyId": "0xabc", "status": "ONLINE"}

    mock_resp = MagicMock()
    mock_resp.raise_for_status = MagicMock()
    mock_resp.json = MagicMock(return_value=payload)
    mock_http = AsyncMock()
    mock_http.is_closed = False
    mock_http.get = AsyncMock(return_value=mock_resp)
    client._http = mock_http

    first  = await client.get_assembly("0xabc")
    second = await client.get_assembly("0xabc")

    assert first == payload
    assert second == payload
    # HTTP layer only called once
    assert mock_http.get.call_count == 1


# ---------------------------------------------------------------------------
# get_assemblies_in_system
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_get_assemblies_in_system_returns_empty_on_error():
    """Network error → [] returned."""
    client = _make_client()
    mock_http = AsyncMock()
    mock_http.is_closed = False
    mock_http.get = AsyncMock(side_effect=httpx.ConnectError("DNS"))
    client._http = mock_http

    result = await client.get_assemblies_in_system(30000001)
    assert result == []


@pytest.mark.asyncio
async def test_get_assemblies_in_system_returns_list():
    """Valid list response is passed through."""
    client = _make_client()
    payload = [{"assemblyId": "0x1"}, {"assemblyId": "0x2"}]

    mock_resp = MagicMock()
    mock_resp.raise_for_status = MagicMock()
    mock_resp.json = MagicMock(return_value=payload)
    mock_http = AsyncMock()
    mock_http.is_closed = False
    mock_http.get = AsyncMock(return_value=mock_resp)
    client._http = mock_http

    result = await client.get_assemblies_in_system(30000001)
    assert result == payload


# ---------------------------------------------------------------------------
# _parse_inventory
# ---------------------------------------------------------------------------

def test_parse_inventory_returns_empty_on_unknown_structure():
    client = _make_client()
    result = client._parse_inventory({"someOtherKey": "value"})
    assert result == []


def test_parse_inventory_returns_empty_on_empty_dict():
    client = _make_client()
    assert client._parse_inventory({}) == []


def test_parse_inventory_reads_inventory_key():
    client = _make_client()
    data = {
        "inventory": [
            {"typeName": "Tritanium", "quantity": 500},
            {"typeName": "Fuel Block", "quantity": 10},
        ]
    }
    result = client._parse_inventory(data)
    assert len(result) == 2
    assert result[0] == {"type_name": "Tritanium", "quantity": 500}
    assert result[1] == {"type_name": "Fuel Block", "quantity": 10}


def test_parse_inventory_reads_items_key():
    client = _make_client()
    data = {"items": [{"name": "Ore", "quantity": 100}]}
    result = client._parse_inventory(data)
    assert len(result) == 1
    assert result[0]["type_name"] == "Ore"
    assert result[0]["quantity"] == 100
