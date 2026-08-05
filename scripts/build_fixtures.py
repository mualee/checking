"""Generate fixture bank-statement PDFs for extraction/validation tests.

Produces three PDFs under tests/fixtures/:
  - sample_statement.pdf              : clean, multi-month, balance chain valid
  - sample_statement_wrapped_desc.pdf : same data, two descriptions wrap across rows
  - sample_statement_mismatch.pdf     : same data, last row's printed balance corrupted

Descriptions are ASCII on purpose: extraction logic (date parsing, continuation-row
detection) is script-agnostic, and ASCII keeps the fixtures independent of whether a
Lao font is installed in the PDF renderer. Real statements are Lao; the logic is identical.

Run:  .venv/Scripts/python.exe scripts/build_fixtures.py
It also prints the ground-truth Table1/Table2/validation values to hardcode in tests.
"""
from __future__ import annotations

import os
from decimal import Decimal

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet

FIXTURES_DIR = os.path.join(os.path.dirname(__file__), "..", "tests", "fixtures")
OPENING_BALANCE = Decimal("1000000.00")

# (date, txn_number, description, debit, credit)   -- balance is computed
RAW = [
    ("01/05/2024", "B001", "SALARY DEPOSIT",      "0",       "5000000"),
    ("10/05/2024", "B002", "ATM WITHDRAWAL",      "2000000", "0"),
    ("20/05/2024", "B003", "TRANSFER IN",         "0",       "3000000"),
    ("05/06/2024", "B004", "LOAN PAYMENT",        "1500000", "0"),
    ("15/06/2024", "B005", "DEPOSIT CASH",        "0",       "8000000"),
    ("25/06/2024", "B006", "BILL PAYMENT",        "500000",  "0"),
    ("02/07/2024", "B007", "SUPPLIER TRANSFER",   "4000000", "0"),
    ("12/07/2024", "B008", "CUSTOMER PAYMENT FOR INVOICE", "0", "10000000"),  # wrapped in variant
    ("22/07/2024", "B009", "RENT",                "1000000", "0"),
    ("03/08/2024", "B010", "MISC CREDIT",         "0",       "2000000"),
    ("18/08/2024", "B011", "OFFICE EQUIPMENT PURCHASE", "6000000", "0"),      # wrapped in variant
]

# For the wrapped variant: txn_number -> list of continuation description lines
WRAP_CONTINUATIONS = {
    "B008": ["INV-2024-0012", "THANK YOU"],
    "B011": ["MODEL XT-500", "3 YEAR WARRANTY"],
}


def compute_rows():
    """Returns list of dicts with computed running balance."""
    rows = []
    bal = OPENING_BALANCE
    for date, num, desc, debit, credit in RAW:
        d = Decimal(debit)
        c = Decimal(credit)
        bal = bal - d + c
        rows.append({
            "date": date, "num": num, "desc": desc,
            "debit": d, "credit": c, "balance": bal,
        })
    return rows


def fmt(d: Decimal) -> str:
    """Thousands-separated with 2 decimals; empty string for zero debit/credit."""
    return f"{d:,.2f}"


def fmt_amount_cell(d: Decimal) -> str:
    return "" if d == 0 else fmt(d)


HEADER = ["ວັນທີ (Date)", "ເລກທີ (No)", "ລາຍລະອຽດ (Description)",
          "ໜີ້ (Debit)", "ມີ (Credit)", "ຍອດເຫຼືອ (Balance)"]
COL_WIDTHS = [22 * mm, 16 * mm, 60 * mm, 26 * mm, 26 * mm, 30 * mm]


def build_table_data(rows, wrap: bool, corrupt_last: bool):
    data = [HEADER]
    for i, r in enumerate(rows):
        balance = r["balance"]
        if corrupt_last and i == len(rows) - 1:
            balance = balance - Decimal("1")  # deliberate off-by-one
        data.append([
            r["date"], r["num"], r["desc"],
            fmt_amount_cell(r["debit"]), fmt_amount_cell(r["credit"]), fmt(balance),
        ])
        if wrap and r["num"] in WRAP_CONTINUATIONS:
            for cont in WRAP_CONTINUATIONS[r["num"]]:
                data.append(["", "", cont, "", "", ""])
    return data


def render_pdf(path: str, rows, wrap=False, corrupt_last=False):
    styles = getSampleStyleSheet()
    doc = SimpleDocTemplate(path, pagesize=A4,
                            leftMargin=12 * mm, rightMargin=12 * mm,
                            topMargin=15 * mm, bottomMargin=15 * mm)
    story = [
        Paragraph("Bank Statement / ໃບລາຍງານບັນຊີ", styles["Title"]),
        Paragraph(f"Account: 001-234-567  &nbsp;&nbsp; Opening Balance: {fmt(OPENING_BALANCE)}",
                  styles["Normal"]),
        Spacer(1, 6 * mm),
    ]
    data = build_table_data(rows, wrap=wrap, corrupt_last=corrupt_last)
    table = Table(data, colWidths=COL_WIDTHS, repeatRows=1)
    table.setStyle(TableStyle([
        ("GRID", (0, 0), (-1, -1), 0.5, colors.black),
        ("BACKGROUND", (0, 0), (-1, 0), colors.lightgrey),
        ("FONTSIZE", (0, 0), (-1, -1), 8),
        ("ALIGN", (3, 1), (5, -1), "RIGHT"),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
    ]))
    story.append(table)
    doc.build(story)
    print(f"wrote {os.path.relpath(path)}  ({len(data) - 1} physical rows)")


