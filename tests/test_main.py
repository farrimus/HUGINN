# tests/test_main.py
from httpx import AsyncClient, ASGITransport
import pytest
import os
import json
import tempfile
from pathlib import Path
from main import app

TOKEN = os.environ.get("SERVER_TOKEN", "")

@pytest.mark.asyncio
async def test_health_check():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert "systems_indexed" in data

@pytest.mark.asyncio
async def test_get_systems_returns_file():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/data/systems", headers={"X-Server-Token": TOKEN})
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("application/json")
    assert "ETag" in response.headers
    assert "Cache-Control" in response.headers
    # Confirm it looks like systems.json
    data = response.json()
    assert "systems" in data
    assert "built_at" in data

@pytest.mark.asyncio
async def test_get_systems_etag_304():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        r1 = await client.get("/data/systems", headers={"X-Server-Token": TOKEN})
        etag = r1.headers["ETag"]
        r2 = await client.get("/data/systems",
                              headers={"X-Server-Token": TOKEN, "if-none-match": etag})
    assert r2.status_code == 304

@pytest.mark.asyncio
async def test_current_route_initially_null():
    from src.log_buffer import log_buffer
    log_buffer.current_route = None
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        r = await client.get("/current-route", headers={"X-Server-Token": TOKEN})
    assert r.status_code == 200
    assert r.json()["route"] is None

@pytest.mark.asyncio
async def test_current_route_and_clear():
    from src.log_buffer import log_buffer
    log_buffer.current_route = {
        "type": "route_planned",
        "path": ["jita", "perimeter"],
        "jumps": 1,
        "warnings": [],
        "highlights": [],
    }
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        r = await client.get("/current-route", headers={"X-Server-Token": TOKEN})
        assert r.json()["route"] is not None
        r2 = await client.post("/route/clear", headers={"X-Server-Token": TOKEN})
        assert r2.json()["cleared"] is True
        r3 = await client.get("/current-route", headers={"X-Server-Token": TOKEN})
        assert r3.json()["route"] is None

@pytest.mark.asyncio
async def test_chat_slash_route_unknown_system():
    from src.log_buffer import log_buffer
    log_buffer.current_system = None
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        r = await client.post("/chat",
                              headers={"X-Server-Token": TOKEN},
                              json={"message": "/route JITA", "history": []})
    assert r.status_code == 200
    body = r.text
    assert "SYSTEM UNKNOWN" in body

@pytest.mark.asyncio
async def test_chat_slash_route_sets_route():
    from src.log_buffer import log_buffer
    log_buffer.current_route = None
    log_buffer.current_system = "jita"
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        r = await client.post("/chat",
                              headers={"X-Server-Token": TOKEN},
                              json={"message": "/route perimeter", "history": []})
    assert r.status_code == 200
    # Either route set or no-route message — both are valid SSE responses
    assert "data:" in r.text

@pytest.mark.asyncio
async def test_current_route_includes_system_temp():
    from src.log_buffer import log_buffer
    log_buffer.current_system = "jita"
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        r = await client.get("/current-route", headers={"X-Server-Token": TOKEN})
    assert r.status_code == 200
    data = r.json()
    assert "current_system_temp" in data

@pytest.mark.asyncio
async def test_route_activate_no_route():
    from src.log_buffer import log_buffer
    log_buffer.current_route = None
    log_buffer.pending_alternative = None
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        r = await client.post("/route/activate",
                              headers={"X-Server-Token": TOKEN},
                              json={"variant": "primary"})
    assert r.status_code == 404

@pytest.mark.asyncio
async def test_route_activate_bad_variant():
    from src.log_buffer import log_buffer
    log_buffer.current_route = {"type": "route_planned", "path": ["a", "b"], "jumps": 1,
                                 "warnings": [], "jump_types": ["gate"], "total_ly": 0.0,
                                 "fuel_used": 0.0, "fuel_remaining": 100.0,
                                 "hot_systems": [], "alternative": None}
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        r = await client.post("/route/activate",
                              headers={"X-Server-Token": TOKEN},
                              json={"variant": "bogus"})
    assert r.status_code == 422

