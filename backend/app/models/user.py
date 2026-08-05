"""User API models."""
from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field

from app.core.constants import UserRole


class UserCreate(BaseModel):
    name: str
    email: str
    password: str = Field(min_length=6)
    role: UserRole
    department: str = ""


class UserUpdate(BaseModel):
    role: UserRole | None = None
    is_active: bool | None = None
    name: str | None = None
    department: str | None = None


class UserOut(BaseModel):
    uid: str
    name: str
    email: str
    role: UserRole
    department: str = ""
    is_active: bool = True
    created_at: datetime | None = None
