"""Statement processing pipeline (spec steps 3-9).

Steps 1-2 (persist original.pdf, create the doc with status 'processing') are done by
the caller/router before invoking this. This function has no FastAPI request/response
coupling — plain args only — so it can later be moved to Cloud Tasks/Jobs unchanged.

The mandatory balance-validation gate (step 4) STOPS on any mismatch: the doc is left
in 'validation_failed' and NO report / table summaries are written.
"""
from __future__ import annotations

import logging
from decimal import Decimal

from app.core.constants import AuditAction, AuditTargetType, ProcessingStatus
from app.services import statement_service
from app.services.audit_service import write_audit_log
from app.services.calculations import build_table1, build_table2, build_table3, validate_balances
from app.services.docx_report import generate_statement_report
from app.services.pdf_extraction import PDFExtractionError, extract_transactions_from_pdf
from app.services.storage_service import upload_bytes, upload_json
from app.utils.money import to_storage_number

logger = logging.getLogger("app.pipeline")


def _storage_prefix(customer_id: str, statement_id: str) -> str:
    return f"statements/{customer_id}/{statement_id}"


def run_statement_pipeline(
    customer_id: str,
    statement_id: str,
    pdf_bytes: bytes,
    uploaded_by: str,
    *,
    customer_name: str = "",
    account_no: str = "",
    opening_balance: Decimal | None = None,
    actor_email: str | None = None,
) -> ProcessingStatus:
    """Run steps 3-9. Returns the terminal ProcessingStatus.

    opening_balance: if None, it is derived from the first transaction
    (balance - credit + debit), i.e. the balance that must have preceded row 1.
    """
    prefix = _storage_prefix(customer_id, statement_id)

    # Step 3: extract
    try:
        transactions = extract_transactions_from_pdf(pdf_bytes)
    except PDFExtractionError as exc:
        logger.warning("extraction failed for %s/%s: %s", customer_id, statement_id, exc)
        statement_service.set_status(customer_id, statement_id, ProcessingStatus.ERROR,
                                     error_detail=str(exc))
        return ProcessingStatus.ERROR

    if opening_balance is None:
        first = transactions[0]
        opening_balance = first.balance - first.credit + first.debit

    # Step 4: mandatory validation gate
    validation = validate_balances(transactions, opening_balance)

    total_debit = sum((t.debit for t in transactions), Decimal("0"))
    total_credit = sum((t.credit for t in transactions), Decimal("0"))
    period_start = transactions[0].date
    period_end = transactions[-1].date

    if not validation.matched:
        # Persist the failed validation summary but NO tables and NO report.
        statement_service.save_results(
            customer_id, statement_id,
            opening_balance=to_storage_number(opening_balance),
            total_transactions=len(transactions),
            total_debit=to_storage_number(total_debit),
            total_credit=to_storage_number(total_credit),
            period_start=period_start, period_end=period_end,
            validation=validation,
        )
        statement_service.set_status(customer_id, statement_id,
                                     ProcessingStatus.VALIDATION_FAILED)
        write_audit_log(
            user_id=uploaded_by, user_email=actor_email, action=AuditAction.PROCESS,
            target_type=AuditTargetType.STATEMENT, target_id=statement_id,
            details={"result": "validation_failed", "mismatchCount": validation.mismatch_count},
        )
        return ProcessingStatus.VALIDATION_FAILED

    # Step 5: tables
    table1 = build_table1(transactions)
    table2 = build_table2(transactions)
    table3 = build_table3(transactions)

    # Step 6: transactions.json in Storage (never per-row in Firestore)
    upload_json(f"{prefix}/transactions.json", [t.to_json_dict() for t in transactions])

    # Step 7: summaries -> Firestore
    statement_service.save_results(
        customer_id, statement_id,
        opening_balance=to_storage_number(opening_balance),
        total_transactions=len(transactions),
        total_debit=to_storage_number(total_debit),
        total_credit=to_storage_number(total_credit),
        period_start=period_start, period_end=period_end,
        validation=validation, table1=table1, table2=table2, table3=table3,
    )

    # Step 8: Word report -> Storage
    report_bytes = generate_statement_report(
        customer_name=customer_name, account_no=account_no,
        period=f"{period_start} - {period_end}",
        table1=table1, table2=table2, table3=table3, validation=validation,
    )
    report_path = f"{prefix}/report.docx"
    upload_bytes(report_path, report_bytes,
                 "application/vnd.openxmlformats-officedocument.wordprocessingml.document")
    statement_service.save_report_path(customer_id, statement_id, report_path)

    # Step 9: completed + audit
    statement_service.set_status(customer_id, statement_id, ProcessingStatus.COMPLETED)
    write_audit_log(
        user_id=uploaded_by, user_email=actor_email, action=AuditAction.PROCESS,
        target_type=AuditTargetType.STATEMENT, target_id=statement_id,
        details={"result": "completed", "transactions": len(transactions)},
    )
    return ProcessingStatus.COMPLETED
