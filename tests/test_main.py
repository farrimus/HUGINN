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
async def test_get_structures_endpoint():
    """Test GET /structures returns all loaded structures."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/structures")
    assert response.status_code == 200
    data = response.json()
    assert "structures" in data
    assert "count" in data
    assert isinstance(data["structures"], list)
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

@pytest.mark.asyncio
async def test_get_structures_empty():
    """Test /structures returns valid response even with no structures."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/structures")
    assert response.status_code == 200
    data = response.json()
    assert data["count"] >= 0
    assert isinstance(data["structures"], list)

@pytest.mark.asyncio
async def test_get_structures_format():
    """Test /structures count matches list length."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/structures")
    data = response.json()
    assert "structures" in data
    assert "count" in data
    assert data["count"] == len(data["structures"])
