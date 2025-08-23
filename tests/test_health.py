import pytest

@pytest.mark.asyncio
async def test_health_ok(client):
    response = await client.get("/health/check")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"

@pytest.mark.asyncio
async def test_health_db(client):
    response = await client.get("/health/db")
    assert response.status_code == 200
    data = response.json()
    assert data["database"] == "connected"
