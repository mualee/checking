"""Audit log search — manager/admin only, read-only.

Filtering is done in Python after a single-field `order_by(timestamp)` fetch, so no
Firestore composite indexes are required (combining where + order_by would otherwise
demand a pre-built index). Fine for moderate log volumes; revisit with real indexes
if audit volume grows large.
"""
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

# Upper bound of recent logs scanned before Python-side filtering.
_SCAN_CAP = 500


@router.get("", response_model=list[AuditLogOut])
async def search_audit_logs(
    _: ManagerUser,
    user_id: str | None = Query(None),
    action: AuditAction | None = Query(None),
    start: str | None = Query(None, description="ISO date lower bound (YYYY-MM-DD)"),
    end: str | None = Query(None, description="ISO date upper bound (YYYY-MM-DD)"),
    limit: int = Query(100, le=500),
) -> list[AuditLogOut]:
    db = get_firestore_client()
    docs = (
        db.collection(COL_AUDIT_LOGS)
        .order_by("timestamp", direction=firestore.Query.DESCENDING)
        .limit(_SCAN_CAP)
        .stream()
    )

    out: list[AuditLogOut] = []
    for doc in docs:
        d = doc.to_dict() or {}
        if user_id and d.get("userId") != user_id:
            continue
        if action and d.get("action") != action.value:
            continue
        ts = d.get("timestamp")
        ts_day = ts.date().isoformat() if hasattr(ts, "date") else ""
        if start and ts_day and ts_day < start:
            continue
        if end and ts_day and ts_day > end:
            continue
        out.append(
            AuditLogOut(
                id=doc.id,
                user_id=d.get("userId", ""),
                user_email=d.get("userEmail", ""),
                action=d.get("action", AuditAction.VIEW.value),
                target_type=d.get("targetType", "statement"),
                target_id=d.get("targetId", ""),
                timestamp=ts,
                details=d.get("details", {}),
            )
        )
        if len(out) >= limit:
            break
    return out
