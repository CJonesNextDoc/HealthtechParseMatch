# tests/test_auth_basics.py
import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app as fastapi_app


@pytest.mark.asyncio
async def test_health_check_no_auth_ok() -> None:
    """/health/check should be accessible without auth headers."""
    async with AsyncClient(transport=ASGITransport(app=fastapi_app), base_url="http://test") as client:
        resp = await client.get("/health/check")
        assert resp.status_code == 200


@pytest.mark.asyncio
async def test_non_health_without_auth_behaves_as_anonymous() -> None:
    """
    The app treats missing auth headers as an 'anonymous@local' user.
    For non-health paths this means the request is processed and, with no matching user,
    the router responds 404 (not a 401).
    """
    async with AsyncClient(transport=ASGITransport(app=fastapi_app), base_url="http://test") as client:
        resp = await client.get("/projects/1")  # any non-health endpoint
        assert resp.status_code == 404
