from app.utils.logger import get_logger
import logging
from fastapi import Request, HTTPException
from app.core.auth import get_caller
import time
from typing import Callable
from app.core.config import get_settings

def _check_logger_config():
    """Temporary diagnostic function to check logger configuration"""
    logger = get_logger(__name__)
    root = logging.getLogger()
    
    print("\n=== Logger Diagnostic Info ===")
    print(f"Logger name: {logger.name}")
    print(f"Logger handlers: {len(logger.handlers)}")
    for i, h in enumerate(logger.handlers):
        print(f"  Handler {i}: {type(h).__name__}")
    
    print(f"\nRoot logger handlers: {len(root.handlers)}")
    for i, h in enumerate(root.handlers):
        print(f"  Handler {i}: {type(h).__name__}")
    print("===========================\n")

class RateLimiter:
    def __init__(self):
        self._cache = {}
        self.logger = get_logger(__name__)
        self.logger.info(f"Creating new RateLimiter instance: {id(self)}")  # Add instance ID
        
        # Get fresh settings
        get_settings.cache_clear()
        settings = get_settings()
        self.WINDOW_SIZE = float(settings.rate_limit_window)
        
        # Store limits
        self.limits = {
            'user': int(settings.user_rate_limit),
            'manager': int(settings.manager_rate_limit),
            'admin': int(settings.admin_rate_limit),
            'vendor_app': int(settings.app_rate_limit)
        }
        self.logger.info(f"Rate limiter {id(self)} initialized with limits: {self.limits}")

    async def check_rate_limit(self, user_email: str, role: str) -> bool:
        # Use the precomputed limits mapping instead of trying to read
        # dynamic attribute names from Settings (avoids vendor_app_rate_limit)
        role_key = (role or "user").lower()
        # Normalize common variants
        if role_key in ("vendor", "vendor_app", "app", "vendorapp"):
            role_key = "vendor_app"

        limit = self.limits.get(role_key, self.limits.get("user"))
        
        now = time.time()
        key = f"{user_email}:{role}"
        
        if key not in self._cache:
            self._cache[key] = []
            self.logger.info(f"Created new cache entry for {key}")
        
        # Clean old requests from window
        window_start = now - self.WINDOW_SIZE
        old_len = len(self._cache[key])
        self._cache[key] = [ts for ts in self._cache[key] if ts > window_start]
        new_len = len(self._cache[key])
        self.logger.info(f"Cache for {key}: removed {old_len - new_len} old entries, {new_len} current entries")
        
        # Check if we would exceed limit
        current_requests = len(self._cache[key])
        # Block when already at (or above) the configured limit
        if current_requests >= limit:
            self.logger.info(f"Rate limit exceeded for {key}: {current_requests}/{limit} requests in window")
            return False

        # record this request
        self._cache[key].append(now)
        self.logger.info(f"Request allowed for {key}: {current_requests + 1}/{limit} requests in window")
        return True

    def reset(self):
        self.logger.info(f"Resetting rate limiter {id(self)} - before reset cache_keys={list(self._cache.keys())} sizes={[len(v) for v in self._cache.values()]}")
        self._cache = {}
        self.logger.info(f"Rate limiter {id(self)} state reset - after reset cache={self._cache}")
        
        # Force settings refresh
        get_settings.cache_clear()
        settings = get_settings()
        
        # Reinitialize limits
        self.WINDOW_SIZE = float(settings.rate_limit_window)
        self.limits = {
            'user': int(settings.user_rate_limit),
            'manager': int(settings.manager_rate_limit),
            'admin': int(settings.admin_rate_limit),
            'vendor_app': int(settings.app_rate_limit)
        }
        self.logger.info(f"Rate limiter {id(self)} reinitialized with limits: {self.limits}")

    def reset_user(self, user_email: str, role: str):
        """Reset rate limit cache for specific user"""
        key = f"{user_email}:{role}"
        self.logger.info(f"Rate limiter {id(self)} resetting user {key} - current state: {self._cache.get(key, [])}")
        if key in self._cache:
            self._cache[key] = []
            self.logger.info(f"Rate limiter {id(self)} cache reset for user {key}")

class RateLimitMiddleware:
    def __init__(self, requests: int = 2, window: int = 60, limiter=None):
        # If a limiter was passed in, use it; otherwise create one
        self.limiter = limiter or RateLimiter()
        self.logger = get_logger(__name__)
        self.logger.info(f"RateLimitMiddleware initialized: self_id={id(self)} limiter_id={id(self.limiter)}")

    async def __call__(self, request: Request, call_next: Callable):
        # If app.state has a rate_limiter, use that shared instance (test injection point)
        app_limiter = getattr(request.app.state, "rate_limiter", None)
        if app_limiter is not None and app_limiter is not self.limiter:
            self.logger.info(f"Using app.state.rate_limiter ({id(app_limiter)}) instead of self.limiter ({id(self.limiter)})")
            self.limiter = app_limiter

        path = request.url.path
        self.logger.info(f"Processing request to {path}")

        try:
            # Get caller info first
            caller = await get_caller(
                request.headers.get("X-User-Email"),
                request.headers.get("X-Role")
            )
            
            # Handle authenticated requests
            if caller:
                self.logger.info(f"Authenticated request from {caller['email']}")
                
                # Skip rate limiting for /health/db only
                if path == "/health/db":
                    return await call_next(request)
                    
                # Apply rate limiting to all other requests
                if not await self.limiter.check_rate_limit(caller["email"], caller["role"]):
                    self.logger.info(f"Rate limit exceeded for {caller['email']}")
                    from fastapi.responses import JSONResponse
                    return JSONResponse(
                        status_code=429,
                        content={"detail": "Rate limit exceeded"}
                    )
                
                # Only proceed if under limit
                return await call_next(request)
                
            # Allow unauthenticated /health/check
            if path == "/health/check":
                self.logger.info("Allowing unauthenticated health check")
                return await call_next(request)
                
            # Require auth for all other requests
            raise HTTPException(status_code=401, detail="Authentication required")
            
        except HTTPException as exc:
            # Let FastAPI handle the conversion to response
            self.logger.warning(f"HTTP error occurred: {exc.detail}")
            raise
        except Exception as e:
            # Log unexpected errors but convert to 500
            self.logger.error(f"Unexpected error: {str(e)}")
            raise HTTPException(status_code=500, detail="Internal server error") from e
        finally:
            self.logger.info(f"Middleware dispatch: {self.__call__}")