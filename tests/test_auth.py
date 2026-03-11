# tests/test_auth.py
from httpx import AsyncClient, ASGITransport
import pytest
from fastapi import FastAPI, Depends
from src.auth import require_token

app = FastAPI()

@app.get("/protected")
async def protected(_=Depends(require_token)):
    return {"ok": True}

@pytest.mark.asyncio
async def test_valid_token_passes(monkeypatch):
    monkeypatch.setenv("SHIP_TOKEN", "test-secret")
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/protected", headers={"X-Ship-Token": "test-secret"})
    assert response.status_code == 200

@pytest.mark.asyncio
async def test_missing_token_rejected(monkeypatch):
    monkeypatch.setenv("SHIP_TOKEN", "test-secret")
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/protected")
    assert response.status_code == 403

@pytest.mark.asyncio
async def test_wrong_token_rejected(monkeypatch):
    monkeypatch.setenv("SHIP_TOKEN", "test-secret")
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/protected", headers={"X-Ship-Token": "wrong"})
    assert response.status_code == 403

@pytest.mark.asyncio
async def test_no_token_configured_allows_all(monkeypatch):
    monkeypatch.delenv("SHIP_TOKEN", raising=False)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/protected")
    assert response.status_code == 200
