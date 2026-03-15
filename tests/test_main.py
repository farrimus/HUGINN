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
