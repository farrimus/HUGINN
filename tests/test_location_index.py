import pytest
import json
import os
from unittest.mock import AsyncMock, patch


@pytest.fixture
def index(tmp_path):
    from src.location_index import LocationIndex
    return LocationIndex(path=str(tmp_path / "location_index.json"))


def _make_event(assembly_id, solarsystem, x, y, z, location_hash="0xhash"):
    return {
        "parsedJson": {
            "assembly_id": assembly_id,
            "solarsystem": solarsystem,
            "x": x,
            "y": y,
            "z": z,
            "location_hash": location_hash,
        }
    }


def _rpc_page(events, has_next=False, next_cursor=None):
    return {
        "result": {
            "data": events,
            "hasNextPage": has_next,
            "nextCursor": next_cursor,
        }
    }


@pytest.mark.asyncio
async def test_rebuild_stores_events(index):
    page = _rpc_page([
        _make_event("0xassem1", "UTR-SN4", 100, 200, 300),
        _make_event("0xassem2", "I.59R.8J2", 400, 500, 600),
    ])
    with patch("src.location_index.nova_client._rpc", new_callable=AsyncMock, return_value=page):
        await index.rebuild()
    assert index.get("0xassem1") == {"solarsystem": "UTR-SN4", "x": 100, "y": 200, "z": 300, "location_hash": "0xhash"}
    assert index.get("0xassem2") is not None


@pytest.mark.asyncio
async def test_rebuild_persists_to_disk(index, tmp_path):
    page = _rpc_page([_make_event("0xassem1", "UTR-SN4", 1, 2, 3)])
    with patch("src.location_index.nova_client._rpc", new_callable=AsyncMock, return_value=page):
        await index.rebuild()
    # Reload from disk
    from src.location_index import LocationIndex
    index2 = LocationIndex(path=str(tmp_path / "location_index.json"))
    index2.load()
    assert index2.get("0xassem1") is not None


@pytest.mark.asyncio
async def test_rebuild_paginates(index):
    page1 = _rpc_page([_make_event("0xassem1", "SYS1", 1, 2, 3)], has_next=True, next_cursor="cursor1")
    page2 = _rpc_page([_make_event("0xassem2", "SYS2", 4, 5, 6)], has_next=False)

    call_count = 0
    async def mock_rpc(method, params):
        nonlocal call_count
        call_count += 1
        return page1 if call_count == 1 else page2

    with patch("src.location_index.nova_client._rpc", side_effect=mock_rpc):
        await index.rebuild()
    assert index.get("0xassem1") is not None
    assert index.get("0xassem2") is not None
    assert call_count == 2


def test_get_missing_returns_none(index):
    assert index.get("0xunknown") is None


def test_get_all_empty(index):
    assert index.get_all() == []


@pytest.mark.asyncio
async def test_rebuild_rpc_error_is_logged_not_raised(index):
    with patch("src.location_index.nova_client._rpc", new_callable=AsyncMock, side_effect=Exception("timeout")):
        # Should not raise
        await index.rebuild()
    assert index.get_all() == []


@pytest.mark.asyncio
async def test_load_from_disk(index, tmp_path):
    """load() reads from disk — no network call."""
    data = {"0xassem1": {"solarsystem": "UTR-SN4", "x": 1, "y": 2, "z": 3, "location_hash": "0xh"}}
    path = tmp_path / "location_index.json"
    path.write_text(json.dumps(data))
    index.load()
    assert index.get("0xassem1") == {"solarsystem": "UTR-SN4", "x": 1, "y": 2, "z": 3, "location_hash": "0xh"}
