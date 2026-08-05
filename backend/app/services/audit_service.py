"""Append-only audit logging. Only the backend (service account) writes these."""
from __future__ import annotations

from firebase_admin import firestore

from app.core.constants import COL_AUDIT_LOGS, AuditAction, AuditTargetType
from app.core.firebase import get_firestore_client


def write_audit_log(
    *,
    user_id: str,
    user_email: str | None,
    action: AuditAction,
    target_type: AuditTargetType,
    target_id: str,
    details: dict | None = None,
) -> None:
    db = get_firestore_client()
    db.collection(COL_AUDIT_LOGS).add(
        {
            "userId": user_id,
            "userEmail": user_email or "",
            "action": action.value,
            "targetType": target_type.value,
            "targetId": target_id,
            "timestamp": firestore.SERVER_TIMESTAMP,
            "details": details or {},
        }
    )
