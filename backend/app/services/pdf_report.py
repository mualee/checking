"""Generate the Lao-language statement report as a PDF (reportlab), in memory.

Mirrors the tables/sections of docx_report but renders straight to PDF so no Word
install or docx->pdf conversion is needed. Lao text needs a Unicode TTF with Lao
glyphs; we bundle Phetsarath OT and register it with reportlab (the same face is
used for the bold slot — Phetsarath ships a single weight, and emphasis comes from
the header/total row shading, as in the Word report).
"""
from __future__ import annotations

import io
import sys
from decimal import Decimal
from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

from app.core.constants import TOTAL_LABEL
from app.services.calculations import Table1Row, Table2Row, Table3Group, ValidationResult
from app.utils.money import format_lao_amount

FONT_NAME = "Phetsarath"
_FONT_FILE = "PhetsarathOT.ttf"
HEADER_FILL = colors.HexColor("#D9D9D9")   # light gray, matches the Word report
TOTAL_FILL = colors.HexColor("#FFF2CC")    # light amber

TABLE1_HEADERS = ["ເດືອນ", "ໜີ້", "ມີ", "ສ່ວນຕ່າງ", "ຍອດເຫຼືອທ້າຍເດືອນ"]
TABLE2_HEADERS = ["ເດືອນ", "ໜີ້", "ມີ", "ສ່ວນຕ່າງ"]
TABLE3_HEADERS = ["ເດືອນ", "ເລກທີ", "ໜີ້", "ລາຍລະອຽດ"]

_FONT_READY = False


def _font_path() -> Path:
    """Locate the bundled TTF in dev (package tree) and in the PyInstaller bundle."""
    here = Path(__file__).resolve().parent            # app/services
    candidate = here.parent / "assets" / "fonts" / _FONT_FILE
    if candidate.exists():
        return candidate
    base = Path(getattr(sys, "_MEIPASS", here.parent.parent))  # PyInstaller _internal
    return base / "app" / "assets" / "fonts" / _FONT_FILE


def _ensure_font() -> None:
    global _FONT_READY
    if _FONT_READY:
        return
    pdfmetrics.registerFont(TTFont(FONT_NAME, str(_font_path())))
    # Register the same face for the bold/italic slots so <b> tags never fall back.
    pdfmetrics.registerFontFamily(FONT_NAME, normal=FONT_NAME, bold=FONT_NAME,
                                  italic=FONT_NAME, boldItalic=FONT_NAME)
    _FONT_READY = True


def _style(size: int, *, align=TA_LEFT, leading: float | None = None) -> ParagraphStyle:
    return ParagraphStyle(
        f"lao{size}{align}", fontName=FONT_NAME, fontSize=size,
        leading=leading or size * 1.35, alignment=align,
    )


def _amt(d: Decimal) -> str:
    return format_lao_amount(d)


def _cell(text: str, size: int = 9, align=TA_LEFT) -> Paragraph:
    return Paragraph(text or "", _style(size, align=align))


def _grid_style(extra: list | None = None) -> TableStyle:
    cmds = [
        ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#7F7F7F")),
        ("BACKGROUND", (0, 0), (-1, 0), HEADER_FILL),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING", (0, 0), (-1, -1), 3),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
        ("LEFTPADDING", (0, 0), (-1, -1), 4),
        ("RIGHTPADDING", (0, 0), (-1, -1), 4),
    ]
    return TableStyle(cmds + (extra or []))


def _table1(table1: list[Table1Row]) -> Table:
    header = [_cell(h, align=TA_CENTER) for h in TABLE1_HEADERS]
    rows = [header]
    total_idx: list[int] = []
    for r in table1:
        is_total = r.month == TOTAL_LABEL
        if is_total:
            total_idx.append(len(rows))
        rows.append([
            _cell(r.month),
            _cell(_amt(r.debit), align=TA_RIGHT),
            _cell(_amt(r.credit), align=TA_RIGHT),
            _cell(_amt(r.diff), align=TA_RIGHT),
            _cell(_amt(r.end_balance), align=TA_RIGHT),
        ])
    extra = [("BACKGROUND", (0, i), (-1, i), TOTAL_FILL) for i in total_idx]
    t = Table(rows, colWidths=[28 * mm, 33 * mm, 33 * mm, 30 * mm, 38 * mm], repeatRows=1)
    t.setStyle(_grid_style(extra))
    return t


