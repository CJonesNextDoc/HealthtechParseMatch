# tests/test_rate_limit_extra_additional.py
import asyncio
import logging

import pytest
from httpx import ASGITransport, AsyncClient

from app.core.config import get_settings
from app.main import app as fastapi_app

# Use fixtures from tests.conftest (pytest will inject them by name)
# expected fixtures: rate_limiter, user_headers_low_clearance, user_headers_mid_clearance,
# manager_headers, admin_headers, vendor_headers

logger = logging.getLogger(__name__)


@pytest.mark.asyncio
async def test_app_state_rate_limiter_used(rate_limiter, user_headers_mid_clearance):
    """Ensure middleware uses app.state.rate_limiter and enforces limits."""
    fastapi_app.state.rate_limiter = rate_limiter
    rate_limiter.reset()

    async with AsyncClient(transport=ASGITransport(app=fastapi_app), base_url="http://test") as client:
        r1 = await client.get("/health/check", headers=user_headers_mid_clearance)
        assert r1.status_code == 200
        r2 = await client.get("/health/check", headers=user_headers_mid_clearance)
        assert r2.status_code == 200
        r3 = await client.get("/health/check", headers=user_headers_mid_clearance)
        assert r3.status_code == 429


@pytest.mark.asyncio
async def test_concurrent_requests_same_user(rate_limiter, user_headers_mid_clearance):
    """Concurrent requests from same user should still observe the limit."""
    fastapi_app.state.rate_limiter = rate_limiter
    rate_limiter.reset()

    async with AsyncClient(transport=ASGITransport(app=fastapi_app), base_url="http://test") as client:

        async def req():
            resp = await client.get("/health/check", headers=user_headers_mid_clearance)
            return resp.status_code

        tasks = [asyncio.create_task(req()) for _ in range(3)]
        results = await asyncio.gather(*tasks, return_exceptions=False)
        # At least one request must be rejected when limit == 2
        assert results.count(200) >= 2
        assert results.count(429) >= 1


@pytest.mark.asyncio
async def test_rate_limits_per_role(
    rate_limiter, user_headers_low_clearance, manager_headers, admin_headers, vendor_headers
):
    """Verify configured per-role limits from settings are applied."""
    settings = get_settings()
    fastapi_app.state.rate_limiter = rate_limiter
    rate_limiter.reset()

    role_cases = [
        (user_headers_low_clearance, int(settings.user_rate_limit)),
        (manager_headers, int(settings.manager_rate_limit)),
        (admin_headers, int(settings.admin_rate_limit)),
        (vendor_headers, int(settings.app_rate_limit)),
    ]

    async with AsyncClient(transport=ASGITransport(app=fastapi_app), base_url="http://test") as client:
        for headers, limit in role_cases:
            # make exactly `limit` requests -> should succeed
            for _ in range(limit):
                r = await client.get("/health/check", headers=headers)
                assert r.status_code == 200
            # next request should be rejected
            r = await client.get("/health/check", headers=headers)
            assert r.status_code == 429
            rate_limiter.reset()


@pytest.mark.asyncio
async def test_rate_limiter_reset_allows_requests_again(rate_limiter, user_headers_low_clearance):
    """Resetting the limiter should allow requests again after being exhausted."""
    fastapi_app.state.rate_limiter = rate_limiter
    rate_limiter.reset()

    async with AsyncClient(transport=ASGITransport(app=fastapi_app), base_url="http://test") as client:
        # exhaust
        for _ in range(2):
            r = await client.get("/health/check", headers=user_headers_low_clearance)
            assert r.status_code == 200
        r = await client.get("/health/check", headers=user_headers_low_clearance)
        assert r.status_code == 429

        # reset and verify allowed
        rate_limiter.reset()
        r = await client.get("/health/check", headers=user_headers_low_clearance)
        assert r.status_code == 200


@pytest.mark.asyncio
async def test_rate_limit_resets_after_window(rate_limiter, user_headers_low_clearance):
    """After the configured window the limiter should allow requests again."""
    fastapi_app.state.rate_limiter = rate_limiter
    rate_limiter.reset()

    async with AsyncClient(transport=ASGITransport(app=fastapi_app), base_url="http://test") as client:
        for _ in range(2):
            r = await client.get("/health/check", headers=user_headers_low_clearance)
            assert r.status_code == 200
        r = await client.get("/health/check", headers=user_headers_low_clearance)
        assert r.status_code == 429

        # wait slightly longer than window (tests configure window=1)
        await asyncio.sleep(1.1)

        r = await client.get("/health/check", headers=user_headers_low_clearance)
        assert r.status_code == 200


@pytest.mark.asyncio
async def test_health_db_skips_rate_limit(rate_limiter, user_headers_low_clearance):
    """/health/db should bypass rate limiting even when user is exhausted."""
    fastapi_app.state.rate_limiter = rate_limiter
    rate_limiter.reset()

    async with AsyncClient(transport=ASGITransport(app=fastapi_app), base_url="http://test") as client:
        # exhaust user on /health/check
        for _ in range(2):
            r = await client.get("/health/check", headers=user_headers_low_clearance)
            assert r.status_code == 200
        r = await client.get("/health/check", headers=user_headers_low_clearance)
        assert r.status_code == 429

        # /health/db must still succeed (bypassed)
        r = await client.get("/health/db", headers=user_headers_low_clearance)
        assert r.status_code == 200


@pytest.mark.asyncio
async def test_projects_endpoint_rate_limit(rate_limiter, user_headers_mid_clearance):
    """Confirm rate limits apply on projects endpoints."""
    fastapi_app.state.rate_limiter = rate_limiter
    rate_limiter.reset()

    async with AsyncClient(transport=ASGITransport(app=fastapi_app), base_url="http://test") as client:
        r1 = await client.get("/projects/2", headers=user_headers_mid_clearance)
        assert r1.status_code == 200
        r2 = await client.get("/projects/2", headers=user_headers_mid_clearance)
        assert r2.status_code == 200
        r3 = await client.get("/projects/2", headers=user_headers_mid_clearance)
        assert r3.status_code == 429
