"""OCR extraction for scanned (image-only) statement PDFs.

Digital PDFs (with a text layer) are handled by pdf_extraction.py. A statement
scanned on a printer is a pure image with no text, so pdfplumber finds nothing.
Here we:

  1. rasterize each page,
  2. detect the table's column boundaries from the printed grid (with a
     proportional fallback when the faint lines can't be found),
  3. OCR the whole table body in one pass and bucket each recognised token into a
     column by its x-centre (isolated columns keep printed digits accurate, and
     x-bucketing stops a long account number in the description bleeding into an
     amount column),
  4. rebuild transactions keyed by the date column, taking only money-shaped
     tokens (ending in .dd) for the amount columns.

OCR is never 100%, so the numbers are meant to be reviewed/corrected by a person
before saving. The pipeline's running-balance check also flags any bad row.
"""
from __future__ import annotations

import io
import logging
import re

import numpy as np

from app.models.transaction import TransactionRow
from app.utils.money import AmountParseError, parse_lao_amount

logger = logging.getLogger("app.ocr")

RENDER_DPI = 150
# Table body occupies this vertical fraction of the page (below the header block).
BODY_TOP, BODY_BOTTOM = 0.27, 0.97
# Fallback column boundaries as a fraction of page width (from the BCEL template):
# [left, date|num, num|desc, desc|debit, debit|credit, credit|balance, right].
FALLBACK_XR = [0.056, 0.131, 0.267, 0.597, 0.706, 0.818, 0.935]
_MONEY_RE = re.compile(r"^\d{1,12}\.\d{2}$")
# A statement date, either BCEL's DD/MM/YYYY or JBL's DD-MM-YYYY.
_DATE_RE = re.compile(r"^\d{2}[-/]\d{2}[-/]\d{4}$")


def _looks_like_date(text: str) -> bool:
    return bool(_DATE_RE.match(text.replace(" ", "")))


class OCRUnavailableError(Exception):
    """OCR engine or its native deps are not available in this build."""


_engine = None


def _get_engine():
    global _engine
    if _engine is None:
        try:
            from rapidocr_onnxruntime import RapidOCR
        except Exception as exc:  # noqa: BLE001
            raise OCRUnavailableError(f"OCR engine not available: {exc}") from exc
        _engine = RapidOCR()
    return _engine


def has_text_layer(pdf_bytes: bytes) -> bool:
    """True if the PDF already has extractable text (=> use pdf_extraction)."""
    import pdfplumber

    with pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf:
        for page in pdf.pages:
            if page.chars:
                return True
    return False


def _render_page(page) -> np.ndarray:
    """pdfplumber page -> BGR ndarray at RENDER_DPI."""
    pil = page.to_image(resolution=RENDER_DPI).original.convert("RGB")
    return np.array(pil)[:, :, ::-1].copy()  # RGB -> BGR for cv2


