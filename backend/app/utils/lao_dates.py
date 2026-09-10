"""Date helpers for statement rows.

Statement dates are printed as DD/MM/YYYY (BCEL) or DD-MM-YYYY (JBL/MARUHAN). A row
starts a new transaction iff its date cell parses under one of those formats;
continuation (wrapped-description) rows have an empty date cell.
"""
from __future__ import annotations

from datetime import datetime

DATE_FORMAT = "%d/%m/%Y"
# Accepted printed date formats across supported banks (slash: BCEL, dash: JBL).
DATE_FORMATS = ("%d/%m/%Y", "%d-%m-%Y")


def parse_statement_date(cell: str | None) -> datetime | None:
    """Return a datetime if the cell is a valid statement date, else None.

    Accepts DD/MM/YYYY and DD-MM-YYYY. Strict otherwise: does not accept partial or
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
