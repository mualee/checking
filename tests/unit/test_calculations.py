"""Unit tests for pure calculation logic — no emulator required."""
from __future__ import annotations

from decimal import Decimal

import pytest

from app.core.constants import TOTAL_LABEL
from app.models.transaction import TransactionRow
from app.services.calculations import (
    build_table1,
    build_table2,
    build_table3,
    validate_balances,
)


def tx(date, debit, credit, balance, num="X", desc="d") -> TransactionRow:
    return TransactionRow(
        date=date, txn_number=num, description=desc,
        debit=Decimal(str(debit)), credit=Decimal(str(credit)), balance=Decimal(str(balance)),
    )


# --------------------------------------------------------------------------- #
# validate_balances
# --------------------------------------------------------------------------- #
def test_validate_all_match():
    txns = [
        tx("01/05/2024", 0, 5000000, 6000000),
        tx("10/05/2024", 2000000, 0, 4000000),
        tx("20/05/2024", 0, 3000000, 7000000),
    ]
    res = validate_balances(txns, Decimal("1000000"))
    assert res.matched is True
    assert res.mismatch_count == 0


def test_validate_single_mismatch_does_not_cascade():
    # Corrupt only the middle row's printed balance. Because validation advances on
    # the PRINTED balance, the following row (whose printed balance is consistent with
    # the corrupted value) must still validate -> exactly one mismatch, no cascade.
    txns = [
        tx("01/05/2024", 0, 5000000, 6000000),   # ok
        tx("10/05/2024", 1000000, 0, 9999999),   # WRONG (should be 5,000,000)
        tx("20/05/2024", 0, 500000, 10499999),   # consistent with printed 9,999,999 -> ok
    ]
    res = validate_balances(txns, Decimal("1000000"))
    assert res.mismatch_count == 1
    assert res.mismatches[0].row_index == 1
    assert res.mismatches[0].expected_balance == Decimal("5000000")
    assert res.mismatches[0].actual_balance == Decimal("9999999")


def test_validate_mismatch_first_row():
    txns = [tx("01/05/2024", 0, 100, 999)]  # expected 1100
    res = validate_balances(txns, Decimal("1000"))
    assert res.matched is False
    assert res.mismatches[0].row_index == 0


def test_validate_mismatch_last_row():
    txns = [
        tx("01/05/2024", 0, 100, 1100),
        tx("02/05/2024", 50, 0, 1049),  # expected 1050
    ]
    res = validate_balances(txns, Decimal("1000"))
    assert res.mismatch_count == 1
    assert res.mismatches[0].row_index == 1


def test_validate_empty_list():
    res = validate_balances([], Decimal("1000"))
    assert res.matched is True
    assert res.mismatch_count == 0


def test_validate_tolerance():
    # 0.005 difference is within default 0.01 tolerance.
    txns = [tx("01/05/2024", 0, Decimal("100.00"), Decimal("1100.005"))]
    res = validate_balances(txns, Decimal("1000.00"))
    assert res.matched is True


# --------------------------------------------------------------------------- #
# build_table1
# --------------------------------------------------------------------------- #
def _fixture_txns() -> list[TransactionRow]:
    """Mirrors scripts/build_fixtures.py so table math matches the fixture ground truth."""
    return [
        tx("01/05/2024", 0, 5000000, 6000000),
        tx("10/05/2024", 2000000, 0, 4000000),
        tx("20/05/2024", 0, 3000000, 7000000),
        tx("05/06/2024", 1500000, 0, 5500000),
        tx("15/06/2024", 0, 8000000, 13500000),
        tx("25/06/2024", 500000, 0, 13000000),
        tx("02/07/2024", 4000000, 0, 9000000),
        tx("12/07/2024", 0, 10000000, 19000000),
        tx("22/07/2024", 1000000, 0, 18000000),
        tx("03/08/2024", 0, 2000000, 20000000),
        tx("18/08/2024", 6000000, 0, 14000000),
    ]


def test_table1_matches_fixture_ground_truth():
    rows = build_table1(_fixture_txns())
    # 4 months + 1 total row
    assert len(rows) == 5
    by_month = {r.month: r for r in rows}
    assert by_month["05/2024"].debit == Decimal("2000000")
    assert by_month["05/2024"].credit == Decimal("8000000")
    assert by_month["05/2024"].end_balance == Decimal("7000000")
    assert by_month["08/2024"].diff == Decimal("-4000000")
    total = rows[-1]
    assert total.month == TOTAL_LABEL
    assert total.debit == Decimal("15000000")
    assert total.credit == Decimal("28000000")
    assert total.diff == Decimal("13000000")
    assert total.end_balance == Decimal("14000000")


def test_table1_chronological_across_year_boundary():
    txns = [
        tx("15/12/2024", 0, 100, 1100),
        tx("10/01/2025", 0, 200, 1300),
    ]
    rows = build_table1(txns)
    # Dec 2024 must sort before Jan 2025 (not string-sorted where "01" < "12").
    assert [r.month for r in rows[:-1]] == ["12/2024", "01/2025"]


def test_table1_end_balance_uses_last_source_row_in_month():
    txns = [
        tx("01/05/2024", 0, 100, 1100),
        tx("02/05/2024", 0, 100, 1200),  # last in source order
    ]
    rows = build_table1(txns)
    assert rows[0].end_balance == Decimal("1200")


def test_table1_empty():
    assert build_table1([]) == []


