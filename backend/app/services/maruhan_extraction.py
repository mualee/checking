"""Digital-PDF extraction for columnar Lao bank statements (JBL, JDB).

These banks share a layout family pdfplumber's table detector can't read (data rows
have no horizontal rules), so we work from the text words directly: bucket each word
into a column by its x-centre and group rows by the Date column. Because this is the
real text layer, accuracy is exact.

Layouts differ only in which column holds the description (and whether there's a
bill/reference number); the money columns are right-anchored the same way:
  JBL / MARUHAN: Date, Description, Code, Chq.No., Debit, Credit, Balance, Teller's ID
  JDB:           Date, Bill No, Code, Description, Debit, Credit, Balance, User Id
"""
from __future__ import annotations

import io
import re

import pdfplumber

from app.models.transaction import TransactionRow
from app.services.pdf_extraction import PDFExtractionError
from app.utils.money import AmountParseError, parse_lao_amount

# Dates print as DD-MM-YYYY (dashes), unlike BCEL's DD/MM/YYYY.
_DATE_RE = re.compile(r"^\d{2}-\d{2}-\d{4}$")
# Money tokens: 1,234,567.89 or 0.00 — filters out stray footer/description words.
_MONEY_RE = re.compile(r"^\d{1,3}(?:,\d{3})*\.\d{2}$")

# Column boundaries as a fraction of page width (fallback when the vertical rules
# can't be read). 8 columns.
_FALLBACK_XR = [0.018, 0.100, 0.350, 0.415, 0.497, 0.614, 0.732, 0.856, 0.974]

# Per-bank column positions. `desc`/`txn` index the detected vertical rules from the
# left; the money columns are always the same three, anchored to the right edge.
_LAYOUTS = {
    "maruhan": {"desc": (1, 2), "txn": None},          # Description is the 2nd column
    "jdb": {"desc": (3, 4), "txn": (1, 2)},            # Description is the 4th; Bill No is 2nd
}


def _page_has_text(page) -> bool:
    """True if the page carries an extractable text layer (digital); False for a
    scanned, image-only page that must go through OCR instead."""
    return len((page.extract_text() or "").strip()) >= 40


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


def _page_transactions(page, layout: dict) -> list[TransactionRow]:
    words = page.extract_words()
    if not words:
        return []
    lines = _column_lines(page)
    if len(lines) < 8:
        return []

    date_x = (lines[0], lines[1])
    desc_x = (lines[layout["desc"][0]], lines[layout["desc"][1]])
    txn_x = None
    if layout["txn"] is not None:
        txn_x = (lines[layout["txn"][0]], lines[layout["txn"][1]])
    # Right-anchored money columns (the rightmost column is a non-amount id/teller).
    debit_x = (lines[-5], lines[-4])
    credit_x = (lines[-4], lines[-3])
    balance_x = (lines[-3], lines[-2])

    def col(w):
        xc = (w["x0"] + w["x1"]) / 2
        candidates = [
            ("date", date_x), ("desc", desc_x),
            ("debit", debit_x), ("credit", credit_x), ("balance", balance_x),
        ]
        if txn_x is not None:
            candidates.append(("txn", txn_x))
        for name, (lo, hi) in candidates:
            if lo <= xc < hi:
                return name
        return None

    dates: list[tuple[float, str]] = []
    desc_words: list[tuple[float, str]] = []
    txn_words: list[tuple[float, str]] = []
    amounts = {"debit": [], "credit": [], "balance": []}
    for w in words:
        c = col(w)
        y = w["top"]
        if c == "date" and _DATE_RE.match(w["text"]):
            dates.append((y, w["text"]))
        elif c == "desc":
            desc_words.append((y, w["text"]))
        elif c == "txn":
            txn_words.append((y, w["text"]))
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

    def words_in(rows: list[tuple[float, str]], y0: float, y1: float) -> str:
        return " ".join(t for (y, t) in sorted(rows) if y0 - 3 <= y < y1).strip()

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
                txn_number=words_in(txn_words, y0, y1) if txn_x is not None else "",
                description=words_in(desc_words, y0, y1),
                debit=debit,
                credit=credit,
                balance=balance,
            )
        )
    return txns


def _extract(pdf_bytes: bytes, layout_name: str, label: str) -> list[TransactionRow]:
    layout = _LAYOUTS[layout_name]
    out: list[TransactionRow] = []
    used_ocr = False
    try:
        with pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf:
            for i, page in enumerate(pdf.pages):
                if _page_has_text(page):
                    out.extend(_page_transactions(page, layout))
                else:
                    # A scanned page inside an otherwise-digital PDF (e.g. the last
                    # page re-scanned): OCR it with the same bank layout and merge.
                    from app.services.ocr_extraction import ocr_page
                    out.extend(ocr_page(page, layout_name, first_page=(i == 0)))
                    used_ocr = True
    except PDFExtractionError:
        raise
    except Exception as exc:  # noqa: BLE001
        raise PDFExtractionError(f"failed to read {label} PDF: {exc}") from exc
    if used_ocr:
        from app.services.ocr_extraction import reconcile_amounts
        out = reconcile_amounts(out)
    if not out:
        raise PDFExtractionError(f"no transactions found in {label} PDF")
    return out


def extract_maruhan_from_pdf(pdf_bytes: bytes) -> list[TransactionRow]:
    """Top-level JBL / MARUHAN entry: digital PDF bytes -> TransactionRow list."""
    return _extract(pdf_bytes, "maruhan", "JBL")


def extract_jdb_from_pdf(pdf_bytes: bytes) -> list[TransactionRow]:
    """Top-level JDB entry: digital PDF bytes -> TransactionRow list."""
    return _extract(pdf_bytes, "jdb", "JDB")