def _table2(table2: list[Table2Row]) -> Table:
    rows = [[_cell(h, align=TA_CENTER) for h in TABLE2_HEADERS]]
    for r in table2:
        rows.append([
            _cell(r.month),
            _cell(_amt(r.debit), align=TA_RIGHT),
            _cell(_amt(r.credit), align=TA_RIGHT),
            _cell(_amt(r.diff), align=TA_RIGHT),
        ])
    t = Table(rows, colWidths=[35 * mm, 42 * mm, 42 * mm, 38 * mm], repeatRows=1)
    t.setStyle(_grid_style())
    return t


def _table3_group(g: Table3Group) -> Table:
    rows = [[_cell(h, align=TA_CENTER) for h in TABLE3_HEADERS]]
    for r in g.rows:
        rows.append([
            _cell(r.month),
            _cell(r.txn_number),
            _cell(_amt(r.debit), align=TA_RIGHT),
            _cell(r.description),
        ])
    t = Table(rows, colWidths=[24 * mm, 28 * mm, 30 * mm, 75 * mm], repeatRows=1)
    t.setStyle(_grid_style())
    return t


def generate_statement_report_pdf(
    *,
    customer_name: str,
    account_no: str,
    period: str,
    table1: list[Table1Row],
    table2: list[Table2Row],
    table3: list[Table3Group] | None = None,
    validation: ValidationResult | None = None,
) -> bytes:
    """Build the report PDF entirely in memory and return raw bytes."""
    _ensure_font()
    buf = io.BytesIO()
    doc = SimpleDocTemplate(
        buf, pagesize=A4,
        leftMargin=15 * mm, rightMargin=15 * mm, topMargin=15 * mm, bottomMargin=15 * mm,
        title="ບົດລາຍງານການກວດສອບ Statement",
    )
    flow: list = [
        Paragraph("ບົດລາຍງານການກວດສອບ Statement", _style(16, align=TA_CENTER)),
        Spacer(1, 6 * mm),
        Paragraph(f"ລູກຄ້າ: {customer_name}", _style(11)),
        Paragraph(f"ເລກບັນຊີ: {account_no}", _style(11)),
        Paragraph(f"ໄລຍະ: {period}", _style(11)),
        Spacer(1, 4 * mm),
        Paragraph("ຕາຕະລາງ 1: ສະຫຼຸບຕໍ່ເດືອນ", _style(13)),
        Spacer(1, 2 * mm),
        _table1(table1),
        Spacer(1, 5 * mm),
        Paragraph("ຕາຕະລາງ 2: 3 ເດືອນທຸລະກຳຮັບສູງສຸດ", _style(13)),
        Spacer(1, 2 * mm),
        _table2(table2),
        Spacer(1, 5 * mm),
        Paragraph("ຕາຕະລາງ 3: ລາຍຈ່າຍປະຈຳ (ຕິດຕໍ່ກັນ 3 ເດືອນຂຶ້ນໄປ)", _style(13)),
        Spacer(1, 2 * mm),
    ]

    groups = table3 or []
    if not groups:
        flow.append(Paragraph("— ບໍ່ພົບລາຍຈ່າຍປະຈຳທີ່ຕິດຕໍ່ກັນ —", _style(10)))
    else:
        for g in groups:
            flow.append(Paragraph(
                f"ຈຳນວນ {_amt(g.amount)} — ຕິດຕໍ່ກັນ {g.month_count} ເດືອນ", _style(11)))
            flow.append(Spacer(1, 1.5 * mm))
            flow.append(_table3_group(g))
            flow.append(Spacer(1, 3 * mm))

    if validation is not None:
        status = "ຖືກຕ້ອງ (matched)" if validation.matched else \
                 f"ພົບຄວາມຄາດເຄື່ອນ {validation.mismatch_count} ແຖວ"
        flow.append(Spacer(1, 4 * mm))
        flow.append(Paragraph(f"ຜົນກວດສອບຄວາມຖືກຕ້ອງ: {status}", _style(11)))

    doc.build(flow)
    return buf.getvalue()
