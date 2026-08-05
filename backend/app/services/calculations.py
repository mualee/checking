"""Pure calculation logic: balance validation + Table 1 / Table 2 / Table 3.

This module imports NO Firestore, Storage, or pdfplumber code — it operates only on
list[TransactionRow], so it is fully unit-testable with hand-built inputs.

Money is kept in Decimal throughout; conversion to storage floats happens elsewhere.
"""
from __future__ import annotations

from collections import OrderedDict, defaultdict
from datetime import datetime, timezone
from decimal import Decimal

from pydantic import BaseModel

from app.core.constants import TOTAL_LABEL
from app.models.transaction import TransactionRow
from app.utils.lao_dates import month_key, month_sort_key


# --------------------------------------------------------------------------- #
# Validation
# --------------------------------------------------------------------------- #
class ValidationMismatch(BaseModel):
    row_index: int          # 0-based index into the transaction list
    date: str
    expected_balance: Decimal
    actual_balance: Decimal
    difference: Decimal


class ValidationResult(BaseModel):
    matched: bool
    mismatch_count: int
    mismatches: list[ValidationMismatch]
    checked_at: datetime


def validate_balances(
    transactions: list[TransactionRow],
    opening_balance: Decimal,
    tolerance: Decimal = Decimal("0.01"),
) -> ValidationResult:
    """Recompute the running balance chain and compare against printed balances.

    expected = previous_balance - debit + credit, per row, in order.
    A row mismatches when abs(expected - printed_balance) > tolerance.

    CRITICAL: previous_balance always advances using the PRINTED balance (not the
    computed one) so a single bad row does not cascade false mismatches into every
    subsequent row.
    """
    mismatches: list[ValidationMismatch] = []
    previous = opening_balance
    for i, row in enumerate(transactions):
        expected = previous - row.debit + row.credit
        diff = expected - row.balance
        if abs(diff) > tolerance:
            mismatches.append(
                ValidationMismatch(
                    row_index=i,
                    date=row.date,
                    expected_balance=expected,
                    actual_balance=row.balance,
                    difference=diff,
                )
            )
        previous = row.balance  # advance on printed balance — no cascade
    return ValidationResult(
        matched=len(mismatches) == 0,
        mismatch_count=len(mismatches),
        mismatches=mismatches,
        checked_at=datetime.now(timezone.utc),
    )


# --------------------------------------------------------------------------- #
# Table 1 — per-month summary + total row
# --------------------------------------------------------------------------- #
class Table1Row(BaseModel):
    month: str          # "MM/YYYY", or TOTAL_LABEL for the final total row
    debit: Decimal
    credit: Decimal
    diff: Decimal       # credit - debit
    end_balance: Decimal


def _group_by_month(transactions: list[TransactionRow]) -> "OrderedDict[str, list[TransactionRow]]":
    """Group rows by 'MM/YYYY', ordered chronologically by (year, month).

    Within a month, rows preserve their original source order so the month's
    end balance is the LAST row in source order (not max-date).
    """
    groups: dict[str, list[TransactionRow]] = {}
    for row in transactions:
        groups.setdefault(month_key(row.date), []).append(row)
    ordered = OrderedDict()
    for mk in sorted(groups, key=month_sort_key):
        ordered[mk] = groups[mk]
    return ordered


def build_table1(transactions: list[TransactionRow]) -> list[Table1Row]:
    if not transactions:
        return []
    groups = _group_by_month(transactions)
    rows: list[Table1Row] = []
    total_debit = Decimal("0")
    total_credit = Decimal("0")
    for mk, month_rows in groups.items():
        debit = sum((r.debit for r in month_rows), Decimal("0"))
        credit = sum((r.credit for r in month_rows), Decimal("0"))
        total_debit += debit
        total_credit += credit
        rows.append(
            Table1Row(
                month=mk,
                debit=debit,
                credit=credit,
                diff=credit - debit,
                end_balance=month_rows[-1].balance,  # last row in source order
            )
        )
    rows.append(
        Table1Row(
            month=TOTAL_LABEL,
            debit=total_debit,
            credit=total_credit,
            diff=total_credit - total_debit,
            end_balance=transactions[-1].balance,  # last balance of the whole statement
        )
    )
    return rows


