"""Statement API models (summary shape stored in Firestore + returned to clients)."""
from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel

from app.core.constants import ProcessingStatus


class Table1RowOut(BaseModel):
    month: str
    debit: float
    credit: float
    diff: float
    endBalance: float


class Table2RowOut(BaseModel):
    month: str
    debit: float
    credit: float
    diff: float


class Table3RowOut(BaseModel):
    month: str
    txnNumber: str
    debit: float
    description: str


class Table3GroupOut(BaseModel):
    amount: float
    monthCount: int
    rows: list[Table3RowOut]


class ValidationOut(BaseModel):
    matched: bool
    mismatchCount: int
    checkedAt: datetime | None = None


class StatementOut(BaseModel):
    id: str
    customer_id: str
    file_name: str
    storage_path: str
    period_start: str = ""
    period_end: str = ""
    opening_balance: float = 0.0
    total_transactions: int = 0
    total_debit: float = 0.0
    total_credit: float = 0.0
    uploaded_by: str
    uploaded_at: datetime | None = None
    processing_status: ProcessingStatus = ProcessingStatus.PENDING
    validation: ValidationOut | None = None
    table1Summary: list[Table1RowOut] = []
    table2Summary: list[Table2RowOut] = []
    table3Summary: list[Table3GroupOut] = []
    report_storage_path: str = ""
    report_generated_at: datetime | None = None
    error_detail: str = ""
