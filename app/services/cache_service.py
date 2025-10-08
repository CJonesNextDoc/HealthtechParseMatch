"""
Caching Service for HealthtechParseMatch

Provides application-level caching for frequently accessed data,
API responses, and computed results using Redis.
"""

import hashlib
from typing import Any, Optional

from app.services.redis_service import redis_service
from app.utils.logger import get_logger

logger = get_logger(__name__)


class CacheService:
    """Application-level caching service"""

    @staticmethod
    def _make_cache_key(*args, **kwargs) -> str:
        """Create a consistent cache key from arguments"""
        # Sort kwargs for consistent key generation
        key_parts = list(args)
        key_parts.extend(f"{k}:{v}" for k, v in sorted(kwargs.items()))
        key_string = "|".join(str(part) for part in key_parts)

        # Create hash for shorter, consistent keys
        return hashlib.md5(key_string.encode()).hexdigest()

    @staticmethod
    async def get_or_set(cache_key: str, getter_func, ttl: Optional[int] = None):
        """
        Get cached value or set it using a getter function.

        Args:
            cache_key: Cache key
            getter_func: Async function to call if cache miss
            ttl: Time to live in seconds

        Returns:
            Cached or freshly computed value
        """
        # Try to get from cache first
        cached_value = await redis_service.get_cache(cache_key)
        if cached_value is not None:
            logger.debug(f"Cache hit for key: {cache_key}")
            return cached_value

        # Cache miss - call getter function
        logger.debug(f"Cache miss for key: {cache_key}")
        try:
            value = await getter_func()
            if value is not None:
                await redis_service.set_cache(cache_key, value, ttl)
                logger.debug(f"Cached value for key: {cache_key}")
            return value
        except Exception as e:
            logger.error(f"Error getting value for cache key {cache_key}: {e}")
            return None

    @staticmethod
    async def cache_patient_data(patient_id: str, data: dict, ttl: Optional[int] = None):
        """Cache patient data"""
        cache_key = f"patient:{patient_id}"
        return await redis_service.set_cache(cache_key, data, ttl)

    @staticmethod
    async def get_cached_patient_data(patient_id: str) -> Optional[dict]:
        """Get cached patient data"""
        cache_key = f"patient:{patient_id}"
        return await redis_service.get_cache(cache_key)

    @staticmethod
    async def cache_api_response(endpoint: str, params: dict, response: Any, ttl: Optional[int] = None):
        """Cache API response"""
        cache_key = CacheService._make_cache_key("api", endpoint, **params)
        return await redis_service.set_cache(cache_key, response, ttl)

    @staticmethod
    async def get_cached_api_response(endpoint: str, params: dict) -> Optional[Any]:
        """Get cached API response"""
        cache_key = CacheService._make_cache_key("api", endpoint, **params)
        return await redis_service.get_cache(cache_key)

    @staticmethod
    async def invalidate_patient_cache(patient_id: str):
        """Invalidate patient cache"""
        cache_key = f"patient:{patient_id}"
        return await redis_service.delete_cache(cache_key)

    @staticmethod
    async def invalidate_api_cache(endpoint: str, params: dict):
        """Invalidate API cache"""
        cache_key = CacheService._make_cache_key("api", endpoint, **params)
        return await redis_service.delete_cache(cache_key)

    @staticmethod
    async def warm_patient_cache(patient_ids: list):
        """
        Warm patient cache by pre-loading frequently accessed patients.

        Args:
            patient_ids: List of patient IDs to cache
        """
        logger.info(f"Warming cache for {len(patient_ids)} patients")
        # This would typically fetch from database and cache
        # For now, just log the intent
        pass


# Global cache service instance
cache_service = CacheService()
