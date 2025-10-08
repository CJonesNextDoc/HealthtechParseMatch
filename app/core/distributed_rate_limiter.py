"""
Distributed Rate Limiter using Redis

Replaces the in-memory rate limiter with Redis-backed distributed rate limiting
that works across multiple instances.
"""

from app.core.config import get_settings
from app.services.redis_service import redis_service
from app.utils.logger import get_logger

logger = get_logger(__name__)


class DistributedRateLimiter:
    """Distributed rate limiter using Redis"""

    def __init__(self):
        self.settings = get_settings()
        self.logger = logger
        self.logger.info("Initializing DistributedRateLimiter with Redis")

        # Get fresh settings
        self.WINDOW_SIZE = float(self.settings.rate_limit_window)

        # Store limits
        self.limits = {
            "user": int(self.settings.user_rate_limit),
            "manager": int(self.settings.manager_rate_limit),
            "admin": int(self.settings.admin_rate_limit),
            "vendor_app": int(self.settings.app_rate_limit),
        }
        self.logger.info(f"DistributedRateLimiter initialized with limits: {self.limits}")

    async def check_rate_limit(self, user_email: str, role: str) -> bool:
        """
        Check rate limit using Redis for distributed rate limiting.

        Args:
            user_email: User email address
            role: User role (user, manager, admin, vendor_app)

        Returns:
            True if request is allowed, False if rate limited
        """
        # Normalize role
        role_key = (role or "user").lower()
        if role_key in ("vendor", "vendor_app", "app", "vendorapp"):
            role_key = "vendor_app"

        limit = self.limits.get(role_key, self.limits.get("user"))
        key = f"{user_email}:{role}"

        try:
            # Use Redis for distributed rate limiting
            allowed = await redis_service.check_rate_limit(key, limit, int(self.WINDOW_SIZE))

            if not allowed:
                self.logger.warning(f"Distributed rate limit exceeded for {key}")
                return False

            self.logger.debug(f"Rate limit check passed for {key}")
            return True

        except Exception as e:
            # Fallback to allow requests if Redis fails
            self.logger.error(f"Redis rate limit check failed for {key}: {e}")
            self.logger.warning("Falling back to allowing request due to Redis failure")
            return True

    async def reset_user(self, user_email: str, role: str):
        """Reset rate limit for specific user"""
        key = f"{user_email}:{role}"
        try:
            await redis_service.reset_rate_limit(key)
            self.logger.info(f"Rate limit reset for user {key}")
        except Exception as e:
            self.logger.error(f"Failed to reset rate limit for {key}: {e}")

    async def reset(self):
        """Reset all rate limits - for testing purposes"""
        # This is a no-op for distributed rate limiter since Redis data persists
        # In a real scenario, you might want to clear all rate limit keys
        self.logger.info("DistributedRateLimiter reset called (no-op for Redis-based limiter)")


# Global distributed rate limiter instance
distributed_rate_limiter = DistributedRateLimiter()
