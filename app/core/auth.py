# app/core/auth.py
from typing import Literal, Optional, TypedDict
from fastapi import Header, HTTPException, status
from logging import getLogger

logger = getLogger(__name__)

class Caller(TypedDict, total=False):
    """Represents an authenticated caller"""
    email: str
    role: Literal["user", "manager", "admin", "vendor_app"]
    
async def get_caller(
    x_user_email: Optional[str] = Header(None),
    x_role: Optional[str] = Header(None)
) -> Optional[Caller]:
    """Extract and validate caller info from headers"""
    if not x_user_email or not x_role:
        return None
        
    if x_role not in ["user", "manager", "admin", "vendor_app"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Invalid role specified"
        )
    
    return Caller(email=x_user_email, role=x_role)

def require_role(*allowed: str):
    async def dep(
        x_role: Optional[str] = Header(default=None, alias="X-Role"),
        x_user_email: Optional[str] = Header(default=None, alias="X-User-Email"),
    ) -> Caller:
        raw_role = (x_role or "").lower()
        role = (raw_role or "").strip().strip('\'"').lower()
        allowed_norm = {a.strip().lower() for a in allowed}
        logger.info(f"raw_role={raw_role}, normalized_role={role}, allowed={allowed_norm}")
        logger.info(f"role in allowed: {(role in allowed)}")
        if role not in allowed_norm:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Forbidden: Role not authorized.")
        return {"role": role, "email": x_user_email}
    return dep


async def check_headers(user):
    if "email" not in user or "role" not in user:
        raise HTTPException(400, "User clearance cannot be checked.")
    return
