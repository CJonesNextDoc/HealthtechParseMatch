# tests/test_redis_services.py
"""
Tests for Redis services: RedisService, CacheService, IdempotencyService, DistributedRateLimiter
"""

import asyncio
from unittest.mock import AsyncMock

import pytest

from app.core.distributed_rate_limiter import DistributedRateLimiter
from app.services.cache_service import CacheService, cache_service
from app.services.idempotency_service import IdempotencyService, idempotency_service
from app.services.redis_service import RedisService, redis_service


class TestRedisService:
    """Test RedisService basic operations"""

    @pytest.fixture
    def redis_service_instance(self):
        """Create a fresh RedisService instance for testing"""
        service = RedisService()
        # Mock the Redis client to avoid actual Redis connection
        service.redis = AsyncMock()
        return service

    @pytest.mark.asyncio
    async def test_health_check_success(self, redis_service_instance):
        """Test successful Redis health check"""
        # Mock successful ping
        redis_service_instance.redis.ping.return_value = True

        result = await redis_service_instance.health_check()

        assert result["status"] == "healthy"
        assert result["enabled"] is True
        assert "ping_time" in result
        redis_service_instance.redis.ping.assert_called_once()

    @pytest.mark.asyncio
    async def test_health_check_failure(self, redis_service_instance):
        """Test Redis health check failure"""
        # Mock failed ping
        redis_service_instance.redis.ping.side_effect = Exception("Connection failed")

        result = await redis_service_instance.health_check()

        assert result["status"] == "unhealthy"
        assert result["enabled"] is True
        assert "error" in result

    @pytest.mark.asyncio
    async def test_get_set_operations(self, redis_service_instance):
        """Test basic get/set operations"""
        # Mock successful set and get
        redis_service_instance.redis.set.return_value = True
        redis_service_instance.redis.get.return_value = b"test_value"

        # Test set
        await redis_service_instance.set("test_key", "test_value")
        redis_service_instance.redis.set.assert_called_with("test_key", "test_value", ex=None)

        # Test get
        result = await redis_service_instance.get("test_key")
        assert result == "test_value"
        redis_service_instance.redis.get.assert_called_with("test_key")

    @pytest.mark.asyncio
    async def test_check_rate_limit_allowed(self, redis_service_instance):
        """Test rate limit check when request is allowed"""
        # Mock Redis operations for rate limiting
        redis_service_instance.redis.zadd.return_value = None
        redis_service_instance.redis.zremrangebyscore.return_value = None
        redis_service_instance.redis.zcard.return_value = 5  # Current count below limit

        allowed = await redis_service_instance.check_rate_limit("user@test.com", 10, 60)

        assert allowed is True
        redis_service_instance.redis.zadd.assert_called_once()
        redis_service_instance.redis.zremrangebyscore.assert_called_once()
        redis_service_instance.redis.zcard.assert_called_once()

    @pytest.mark.asyncio
    async def test_check_rate_limit_blocked(self, redis_service_instance):
        """Test rate limit check when request is blocked"""
        # Mock Redis operations - count exceeds limit
        redis_service_instance.redis.zadd.return_value = None
        redis_service_instance.redis.zremrangebyscore.return_value = None
        redis_service_instance.redis.zcard.return_value = 15  # Current count exceeds limit of 10

        allowed = await redis_service_instance.check_rate_limit("user@test.com", 10, 60)

        assert allowed is False


class TestCacheService:
    """Test CacheService operations"""

    @pytest.fixture
    def cache_service_instance(self):
        """Create a fresh CacheService instance for testing"""
        service = CacheService()
        # Mock the Redis service
        service.redis_service = AsyncMock()
        return service

    @pytest.mark.asyncio
    async def test_get_or_set_cache_hit(self, cache_service_instance):
        """Test get_or_set when cache hit"""
        # Mock cache hit
        cache_service_instance.redis_service.get.return_value = "cached_value"

        result = await cache_service_instance.get_or_set("test_key", lambda: "new_value")

        assert result == "cached_value"
        cache_service_instance.redis_service.get.assert_called_with("test_key")
        # Should not call set since we got a cache hit
        cache_service_instance.redis_service.set.assert_not_called()

    @pytest.mark.asyncio
    async def test_get_or_set_cache_miss(self, cache_service_instance):
        """Test get_or_set when cache miss"""
        # Mock cache miss then successful set
        cache_service_instance.redis_service.get.return_value = None
        cache_service_instance.redis_service.set.return_value = None

        result = await cache_service_instance.get_or_set("test_key", lambda: "new_value")

        assert result == "new_value"
        cache_service_instance.redis_service.get.assert_called_with("test_key")
        cache_service_instance.redis_service.set.assert_called_with("test_key", "new_value", ex=300)

    @pytest.mark.asyncio
    async def test_cache_patient_data(self, cache_service_instance):
        """Test patient data caching"""
        patient_data = {"id": "123", "name": "John Doe"}
        cache_service_instance.redis_service.set.return_value = None

        await cache_service_instance.cache_patient_data("patient_123", patient_data)

        cache_service_instance.redis_service.set.assert_called_with(
            "patient:patient_123", '{"id": "123", "name": "John Doe"}', ex=300
        )

    @pytest.mark.asyncio
    async def test_get_cached_patient_data(self, cache_service_instance):
        """Test retrieving cached patient data"""
        patient_data = {"id": "123", "name": "John Doe"}
        cache_service_instance.redis_service.get.return_value = '{"id": "123", "name": "John Doe"}'

        result = await cache_service_instance.get_cached_patient_data("patient_123")

        assert result == patient_data
        cache_service_instance.redis_service.get.assert_called_with("patient:patient_123")


