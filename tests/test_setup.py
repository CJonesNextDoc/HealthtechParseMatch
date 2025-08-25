import os
import pytest
from httpx import AsyncClient
from app.db.test_db import TestingSessionLocal

@pytest.mark.asyncio
async def test_environment_variables():
    """Test that environment variables are set correctly"""
    assert os.getenv("TESTING") == "1"
    assert os.getenv("RATE_LIMIT_TEST") == "1"
    assert os.getenv("DATABASE_URL") == "sqlite+aiosqlite:///./test.db"
    assert os.getenv("USER_RATE_LIMIT") == "2"

@pytest.mark.asyncio
async def test_client_fixture(client):
    """Test that client fixture returns working client"""
    assert isinstance(client, AsyncClient)
    response = await client.get("/health/check")
    assert response.status_code == 200

@pytest.mark.asyncio
async def test_database_fixture():
    """Test that test database is configured correctly"""
    async with TestingSessionLocal() as session:
        assert session is not None