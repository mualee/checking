"""Extraction tests against the generated fixture PDFs — no emulator required."""
from __future__ import annotations

import os
from decimal import Decimal

import pytest

from app.services.calculations import (
    build_table1,
    build_table2,
    build_table3,
    validate_balances,
)
from app.services.pdf_extraction import extract_transactions_from_pdf

FIXTURES = os.path.join(os.path.dirname(__file__), "..", "fixtures")


def _load(name: str) -> bytes:
    with open(os.path.join(FIXTURES, name), "rb") as f:
        return f.read()


def test_extract_plain_row_count_and_values():
    txns = extract_transactions_from_pdf(_load("sample_statement.pdf"))
    assert len(txns) == 11
    first = txns[0]
    assert first.date == "01/05/2024"
    assert first.txn_number == "B001"
    assert first.description == "SALARY DEPOSIT"
    assert first.credit == Decimal("5000000.00")
    assert first.debit == Decimal("0")
    assert first.balance == Decimal("6000000.00")


def test_extract_wrapped_descriptions_are_concatenated():
    txns = extract_transactions_from_pdf(_load("sample_statement_wrapped_desc.pdf"))
    # Wrapping must not create phantom rows.
    assert len(txns) == 11
    by_num = {t.txn_number: t for t in txns}
    assert by_num["B008"].description == "CUSTOMER PAYMENT FOR INVOICE INV-2024-0012 THANK YOU"
    assert by_num["B011"].description == "OFFICE EQUIPMENT PURCHASE MODEL XT-500 3 YEAR WARRANTY"
    # Amounts on the primary row are preserved despite the wraps.
    assert by_num["B008"].credit == Decimal("10000000.00")


def test_extracted_plain_passes_validation():
    txns = extract_transactions_from_pdf(_load("sample_statement.pdf"))
    res = validate_balances(txns, Decimal("1000000.00"))
    assert res.matched is True, res.mismatches


def test_extracted_mismatch_fails_validation():
    txns = extract_transactions_from_pdf(_load("sample_statement_mismatch.pdf"))
    res = validate_balances(txns, Decimal("1000000.00"))
    assert res.matched is False
    assert res.mismatch_count == 1
    # The corrupted row is the last one (off-by-one on printed balance).
    assert res.mismatches[0].row_index == 10


def test_recurring_fixture_table3():
    txns = extract_transactions_from_pdf(_load("sample_statement_recurring.pdf"))
    # Balance chain must still validate.
    assert validate_balances(txns, Decimal("1000000.00")).matched
    groups = build_table3(txns)
    # LOAN (5 months) ranks before INSURANCE (4 months); RENT excluded (dup in March).
    assert [g.month_count for g in groups] == [5, 4]
    assert groups[0].amount == Decimal("1500000")
    assert [r.month for r in groups[0].rows] == [
        "01/2025", "02/2025", "03/2025", "04/2025", "05/2025"
    ]
    assert groups[1].amount == Decimal("500000")
    assert groups[1].month_count == 4
    amounts = {g.amount for g in groups}
    assert Decimal("800000") not in amounts  # RENT duplicate-in-March excluded


def test_extraction_composes_with_tables():
    """Extracted rows must feed the pure table calculations to the fixture ground truth."""
    txns = extract_transactions_from_pdf(_load("sample_statement.pdf"))
    t1 = build_table1(txns)
    total = t1[-1]
    assert total.debit == Decimal("15000000")
    assert total.credit == Decimal("28000000")
    assert total.end_balance == Decimal("14000000")
    t2 = build_table2(txns)
    assert [r.month for r in t2] == ["07/2024", "06/2024", "05/2024"]
