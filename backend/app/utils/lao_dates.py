"""Date helpers for statement rows.

Statement dates print differently per bank: DD/MM/YYYY (BCEL), DD-MM-YYYY
(JBL/JDB), or "DD MMM YY" with an English month abbreviation (LDB, e.g. 02 APR 26).
A row starts a new transaction iff its date cell parses under one of these formats;
continuation (wrapped-description) rows have an empty date cell.
"""
from __future__ import annotations

import re
from datetime import datetime

DATE_FORMAT = "%d/%m/%Y"
# Accepted printed date formats across supported banks (slash: BCEL, dash: JBL/JDB).
DATE_FORMATS = ("%d/%m/%Y", "%d-%m-%Y")
# LDB prints "DD MMM YY" with an uppercase English month; parse it manually since
# %b is locale-dependent.
_MONTHS = {m: i for i, m in enumerate(
    ["JAN", "FEB", "MAR", "APR", "MAY", "JUN", "JUL", "AUG", "SEP", "OCT", "NOV", "DEC"], 1)}
_LDB_DATE_RE = re.compile(r"^(\d{1,2}) ([A-Za-z]{3}) (\d{2})$")


def parse_statement_date(cell: str | None) -> datetime | None:
    """Return a datetime if the cell is a valid statement date, else None.

    Accepts DD/MM/YYYY, DD-MM-YYYY and "DD MMM YY". Strict otherwise: no partial or
    malformed dates. Used as the discriminator between new-transaction and
    continuation rows, and by report generation to bucket rows by month.
    """
    text = (cell or "").strip()
    if not text:
        return None
    for fmt in DATE_FORMATS:
        try:
            return datetime.strptime(text, fmt)
        except ValueError:
            continue
    m = _LDB_DATE_RE.match(text)
    if m:
        day, mon, yy = m.group(1), m.group(2).upper(), m.group(3)
        if mon in _MONTHS:
            try:
                return datetime(2000 + int(yy), _MONTHS[mon], int(day))
            except ValueError:
                return None
    return None


def is_statement_date(cell: str | None) -> bool:
    return parse_statement_date(cell) is not None


def month_key(cell: str) -> str:
    """DD/MM/YYYY -> 'MM/YYYY' month key. Raises ValueError on a bad date."""
    dt = parse_statement_date(cell)
    if dt is None:
        raise ValueError(f"not a valid statement date: {cell!r}")
    return f"{dt.month:02d}/{dt.year}"


def month_sort_key(mk: str) -> tuple[int, int]:
    """'MM/YYYY' -> (year, month) for correct chronological ordering across years."""
    mm, yyyy = mk.split("/")
    return (int(yyyy), int(mm))
