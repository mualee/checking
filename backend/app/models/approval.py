"""Approval API models."""
from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel

from app.core.constants import ApprovalDecision


class ApprovalCreate(BaseModel):
    decision: ApprovalDecision
    approved_amount: float = 0.0
    reason: str = ""


class ApprovalOut(BaseModel):
    id: str
    decided_by: str
    decided_at: datetime | None = None
    decision: ApprovalDecision
    approved_amount: float = 0.0
    reason: str = ""
