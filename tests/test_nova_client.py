import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from src.nova_client import NovaClient, AccessRegistry


def make_mock_client(json_response):
    """Build a mock httpx.AsyncClient context manager that returns the given JSON."""
    mock_resp = MagicMock()
    mock_resp.json.return_value = json_response
    mock_resp.raise_for_status = MagicMock()
    mock_instance = AsyncMock()
    mock_instance.post = AsyncMock(return_value=mock_resp)
    mock_cm = MagicMock()
    mock_cm.__aenter__ = AsyncMock(return_value=mock_instance)
    mock_cm.__aexit__ = AsyncMock(return_value=False)
    return mock_cm


@pytest.fixture
def client():
    return NovaClient(rpc_url="https://mock-nova-rpc.example.com")


@pytest.mark.asyncio
async def test_get_access_registry_returns_registry(client):
    mock_response = {
        "result": {
            "data": {
                "content": {
                    "fields": {
                        "structure_id": "keep-7a",
                        "owner": "0xowner",
                        "tribe": ["0xtribe1", "0xtribe2"],
                        "vetted": ["0xvetted1"],
                    }
                }
            }
        }
    }
    with patch("src.nova_client.httpx.AsyncClient", return_value=make_mock_client(mock_response)):
        registry = await client.get_access_registry("0xreg_object_id")
    assert registry.owner == "0xowner"
    assert "0xtribe1" in registry.tribe
    assert "0xvetted1" in registry.vetted


def test_resolve_tier_owner(client):
    registry = AccessRegistry(owner="0xowner", tribe=[], vetted=[])
    assert client.resolve_tier("0xowner", registry) == "OWNER"


def test_resolve_tier_tribe(client):
    registry = AccessRegistry(owner="0xowner", tribe=["0xtribe1"], vetted=[])
    assert client.resolve_tier("0xtribe1", registry) == "TRIBE"


def test_resolve_tier_vetted(client):
    registry = AccessRegistry(owner="0xother", tribe=[], vetted=["0xvetted1"])
    assert client.resolve_tier("0xvetted1", registry) == "VETTED"


def test_resolve_tier_none(client):
    registry = AccessRegistry(owner="0xother", tribe=[], vetted=[])
    assert client.resolve_tier("0xstranger", registry) == "NONE"


@pytest.mark.asyncio
async def test_get_access_registry_rpc_error_returns_none(client):
    mock_cm = MagicMock()
    mock_instance = AsyncMock()
    mock_instance.post = AsyncMock(side_effect=Exception("RPC connection refused"))
    mock_cm.__aenter__ = AsyncMock(return_value=mock_instance)
    mock_cm.__aexit__ = AsyncMock(return_value=False)
    with patch("src.nova_client.httpx.AsyncClient", return_value=mock_cm):
        registry = await client.get_access_registry("0xreg_object_id")
    assert registry is None
