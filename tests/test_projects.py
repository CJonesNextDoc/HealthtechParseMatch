"""
on /projects/visible endpoint

user with insufficient clearance (sees none)
user with sufficient clearance but not assigned (sees none)
user with sufficient clearance and assigned (sees those)
manager with sufficient clearance (sees all permitted)
admin with high clearance (sees all)
"""
import asyncio
import logging
# import fastapi
import pytest
from app.core.middleware import RateLimiter
import httpx
from httpx import AsyncClient
from app.main import app as fastapi_app

@pytest.fixture
def rate_limiter():
    """Create a fresh rate limiter for each test"""
    limiter = RateLimiter()
    return limiter

@pytest.fixture
async def client(rate_limiter):
    """Get test client with fresh rate limiter"""
    logger = logging.getLogger(__name__)

    # Attach fixture limiter to the app state so middleware will use it
    fastapi_app.state.rate_limiter = rate_limiter
    logger.info(f"Attached test rate_limiter to app.state: {id(rate_limiter)}")

    async with AsyncClient(transport=httpx.ASGITransport(app=fastapi_app), base_url="http://test") as client:
        yield client

@pytest.mark.asyncio
async def test_projects_get(client, manager_headers):
    resp = await client.get("/projects/1", headers=manager_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["id"] == 1
    assert data["code"] == "PRJ-RED"

@pytest.mark.asyncio
async def test_projects_get_low_clearance(client, manager_headers_low_clearance):
    resp = await client.get("/projects/1", headers=manager_headers_low_clearance)
    assert resp.status_code == 404
    data = resp.json()
    assert "id" not in data

@pytest.mark.asyncio
async def test_projects_get_admin(client, admin_headers):
    resp = await client.get("/projects/1", headers=admin_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert "id" in data
    assert data["code"] == "PRJ-RED"

@pytest.mark.asyncio
async def test_projects_get_user(client, user_headers_low_clearance):
    resp = await client.get("/projects/1", headers=user_headers_low_clearance)
    assert resp.status_code == 404
    data = resp.json()
    assert "id" not in data

@pytest.mark.asyncio
async def test_projects_get_list_visible_none(client, user_headers_low_clearance):
    resp = await client.get(
        "/projects/visible",
        params={"limit": 10, "offset": 0},
        headers=user_headers_low_clearance
    )
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_projects_get_list_visible(client, user_headers_mid_clearance):
    resp = await client.get(
        "/projects/visible",
        params={"limit": 5, "offset": 0},
        headers=user_headers_mid_clearance
    )
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) > 0
    assert any(p["code"] == "PRJ-BLUE" for p in data)


@pytest.mark.asyncio
async def test_list_projects_rate_limit(client, user_headers_mid_clearance, rate_limiter):
    """Test rate limiting on project list endpoint"""
    logger = logging.getLogger(__name__)
    
    # Reset rate limiter and force settings refresh
    from app.core.config import get_settings
    get_settings.cache_clear()
    rate_limiter.reset()
    
    # First request
    logger.info("Making request 1 of 2")
    response = await client.get("/projects/visible", headers=user_headers_mid_clearance)
    assert response.status_code == 200
    logger.info("Request 1 succeeded with status 200")

    await asyncio.sleep(0.1)

    # Second request
    logger.info("Making request 2 of 2")
    response = await client.get("/projects/visible", headers=user_headers_mid_clearance)
    assert response.status_code == 200
    logger.info("Request 2 succeeded with status 200")

    await asyncio.sleep(0.1)

    # Third request should be rate limited
    logger.info("Making final request that should exceed rate limit")
    response = await client.get("/projects/visible", headers=user_headers_mid_clearance)
    assert response.status_code == 429
    error_data = response.json()
    assert error_data["detail"] == "Rate limit exceeded"
    logger.info("Rate limit exceeded as expected on request 3")

@pytest.mark.asyncio
async def test_project_detail_rate_limit(client, user_headers_mid_clearance, rate_limiter):
    logger = logging.getLogger(__name__)

    # Dump middleware registry for diagnostics
    logger.info("DUMP user_middleware START")
    for i, mw in enumerate(fastapi_app.user_middleware):
        try:
            logger.info(f"mw[{i}] repr={mw} cls={getattr(mw,'cls',None)} options={getattr(mw,'options',None)} dispatch_attr={getattr(mw,'dispatch', None)}")
        except Exception as exc:
            logger.info(f"mw[{i}] error while introspecting: {exc}")
    logger.info("DUMP user_middleware END")

    # Also print the test fixture limiter id and its cache
    logger.info(f"Test rate_limiter instance id={id(rate_limiter)} cache_keys={list(rate_limiter._cache.keys())}")

    # Now reset and re-log
    from app.core.config import get_settings
    get_settings.cache_clear()
    rate_limiter.reset()
    logger.info(f"After reset test limiter id={id(rate_limiter)} cache={rate_limiter._cache}")

    # Continue test...
    # First request
    logger.info("Making request 1 of 2")
    response = await client.get("/projects/2", headers=user_headers_mid_clearance)
    assert response.status_code == 200
    logger.info("Request 1 succeeded with status 200")

    await asyncio.sleep(0.1)

    # Second request
    logger.info("Making request 2 of 2")
    response = await client.get("/projects/2", headers=user_headers_mid_clearance)
    assert response.status_code == 200
    logger.info("Request 2 succeeded with status 200")

    await asyncio.sleep(0.1)

    # Third request should be rate limited
    logger.info("Making final request that should exceed rate limit")
    response = await client.get("/projects/2", headers=user_headers_mid_clearance)
    assert response.status_code == 429
    error_data = response.json()
    assert error_data["detail"] == "Rate limit exceeded"
    logger.info("Rate limit exceeded as expected on request 3")
