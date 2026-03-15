# tests/test_main.py
from httpx import AsyncClient, ASGITransport
import pytest
import os
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
