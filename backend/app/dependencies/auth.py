"""Authentication + role resolution dependencies.

Every protected route depends on get_current_user(), which verifies the Firebase ID
token and loads the caller's users/{uid} profile (role + isActive) from Firestore.

401: missing/malformed/invalid/expired token, or no users/{uid} doc (unprovisioned).
403: valid user but deactivated (isActive == False) or role not permitted.
"""
from __future__ import annotations

from typing import Annotated

from fastapi import Depends, Header, HTTPException, status
from pydantic import BaseModel

from app.core.constants import COL_USERS, UserRole
from app.core.firebase import get_auth, get_firestore_client


class AuthUser(BaseModel):
    uid: str
    email: str | None = None
    role: UserRole
    is_active: bool


def _unauthorized(detail: str) -> HTTPException:
    return HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=detail,
                         headers={"WWW-Authenticate": "Bearer"})


async def get_current_user(
    authorization: Annotated[str | None, Header()] = None,
) -> AuthUser:
    if not authorization or not authorization.lower().startswith("bearer "):
        raise _unauthorized("missing or malformed Authorization header")
    token = authorization.split(" ", 1)[1].strip()
    if not token:
        raise _unauthorized("empty bearer token")

    auth = get_auth()
    try:
        decoded = auth.verify_id_token(token)
    except Exception as exc:  # noqa: BLE001 - any verification failure is a 401
        raise _unauthorized(f"invalid token: {exc}") from exc

    uid = decoded["uid"]
    snap = get_firestore_client().collection(COL_USERS).document(uid).get()
    if not snap.exists:
        raise _unauthorized("user is not provisioned")
    data = snap.to_dict() or {}

    if data.get("isActive") is False:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="account deactivated")

    try:
        role = UserRole(data["role"])
    except (KeyError, ValueError) as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN,
                            detail="user has no valid role") from exc

    return AuthUser(uid=uid, email=decoded.get("email") or data.get("email"),
                    role=role, is_active=bool(data.get("isActive", True)))


def require_role(*roles: UserRole):
    """Dependency factory: allow only the given roles."""
    allowed = set(roles)

    async def _dep(user: Annotated[AuthUser, Depends(get_current_user)]) -> AuthUser:
        if user.role not in allowed:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN,
                                detail="insufficient role")
        return user

    return _dep
