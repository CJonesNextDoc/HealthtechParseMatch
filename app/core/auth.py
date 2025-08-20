# app/core/auth.py
from typing import Literal, Optional, TypedDict
from fastapi import Header, HTTPException, status

class Caller(TypedDict, total=False):
    role: Literal["admin", "manager", "user", "vendor_app"]
    email: Optional[str]

def require_role(*allowed: str):
    async def dep(
        x_role: Optional[str] = Header(default=None, alias="X-Role"),
        x_user_email: Optional[str] = Header(default=None, alias="X-User-Email"),
    ) -> Caller:
        role = (x_role or "").lower()
        if role not in allowed:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Forbidden")
        return {"role": role, "email": x_user_email}
    return dep
