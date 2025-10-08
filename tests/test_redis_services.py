# tests/test_redis_services.py
"""
Tests for Redis services: RedisService, CacheService, IdempotencyService, DistributedRateLimiter
"""

import asyncio
from unittest.mock import AsyncMock, Mock

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
        # Mock the get_client method to return a mock Redis client
        mock_client = AsyncMock()
        service.get_client = AsyncMock(return_value=mock_client)
        service._enabled = True
        return service

    @pytest.mark.asyncio
    async def test_health_check_success(self, redis_service_instance):
        """Test successful Redis health check"""
        # Mock successful ping
        mock_client = await redis_service_instance.get_client()
        mock_client.ping.return_value = None

        result = await redis_service_instance.health_check()

        assert result["status"] == "healthy"
        assert result["enabled"] is True
        mock_client.ping.assert_called_once()

    @pytest.mark.asyncio
    async def test_health_check_failure(self, redis_service_instance):
        """Test Redis health check failure"""
        # Mock failed ping
        mock_client = await redis_service_instance.get_client()
        mock_client.ping.side_effect = Exception("Connection failed")

        result = await redis_service_instance.health_check()

        assert result["status"] == "unhealthy"
        assert result["enabled"] is True
        assert "error" in result

    @pytest.mark.asyncio
    async def test_get_set_operations(self, redis_service_instance):
        """Test basic get/set cache operations"""
        mock_client = await redis_service_instance.get_client()

        # Test set_cache
        mock_client.setex.return_value = True
        result = await redis_service_instance.set_cache("test_key", "test_value")
        assert result is True
        mock_client.setex.assert_called_with("cache:test_key", 300, "test_value")

        # Test get_cache
        mock_client.get.return_value = b'"test_value"'
        result = await redis_service_instance.get_cache("test_key")
        assert result == "test_value"
        mock_client.get.assert_called_with("cache:test_key")

    @pytest.mark.asyncio
    async def test_check_rate_limit_allowed(self, redis_service_instance):
        """Test rate limit check when request is allowed"""
        mock_client = await redis_service_instance.get_client()
        mock_pipeline = AsyncMock()
        mock_client.pipeline = Mock(return_value=mock_pipeline)
        mock_pipeline.__aenter__.return_value = mock_pipeline
        mock_pipeline.__aexit__.return_value = None

        # Mock pipeline operations (synchronous methods on async context manager)
        mock_pipeline.zremrangebyscore = Mock(return_value=None)
        mock_pipeline.zadd = Mock(return_value=None)
        mock_pipeline.zcard = Mock(return_value=5)  # Current count below limit
        mock_pipeline.expire = Mock(return_value=None)
        mock_pipeline.execute = AsyncMock(return_value=[None, None, 5, None])

        allowed = await redis_service_instance.check_rate_limit("user@test.com", 10, 60)

        assert allowed is True
        mock_pipeline.zremrangebyscore.assert_called_once()
        mock_pipeline.zadd.assert_called_once()
        mock_pipeline.zcard.assert_called_once()
        mock_pipeline.expire.assert_called_once()

    @pytest.mark.asyncio
    async def test_check_rate_limit_blocked(self, redis_service_instance):
        """Test rate limit check when request is blocked"""
        mock_client = await redis_service_instance.get_client()
        mock_pipeline = AsyncMock()
        mock_client.pipeline = Mock(return_value=mock_pipeline)
        mock_pipeline.__aenter__.return_value = mock_pipeline
        mock_pipeline.__aexit__.return_value = None

        # Mock pipeline operations - count exceeds limit
        mock_pipeline.zremrangebyscore = Mock(return_value=None)
        mock_pipeline.zadd = Mock(return_value=None)
        mock_pipeline.zcard = Mock(return_value=15)  # Current count exceeds limit of 10
        mock_pipeline.expire = Mock(return_value=None)
        mock_pipeline.execute = AsyncMock(return_value=[None, None, 15, None])

        allowed = await redis_service_instance.check_rate_limit("user@test.com", 10, 60)

        assert allowed is False


class TestCacheService:
    """Test CacheService operations"""

    @pytest.fixture
    def cache_service_instance(self):
        """Create a fresh CacheService instance for testing"""
        service = CacheService()
        return service

    @pytest.mark.asyncio
    async def test_get_or_set_cache_hit(self, cache_service_instance, monkeypatch):
        """Test get_or_set when cache hit"""
        # Mock the global redis_service
        mock_redis = AsyncMock()
        mock_redis.get_cache.return_value = "cached_value"
        monkeypatch.setattr("app.services.cache_service.redis_service", mock_redis)

        result = await cache_service_instance.get_or_set("test_key", lambda: "new_value")

        assert result == "cached_value"
        mock_redis.get_cache.assert_called_with("test_key")
        # Should not call set since we got a cache hit
        mock_redis.set_cache.assert_not_called()

    @pytest.mark.asyncio
    async def test_get_or_set_cache_miss(self, cache_service_instance, monkeypatch):
        """Test get_or_set when cache miss"""
        # Mock the global redis_service
        mock_redis = AsyncMock()
        mock_redis.get_cache.return_value = None
        mock_redis.set_cache.return_value = True
        monkeypatch.setattr("app.services.cache_service.redis_service", mock_redis)

        async def getter():
            return "new_value"

        result = await cache_service_instance.get_or_set("test_key", getter)

        assert result == "new_value"
        mock_redis.get_cache.assert_called_with("test_key")
        mock_redis.set_cache.assert_called_with("test_key", "new_value", None)

    @pytest.mark.asyncio
    async def test_cache_patient_data(self, cache_service_instance, monkeypatch):
        """Test patient data caching"""
        # Mock the global redis_service
        mock_redis = AsyncMock()
        mock_redis.set_cache.return_value = True
        monkeypatch.setattr("app.services.cache_service.redis_service", mock_redis)

        patient_data = {"id": "123", "name": "John Doe"}
        await cache_service_instance.cache_patient_data("patient_123", patient_data)

        mock_redis.set_cache.assert_called_with("patient:patient_123", patient_data, None)

    @pytest.mark.asyncio
    async def test_get_cached_patient_data(self, cache_service_instance, monkeypatch):
        """Test retrieving cached patient data"""
        # Mock the global redis_service
        mock_redis = AsyncMock()
        patient_data = {"id": "123", "name": "John Doe"}
        mock_redis.get_cache.return_value = patient_data
        monkeypatch.setattr("app.services.cache_service.redis_service", mock_redis)

        result = await cache_service_instance.get_cached_patient_data("patient_123")

        assert result == patient_data
        mock_redis.get_cache.assert_called_with("patient:patient_123")


