"""
Idempotency Service for HealthtechParseMatch

Provides idempotency keys to prevent duplicate operations and cache results
for expensive operations.
"""

import hashlib
from typing import Any, Optional

from app.services.redis_service import redis_service
from app.utils.logger import get_logger

logger = get_logger(__name__)


class IdempotencyService:
    """Service for handling idempotent operations"""

    @staticmethod
    def generate_key(operation: str, *args, **kwargs) -> str:
        """
        Generate a consistent idempotency key from operation and parameters.

        Args:
            operation: Operation name (e.g., "patient_match", "send_message")
            *args: Positional arguments
            **kwargs: Keyword arguments

        Returns:
            Consistent idempotency key
        """
        # Create a string representation of all parameters
        key_parts = [operation]
        key_parts.extend(str(arg) for arg in args)
        key_parts.extend(f"{k}:{v}" for k, v in sorted(kwargs.items()))

        key_string = "|".join(key_parts)
        return hashlib.sha256(key_string.encode()).hexdigest()

    @staticmethod
    async def execute_idempotent(operation: str, func, ttl: int = 3600, *args, **kwargs) -> Any:
        """
        Execute an operation with idempotency guarantees.

        Args:
            operation: Operation name
            func: Async function to execute
            ttl: Time to live for idempotency result in seconds
            *args: Arguments to pass to func
            **kwargs: Keyword arguments to pass to func

        Returns:
            Result of the operation (cached or fresh)
        """
        idempotency_key = IdempotencyService.generate_key(operation, *args, **kwargs)

        # Check if operation was already performed
        if not await redis_service.check_idempotency(idempotency_key, ttl):
            # Operation already performed, get cached result
            cached_result = await redis_service.get_idempotency_result(idempotency_key)
            if cached_result is not None:
                logger.info(f"Returning cached result for idempotent operation: {operation}")
                return cached_result
            else:
                logger.warning(f"Idempotency key exists but no cached result for: {operation}")

        # Execute the operation
        try:
            logger.info(f"Executing idempotent operation: {operation}")
            result = await func(*args, **kwargs)

            # Cache the result
            await redis_service.store_idempotency_result(idempotency_key, result, ttl)

            return result

        except Exception as e:
            logger.error(f"Idempotent operation failed: {operation} - {e}")
            # Don't cache failed results to allow retries
            raise

    @staticmethod
    async def check_operation_status(operation: str, *args, **kwargs) -> Optional[Any]:
        """
        Check if an operation has been completed and get its result.

        Returns:
            Result if operation completed, None if not started or expired
        """
        idempotency_key = IdempotencyService.generate_key(operation, *args, **kwargs)
        return await redis_service.get_idempotency_result(idempotency_key)

    @staticmethod
    async def clear_idempotency(operation: str, *args, **kwargs):
        """Clear idempotency state for an operation (for testing/admin purposes)"""
        IdempotencyService.generate_key(operation, *args, **kwargs)
        # This would need additional methods in RedisService to clear idempotency keys
        # For now, just log the intent
        logger.info(f"Would clear idempotency for operation: {operation}")


# Global idempotency service instance
idempotency_service = IdempotencyService()