# --------------------------------------------------------------------------- #
# Table 2 — top 3 months by single-largest credit, paired with single-largest debit
# --------------------------------------------------------------------------- #
class Table2Row(BaseModel):
    month: str
    debit: Decimal      # the single largest debit in that month
    credit: Decimal     # the single largest credit in that month
    diff: Decimal       # credit - debit


def build_table2(transactions: list[TransactionRow]) -> list[Table2Row]:
    """1. Per month, the single largest credit (max over individual rows).
    2. Rank months by that value descending; take the top 3 (stable tie-break =
       chronological order).
    3. For each selected month, independently find the single largest debit.
    Returns fewer than 3 rows if the statement spans fewer distinct months.
    """
    if not transactions:
        return []
    groups = _group_by_month(transactions)  # chronological order preserved

    max_credit_by_month: "OrderedDict[str, Decimal]" = OrderedDict()
    for mk, month_rows in groups.items():
        max_credit_by_month[mk] = max((r.credit for r in month_rows), default=Decimal("0"))

    # Stable sort by max-credit desc; ties keep chronological order (groups is chronological).
    ranked_months = sorted(
        max_credit_by_month.keys(),
        key=lambda mk: max_credit_by_month[mk],
        reverse=True,
    )[:3]

    result: list[Table2Row] = []
    for mk in ranked_months:
        month_rows = groups[mk]
        max_credit = max_credit_by_month[mk]
        max_debit = max((r.debit for r in month_rows), default=Decimal("0"))
        result.append(
            Table2Row(
                month=mk,
                debit=max_debit,
                credit=max_credit,
                diff=max_credit - max_debit,
            )
        )
    return result


# --------------------------------------------------------------------------- #
# Table 3 — recurring equal debits across consecutive months (fixed obligations)
# --------------------------------------------------------------------------- #
class Table3Row(BaseModel):
    month: str
    txn_number: str
    debit: Decimal
    description: str


class Table3Group(BaseModel):
    amount: Decimal          # the recurring debit amount
    month_count: int         # length of the consecutive-month run
    rows: list[Table3Row]    # one row per month in the run, chronological


def _month_ordinal(mk: str) -> int:
    year, month = month_sort_key(mk)
    return year * 12 + (month - 1)


def _consecutive_runs(sorted_months: list[str]) -> list[list[str]]:
    """Split chronologically-sorted month keys into maximal runs of adjacent months."""
    runs: list[list[str]] = []
    current: list[str] = []
    for mk in sorted_months:
        if not current:
            current = [mk]
        elif _month_ordinal(mk) - _month_ordinal(current[-1]) == 1:
            current.append(mk)
        else:
            runs.append(current)
            current = [mk]
    if current:
        runs.append(current)
    return runs


def build_table3(
    transactions: list[TransactionRow],
    *,
    min_months: int = 3,
    top_n: int = 10,
) -> list[Table3Group]:
    """Detect recurring fixed obligations: the same debit amount appearing exactly
    once per month across a run of consecutive months.

    1. Group debit transactions (debit > 0) by exact amount.
    2. Per amount, a month is VALID only if it has exactly ONE such transaction;
       a month with 2+ identical-amount debits is excluded (likely a coincidental
       round number, not a real obligation).
    3. Within the valid months, find maximal runs of consecutive months.
    4/6. Keep runs of at least `min_months` (default 3 — 2-month runs are dropped),
       rank by run length descending, and return the top `top_n`.
    """
    by_amount: dict[Decimal, dict[str, list[TransactionRow]]] = defaultdict(
        lambda: defaultdict(list)
    )
    for r in transactions:
        if r.debit > 0:
            by_amount[r.debit][month_key(r.date)].append(r)

    groups: list[Table3Group] = []
    for amount, months in by_amount.items():
        valid = {m: rows[0] for m, rows in months.items() if len(rows) == 1}
        sorted_months = sorted(valid.keys(), key=month_sort_key)
        for run in _consecutive_runs(sorted_months):
            if len(run) < min_months:
                continue
            rows = [
                Table3Row(
                    month=m,
                    txn_number=valid[m].txn_number,
                    debit=amount,
                    description=valid[m].description,
                )
                for m in run
            ]
            groups.append(Table3Group(amount=amount, month_count=len(run), rows=rows))

    # Rank by run length desc; tie-break by larger amount first, then earliest month.
    groups.sort(
        key=lambda g: (-g.month_count, -g.amount, _month_ordinal(g.rows[0].month))
    )
    return groups[:top_n]
