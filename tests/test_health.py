import asyncio
import logging
from unittest.mock import AsyncMock

import httpx
import pytest
from httpx import AsyncClient

from app.core.middleware import RateLimiter  #  RateLimitMiddleware,
from app.integrations.redox_gateway import RedoxIntegrationGateway
from app.main import app as fastapi_app

# Add logger at module level
logger = logging.getLogger(__name__)


@pytest.fixture
def rate_limiter():
    """Create a fresh rate limiter for each test"""
    limiter = RateLimiter()
    return limiter


@pytest.fixture
async def client(rate_limiter):
    """Get test client with fresh rate limiter"""
    logger = logging.getLogger(__name__)

    # Attach fixture limiter to app.state so middleware will use it
    fastapi_app.state.rate_limiter = rate_limiter
    logger.info(f"Attached rate_limiter to app.state: {id(rate_limiter)}")

    async with AsyncClient(transport=httpx.ASGITransport(app=fastapi_app), base_url="http://test") as client:
        yield client


@pytest.fixture(autouse=True)
async def reset_rate_limiter(rate_limiter):
    """Reset rate limiter state between tests"""
    # Reset the instance and ensure app.state uses it
    rate_limiter.reset()
    fastapi_app.state.rate_limiter = rate_limiter
    yield


@pytest.mark.asyncio
async def test_health_ok(client):
    """Test basic health check endpoint"""
    response = await client.get("/health/check")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"


@pytest.mark.asyncio
async def test_health_db(client, user_headers_low_clearance):
    """Test health check with database check"""
    response = await client.get("/health/db", headers=user_headers_low_clearance)
    assert response.status_code == 200
    data = response.json()
    assert data["database"] == "connected"


@pytest.mark.asyncio
async def test_metrics_endpoint(client):
    """Test Prometheus metrics endpoint"""
    response = await client.get("/health/metrics")
    assert response.status_code == 200
    assert response.headers["content-type"] == "text/plain; charset=utf-8"

    # Check that response contains Prometheus metrics format
    metrics_text = response.text
    assert "# HELP" in metrics_text
    assert "# TYPE" in metrics_text

    # Should contain some basic Python metrics from prometheus_client
    assert "python_gc_objects_collected_total" in metrics_text


@pytest.mark.asyncio
async def test_metrics_with_redox_calls(client):
    """Test that Redox metrics appear in Prometheus output after API calls"""
    # Create a mock client for testing
    mock_client = AsyncMock()
    mock_client.send_patient_admin_message = AsyncMock(return_value={"status": "success"})

    # Create gateway with mock client
    gateway = RedoxIntegrationGateway(mock_client)

    # Make a Redox call to generate metrics
    await gateway.send_patient_message({"test": "data"})

    # Now check that metrics endpoint includes Redox metrics
    response = await client.get("/health/metrics")
    assert response.status_code == 200

    metrics_text = response.text

    # Should contain Redox-specific metrics
    assert 'redox_requests_total{method="send_patient_admin_message",status="success"} 1.0' in metrics_text
    assert 'redox_request_duration_seconds_count{method="send_patient_admin_message"} 1.0' in metrics_text


@pytest.mark.asyncio
async def test_rate_limiting(client, user_headers_low_clearance, rate_limiter):
    """Test that rate limiting works for regular users"""
    logger = logging.getLogger(__name__)

    # Force settings refresh and reset rate limiter
    from app.core.config import get_settings

    settings = get_settings()
    rate_limiter.reset()

    # Verify test settings
    assert settings.rate_limit_test is True
    assert settings.user_rate_limit == 2
    assert settings.rate_limit_window == 1

    # First request
    logger.info("Making request 1 of 2")
    response = await client.get("/health/check", headers=user_headers_low_clearance)
    assert response.status_code == 200
    logger.info("Request 1 succeeded with status 200")

    await asyncio.sleep(0.1)  # Small delay between requests

    # Second request
    logger.info("Making request 2 of 2")
    response = await client.get("/health/check", headers=user_headers_low_clearance)
    assert response.status_code == 200
    logger.info("Request 2 succeeded with status 200")

    await asyncio.sleep(0.1)  # Small delay before rate limited request

    # Third request should be rate limited
    logger.info("Making final request that should exceed rate limit")
    response = await client.get("/health/check", headers=user_headers_low_clearance)
    assert response.status_code == 429
    assert response.json().get("detail") == "Rate limit exceeded"
    logger.info("Rate limit exceeded as expected on request 3")


@pytest.mark.asyncio
async def test_rate_limiting_different_users(client, user_headers_low_clearance, user_headers_mid_clearance, rate_limiter):
    """Test that rate limiting is per-user"""
    logger = logging.getLogger(__name__)

    logger.info(f"Starting different users test with rate_limiter instance {id(rate_limiter)}")

    # Reset only the test users
    logger.info("Resetting test users...")
    rate_limiter.reset_user("john.doe@example.com", "user")
    rate_limiter.reset_user("tom.smith@example.com", "user")

    logger.info("Waiting for window reset...")
    await asyncio.sleep(1.1)  # Wait longer than window size

    logger.info("Testing first user (john.doe)...")
    # First user - 2 requests
    response = await client.get("/health/check", headers=user_headers_low_clearance)
    assert response.status_code == 200
    logger.info("First user request 1 succeeded")

    response = await client.get("/health/check", headers=user_headers_low_clearance)
    assert response.status_code == 200
    logger.info("First user request 2 succeeded")

    logger.info("Testing first user rate limit...")
    response = await client.get("/health/check", headers=user_headers_low_clearance)
    assert response.status_code == 429
    logger.info("First user properly rate limited")

    logger.info("Testing second user (tom.smith)...")
    # Second user should still work (different rate limit bucket)
    response = await client.get("/health/check", headers=user_headers_mid_clearance)
    assert response.status_code == 200
    logger.info("Second user request succeeded (different bucket)")
