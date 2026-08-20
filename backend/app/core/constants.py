"""Shared enums and constants."""
from __future__ import annotations

from enum import Enum


class UserRole(str, Enum):
    OFFICER = "officer"
    MANAGER = "manager"
    ADMIN = "admin"


# users/{uid} is a directory shared with other internal apps, whose own role
# vocabulary (job categories, not this app's permissions) leaks in here.
# Map those to the closest equivalent in this app's model.
_EXTERNAL_ROLE_ALIASES = {
    "employee": UserRole.OFFICER,
    "it": UserRole.OFFICER,
    "user": UserRole.OFFICER,
}


def resolve_role(raw: str) -> UserRole:
    """Map a Firestore users/{uid}.role value to this app's UserRole.

    Raises ValueError for values with no known mapping (same as UserRole(raw)).
    """
    try:
        return UserRole(raw)
    except ValueError:
        mapped = _EXTERNAL_ROLE_ALIASES.get(raw)
        if mapped is None:
            raise
        return mapped


class CustomerStatus(str, Enum):
    ACTIVE = "active"
    ARCHIVED = "archived"


class ProcessingStatus(str, Enum):
    PENDING = "pending"
    PROCESSING = "processing"
    VALIDATED = "validated"
    VALIDATION_FAILED = "validation_failed"
    COMPLETED = "completed"
    ERROR = "error"


class ApprovalDecision(str, Enum):
    APPROVED = "approved"
    REJECTED = "rejected"
    PARTIAL = "partial"


class AuditAction(str, Enum):
    LOGIN = "login"
    UPLOAD = "upload"
    PROCESS = "process"
    APPROVE = "approve"
    REJECT = "reject"
    VIEW = "view"
    DOWNLOAD = "download"


class AuditTargetType(str, Enum):
    STATEMENT = "statement"
    CUSTOMER = "customer"
    USER = "user"


# Label used for the "total" row in Table 1 (Lao: "ລວມ").
TOTAL_LABEL = "ລວມ"

# Firestore collection names.
COL_USERS = "users"
COL_CUSTOMERS = "customers"
COL_STATEMENTS = "statements"        # subcollection under a customer
COL_APPROVALS = "approvals"          # subcollection under a statement
COL_AUDIT_LOGS = "auditLogs"
