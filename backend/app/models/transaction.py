"""The single transaction shape used across extraction, validation, tables, JSON, and docx."""
from __future__ import annotations

from decimal import Decimal

from pydantic import BaseModel, Field


class TransactionRow(BaseModel):
    date: str          # "DD/MM/YYYY" as printed, preserved verbatim for report fidelity
    txn_number: str    # receipt / bill number (Lao: ເລກບີນ)
    description: str
    debit: Decimal     # Lao: ໜີ້ (paid out)
    credit: Decimal    # Lao: ມີ (received)
    balance: Decimal   # running balance printed on that row (Lao: ຍອດຄົງເຫຼືອ)
    # Fields the OCR read with low confidence (e.g. ["balance"]); empty for digital
    # rows. Surfaced in the review UI so the reviewer knows which cells to double-check.
    low_conf: list[str] = Field(default_factory=list)

    def to_json_dict(self) -> dict:
        """Storage/JSON form: amounts as 2dp floats (see utils.money.to_storage_number)."""
        from app.utils.money import to_storage_number
        return {
            "date": self.date,
            "txnNumber": self.txn_number,
            "description": self.description,
            "debit": to_storage_number(self.debit),
            "credit": to_storage_number(self.credit),
            "balance": to_storage_number(self.balance),
            "lowConf": self.low_conf,
        }

    @classmethod
    def from_json_dict(cls, d: dict) -> "TransactionRow":
        return cls(
            date=d["date"],
            txn_number=d.get("txnNumber", ""),
            description=d.get("description", ""),
            debit=Decimal(str(d.get("debit", 0))),
            credit=Decimal(str(d.get("credit", 0))),
            balance=Decimal(str(d.get("balance", 0))),
            low_conf=list(d.get("lowConf", [])),
        )