def print_ground_truth(rows):
    """Compute and print expected Table1/Table2/validation values for test assertions."""
    from collections import defaultdict
    by_month = defaultdict(list)
    for r in rows:
        dd, mm_, yyyy = r["date"].split("/")
        by_month[f"{mm_}/{yyyy}"].append(r)

    print("\n=== GROUND TRUTH (hardcode in tests) ===")
    print(f"opening_balance = {OPENING_BALANCE}")
    print(f"total_transactions = {len(rows)}")

    total_debit = sum((r["debit"] for r in rows), Decimal("0"))
    total_credit = sum((r["credit"] for r in rows), Decimal("0"))
    print("\n-- Table1 (chronological) --")
    months_sorted = sorted(by_month, key=lambda k: (int(k[3:]), int(k[:2])))
    for m in months_sorted:
        mr = by_month[m]
        d = sum((x["debit"] for x in mr), Decimal("0"))
        c = sum((x["credit"] for x in mr), Decimal("0"))
        end = mr[-1]["balance"]
        print(f"  {m}: debit={d} credit={c} diff={c-d} endBalance={end}")
    print(f"  TOTAL: debit={total_debit} credit={total_credit} "
          f"diff={total_credit-total_debit} endBalance={rows[-1]['balance']}")

    print("\n-- Table2 (top 3 months by max single credit) --")
    max_credit_by_month = {m: max(x["credit"] for x in by_month[m]) for m in by_month}
    ranked = sorted(months_sorted, key=lambda m: max_credit_by_month[m], reverse=True)[:3]
    for m in ranked:
        mr = by_month[m]
        max_c = max(x["credit"] for x in mr)
        max_d = max(x["debit"] for x in mr)
        print(f"  {m}: debit(max)={max_d} credit(max)={max_c} diff={max_c-max_d}")


# Recurring-payments statement: exercises Table 3 (fixed obligations).
# LOAN 1,500,000 recurs monthly 01-05/2025 (5 consecutive); INSURANCE 500,000 recurs
# 01-04/2025 (4 consecutive). RENT 800,000 appears TWICE in 03/2025 (noise -> 03 excluded
# for 800,000 so it forms no 3+ run). Salary credits keep the balance moving.
RECURRING_RAW = [
    ("05/01/2025", "L01", "LOAN REPAYMENT",  "1500000", "0"),
    ("10/01/2025", "I01", "INSURANCE",       "500000",  "0"),
    ("25/01/2025", "S01", "SALARY",          "0",       "9000000"),
    ("05/02/2025", "L02", "LOAN REPAYMENT",  "1500000", "0"),
    ("10/02/2025", "I02", "INSURANCE",       "500000",  "0"),
    ("25/02/2025", "S02", "SALARY",          "0",       "9000000"),
    ("05/03/2025", "L03", "LOAN REPAYMENT",  "1500000", "0"),
    ("10/03/2025", "I03", "INSURANCE",       "500000",  "0"),
    ("15/03/2025", "R03a", "RENT",           "800000",  "0"),
    ("16/03/2025", "R03b", "RENT",           "800000",  "0"),  # duplicate in March
    ("25/03/2025", "S03", "SALARY",          "0",       "9000000"),
    ("05/04/2025", "L04", "LOAN REPAYMENT",  "1500000", "0"),
    ("10/04/2025", "I04", "INSURANCE",       "500000",  "0"),
    ("25/04/2025", "S04", "SALARY",          "0",       "9000000"),
    ("05/05/2025", "L05", "LOAN REPAYMENT",  "1500000", "0"),
    ("25/05/2025", "S05", "SALARY",          "0",       "9000000"),
]


def compute_rows_from(raw):
    rows = []
    bal = OPENING_BALANCE
    for date, num, desc, debit, credit in raw:
        d, c = Decimal(debit), Decimal(credit)
        bal = bal - d + c
        rows.append({"date": date, "num": num, "desc": desc, "debit": d, "credit": c, "balance": bal})
    return rows


def main():
    os.makedirs(FIXTURES_DIR, exist_ok=True)
    rows = compute_rows()
    render_pdf(os.path.join(FIXTURES_DIR, "sample_statement.pdf"), rows)
    render_pdf(os.path.join(FIXTURES_DIR, "sample_statement_wrapped_desc.pdf"), rows, wrap=True)
    render_pdf(os.path.join(FIXTURES_DIR, "sample_statement_mismatch.pdf"), rows, corrupt_last=True)
    print_ground_truth(rows)

    recurring = compute_rows_from(RECURRING_RAW)
    render_pdf(os.path.join(FIXTURES_DIR, "sample_statement_recurring.pdf"), recurring)
    print("\n=== RECURRING fixture: expected Table 3 ===")
    print("  LOAN 1,500,000 -> 5 consecutive months (01-05/2025)")
    print("  INSURANCE 500,000 -> 4 consecutive months (01-04/2025)")
    print("  RENT 800,000 -> excluded (duplicate in 03/2025), no 3+ run")


if __name__ == "__main__":
    main()