def _column_lines(gray: np.ndarray) -> list[int]:
    """Detect vertical grid lines; fall back to template proportions if too few."""
    import cv2

    h, w = gray.shape
    th = cv2.adaptiveThreshold(~gray, 255, cv2.ADAPTIVE_THRESH_MEAN_C, cv2.THRESH_BINARY, 15, -2)
    band = th[int(h * BODY_TOP):int(h * BODY_BOTTOM), :]
    vk = cv2.getStructuringElement(cv2.MORPH_RECT, (1, max(8, band.shape[0] // 25)))
    vert = cv2.dilate(cv2.erode(band, vk), vk)
    thr = band.shape[0] * 0.25 * 255
    xs = [x for x in range(w) if vert[:, x].sum() > thr]
    lines: list[int] = []
    if xs:
        cur = [xs[0]]
        for v in xs[1:]:
            if v - cur[-1] <= 20:
                cur.append(v)
            else:
                lines.append(int(np.mean(cur)))
                cur = [v]
        lines.append(int(np.mean(cur)))
        # keep the table's left border too (JBL's is close to the page edge);
        # only drop true far-left margin ticks.
        lines = [x for x in lines if x > w * 0.012]
    if len(lines) >= 5:
        return lines
    return [int(w * r) for r in FALLBACK_XR]  # fallback for pages with faint rules


def _normalize_amount(text: str) -> str:
    """OCR renders thousands separators inconsistently ('.' or ','). Amounts are
    #,###,###.dd, so keep the last separator with 2 trailing digits as the decimal
    point and drop the rest."""
    t = "".join(ch for ch in text if ch.isdigit() or ch in ".,")
    if not t:
        return ""
    for i in range(len(t) - 1, -1, -1):
        if t[i] in ".,":
            dec = t[i + 1:]
            if len(dec) == 2 and dec.isdigit():
                return f"{t[:i].replace('.', '').replace(',', '')}.{dec}"
            break
    return t.replace(".", "").replace(",", "")


def _page_transactions(engine, page, layout: str = "bcel") -> list[TransactionRow]:
    import cv2

    img = _render_page(page)
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    lines = _column_lines(gray)
    h = gray.shape[0]
    top, bottom = int(h * BODY_TOP), int(h * BODY_BOTTOM)
    x0, right = lines[0], lines[-1]

    result, _ = engine(img[top:bottom, x0:right])
    if not result:
        return []

    # Column x-ranges (relative to the crop), right-anchored so a missing faint
    # rule doesn't shift the money columns. BCEL: balance is the rightmost column.
    # MARUHAN/JBL: Teller's ID is rightmost, so balance is second from the right.
    b = [x - x0 for x in lines]
    date_x = (b[0], b[1])
    if layout == "maruhan":
        numdesc_x = (b[1], b[-5])
        debit_x = (b[-5], b[-4])
        credit_x = (b[-4], b[-3])
        balance_x = (b[-3], b[-2])
    else:
        numdesc_x = (b[1], b[-4])
        debit_x = (b[-4], b[-3])
        credit_x = (b[-3], b[-2])
        balance_x = (b[-2], b[-1])

    date_toks: list[tuple[int, str]] = []
    numdesc_toks: list[tuple[int, str]] = []
    amount_toks = {"debit": [], "credit": [], "balance": []}
    for item in result:
        box, text = item[0], item[1]
        text = text.strip()
        xc = (min(p[0] for p in box) + max(p[0] for p in box)) / 2
        y = int(min(p[1] for p in box))
        if date_x[0] <= xc < date_x[1]:
            date_toks.append((y, text))
        elif numdesc_x[0] <= xc < numdesc_x[1]:
            numdesc_toks.append((y, text))
        else:
            norm = _normalize_amount(text)
            if _MONEY_RE.match(norm):  # only money-shaped tokens count as amounts
                for name, (lo, hi) in (("debit", debit_x), ("credit", credit_x), ("balance", balance_x)):
                    if lo <= xc < hi:
                        amount_toks[name].append((y, norm))
                        break

    dates = sorted((y, t) for (y, t) in date_toks if _looks_like_date(t))
    if not dates:
        return []
    ys = [y for (y, _t) in dates]

    def by_row(col: str) -> dict[int, str]:
        best: dict[int, tuple[int, str]] = {}
        for (y, t) in amount_toks[col]:
            i = min(range(len(ys)), key=lambda k: abs(y - ys[k]))
            d = abs(y - ys[i])
            if i not in best or d < best[i][0]:
                best[i] = (d, t)
        return {i: v[1] for i, v in best.items()}

    debit_by, credit_by, balance_by = by_row("debit"), by_row("credit"), by_row("balance")

    def num_desc(y0: int, y1: int) -> tuple[str, str]:
        num, parts = "", []
        for (y, t) in sorted(numdesc_toks):
            if y0 - 15 <= y < y1:
                digits = "".join(ch for ch in t if ch.isdigit())
                if not num and len(digits) >= 10 and digits == t.replace(" ", ""):
                    num = digits
                else:
                    parts.append(t)
        return num, " ".join(parts).strip()

    txns: list[TransactionRow] = []
    for idx, (y0, dtext) in enumerate(dates):
        y1 = ys[idx + 1] if idx + 1 < len(ys) else bottom
        num, desc = num_desc(y0, y1)
        try:
            debit = parse_lao_amount(debit_by.get(idx, ""), default_zero=True)
            credit = parse_lao_amount(credit_by.get(idx, ""), default_zero=True)
            balance = parse_lao_amount(balance_by.get(idx, ""), default_zero=False)
        except AmountParseError:
            debit = credit = balance = 0
        txns.append(
            TransactionRow(
                date=dtext.replace(" ", ""),
                txn_number=num,
                description=desc,
                debit=debit,
                credit=credit,
                balance=balance,
            )
        )
    return txns


def extract_transactions_via_ocr(pdf_bytes: bytes, layout: str = "bcel") -> list[TransactionRow]:
    """Top-level OCR entry: scanned PDF bytes -> ordered TransactionRow list.

    layout: "bcel" (6-column) or "maruhan"/JBL (8-column, Teller's ID rightmost).
    """
    import pdfplumber

    engine = _get_engine()
    out: list[TransactionRow] = []
    with pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf:
        for page in pdf.pages:
            out.extend(_page_transactions(engine, page, layout))
    return out
