"""
Redis Service for HealthtechParseMatch

Provides distributed caching, rate limiting, session management, and other Redis-backed features.
"""

import json
import time
from typing import Any, Dict, Optional

import redis.asyncio as redis
from redis.asyncio import Redis

from app.core.config import get_settings
from app.utils.logger import get_logger

logger = get_logger(__name__)


class RedisService:
    """Redis service for distributed features"""

    def __init__(self):
        self.settings = get_settings()
        self._client: Optional[Redis] = None
        self._enabled = self.settings.redis_enabled

    async def get_client(self) -> Redis:
        """Get or create Redis client"""
        if not self._enabled:
            raise RuntimeError("Redis is disabled in configuration")

        if self._client is None:
            try:
                self._client = redis.from_url(self.settings.redis_url, decode_responses=True)
                await self._client.ping()
                logger.info("Redis connection established")
            except Exception as e:
                logger.error(f"Failed to connect to Redis: {e}")
                raise

        return self._client

    async def close(self):
        """Close Redis connection"""
        if self._client:
            await self._client.close()
            self._client = None

    # Rate Limiting Methods
    async def check_rate_limit(self, key: str, limit: int, window: int) -> bool:
        """
        Check if rate limit is exceeded using Redis sorted sets.

        Args:
            key: Rate limit key (e.g., "user:email@domain.com")
            limit: Maximum requests allowed in window
            window: Time window in seconds

        Returns:
            True if request is allowed, False if rate limited
        """
        if not self._enabled:
            return True  # Allow all if Redis disabled

        client = await self.get_client()
        now = time.time()
        window_start = now - window

        # Use a pipeline for atomic operations
        async with client.pipeline() as pipe:
            # Remove old entries and count current entries
            rate_key = f"rate_limit:{key}"

            # Remove entries outside the window
            pipe.zremrangebyscore(rate_key, 0, window_start)
            # Add current timestamp
            pipe.zadd(rate_key, {str(now): now})
            # Count entries in window
            pipe.zcard(rate_key)
            # Set expiration on the key
            pipe.expire(rate_key, window * 2)  # Expire after 2x window to clean up

            results = await pipe.execute()

        current_count = results[2]

        if current_count > limit:
            logger.warning(f"Rate limit exceeded for {key}: {current_count}/{limit}")
            return False

        logger.debug(f"Rate limit check passed for {key}: {current_count}/{limit}")
        return True

    async def reset_rate_limit(self, key: str):
        """Reset rate limit for a key"""
        if not self._enabled:
            return

        client = await self.get_client()
        rate_key = f"rate_limit:{key}"
        await client.delete(rate_key)
        logger.info(f"Rate limit reset for {key}")

    # Caching Methods
    async def get_cache(self, key: str) -> Optional[Any]:
        """Get value from cache"""
        if not self._enabled:
            return None

        try:
            client = await self.get_client()
            cache_key = f"cache:{key}"
            value = await client.get(cache_key)

            if value:
                # Try to parse as JSON, fallback to string
                try:
                    return json.loads(value)
                except json.JSONDecodeError:
                    return value

        except Exception as e:
            logger.error(f"Cache get error for key {key}: {e}")

        return None

    async def set_cache(self, key: str, value: Any, ttl: Optional[int] = None) -> bool:
        """Set value in cache with optional TTL"""
        if not self._enabled:
            return False

        try:
            client = await self.get_client()
            cache_key = f"cache:{key}"

            # Serialize value
            if isinstance(value, (dict, list)):
                serialized_value = json.dumps(value)
            else:
                serialized_value = str(value)

            ttl_value = ttl or self.settings.redis_ttl_cache
            await client.setex(cache_key, ttl_value, serialized_value)

            logger.debug(f"Cache set for key {key} with TTL {ttl_value}")
            return True

        except Exception as e:
            logger.error(f"Cache set error for key {key}: {e}")
            return False

    async def delete_cache(self, key: str) -> bool:
        """Delete value from cache"""
        if not self._enabled:
            return False

        try:
            client = await self.get_client()
            cache_key = f"cache:{key}"
            result = await client.delete(cache_key)
            return result > 0
        except Exception as e:
            logger.error(f"Cache delete error for key {key}: {e}")
            return False

    # Session Management
    async def get_session(self, session_id: str) -> Optional[Dict[str, Any]]:
        """Get session data"""
        return await self.get_cache(f"session:{session_id}")

    async def set_session(self, session_id: str, data: Dict[str, Any]) -> bool:
        """Set session data"""
        return await self.set_cache(f"session:{session_id}", data, self.settings.redis_ttl_session)

    async def update_session(self, session_id: str, updates: Dict[str, Any]) -> bool:
        """Update session data"""
        current = await self.get_session(session_id) or {}
        current.update(updates)
        return await self.set_session(session_id, current)

    async def delete_session(self, session_id: str) -> bool:
        """Delete session"""
        return await self.delete_cache(f"session:{session_id}")

    # Idempotency Methods
    async def check_idempotency(self, key: str, ttl: int = 3600) -> bool:
        """
        Check if operation is idempotent (hasn't been performed recently).

        Args:
            key: Idempotency key
            ttl: Time to live in seconds

        Returns:
            True if operation can proceed (first time), False if duplicate
        """
        if not self._enabled:
            return True

        try:
            client = await self.get_client()
            idempotency_key = f"idempotency:{key}"

            # Try to set the key (only succeeds if it doesn't exist)
            result = await client.set(idempotency_key, "1", ex=ttl, nx=True)
            return result is not None

        except Exception as e:
            logger.error(f"Idempotency check error for key {key}: {e}")
            return True  # Allow operation if Redis fails

    async def store_idempotency_result(self, key: str, result: Any, ttl: int = 3600) -> bool:
        """Store result of idempotent operation"""
        return await self.set_cache(f"idempotency_result:{key}", result, ttl)

    async def get_idempotency_result(self, key: str) -> Optional[Any]:
        """Get cached result of idempotent operation"""
        return await self.get_cache(f"idempotency_result:{key}")

    # Distributed Locks
    async def acquire_lock(self, lock_key: str, ttl: int = 30) -> bool:
        """
        Acquire a distributed lock.

        Args:
            lock_key: Lock identifier
            ttl: Time to live in seconds

        Returns:
            True if lock acquired, False if already locked
        """
        if not self._enabled:
            return True

        try:
            client = await self.get_client()
            lock_redis_key = f"lock:{lock_key}"
            result = await client.set(lock_redis_key, "1", ex=ttl, nx=True)
            return result is not None
        except Exception as e:
            logger.error(f"Lock acquisition error for key {lock_key}: {e}")
            return False

    async def release_lock(self, lock_key: str) -> bool:
        """Release a distributed lock"""
        if not self._enabled:
            return True

        try:
            client = await self.get_client()
            lock_redis_key = f"lock:{lock_key}"
            result = await client.delete(lock_redis_key)
            return result > 0
        except Exception as e:
            logger.error(f"Lock release error for key {lock_key}: {e}")
            return False

    # Feature Flags
    async def get_feature_flag(self, flag_name: str) -> bool:
        """Get feature flag value"""
        if not self._enabled:
            return False

        try:
            client = await self.get_client()
            flag_key = f"feature_flag:{flag_name}"
            value = await client.get(flag_key)
            return value == "true"
        except Exception as e:
            logger.error(f"Feature flag get error for {flag_name}: {e}")
            return False

    async def set_feature_flag(self, flag_name: str, enabled: bool) -> bool:
        """Set feature flag value"""
        if not self._enabled:
            return False

        try:
            client = await self.get_client()
            flag_key = f"feature_flag:{flag_name}"
            value = "true" if enabled else "false"
            await client.set(flag_key, value)
            return True
        except Exception as e:
            logger.error(f"Feature flag set error for {flag_name}: {e}")
            return False

    # Message Deduplication (for message bus)
    async def check_message_duplicate(self, message_id: str, ttl: int = 86400) -> bool:
        """
        Check if message has been processed before.

        Args:
            message_id: Unique message identifier
            ttl: Time to remember message (default 24 hours)

        Returns:
            True if message is duplicate, False if new
        """
        if not self._enabled:
            return False

        try:
            client = await self.get_client()
            dedup_key = f"message_dedup:{message_id}"
            result = await client.set(dedup_key, "1", ex=ttl, nx=True)
            return result is None  # None means key already existed (duplicate)
        except Exception as e:
            logger.error(f"Message deduplication check error for {message_id}: {e}")
            return False

    # Health Check
    async def health_check(self) -> Dict[str, Any]:
        """Redis health check"""
        if not self._enabled:
            return {"status": "disabled", "enabled": False}

        try:
            client = await self.get_client()
            await client.ping()
            return {"status": "healthy", "enabled": True}
        except Exception as e:
            return {"status": "unhealthy", "enabled": True, "error": str(e)}


# Global Redis service instance
redis_service = RedisService()
