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
from app.services.pdf_report import generate_statement_report_pdf
from app.services.pdf_extraction import PDFExtractionError, extract_transactions_from_pdf
from app.services.storage_service import upload_bytes, upload_json
from app.utils.money import to_storage_number

logger = logging.getLogger("app.pipeline")


def _storage_prefix(customer_id: str, statement_id: str) -> str:
    return f"statements/{customer_id}/{statement_id}"


def _extract(pdf_bytes: bytes, source: str):
    """Route to the right extractor. Logical separation of the two PDF kinds:

      - digital PDF (has a text layer)  -> pdfplumber table extraction
      - scanned/printer PDF (image only) -> offline OCR

    Sources — three banks × two media:
      "digital"  BCEL digital  -> pdfplumber (BCEL layout)
      "scan"     BCEL printer  -> OCR (BCEL layout)
      "jbl"      JBL digital   -> pdfplumber (MARUHAN layout)
      "jbl_scan" JBL printer   -> OCR (MARUHAN layout)
      "jdb"      JDB digital   -> pdfplumber (JDB layout)
      "jdb_scan" JDB printer   -> OCR (JDB layout)
      "auto"     try BCEL digital, then JBL, then JDB digital, then OCR.
    OCR (onnxruntime/opencv) is imported lazily so digital paths never load it.
    """
    # Explicit digital banks: straight to their text parser (fastest, no OCR).
    if source == "digital":
        return extract_transactions_from_pdf(pdf_bytes)
    if source == "jbl":
        from app.services.maruhan_extraction import extract_maruhan_from_pdf
        return extract_maruhan_from_pdf(pdf_bytes)
    if source == "jdb":
        from app.services.maruhan_extraction import extract_jdb_from_pdf
        return extract_jdb_from_pdf(pdf_bytes)
    if source == "ldb":
        from app.services.ldb_extraction import extract_ldb_from_pdf
        return extract_ldb_from_pdf(pdf_bytes)

    if source in ("jbl_scan", "jdb_scan", "ldb_scan"):
        layout = {"jdb_scan": "jdb", "ldb_scan": "ldb"}.get(source, "maruhan")
        bank = {"jdb_scan": "JDB", "ldb_scan": "LDB"}.get(source, "JBL")
        from app.services.ocr_extraction import OCRUnavailableError, extract_transactions_via_ocr
        try:
            rows = extract_transactions_via_ocr(pdf_bytes, layout=layout)
        except OCRUnavailableError as exc:
            raise PDFExtractionError(f"OCR is not available in this build: {exc}") from exc
        if not rows:
            raise PDFExtractionError(f"OCR found no transactions in the scanned {bank} PDF")
        return rows

    if source == "auto":
        # Try the (fast) digital extractors first; fall back to OCR only if none
        # yields text rows. Avoids a separate full-document text-layer scan.
        for fn in (_try_bcel_digital, _try_jbl_digital, _try_jdb_digital, _try_ldb_digital):
            rows = fn(pdf_bytes)
            if rows:
                return rows

    from app.services.ocr_extraction import OCRUnavailableError, extract_transactions_via_ocr
    try:
        rows = extract_transactions_via_ocr(pdf_bytes)
    except OCRUnavailableError as exc:
        raise PDFExtractionError(f"OCR is not available in this build: {exc}") from exc
    if not rows:
        raise PDFExtractionError("OCR found no transactions in the scanned PDF")
    return rows


def _try_bcel_digital(pdf_bytes: bytes):
    try:
        return extract_transactions_from_pdf(pdf_bytes)
    except PDFExtractionError:
        return None


def _try_jbl_digital(pdf_bytes: bytes):
    from app.services.maruhan_extraction import extract_maruhan_from_pdf
    try:
        return extract_maruhan_from_pdf(pdf_bytes)
    except PDFExtractionError:
        return None


def _try_jdb_digital(pdf_bytes: bytes):
    from app.services.maruhan_extraction import extract_jdb_from_pdf
    try:
        return extract_jdb_from_pdf(pdf_bytes)
    except PDFExtractionError:
        return None


def _try_ldb_digital(pdf_bytes: bytes):
    from app.services.ldb_extraction import extract_ldb_from_pdf
    try:
        return extract_ldb_from_pdf(pdf_bytes)
    except PDFExtractionError:
        return None


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
    source: str = "auto",
) -> ProcessingStatus:
    """Run steps 3-9. Returns the terminal ProcessingStatus.

    opening_balance: if None, it is derived from the first transaction
    (balance - credit + debit), i.e. the balance that must have preceded row 1.
    """
    prefix = _storage_prefix(customer_id, statement_id)

    # Step 3: extract (auto-routes scanned PDFs through OCR)
    try:
        transactions = _extract(pdf_bytes, source)
    except PDFExtractionError as exc:
        logger.warning("extraction failed for %s/%s: %s", customer_id, statement_id, exc)
        statement_service.set_status(customer_id, statement_id, ProcessingStatus.ERROR,
                                     error_detail=str(exc))
        return ProcessingStatus.ERROR

    # Persist the extracted rows immediately so a person can review/correct them
    # (esp. OCR results) even if validation later fails.
    upload_json(f"{prefix}/transactions.json", [t.to_json_dict() for t in transactions])

    # Any failure in validation/report (steps 4-9) must land the statement in 'error'
    # rather than leaving it stuck on 'processing' forever (the task runs detached, so
    # an uncaught exception would otherwise just be logged and the UI would hang).
    try:
        return process_transactions(
            customer_id, statement_id, transactions, uploaded_by,
            customer_name=customer_name, account_no=account_no,
            opening_balance=opening_balance, actor_email=actor_email,
        )
    except Exception as exc:  # noqa: BLE001
        logger.exception("processing failed for %s/%s", customer_id, statement_id)
        statement_service.set_status(customer_id, statement_id, ProcessingStatus.ERROR,
                                     error_detail=str(exc))
        return ProcessingStatus.ERROR


def process_transactions(
    customer_id: str,
    statement_id: str,
    transactions,
    uploaded_by: str,
    *,
    customer_name: str = "",
    account_no: str = "",
    opening_balance: Decimal | None = None,
    actor_email: str | None = None,
) -> ProcessingStatus:
    """Steps 4-9 over an explicit transaction list. Reused by the review/correct
    flow (re-validate after a human edits OCR output) as well as initial upload.
    The caller is responsible for having saved transactions.json."""
    prefix = _storage_prefix(customer_id, statement_id)

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

    # (transactions.json already persisted by the caller.)

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

    # Step 8: report -> Storage, in both PDF and Word (user picks the format).
    report_args = dict(
        customer_name=customer_name, account_no=account_no,
        period=f"{period_start} - {period_end}",
        table1=table1, table2=table2, table3=table3, validation=validation,
    )
    pdf_path = f"{prefix}/report.pdf"
    upload_bytes(pdf_path, generate_statement_report_pdf(**report_args), "application/pdf")
    upload_bytes(
        f"{prefix}/report.docx", generate_statement_report(**report_args),
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    )
    # reportStoragePath is the PDF (primary); the .docx sibling shares the prefix.
    statement_service.save_report_path(customer_id, statement_id, pdf_path)

    # Step 9: completed + audit
    statement_service.set_status(customer_id, statement_id, ProcessingStatus.COMPLETED)
    write_audit_log(
        user_id=uploaded_by, user_email=actor_email, action=AuditAction.PROCESS,
        target_type=AuditTargetType.STATEMENT, target_id=statement_id,
        details={"result": "completed", "transactions": len(transactions)},
    )
    return ProcessingStatus.COMPLETED