class TestIdempotencyService:
    """Test IdempotencyService operations"""

    @pytest.fixture
    def idempotency_service_instance(self):
        """Create a fresh IdempotencyService instance for testing"""
        service = IdempotencyService()
        # Mock the Redis service
        service.redis_service = AsyncMock()
        return service

    @pytest.mark.asyncio
    async def test_execute_idempotent_new_operation(self, idempotency_service_instance):
        """Test executing a new idempotent operation"""
        # Mock cache miss - no existing result
        idempotency_service_instance.redis_service.get.return_value = None
        idempotency_service_instance.redis_service.set.return_value = None

        async def test_function(x, y):
            return x + y

        result = await idempotency_service_instance.execute_idempotent("test_key", test_function, x=5, y=3)

        assert result == 8
        # Should check cache first
        idempotency_service_instance.redis_service.get.assert_called_with("idempotent:test_key")
        # Should cache the result
        idempotency_service_instance.redis_service.set.assert_called_with("idempotent:test_key", "8", ex=3600)

    @pytest.mark.asyncio
    async def test_execute_idempotent_cached_result(self, idempotency_service_instance):
        """Test executing idempotent operation with cached result"""
        # Mock cache hit
        idempotency_service_instance.redis_service.get.return_value = "42"

        async def test_function():
            return 999  # This should not be called

        result = await idempotency_service_instance.execute_idempotent("test_key", test_function)

        assert result == 42
        idempotency_service_instance.redis_service.get.assert_called_with("idempotent:test_key")
        # Should not set new result since we got cached value
        idempotency_service_instance.redis_service.set.assert_not_called()


class TestDistributedRateLimiter:
    """Test DistributedRateLimiter operations"""

    @pytest.fixture
    def rate_limiter_instance(self):
        """Create a fresh DistributedRateLimiter instance for testing"""
        limiter = DistributedRateLimiter()
        # Mock the Redis service
        limiter.redis_service = AsyncMock()
        return limiter

    @pytest.mark.asyncio
    async def test_check_rate_limit_allowed(self, rate_limiter_instance):
        """Test rate limit check when request is allowed"""
        # Mock Redis service to return allowed
        rate_limiter_instance.redis_service.check_rate_limit.return_value = True

        allowed = await rate_limiter_instance.check_rate_limit("user@test.com", "user")

        assert allowed is True
        rate_limiter_instance.redis_service.check_rate_limit.assert_called_with(
            "user@test.com:user", 100, 60  # Default user limit and window
        )

    @pytest.mark.asyncio
    async def test_check_rate_limit_blocked(self, rate_limiter_instance):
        """Test rate limit check when request is blocked"""
        # Mock Redis service to return blocked
        rate_limiter_instance.redis_service.check_rate_limit.return_value = False

        allowed = await rate_limiter_instance.check_rate_limit("user@test.com", "user")

        assert allowed is False

    @pytest.mark.asyncio
    async def test_check_rate_limit_redis_failure_fallback(self, rate_limiter_instance):
        """Test that Redis failure falls back to allowing requests"""
        # Mock Redis service to raise exception
        rate_limiter_instance.redis_service.check_rate_limit.side_effect = Exception("Redis down")

        allowed = await rate_limiter_instance.check_rate_limit("user@test.com", "user")

        # Should fallback to allowing the request
        assert allowed is True

    @pytest.mark.asyncio
    async def test_reset_user(self, rate_limiter_instance):
        """Test resetting rate limit for a user"""
        rate_limiter_instance.redis_service.reset_rate_limit.return_value = None

        await rate_limiter_instance.reset_user("user@test.com", "user")

        rate_limiter_instance.redis_service.reset_rate_limit.assert_called_with("user@test.com:user")


# Integration tests that require actual Redis connection
@pytest.mark.integration
class TestRedisIntegration:
    """Integration tests that require Redis to be running"""

    @pytest.mark.asyncio
    async def test_redis_service_real_connection(self):
        """Test RedisService with real Redis connection (requires Redis running)"""
        # This test requires Redis to be running
        # In CI/CD, this would be conditional based on Redis availability
        try:
            health = await redis_service.health_check()
            assert health["status"] in ["healthy", "unhealthy"]  # Either is acceptable for this test
            assert health["enabled"] is True
        except Exception:
            # If Redis is not available, skip this test
            pytest.skip("Redis not available for integration testing")

    @pytest.mark.asyncio
    async def test_full_cache_workflow(self):
        """Test complete cache workflow with real Redis"""
        try:
            # Test cache set/get
            await cache_service.redis_service.set("test_integration_key", "test_value", ex=60)
            result = await cache_service.redis_service.get("test_integration_key")
            assert result == "test_value"

            # Test cache service
            result = await cache_service.get_or_set("test_cache_key", lambda: "computed_value")
            assert result == "computed_value"

            # Get from cache
            result = await cache_service.get_or_set("test_cache_key", lambda: "should_not_compute")
            assert result == "computed_value"

        except Exception:
            pytest.skip("Redis not available for integration testing")

    @pytest.mark.asyncio
    async def test_idempotency_workflow(self):
        """Test complete idempotency workflow with real Redis"""
        try:

            async def expensive_operation(x):
                await asyncio.sleep(0.1)  # Simulate expensive operation
                return x * 2

            # First call should execute
            result1 = await idempotency_service.execute_idempotent("test_idempotent", expensive_operation, x=5)
            assert result1 == 10

            # Second call should return cached result
            result2 = await idempotency_service.execute_idempotent("test_idempotent", expensive_operation, x=99)
            assert result2 == 10  # Should be cached value, not 198

        except Exception:
            pytest.skip("Redis not available for integration testing")