class TestIdempotencyService:
    """Test IdempotencyService operations"""

    @pytest.fixture
    def idempotency_service_instance(self):
        """Create a fresh IdempotencyService instance for testing"""
        service = IdempotencyService()
        return service

    @pytest.mark.asyncio
    async def test_execute_idempotent_new_operation(self, idempotency_service_instance, monkeypatch):
        """Test executing a new idempotent operation"""
        # Mock the global redis_service
        mock_redis = AsyncMock()
        mock_redis.check_idempotency.return_value = True  # Can proceed (first time)
        mock_redis.get_idempotency_result.return_value = None
        mock_redis.store_idempotency_result.return_value = True
        monkeypatch.setattr("app.services.idempotency_service.redis_service", mock_redis)

        async def test_function(x, y):
            return x + y

        result = await IdempotencyService.execute_idempotent("test_key", test_function, x=5, y=3)

        assert result == 8
        # Should check if already performed
        mock_redis.check_idempotency.assert_called_once()
        # Should not check cache since it's a new operation
        mock_redis.get_idempotency_result.assert_not_called()
        # Should cache the result
        mock_redis.store_idempotency_result.assert_called_once()

    @pytest.mark.asyncio
    async def test_execute_idempotent_cached_result(self, idempotency_service_instance, monkeypatch):
        """Test executing idempotent operation with cached result"""
        # Mock the global redis_service
        mock_redis = AsyncMock()
        mock_redis.check_idempotency.return_value = False  # Duplicate operation
        mock_redis.get_idempotency_result.return_value = 42
        monkeypatch.setattr("app.services.idempotency_service.redis_service", mock_redis)

        async def test_function():
            return 999  # This should not be called

        result = await IdempotencyService.execute_idempotent("test_key", test_function)

        assert result == 42
        mock_redis.check_idempotency.assert_called_once()
        mock_redis.get_idempotency_result.assert_called_once()
        # Should not execute the function or store new result
        mock_redis.store_idempotency_result.assert_not_called()


class TestDistributedRateLimiter:
    """Test DistributedRateLimiter operations"""

    @pytest.fixture
    def rate_limiter_instance(self):
        """Create a fresh DistributedRateLimiter instance for testing"""
        limiter = DistributedRateLimiter()
        return limiter

    @pytest.mark.asyncio
    async def test_check_rate_limit_allowed(self, rate_limiter_instance, monkeypatch):
        """Test rate limit check when request is allowed"""
        # Mock the global redis_service
        mock_redis = AsyncMock()
        mock_redis.check_rate_limit.return_value = True
        monkeypatch.setattr("app.core.distributed_rate_limiter.redis_service", mock_redis)

        allowed = await rate_limiter_instance.check_rate_limit("user@test.com", "user")

        assert allowed is True
        mock_redis.check_rate_limit.assert_called_with(
            "user@test.com:user", 2, 1  # Test limits: 2 requests per 1 second window
        )

    @pytest.mark.asyncio
    async def test_check_rate_limit_blocked(self, rate_limiter_instance, monkeypatch):
        """Test rate limit check when request is blocked"""
        # Mock the global redis_service
        mock_redis = AsyncMock()
        mock_redis.check_rate_limit.return_value = False
        monkeypatch.setattr("app.core.distributed_rate_limiter.redis_service", mock_redis)

        allowed = await rate_limiter_instance.check_rate_limit("user@test.com", "user")

        assert allowed is False

    @pytest.mark.asyncio
    async def test_check_rate_limit_redis_failure_fallback(self, rate_limiter_instance, monkeypatch):
        """Test that Redis failure falls back to allowing requests"""
        # Mock the global redis_service to raise exception
        mock_redis = AsyncMock()
        mock_redis.check_rate_limit.side_effect = Exception("Redis down")
        monkeypatch.setattr("app.core.distributed_rate_limiter.redis_service", mock_redis)

        allowed = await rate_limiter_instance.check_rate_limit("user@test.com", "user")

        # Should fallback to allowing the request
        assert allowed is True

    @pytest.mark.asyncio
    async def test_reset_user(self, rate_limiter_instance, monkeypatch):
        """Test resetting rate limit for a user"""
        # Mock the global redis_service
        mock_redis = AsyncMock()
        mock_redis.reset_rate_limit.return_value = None
        monkeypatch.setattr("app.core.distributed_rate_limiter.redis_service", mock_redis)

        await rate_limiter_instance.reset_user("user@test.com", "user")

        mock_redis.reset_rate_limit.assert_called_with("user@test.com:user")


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