# --------------------------------------------------------------------------- #
# build_table2
# --------------------------------------------------------------------------- #
def test_table2_matches_fixture_ground_truth():
    rows = build_table2(_fixture_txns())
    assert [r.month for r in rows] == ["07/2024", "06/2024", "05/2024"]
    by_month = {r.month: r for r in rows}
    # 07/2024: max debit (4,000,000 @ 02/07) is a DIFFERENT row than max credit
    # (10,000,000 @ 12/07) — proves independent lookups.
    assert by_month["07/2024"].debit == Decimal("4000000")
    assert by_month["07/2024"].credit == Decimal("10000000")
    assert by_month["07/2024"].diff == Decimal("6000000")
    assert by_month["06/2024"].debit == Decimal("1500000")
    assert by_month["06/2024"].credit == Decimal("8000000")
    assert by_month["05/2024"].credit == Decimal("5000000")


def test_table2_independent_debit_credit_lookup():
    # Max credit and max debit are on different rows/dates within the month.
    txns = [
        tx("01/07/2024", 9000000, 0, 1000000),   # max debit
        tx("15/07/2024", 0, 7000000, 8000000),   # max credit
        tx("20/07/2024", 100, 0, 7999900),
    ]
    rows = build_table2(txns)
    assert rows[0].debit == Decimal("9000000")
    assert rows[0].credit == Decimal("7000000")


def test_table2_fewer_than_three_months():
    txns = [
        tx("01/05/2024", 0, 100, 1100),
        tx("01/06/2024", 0, 200, 1300),
    ]
    rows = build_table2(txns)
    assert len(rows) == 2  # no padding


def test_table2_tie_break_is_chronological():
    # Two months share the same max single credit -> earlier month ranks first (stable).
    txns = [
        tx("01/05/2024", 0, 500, 1500),
        tx("01/06/2024", 0, 500, 2000),
        tx("01/07/2024", 0, 900, 2900),
    ]
    rows = build_table2(txns)
    assert rows[0].month == "07/2024"          # highest
    assert [r.month for r in rows[1:]] == ["05/2024", "06/2024"]  # tie -> chronological


def test_table2_empty():
    assert build_table2([]) == []


# --------------------------------------------------------------------------- #
# build_table3 (recurring fixed obligations)
# --------------------------------------------------------------------------- #
def test_table3_detects_consecutive_run():
    # 500,000 debit once per month for 3 consecutive months -> one group.
    txns = [
        tx("05/05/2024", 500000, 0, 1, num="A1", desc="LOAN"),
        tx("05/06/2024", 500000, 0, 1, num="A2", desc="LOAN"),
        tx("05/07/2024", 500000, 0, 1, num="A3", desc="LOAN"),
    ]
    groups = build_table3(txns)
    assert len(groups) == 1
    g = groups[0]
    assert g.amount == Decimal("500000")
    assert g.month_count == 3
    assert [r.month for r in g.rows] == ["05/2024", "06/2024", "07/2024"]
    assert [r.txn_number for r in g.rows] == ["A1", "A2", "A3"]


def test_table3_drops_two_month_runs():
    txns = [
        tx("05/05/2024", 500000, 0, 1),
        tx("05/06/2024", 500000, 0, 1),  # only 2 consecutive -> dropped (min 3)
    ]
    assert build_table3(txns) == []


def test_table3_month_with_duplicate_amount_excluded_breaks_run():
    # 300,000 appears twice in 06/2024 -> 06 excluded -> run 05,06,07 broken.
    txns = [
        tx("05/05/2024", 300000, 0, 1),
        tx("10/06/2024", 300000, 0, 1),
        tx("20/06/2024", 300000, 0, 1),  # duplicate in June
        tx("05/07/2024", 300000, 0, 1),
    ]
    # Valid months = {05, 07} (06 excluded) -> not consecutive, no run >= 3.
    assert build_table3(txns) == []


def test_table3_gap_breaks_run():
    txns = [
        tx("05/05/2024", 700000, 0, 1),
        tx("05/06/2024", 700000, 0, 1),
        # July missing (gap)
        tx("05/08/2024", 700000, 0, 1),
        tx("05/09/2024", 700000, 0, 1),
    ]
    # Runs: [05,06] (len 2, dropped) and [08,09] (len 2, dropped).
    assert build_table3(txns) == []


def test_table3_year_boundary_consecutive():
    txns = [
        tx("05/11/2024", 900000, 0, 1),
        tx("05/12/2024", 900000, 0, 1),
        tx("05/01/2025", 900000, 0, 1),
    ]
    groups = build_table3(txns)
    assert len(groups) == 1
    assert [r.month for r in groups[0].rows] == ["11/2024", "12/2024", "01/2025"]


def test_table3_ranks_by_length_then_amount():
    txns = [
        # amount 100 for 4 consecutive months
        tx("01/01/2025", 100, 0, 1), tx("01/02/2025", 100, 0, 1),
        tx("01/03/2025", 100, 0, 1), tx("01/04/2025", 100, 0, 1),
        # amount 200 for 3 consecutive months
        tx("01/01/2025", 200, 0, 1), tx("01/02/2025", 200, 0, 1),
        tx("01/03/2025", 200, 0, 1),
    ]
    groups = build_table3(txns)
    assert [g.month_count for g in groups] == [4, 3]
    assert groups[0].amount == Decimal("100")


def test_table3_ignores_credits_and_zero_debits():
    txns = [
        tx("01/01/2025", 0, 500000, 1),  # credit, ignored
        tx("01/02/2025", 0, 500000, 1),
        tx("01/03/2025", 0, 500000, 1),
    ]
    assert build_table3(txns) == []


def test_table3_empty():
    assert build_table3([]) == []
