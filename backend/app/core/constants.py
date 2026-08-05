"""Shared enums and constants."""
from __future__ import annotations

from enum import Enum


class UserRole(str, Enum):
    OFFICER = "officer"
    MANAGER = "manager"
    ADMIN = "admin"


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
