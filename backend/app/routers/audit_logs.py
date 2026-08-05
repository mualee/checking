"""Audit log search — manager/admin only, read-only."""
from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Query
from firebase_admin import firestore

from app.core.constants import COL_AUDIT_LOGS, AuditAction, UserRole
from app.core.firebase import get_firestore_client
from app.dependencies.auth import AuthUser, require_role
from app.models.audit_log import AuditLogOut

router = APIRouter(prefix="/audit-logs", tags=["audit-logs"])

ManagerUser = Annotated[AuthUser, Depends(require_role(UserRole.MANAGER, UserRole.ADMIN))]


@router.get("", response_model=list[AuditLogOut])
async def search_audit_logs(
    _: ManagerUser,
    user_id: str | None = Query(None),
    action: AuditAction | None = Query(None),
    start: str | None = Query(None, description="ISO date/time lower bound"),
    end: str | None = Query(None, description="ISO date/time upper bound"),
    limit: int = Query(100, le=500),
) -> list[AuditLogOut]:
    db = get_firestore_client()
    q = db.collection(COL_AUDIT_LOGS)
    if user_id:
        q = q.where("userId", "==", user_id)
    if action:
        q = q.where("action", "==", action.value)
    if start:
        q = q.where("timestamp", ">=", start)
    if end:
        q = q.where("timestamp", "<=", end)
    q = q.order_by("timestamp", direction=firestore.Query.DESCENDING).limit(limit)

    out: list[AuditLogOut] = []
    for doc in q.stream():
        d = doc.to_dict() or {}
        out.append(
            AuditLogOut(
                id=doc.id,
                user_id=d.get("userId", ""),
                user_email=d.get("userEmail", ""),
                action=d.get("action", AuditAction.VIEW.value),
                target_type=d.get("targetType", "statement"),
                target_id=d.get("targetId", ""),
                timestamp=d.get("timestamp"),
                details=d.get("details", {}),
            )
        )
    return out
