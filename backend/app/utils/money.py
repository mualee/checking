"""Decimal-safe money parsing/formatting for Lao-Kip statement amounts.

Calculations use Decimal end-to-end to avoid float drift across 10,000+ row sums.
Conversion to a storage-friendly float happens in exactly one place: to_storage_number().
"""
from __future__ import annotations

from decimal import Decimal, InvalidOperation

# Characters that may appear as grouping separators or currency noise in cells.
_STRIP_CHARS = str.maketrans({",": "", " ": "", " ": "", "₭": "", "K": ""})


class AmountParseError(ValueError):
    """Raised when a cell that must contain a number cannot be parsed."""


def parse_lao_amount(cell: str | None, *, default_zero: bool = False) -> Decimal:
    """Parse a statement money cell into a Decimal.

    - Strips thousands separators, spaces, and Kip symbols.
    - Empty/whitespace cell -> Decimal("0") when default_zero=True (used for debit/credit,
      where a row is typically debit-only or credit-only), else raises AmountParseError
      (used for the balance column, which must always be present).
    - Parentheses denote a negative value, e.g. "(1,234.00)" -> -1234.00.
    """
    text = (cell or "").strip()
    if not text:
        if default_zero:
            return Decimal("0")
        raise AmountParseError("empty amount cell")

    negative = False
    if text.startswith("(") and text.endswith(")"):
        negative = True
        text = text[1:-1]
    if text.startswith("-"):
        negative = True
        text = text[1:]

    text = text.translate(_STRIP_CHARS)
    try:
        value = Decimal(text)
    except InvalidOperation as exc:
        raise AmountParseError(f"cannot parse amount: {cell!r}") from exc
    return -value if negative else value


def to_storage_number(d: Decimal) -> float:
    """Single boundary where Decimal precision is converted to a Firestore/JSON number.

    Rounds to 2 decimal places (statement amounts are 2dp) and returns a float.
    """
    return float(d.quantize(Decimal("0.01")))


def format_lao_amount(d: Decimal) -> str:
    """Presentation formatter: thousands separators, 2 decimals (e.g. 1,234,567.00)."""
    return f"{d.quantize(Decimal('0.01')):,.2f}"
