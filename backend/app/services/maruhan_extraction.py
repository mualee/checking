"""Digital-PDF extraction for MARUHAN (Japan Bank Lao / JBL) statements.

A separate logical path from the BCEL extractor: JBL statements have a different
layout (8 columns: Date, Description, Code, Chq.No., Debit, Credit, Balance,
Teller's ID) and dash dates (DD-MM-YYYY). pdfplumber's table detection only
catches the header (data rows have no horizontal rules), so we work from the text
words directly: bucket each word into a column by its x-centre and group rows by
the Date column. Because this is the real text layer, accuracy is exact.
"""
from __future__ import annotations

import io
import re

import pdfplumber

from app.models.transaction import TransactionRow
from app.services.pdf_extraction import PDFExtractionError
from app.utils.money import AmountParseError, parse_lao_amount

# JBL dates print as DD-MM-YYYY (dashes), unlike BCEL's DD/MM/YYYY.
_DATE_RE = re.compile(r"^\d{2}-\d{2}-\d{4}$")
# Money tokens: 1,234,567.89 or 0.00 — filters out stray footer/description words.
_MONEY_RE = re.compile(r"^\d{1,3}(?:,\d{3})*\.\d{2}$")

# Column boundaries as a fraction of page width (fallback when the vertical rules
# can't be read). From the JBL template: 8 columns.
_FALLBACK_XR = [0.018, 0.100, 0.350, 0.415, 0.497, 0.614, 0.732, 0.856, 0.974]


def _column_lines(page) -> list[int]:
    """Vertical rule x-positions (grouped); fall back to template proportions."""
    xs = sorted({round(e["x0"]) for e in page.vertical_edges})
    lines: list[int] = []
    for x in xs:
        if lines and x - lines[-1] <= 6:
            continue
        lines.append(x)
    if len(lines) >= 8:
        return lines
    w = page.width
    return [int(w * r) for r in _FALLBACK_XR]


def _page_transactions(page) -> list[TransactionRow]:
    words = page.extract_words()
    if not words:
        return []
    lines = _column_lines(page)
    if len(lines) < 8:
        return []

    # Right-anchored mapping (Teller's ID is the rightmost column, so balance is
    # second from the right). date/description are the two leftmost.
    date_x = (lines[0], lines[1])
    desc_x = (lines[1], lines[2])
    debit_x = (lines[-5], lines[-4])
    credit_x = (lines[-4], lines[-3])
    balance_x = (lines[-3], lines[-2])

    def col(w):
        xc = (w["x0"] + w["x1"]) / 2
        for name, (lo, hi) in (
            ("date", date_x), ("desc", desc_x),
            ("debit", debit_x), ("credit", credit_x), ("balance", balance_x),
        ):
            if lo <= xc < hi:
                return name
        return None

    dates: list[tuple[float, str]] = []
    desc_words: list[tuple[float, str]] = []
    amounts = {"debit": [], "credit": [], "balance": []}
    for w in words:
        c = col(w)
        y = w["top"]
        if c == "date" and _DATE_RE.match(w["text"]):
            dates.append((y, w["text"]))
        elif c == "desc":
            desc_words.append((y, w["text"]))
        elif c in amounts and _MONEY_RE.match(w["text"]):
            amounts[c].append((y, w["text"]))

    dates.sort()
    if not dates:
        return []
    ys = [y for (y, _t) in dates]

    def by_row(name: str) -> dict[int, str]:
        best: dict[int, tuple[float, str]] = {}
        for (y, t) in amounts[name]:
            i = min(range(len(ys)), key=lambda k: abs(y - ys[k]))
            d = abs(y - ys[i])
            if i not in best or d < best[i][0]:
                best[i] = (d, t)
        return {i: v[1] for i, v in best.items()}

    debit_by, credit_by, balance_by = by_row("debit"), by_row("credit"), by_row("balance")

    def desc_for(y0: float, y1: float) -> str:
        parts = [t for (y, t) in sorted(desc_words) if y0 - 3 <= y < y1]
        return " ".join(parts).strip()

    txns: list[TransactionRow] = []
    bottom = page.height
    for idx, (y0, dtext) in enumerate(dates):
        y1 = ys[idx + 1] if idx + 1 < len(ys) else bottom
        try:
            debit = parse_lao_amount(debit_by.get(idx, ""), default_zero=True)
            credit = parse_lao_amount(credit_by.get(idx, ""), default_zero=True)
            balance = parse_lao_amount(balance_by.get(idx, "") or "0", default_zero=True)
        except AmountParseError:
            debit = credit = balance = 0  # flagged by the running-balance check
        txns.append(
            TransactionRow(
                date=dtext,
                txn_number="",
                description=desc_for(y0, y1),
                debit=debit,
                credit=credit,
                balance=balance,
            )
        )
    return txns


def extract_maruhan_from_pdf(pdf_bytes: bytes) -> list[TransactionRow]:
    """Top-level JBL entry: digital PDF bytes -> ordered TransactionRow list."""
    out: list[TransactionRow] = []
    try:
        with pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf:
            for page in pdf.pages:
                out.extend(_page_transactions(page))
    except PDFExtractionError:
        raise
    except Exception as exc:  # noqa: BLE001
        raise PDFExtractionError(f"failed to read JBL PDF: {exc}") from exc
    if not out:
        raise PDFExtractionError("no transactions found in JBL PDF")
    return out
