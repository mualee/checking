"""Extract transactions from a statement PDF with pdfplumber.

Handles multi-row (wrapped) descriptions: a new transaction starts on a row whose
date cell is a valid DD/MM/YYYY date; a continuation row has an empty date cell and
its description text is appended to the current transaction.

Column layout (positional), matching the statement spec:
    [date, txn_number, description, debit, credit, balance]

NOTE: the pdfplumber table strategy that works depends on the real PDF's ruling.
Our fixtures have grid lines, so the default "lines"-based extract_table() works.
If production statements are borderless, tune TableSettings here (explicit vertical
lines / text strategy) — this is the one place that needs a representative sample.
"""
from __future__ import annotations

import io
import logging

import pdfplumber

from app.models.transaction import TransactionRow
from app.utils.lao_dates import is_statement_date
from app.utils.money import AmountParseError, parse_lao_amount

logger = logging.getLogger("app.pdf")

# Positional column indices.
COL_DATE = 0
COL_NUM = 1
COL_DESC = 2
COL_DEBIT = 3
COL_CREDIT = 4
COL_BALANCE = 5
MIN_COLS = 6


class PDFExtractionError(Exception):
    """Raised when the PDF cannot be parsed into well-formed transaction rows.

    Distinct from validation failure: this means the structure/data is unreadable,
    surfaced as processingStatus 'error' (not 'validation_failed').
    """


def _cell(row: list, idx: int) -> str:
    if idx >= len(row):
        return ""
    return (row[idx] or "").strip()


def _extract_raw_rows(pdf_bytes: bytes) -> list[list[str]]:
    rows: list[list[str]] = []
    try:
        with pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf:
            for page in pdf.pages:
                for table in page.extract_tables() or []:
                    rows.extend(table)
    except PDFExtractionError:
        raise
    except Exception as exc:  # noqa: BLE001 - surface any pdfplumber failure uniformly
        raise PDFExtractionError(f"failed to read PDF: {exc}") from exc
    return rows


def merge_continuation_rows(raw_rows: list[list[str]]) -> list[TransactionRow]:
    """Fold continuation rows into their preceding transaction.

    Classification per row:
      - date cell is a valid date        -> starts a new transaction
      - date cell empty, other cell set  -> continuation (append description)
      - date cell empty, all cells empty -> blank filler, skipped
      - date cell non-empty, not a date  -> header/noise, skipped
    """
    transactions: list[TransactionRow] = []
    current: dict | None = None

    def _finalize(acc: dict) -> None:
        transactions.append(
            TransactionRow(
                date=acc["date"],
                txn_number=acc["num"],
                description=" ".join(p for p in acc["desc_parts"] if p).strip(),
                debit=acc["debit"],
                credit=acc["credit"],
                balance=acc["balance"],
            )
        )

    for raw in raw_rows:
        date_cell = _cell(raw, COL_DATE)
        if is_statement_date(date_cell):
            if current is not None:
                _finalize(current)
            balance_cell = _cell(raw, COL_BALANCE)
            try:
                debit = parse_lao_amount(_cell(raw, COL_DEBIT), default_zero=True)
                credit = parse_lao_amount(_cell(raw, COL_CREDIT), default_zero=True)
                balance = parse_lao_amount(balance_cell, default_zero=False)
            except AmountParseError as exc:
                raise PDFExtractionError(
                    f"row for {date_cell!r}: {exc} (debit={_cell(raw, COL_DEBIT)!r}, "
                    f"credit={_cell(raw, COL_CREDIT)!r}, balance={balance_cell!r})"
                ) from exc
            current = {
                "date": date_cell,
                "num": _cell(raw, COL_NUM),
                "desc_parts": [_cell(raw, COL_DESC)],
                "debit": debit,
                "credit": credit,
                "balance": balance,
            }
            continue

        # Non-date rows:
        if date_cell:
            # Non-empty but not a date -> header / page-repeat header / noise.
            logger.debug("skipping non-date row: %r", raw)
            continue

        # Empty date cell:
        other_cells = [_cell(raw, i) for i in range(1, max(len(raw), MIN_COLS))]
        if not any(other_cells):
            continue  # fully blank filler row
        if current is None:
            # Continuation before any transaction (e.g. wrapped header) -> drop.
            logger.warning("dropping continuation row before any transaction: %r", raw)
            continue
        cont_desc = _cell(raw, COL_DESC)
        if cont_desc:
            current["desc_parts"].append(cont_desc)

    if current is not None:
        _finalize(current)
    return transactions


def extract_transactions_from_pdf(pdf_bytes: bytes) -> list[TransactionRow]:
    """Top-level entry: PDF bytes -> ordered list of TransactionRow."""
    raw_rows = _extract_raw_rows(pdf_bytes)
    transactions = merge_continuation_rows(raw_rows)
    if not transactions:
        raise PDFExtractionError("no transactions found in PDF")
    return transactions
