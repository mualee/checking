"""Customer API models."""
from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel

from app.core.constants import CustomerStatus


class CustomerCreate(BaseModel):
    full_name: str
    national_id: str = ""
    phone: str = ""
    address: str = ""
    account_no: str = ""


class CustomerUpdate(BaseModel):
    full_name: str | None = None
    national_id: str | None = None
    phone: str | None = None
    address: str | None = None
    account_no: str | None = None
    status: CustomerStatus | None = None


class CustomerOut(BaseModel):
    id: str
    full_name: str
    national_id: str = ""
    phone: str = ""
    address: str = ""
    account_no: str = ""
    status: CustomerStatus = CustomerStatus.ACTIVE
    created_by: str
    created_at: datetime | None = None
    updated_at: datetime | None = None
