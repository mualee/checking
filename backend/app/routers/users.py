"""User management endpoints — admin only."""
from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status

from app.core.constants import AuditAction, AuditTargetType, UserRole
from app.dependencies.auth import AuthUser, get_current_user, require_role
from app.models.user import UserCreate, UserOut, UserUpdate
from app.services import user_service
from app.services.audit_service import write_audit_log

router = APIRouter(prefix="/users", tags=["users"])

AdminUser = Annotated[AuthUser, Depends(require_role(UserRole.ADMIN))]
CurrentUser = Annotated[AuthUser, Depends(get_current_user)]


@router.get("/me", response_model=UserOut)
async def get_me(user: CurrentUser) -> UserOut:
    """Return the caller's own profile (any authenticated, active user).

    Needed by the SPA to resolve role after login, since Firestore is
    deny-by-default for clients and all access is backend-mediated.
    """
    profile = user_service.get_user(user.uid)
    if profile is None:
        # get_current_user already guarantees the doc exists; defensive fallback.
        return UserOut(uid=user.uid, name="", email=user.email or "", role=user.role,
                       is_active=user.is_active)
    return profile


@router.get("", response_model=list[UserOut])
async def list_users(_: AdminUser) -> list[UserOut]:
    return user_service.list_users()


@router.post("", response_model=UserOut, status_code=status.HTTP_201_CREATED)
async def create_user(payload: UserCreate, admin: AdminUser) -> UserOut:
    created = user_service.create_user(payload)
    write_audit_log(user_id=admin.uid, user_email=admin.email, action=AuditAction.PROCESS,
                    target_type=AuditTargetType.USER, target_id=created.uid,
                    details={"created": True, "role": created.role.value})
    return created


@router.patch("/{uid}", response_model=UserOut)
async def update_user(uid: str, payload: UserUpdate, admin: AdminUser) -> UserOut:
    try:
        updated = user_service.update_user(uid, payload)
    except KeyError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="user not found") from exc
    write_audit_log(user_id=admin.uid, user_email=admin.email, action=AuditAction.PROCESS,
                    target_type=AuditTargetType.USER, target_id=uid,
                    details=payload.model_dump(exclude_none=True))
    return updated
