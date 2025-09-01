# tests/test_auth_more.py
import pytest
from fastapi import HTTPException
from httpx import ASGITransport, AsyncClient

from app.main import app as fastapi_app


@pytest.mark.asyncio
async def test_headers_case_insensitive() -> None:
    """Lowercase header names should be accepted by the middleware."""
    headers = {"x-user-email": "curtisjonesknox@gmail.com", "x-role": "admin"}
    async with AsyncClient(transport=ASGITransport(app=fastapi_app), base_url="http://test") as c:
        r = await c.get("/projects/1", headers=headers)
        # Router may 200 or 404 depending on seeded data, but it must *not* 401/403 due to header case
        assert r.status_code in (200, 404)


@pytest.mark.asyncio
async def test_role_with_spaces_and_casing_normalizes() -> None:
    """
    Role header with spaces and mixed case should normalize to a valid role.
    (Quotes are NOT stripped by the app, so we don't include them here.)
    """
    headers = {"X-User-Email": "curtisjonesknox@gmail.com", "X-Role": "   ADMIN   "}
    async with AsyncClient(transport=ASGITransport(app=fastapi_app), base_url="http://test") as c:
        r = await c.get("/projects/1", headers=headers)
        # Should authenticate as admin after normalization, so not 401/403 from auth
        assert r.status_code in (200, 404)


@pytest.mark.asyncio
async def test_invalid_role_is_rejected() -> None:
    """Supplying an unknown role should be blocked at auth with 403."""
    headers = {"X-User-Email": "john.doe@example.com", "X-Role": "guest"}
    async with AsyncClient(transport=ASGITransport(app=fastapi_app), base_url="http://test") as c:
        try:
            r = await c.get("/projects/1", headers=headers)
            assert r.status_code == 403
        except HTTPException as exc:
            # Some setups raise from middleware; assert it is the expected 403.
            assert exc.status_code == 403
            assert "Invalid role" in str(exc.detail)


@pytest.mark.asyncio
async def test_openapi_and_docs_are_public() -> None:
    """Spec and interactive docs should be accessible without auth."""
    async with AsyncClient(transport=ASGITransport(app=fastapi_app), base_url="http://test") as c:
        spec = await c.get("/openapi.json")
        docs = await c.get("/docs")
        redoc = await c.get("/redoc")
        assert spec.status_code == 200
        assert docs.status_code in (200, 307, 308)
        assert redoc.status_code in (200, 307, 308)
