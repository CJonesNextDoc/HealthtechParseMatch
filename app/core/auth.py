# app/core/auth.py
from logging import getLogger
from typing import Literal, Optional, TypedDict, cast

from fastapi import Depends, HTTPException, Request, status

logger = getLogger(__name__)

Role = Literal["user", "manager", "admin", "vendor_app"]


class Caller(TypedDict):
    email: str
    role: Role


def _first_header(request: Request, *keys: str) -> Optional[str]:
    """Return the first present header among keys (case-insensitive)."""
    hdrs = request.headers
    for k in keys:
        v = hdrs.get(k)
        if v is not None:
            return v
    return None


def _normalize_role(raw: Optional[str]) -> Role:
    """Normalize and validate a role header value into a Role literal."""
    allowed: tuple[Role, ...] = ("user", "manager", "admin", "vendor_app")
    role = (raw or "").strip().strip("'\"").lower()

    if not role:
        return "user"  # <- no cast needed; this is already a Literal

    if role not in allowed:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Invalid role specified",
        )

    return cast(Role, role)  # dynamic string, safe after validation


async def get_caller(
    request: Request,
    x_user_email: Optional[str] = None,
    x_user_role: Optional[str] = None,
) -> Caller:
    """
    Extract and validate caller info from headers.

    Accepts both:
      - "X-User-Email" or "x-user-email"
      - "X-Role", "x-role", or "x-user-role"

    If headers are missing, falls back to anonymous "user"
    so public endpoints (e.g., /health) still work.
    """
    # Prefer explicit args if provided; otherwise read from request headers
    email = (x_user_email or _first_header(request, "X-User-Email", "x-user-email") or "").strip()
    role_raw = x_user_role or _first_header(request, "X-Role", "x-role", "X-User-Role", "x-user-role")

    role = _normalize_role(role_raw)

    if not email:
        email = "anonymous@local"

    return {"role": role, "email": email}


def require_role(*allowed: Role):
    """Dependency enforcing that the caller's role is in `allowed`."""

    async def dep(caller: Caller = Depends(get_caller)) -> Caller:
        if caller["role"] not in allowed:
            logger.info("Forbidden role=%s; allowed=%s", caller["role"], allowed)
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Forbidden: Role not authorized.",
            )
        return caller

    return dep


async def check_headers(user: Caller) -> Caller:
    if "email" not in user or "role" not in user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="User clearance cannot be checked.",
        )
    return user
