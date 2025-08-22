# app/core/auth.py
from typing import Literal, Optional, TypedDict
from fastapi import Header, HTTPException, status
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class Caller(TypedDict, total=False):
    role: Literal["admin", "manager", "user", "vendor_app"]
    email: Optional[str]


def require_role(*allowed: str):
    async def dep(
        x_role: Optional[str] = Header(default=None, alias="X-Role"),
        x_user_email: Optional[str] = Header(default=None, alias="X-User-Email"),
    ) -> Caller:
        raw_role = (x_role or "").lower()
        role = (raw_role or "").strip().strip('\'"').lower()
        allowed_norm = {a.strip().lower() for a in allowed}
        logger.debug(f"raw_role={raw_role}, normalized_role={role}, allowed={allowed_norm}")
        logger.debug(f"role in allowed: {(role in allowed)}")
        if role not in allowed_norm:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Forbidden: Role not authorized.")
        return {"role": role, "email": x_user_email}
    return dep


async def check_headers(user):
    if "email" not in user or "role" not in user:
        raise HTTPException(400, "User clearance cannot be checked.")
    return
