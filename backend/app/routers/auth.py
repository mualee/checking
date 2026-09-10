"""Local authentication endpoints (offline desktop mode).

POST /auth/login            email + password -> { token }
POST /auth/change-password  current + new password (authenticated)

These replace Firebase Auth. Tokens are the local JWTs verified by
get_current_user when settings.local_mode is on.
"""
from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field

from app.core.local_auth import issue_token, verify_password
from app.dependencies.auth import AuthUser, get_current_user
from app.services import user_service

router = APIRouter(prefix="/auth", tags=["auth"])


class LoginRequest(BaseModel):
    email: str
    password: str


class LoginResponse(BaseModel):
    token: str


class ChangePasswordRequest(BaseModel):
    current_password: str
    new_password: str = Field(min_length=6)


@router.post("/login", response_model=LoginResponse)
async def login(payload: LoginRequest) -> LoginResponse:
    found = user_service.find_by_email(payload.email)
    if not found:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED,
                            detail="invalid email or password")
    uid, data = found
    if not verify_password(payload.password, data.get("passwordHash", "")):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED,
                            detail="invalid email or password")
    if data.get("isActive") is False:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="account deactivated")
    return LoginResponse(token=issue_token(uid, data.get("email")))


@router.post("/change-password", status_code=status.HTTP_204_NO_CONTENT)
async def change_password(
    payload: ChangePasswordRequest,
    user: Annotated[AuthUser, Depends(get_current_user)],
) -> None:
    found = user_service.find_by_email(user.email) if user.email else None
    data = found[1] if found else {}
    if not verify_password(payload.current_password, data.get("passwordHash", "")):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST,
                            detail="current password is incorrect")
    user_service.set_password(user.uid, payload.new_password)
