"""Structural + text assertions on the generated PDF report — no emulator needed."""
from __future__ import annotations

import io
from decimal import Decimal

import pdfplumber

from app.services.calculations import build_table1, build_table2, build_table3, validate_balances
from app.services.pdf_report import generate_statement_report_pdf
from app.models.transaction import TransactionRow


def _sample_txns() -> list[TransactionRow]:
    return [
        TransactionRow(date="01/05/2024", txn_number="B1", description="d",
                       debit=Decimal("0"), credit=Decimal("5000000"), balance=Decimal("6000000")),
        TransactionRow(date="10/05/2024", txn_number="B2", description="d",
                       debit=Decimal("2000000"), credit=Decimal("0"), balance=Decimal("4000000")),
        TransactionRow(date="05/06/2024", txn_number="B3", description="d",
                       debit=Decimal("0"), credit=Decimal("8000000"), balance=Decimal("12000000")),
    ]


def _generate() -> bytes:
    txns = _sample_txns()
    data = generate_statement_report_pdf(
        customer_name="ທ້າວ ສົມໃຈ", account_no="001-234-567", period="05/2024 - 06/2024",
        table1=build_table1(txns), table2=build_table2(txns), table3=build_table3(txns),
        validation=validate_balances(txns, Decimal("1000000")),
    )
    assert data[:4] == b"%PDF", "output must be a valid PDF"
    return data


def test_pdf_is_valid_and_single_stream():
    data = _generate()
    with pdfplumber.open(io.BytesIO(data)) as pdf:
        assert len(pdf.pages) >= 1


def test_lao_text_is_embedded_as_unicode():
    # Extractable Lao text proves the bundled font is registered and used (not tofu).
    data = _generate()
    with pdfplumber.open(io.BytesIO(data)) as pdf:
        text = "\n".join(p.extract_text() or "" for p in pdf.pages)
    for expected in (
        "ບົດລາຍງານການກວດສອບ",   # title
        "ສະຫຼຸບຕໍ່ເດືອນ",         # table 1 heading
        "ເດືອນ",                   # column header
        "ທ້າວ ສົມໃຈ",             # customer name
        "001-234-567",             # account number
    ):
        assert expected in text, f"missing from PDF: {expected!r}"
