"""Firestore CRUD + serialization for statement summary docs.

The full transaction list is NEVER stored per-row in Firestore — only in
transactions.json in Storage. Firestore holds summaries + status only.
"""
from __future__ import annotations

from firebase_admin import firestore

from app.core.constants import COL_CUSTOMERS, COL_STATEMENTS, ProcessingStatus
from app.core.firebase import get_firestore_client
from app.services.calculations import Table1Row, Table2Row, Table3Group, ValidationResult
from app.models.statement import StatementOut
from app.utils.money import to_storage_number


def _statements_col(customer_id: str):
    return (
        get_firestore_client()
        .collection(COL_CUSTOMERS)
        .document(customer_id)
        .collection(COL_STATEMENTS)
    )


def table1_to_storage(rows: list[Table1Row]) -> list[dict]:
    return [
        {
            "month": r.month,
            "debit": to_storage_number(r.debit),
            "credit": to_storage_number(r.credit),
            "diff": to_storage_number(r.diff),
            "endBalance": to_storage_number(r.end_balance),
        }
        for r in rows
    ]


def table2_to_storage(rows: list[Table2Row]) -> list[dict]:
    return [
        {
            "month": r.month,
            "debit": to_storage_number(r.debit),
            "credit": to_storage_number(r.credit),
            "diff": to_storage_number(r.diff),
        }
        for r in rows
    ]


def table3_to_storage(groups: list[Table3Group]) -> list[dict]:
    return [
        {
            "amount": to_storage_number(g.amount),
            "monthCount": g.month_count,
            "rows": [
                {
                    "month": r.month,
                    "txnNumber": r.txn_number,
                    "debit": to_storage_number(r.debit),
                    "description": r.description,
                }
                for r in g.rows
            ],
        }
        for g in groups
    ]


def validation_to_storage(result: ValidationResult) -> dict:
    return {
        "matched": result.matched,
        "mismatchCount": result.mismatch_count,
        "checkedAt": firestore.SERVER_TIMESTAMP,
    }


def create_statement_doc(customer_id: str, *, file_name: str, storage_path: str,
                         uploaded_by: str) -> str:
    ref = _statements_col(customer_id).document()
    ref.set(
        {
            "fileName": file_name,
            "storagePath": storage_path,
            "uploadedBy": uploaded_by,
            "uploadedAt": firestore.SERVER_TIMESTAMP,
            "processingStatus": ProcessingStatus.PROCESSING.value,
        }
    )
    return ref.id


def set_status(customer_id: str, statement_id: str, status: ProcessingStatus,
               *, error_detail: str | None = None) -> None:
    updates: dict = {"processingStatus": status.value}
    if error_detail is not None:
        updates["errorDetail"] = error_detail
    _statements_col(customer_id).document(statement_id).update(updates)


def save_results(
    customer_id: str,
    statement_id: str,
    *,
    opening_balance: float,
    total_transactions: int,
    total_debit: float,
    total_credit: float,
    period_start: str,
    period_end: str,
    validation: ValidationResult,
    table1: list[Table1Row] | None = None,
    table2: list[Table2Row] | None = None,
    table3: list[Table3Group] | None = None,
) -> None:
    updates: dict = {
        "openingBalance": opening_balance,
        "totalTransactions": total_transactions,
        "totalDebit": total_debit,
        "totalCredit": total_credit,
        "periodStart": period_start,
        "periodEnd": period_end,
        "validation": validation_to_storage(validation),
    }
    if table1 is not None:
        updates["table1Summary"] = table1_to_storage(table1)
    if table2 is not None:
        updates["table2Summary"] = table2_to_storage(table2)
    if table3 is not None:
        updates["table3Summary"] = table3_to_storage(table3)
    _statements_col(customer_id).document(statement_id).update(updates)


def save_report_path(customer_id: str, statement_id: str, report_path: str) -> None:
    _statements_col(customer_id).document(statement_id).update(
        {
            "reportStoragePath": report_path,
            "reportGeneratedAt": firestore.SERVER_TIMESTAMP,
        }
    )


def get_statement_raw(customer_id: str, statement_id: str):
    return _statements_col(customer_id).document(statement_id).get()


def list_statements(customer_id: str) -> list[StatementOut]:
    docs = _statements_col(customer_id).order_by(
        "uploadedAt", direction=firestore.Query.DESCENDING
    ).stream()
    return [doc_to_out(customer_id, d.id, d.to_dict() or {}) for d in docs]


def doc_to_out(customer_id: str, statement_id: str, data: dict) -> StatementOut:
    validation = None
    if isinstance(data.get("validation"), dict):
        v = data["validation"]
        validation = {
            "matched": v.get("matched", False),
            "mismatchCount": v.get("mismatchCount", 0),
            "checkedAt": v.get("checkedAt"),
        }
    return StatementOut(
        id=statement_id,
        customer_id=customer_id,
        file_name=data.get("fileName", ""),
        storage_path=data.get("storagePath", ""),
        period_start=data.get("periodStart", ""),
        period_end=data.get("periodEnd", ""),
        opening_balance=data.get("openingBalance", 0.0),
        total_transactions=data.get("totalTransactions", 0),
        total_debit=data.get("totalDebit", 0.0),
        total_credit=data.get("totalCredit", 0.0),
        uploaded_by=data.get("uploadedBy", ""),
        uploaded_at=data.get("uploadedAt"),
        processing_status=data.get("processingStatus", ProcessingStatus.PENDING.value),
        validation=validation,
        table1Summary=data.get("table1Summary", []),
        table2Summary=data.get("table2Summary", []),
        table3Summary=data.get("table3Summary", []),
        report_storage_path=data.get("reportStoragePath", ""),
        report_generated_at=data.get("reportGeneratedAt"),
        error_detail=data.get("errorDetail", ""),
    )
