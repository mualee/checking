"""Digital-PDF extraction for LDB (Lao Development Bank) statements.

LDB statements print no table borders (unlike BCEL/JBL/JDB), so there are no
vertical rules to detect — columns are located from the printed word x-positions
instead. Layout (7 columns):

    Booking Date | Reference | Description | Value Date | Debit | Credit | Closing Balance

Dates read as "DD MMM YY" (e.g. "02 APR 26"). Amount columns are right-aligned, so
they're bucketed by each number's right edge; text columns by centre.
"""
from __future__ import annotations

import io
import re

import pdfplumber

from app.models.transaction import TransactionRow
from app.services.pdf_extraction import PDFExtractionError
from app.utils.money import AmountParseError, parse_lao_amount

_DATE_RE = re.compile(r"^\d{1,2} [A-Z]{3} \d{2}$")  # 02 APR 26
_MONEY_RE = re.compile(r"^\d{1,3}(?:,\d{3})*\.\d{2}$")

# Column x-ranges as a fraction of page width. Text columns use the word centre;
# amount columns use the number's right edge (right-aligned figures).
_DATE_X = (0.00, 0.106)     # Booking Date (leftmost)
_REF_X = (0.106, 0.268)     # Reference
_DESC_X = (0.268, 0.574)    # Description
# Amount right-edge ranges: Debit, Credit, Closing Balance (Value Date sits between
# desc and debit and is ignored). Figures are right-aligned and cluster at ~0.72 /
# ~0.82 / ~0.93 of the width; the boundaries sit in the gaps between those clusters.
_DEBIT_X = (0.640, 0.780)
_CREDIT_X = (0.780, 0.880)
_BALANCE_X = (0.880, 1.01)


def _page_transactions(page) -> list[TransactionRow]:
    words = page.extract_words()
    if not words:
        return []
    w_page = page.width

    date_lines: dict[int, list[tuple[float, str]]] = {}
    ref_words: list[tuple[float, str]] = []
    desc_words: list[tuple[float, str]] = []
    amounts: dict[str, list[tuple[float, str]]] = {"debit": [], "credit": [], "balance": []}
    for w in words:
        xc = ((w["x0"] + w["x1"]) / 2) / w_page
        x1 = w["x1"] / w_page
        y = w["top"]
        if _DATE_X[0] <= xc < _DATE_X[1]:
            date_lines.setdefault(round(y), []).append((w["x0"], w["text"]))
        elif _REF_X[0] <= xc < _REF_X[1]:
            ref_words.append((y, w["text"]))
        elif _DESC_X[0] <= xc < _DESC_X[1]:
            desc_words.append((y, w["text"]))
        elif _MONEY_RE.match(w["text"]):
            for name, (lo, hi) in (
                ("debit", _DEBIT_X), ("credit", _CREDIT_X), ("balance", _BALANCE_X),
            ):
                if lo <= x1 < hi:
                    amounts[name].append((y, w["text"]))
                    break

    dates: list[tuple[float, str]] = []
    for y, toks in date_lines.items():
        text = " ".join(t for _x, t in sorted(toks))
        if _DATE_RE.match(text):
            dates.append((y, text))
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
            debit = credit = balance = 0
        txns.append(
            TransactionRow(
                date=dtext,
                txn_number=words_in(ref_words, y0, y1),
                description=words_in(desc_words, y0, y1),
                debit=debit,
                credit=credit,
                balance=balance,
            )
        )
    return txns


def _page_has_text(page) -> bool:
    return len((page.extract_text() or "").strip()) >= 40


def extract_ldb_from_pdf(pdf_bytes: bytes) -> list[TransactionRow]:
    """Top-level LDB entry: digital PDF bytes -> ordered TransactionRow list.

    Scanned (image-only) pages inside the PDF are OCR'd with the LDB layout and
    merged, so a re-scanned last page is still read.
    """
    out: list[TransactionRow] = []
    used_ocr = False
    try:
        with pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf:
            for i, page in enumerate(pdf.pages):
                if _page_has_text(page):
                    out.extend(_page_transactions(page))
                else:
                    from app.services.ocr_extraction import ocr_page
                    out.extend(ocr_page(page, "ldb", first_page=(i == 0)))
                    used_ocr = True
    except PDFExtractionError:
        raise
    except Exception as exc:  # noqa: BLE001
        raise PDFExtractionError(f"failed to read LDB PDF: {exc}") from exc
    if used_ocr:
        from app.services.ocr_extraction import reconcile_amounts
        out = reconcile_amounts(out)
    if not out:
        raise PDFExtractionError("no transactions found in LDB PDF")
    return out
