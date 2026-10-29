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

RENDER_DPI = 220  # higher DPI -> sharper glyphs -> fewer digit misreads
# Table body occupies this vertical fraction of the page. The first page carries the
# tall account-info header, so its body starts lower; continuation pages start with
# only the thin column-header row, so cropping 0.27 there would drop the first several
# transactions.
BODY_TOP, BODY_BOTTOM = 0.27, 0.97
CONT_BODY_TOP = 0.04  # continuation pages (no account header)
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


def _column_lines(gray: np.ndarray, body_top: float = BODY_TOP) -> list[int]:
    """Detect vertical grid lines; fall back to template proportions if too few."""
    import cv2

    h, w = gray.shape
    th = cv2.adaptiveThreshold(~gray, 255, cv2.ADAPTIVE_THRESH_MEAN_C, cv2.THRESH_BINARY, 15, -2)
    band = th[int(h * body_top):int(h * BODY_BOTTOM), :]
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


def _page_transactions(engine, page, layout: str = "bcel", first_page: bool = True) -> list[TransactionRow]:
    import cv2

    img = _render_page(page)
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    body_top = BODY_TOP if first_page else CONT_BODY_TOP
    lines = _column_lines(gray, body_top)
    h = gray.shape[0]
    top, bottom = int(h * body_top), int(h * BODY_BOTTOM)
    x0, right = lines[0], lines[-1]

    result, _ = engine(img[top:bottom, x0:right])
    if not result:
        return []

    # Column x-ranges (relative to the crop), right-anchored so a missing faint
    # rule doesn't shift the money columns. BCEL: balance is the rightmost column.
    # MARUHAN/JBL: Teller's ID is rightmost, so balance is second from the right.
    b = [x - x0 for x in lines]
    date_x = (b[0], b[1])
    if layout in ("maruhan", "jdb"):
        # Both have a non-amount id column on the right, so the money columns are the
        # 4th–2nd rules from the right. JDB's description sits after Bill No + Code, so
        # its text column starts further in than MARUHAN's.
        numdesc_x = (b[3] if layout == "jdb" and len(b) >= 6 else b[1], b[-5])
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

    # Anchor one row per balance token: every transaction prints a running balance,
    # so a row survives even when its date column doesn't OCR as a valid date (which
    # otherwise silently drops the whole transaction). The date is matched to the row
    # by y and forward-filled from the last good date when this row's didn't read.
    bal_rows = sorted(amount_toks["balance"])
    if not bal_rows:
        return []
    row_ys = [y for (y, _t) in bal_rows]
    gaps = sorted(row_ys[i + 1] - row_ys[i] for i in range(len(row_ys) - 1))
    tol = max(10.0, (gaps[len(gaps) // 2] * 0.5) if gaps else 40.0)

    valid_dates = sorted((y, t.replace(" ", "")) for (y, t) in date_toks if _looks_like_date(t))

    def nearest(col: str, y: int) -> str:
        best_t, best_d = "", tol
        for (ty, t) in amount_toks[col]:
            d = abs(ty - y)
            if d <= best_d:
                best_d, best_t = d, t
        return best_t

    def date_at(y: int) -> str:
        best_t, best_d = "", tol
        for (ty, t) in valid_dates:
            d = abs(ty - y)
            if d <= best_d:
                best_d, best_t = d, t
        return best_t

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
    last_date = ""
    for idx, (y0, btext) in enumerate(bal_rows):
        y1 = row_ys[idx + 1] if idx + 1 < len(row_ys) else bottom
        date = date_at(y0)
        if date:
            last_date = date
        else:
            date = last_date
        num, desc = num_desc(y0, y1)
        try:
            debit = parse_lao_amount(nearest("debit", y0), default_zero=True)
            credit = parse_lao_amount(nearest("credit", y0), default_zero=True)
            balance = parse_lao_amount(btext, default_zero=False)
        except AmountParseError:
            debit = credit = balance = 0
        # Skip non-transaction lines: the opening-balance line (a balance with no
        # date and no movement), and the totals / summary block printed under the
        # table (rows with neither a bill number nor a description — a real
        # transaction always carries a bill number).
        if (not date and debit == 0 and credit == 0) or (not num and not desc):
            continue
        txns.append(
            TransactionRow(date=date, txn_number=num, description=desc,
                           debit=debit, credit=credit, balance=balance)
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
        for i, page in enumerate(pdf.pages):
            out.extend(_page_transactions(engine, page, layout, first_page=(i == 0)))
    out = _drop_trailing_summary(out, layout)
    # Cross-page date fill: the per-page pass resets at each page, so a row at the top
    # of a page whose date didn't OCR inherits the previous row's date here.
    last = ""
    for i, r in enumerate(out):
        if r.date:
            last = r.date
        elif last:
            out[i] = r.model_copy(update={"date": last})
    return _reconcile_amounts(out)


def ocr_page(page, layout: str = "bcel", first_page: bool = True) -> list[TransactionRow]:
    """OCR a single already-open pdfplumber page.

    Used to fill in scanned (image-only) pages inside an otherwise-digital PDF: the
    digital parser calls this for pages with no text layer, then reconciles the merged
    set. Loads the OCR engine lazily (and caches it) like the full-document path.
    """
    return _page_transactions(_get_engine(), page, layout, first_page)


def reconcile_amounts(rows: list[TransactionRow]) -> list[TransactionRow]:
    """Public wrapper: balance-based auto-correction over a (possibly mixed) row set."""
    return _reconcile_amounts(rows)


def _drop_trailing_summary(rows: list[TransactionRow], layout: str) -> list[TransactionRow]:
    """Drop the totals / summary block printed under the table on the last page.

    For banks that print a bill number on every transaction (BCEL, JDB) those rows
    are the trailing ones with no bill number — the OCR can still pick up the Lao
    summary labels as a description, so an empty-description test isn't enough. We cut
    only the trailing no-bill rows, leaving any mid-statement rows untouched.
    """
    if layout not in ("bcel", "jdb"):
        return rows
    last_real = -1
    for i, r in enumerate(rows):
        if r.txn_number:
            last_real = i
    return rows[: last_real + 1] if last_real >= 0 else rows


def _reconcile_amounts(rows: list[TransactionRow]) -> list[TransactionRow]:
    """Auto-correct debit/credit misreads using the running balance as ground truth.

    The balance column is the most reliably OCR'd (right-aligned, fixed 2dp format).
    When a row's OCR'd debit/credit don't match the balance movement, but the balance
    column is internally consistent across its neighbours, the movement is derived
    from the balance delta (positive -> credit, negative -> debit). Balance-column
    misreads are left for the human review step. This measurably cuts the number of
    rows a reviewer must fix without touching the digital paths.
    """
    from decimal import Decimal

    tol = Decimal("0.005")
    n = len(rows)

    def consistent(prev_bal: Decimal, r: TransactionRow) -> bool:
        return abs((r.balance - prev_bal) - (r.credit - r.debit)) <= tol

    for i in range(1, n):
        prev_bal = rows[i - 1].balance
        cur = rows[i]
        if consistent(prev_bal, cur):
            continue
        # Only trust the balance column here if the *next* row reconciles against
        # cur.balance — a misread balance would break that neighbour too.
        trust_balance = True
        if i + 1 < n:
            trust_balance = consistent(cur.balance, rows[i + 1])
        if not trust_balance:
            # The balance itself looks misread. If the OCR'd debit/credit instead
            # reconcile the next row, derive the balance from them.
            if i + 1 < n:
                cand = prev_bal + (cur.credit - cur.debit)
                if consistent(cand, rows[i + 1]):
                    rows[i] = cur.model_copy(update={"balance": cand})
            continue
        delta = cur.balance - prev_bal
        credit = delta if delta >= 0 else Decimal("0")
        debit = -delta if delta < 0 else Decimal("0")
        if credit == cur.credit and debit == cur.debit:
            continue
        rows[i] = cur.model_copy(update={"debit": debit, "credit": credit})
    return rows
