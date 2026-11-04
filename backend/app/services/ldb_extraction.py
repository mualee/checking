"""Digital-PDF extraction for LDB (Lao Development Bank) statements.

LDB statements print no table borders (unlike BCEL/JBL/JDB), so there are no
vertical rules to detect — and the column x-positions shift between statements
(account-number width, template version). So geometry is detected per file:

  * the left-aligned text columns (Booking Date | Reference | Description) are
    bounded by the x-positions of the "Reference"/"Description"/"Value" header words;
  * the right-aligned amount columns (Debit | Credit | Closing Balance) are found by
    clustering the right edges of the money tokens into three groups.

Layout: Booking Date | Reference | Description | Value Date | Debit | Credit |
Closing Balance, with "DD MMM YY" dates (e.g. 02 MAY 26).
"""
from __future__ import annotations

import io
import re

import pdfplumber

from app.models.transaction import TransactionRow
from app.services.pdf_extraction import PDFExtractionError
from app.utils.money import AmountParseError, parse_lao_amount

_DATE_RE = re.compile(r"^\d{1,2} [A-Z]{3} \d{2}$")  # 02 MAY 26
_MONEY_RE = re.compile(r"^\d{1,3}(?:,\d{3})*\.\d{2}$")


class _Geometry:
    """Per-file column boundaries as fractions of page width."""

    def __init__(self, ref: float, desc: float, value: float, amt_b1: float, amt_b2: float):
        self.ref = ref          # Reference column starts here (= Date column ends)
        self.desc = desc        # Description starts
        self.value = value      # Value Date starts (= Description ends)
        self.amt_b1 = amt_b1    # Debit | Credit split (by money right-edge)
        self.amt_b2 = amt_b2    # Credit | Balance split


def _amount_bounds(x1s: list[float]) -> tuple[float, float] | None:
    """Split money right-edges into Debit/Credit/Balance by the two widest gaps."""
    xs = sorted(x1s)
    if len(xs) < 6:
        return None
    gaps = sorted(((xs[i + 1] - xs[i], i) for i in range(len(xs) - 1)), reverse=True)
    top = sorted(i for _g, i in gaps[:2])
    if len(top) < 2:
        return None
    b1 = (xs[top[0]] + xs[top[0] + 1]) / 2
    b2 = (xs[top[1]] + xs[top[1] + 1]) / 2
    return b1, b2


def _detect_geometry(pdf) -> _Geometry:
    page = pdf.pages[0]
    w = page.width
    words = page.extract_words()
    hx: dict[str, float] = {}
    for word in words:
        if word["text"] in ("Reference", "Description", "Value") and word["text"] not in hx:
            hx[word["text"]] = word["x0"] / w
    ref = hx.get("Reference", 0.11)
    desc = hx.get("Description", 0.29)
    value = hx.get("Value", 0.57)
    # Amount right-edges from the first few pages (enough rows for 3 clusters).
    x1s: list[float] = []
    for p in pdf.pages[:3]:
        pw = p.width
        for word in p.extract_words():
            if _MONEY_RE.match(word["text"]):
                x1s.append(word["x1"] / pw)
    bounds = _amount_bounds(x1s)
    if bounds:
        amt_b1, amt_b2 = bounds
    else:  # fallback: proportional to the amount headers
        amt_b1, amt_b2 = 0.72, 0.88
    return _Geometry(ref, desc, value, amt_b1, amt_b2)


def _page_transactions(page, geom: _Geometry) -> list[TransactionRow]:
    words = page.extract_words()
    if not words:
        return []
    w_page = page.width

    date_lines: dict[int, list[tuple[float, str]]] = {}
    ref_words: list[tuple[float, str]] = []
    desc_words: list[tuple[float, str]] = []
    amounts: dict[str, list[tuple[float, str]]] = {"debit": [], "credit": [], "balance": []}
    for word in words:
        xc = ((word["x0"] + word["x1"]) / 2) / w_page
        x1 = word["x1"] / w_page
        y = word["top"]
        if xc < geom.ref:
            date_lines.setdefault(round(y), []).append((word["x0"], word["text"]))
        elif xc < geom.desc:
            ref_words.append((y, word["text"]))
        elif xc < geom.value:
            desc_words.append((y, word["text"]))
        elif _MONEY_RE.match(word["text"]):
            name = "debit" if x1 < geom.amt_b1 else "credit" if x1 < geom.amt_b2 else "balance"
            amounts[name].append((y, word["text"]))

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
            geom = _detect_geometry(pdf)
            for i, page in enumerate(pdf.pages):
                if _page_has_text(page):
                    out.extend(_page_transactions(page, geom))
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
