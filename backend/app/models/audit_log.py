"""Audit log API model."""
from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel

from app.core.constants import AuditAction, AuditTargetType


class AuditLogOut(BaseModel):
    id: str
    user_id: str
    user_email: str = ""
    action: AuditAction
    target_type: AuditTargetType
    target_id: str
    timestamp: datetime | None = None
    details: dict = {}