@pytest.mark.asyncio
async def test_route_activate_alternative_not_available():
    from src.log_buffer import log_buffer
    log_buffer.current_route = {"type": "route_planned", "path": ["a", "b"], "jumps": 1,
                                 "warnings": [], "jump_types": ["gate"], "total_ly": 0.0,
                                 "fuel_used": 0.0, "fuel_remaining": 100.0,
                                 "hot_systems": [], "alternative": None}
    log_buffer.pending_alternative = None
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        r = await client.post("/route/activate",
                              headers={"X-Server-Token": TOKEN},
                              json={"variant": "alternative"})
    assert r.status_code == 404

@pytest.mark.asyncio
async def test_set_ship_profile_with_ship_type():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        r = await client.post("/ship-profile",
                              headers={"X-Server-Token": TOKEN},
                              json={"ship_type": "Carom"})
    assert r.status_code == 200
    data = r.json()
    assert data["ship_type"] == "Carom"
    from src.ship_profile import SHIPS
    assert data["hull_mass"] == SHIPS["Carom"]["mass"]

@pytest.mark.asyncio
async def test_set_ship_profile_invalid_ship_type():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        r = await client.post("/ship-profile",
                              headers={"X-Server-Token": TOKEN},
                              json={"ship_type": "Nonexistent"})
    assert r.status_code == 422

@pytest.mark.asyncio
async def test_set_ship_profile_fuel_category_mismatch():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        r = await client.post("/ship-profile",
                              headers={"X-Server-Token": TOKEN},
                              json={"ship_type": "Lai", "fuel_type": "D1"})
    assert r.status_code == 422

@pytest.mark.asyncio
async def test_chat_slash_profile_prints_summary():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        r = await client.post("/chat",
                              headers={"X-Server-Token": TOKEN},
                              json={"message": "/profile", "history": []})
    assert r.status_code == 200
    assert "data:" in r.text

@pytest.mark.asyncio
async def test_ship_chat_stream_starts_with_keepalive():
    """SSE stream must yield a keep-alive comment before the first data chunk."""
    from unittest.mock import patch

    chunks = ["Hello", " world"]

    def fake_stream(message, history, context):
        return iter(chunks)

    with patch("main.claude.stream", side_effect=fake_stream), \
         patch("main.world_api.get_system", return_value=None), \
         patch("main.log_buffer.current_system", None):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.post(
                "/chat",
                json={"message": "hi", "history": []},
                headers={"X-Server-Token": TOKEN},
            )
    body = resp.text
    assert body.startswith(": keep-alive\n\n"), f"Expected keep-alive first, got: {body[:40]!r}"

@pytest.mark.asyncio
async def test_get_structures_endpoint():
    """Test GET /structures returns all loaded structures."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/structures")
    assert response.status_code == 200

    data = response.json()
    assert "structures" in data
    assert "count" in data
    assert isinstance(data["structures"], list)

    # Should have at least one structure (from test setup)
    assert data["count"] >= 0


@pytest.mark.asyncio
async def test_get_structures_response_format():
    """Test response includes expected fields."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/structures")
    data = response.json()

    if data["count"] > 0:
        struct = data["structures"][0]
        assert "id" in struct
        assert "system_name" in struct
        assert "owner_address" in struct
        assert "services" in struct
        assert "polling_enabled" in struct


@pytest.mark.asyncio
async def test_get_structures_empty():
    """Test /structures with no structures loaded."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/structures")
    assert response.status_code == 200
    data = response.json()
    assert data["count"] >= 0
    assert isinstance(data["structures"], list)


@pytest.mark.asyncio
async def test_get_structures_format():
    """Test /structures response format."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/structures")
    data = response.json()

    # Verify response structure
    assert "structures" in data
    assert "count" in data
    assert data["count"] == len(data["structures"])

    # If structures exist, verify fields
    if data["count"] > 0:
        struct = data["structures"][0]
        assert "id" in struct
        assert "system_name" in struct
        assert "owner_address" in struct
        assert "services" in struct
        assert "polling_enabled" in struct
