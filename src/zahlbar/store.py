"""SQLite storage for tracked invoices and imported payments.

Only the minimum is stored: invoice number, amount, reference, due date and
status. The debtor is optional and can be deleted with the invoice.
"""
from __future__ import annotations

import json
import sqlite3
import threading
import uuid
from contextlib import contextmanager
from datetime import date, datetime, timezone
from decimal import Decimal
from pathlib import Path
from typing import Any, Iterator

__all__ = ["Store", "StoreError"]

SCHEMA = """
CREATE TABLE IF NOT EXISTS invoices (
    id TEXT PRIMARY KEY,
    number TEXT NOT NULL,
    reference TEXT NOT NULL UNIQUE,
    reference_type TEXT NOT NULL,
    amount TEXT NOT NULL,
    currency TEXT NOT NULL,
    account TEXT NOT NULL,
    creditor_json TEXT NOT NULL,
    debtor_json TEXT,
    message TEXT NOT NULL DEFAULT '',
    language TEXT NOT NULL DEFAULT 'en',
    due_date TEXT,
    paid_amount TEXT NOT NULL DEFAULT '0.00',
    status TEXT NOT NULL DEFAULT 'open',
    paid_at TEXT,
    created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS payments (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    entry_key TEXT NOT NULL UNIQUE,
    invoice_id TEXT REFERENCES invoices(id) ON DELETE SET NULL,
    reference TEXT,
    amount TEXT NOT NULL,
    currency TEXT NOT NULL,
    booking_date TEXT,
    bank_reference TEXT,
    imported_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_payments_reference ON payments(reference);
"""


class StoreError(ValueError):
    pass


def _now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


class Store:
    def __init__(self, path: str | Path):
        self.path = str(path)
        if self.path != ":memory:":
            Path(self.path).parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()
        with self._connect() as conn:
            conn.executescript(SCHEMA)

    @contextmanager
    def _connect(self) -> Iterator[sqlite3.Connection]:
        with self._lock:
            conn = sqlite3.connect(self.path)
            conn.row_factory = sqlite3.Row
            conn.execute("PRAGMA foreign_keys = ON")
            try:
                yield conn
                conn.commit()
            except Exception:
                conn.rollback()
                raise
            finally:
                conn.close()

    # ---- invoices -------------------------------------------------------
    def add_invoice(self, *, number: str, reference: str, reference_type: str, amount: Decimal,
                    currency: str, account: str, creditor: dict, debtor: dict | None,
                    message: str, language: str, due_date: date | None) -> dict[str, Any]:
        invoice_id = uuid.uuid4().hex[:12]
        try:
            with self._connect() as conn:
                conn.execute(
                    "INSERT INTO invoices (id, number, reference, reference_type, amount, currency, account,"
                    " creditor_json, debtor_json, message, language, due_date, created_at)"
                    " VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)",
                    (invoice_id, number, reference, reference_type, str(amount), currency, account,
                     json.dumps(creditor, ensure_ascii=False),
                     json.dumps(debtor, ensure_ascii=False) if debtor else None,
                     message, language, due_date.isoformat() if due_date else None, _now()),
                )
        except sqlite3.IntegrityError as exc:
            raise StoreError(f"An invoice with reference {reference} already exists") from exc
        invoice = self.get_invoice(invoice_id)
        assert invoice is not None
        return invoice

    def get_invoice(self, invoice_id: str) -> dict[str, Any] | None:
        with self._connect() as conn:
            row = conn.execute("SELECT * FROM invoices WHERE id = ?", (invoice_id,)).fetchone()
        return self._invoice(row) if row else None

    def find_by_reference(self, reference: str) -> dict[str, Any] | None:
        with self._connect() as conn:
            row = conn.execute("SELECT * FROM invoices WHERE reference = ?", (reference,)).fetchone()
        return self._invoice(row) if row else None

    def list_invoices(self, status: str | None = None, today: date | None = None) -> list[dict[str, Any]]:
        today = today or date.today()
        with self._connect() as conn:
            rows = conn.execute("SELECT * FROM invoices ORDER BY created_at, number").fetchall()
        invoices = [self._invoice(row, today) for row in rows]
        if status is None or status == "all":
            return invoices
        if status == "overdue":
            return [i for i in invoices if i["overdue"]]
        if status == "unpaid":
            return [i for i in invoices if i["status"] in ("open", "partial")]
        return [i for i in invoices if i["status"] == status]

    def delete_invoice(self, invoice_id: str) -> bool:
        with self._connect() as conn:
            cur = conn.execute("DELETE FROM invoices WHERE id = ?", (invoice_id,))
        return cur.rowcount > 0

    # ---- payments -------------------------------------------------------
    def payment_exists(self, entry_key: str) -> bool:
        with self._connect() as conn:
            return conn.execute("SELECT 1 FROM payments WHERE entry_key = ?", (entry_key,)).fetchone() is not None

    def record_payment(self, *, entry_key: str, invoice_id: str | None, reference: str | None,
                       amount: Decimal, currency: str, booking_date: str | None,
                       bank_reference: str | None) -> None:
        with self._connect() as conn:
            conn.execute(
                "INSERT INTO payments (entry_key, invoice_id, reference, amount, currency, booking_date,"
                " bank_reference, imported_at) VALUES (?,?,?,?,?,?,?,?)",
                (entry_key, invoice_id, reference, str(amount), currency, booking_date, bank_reference, _now()),
            )
            if invoice_id:
                row = conn.execute("SELECT amount, paid_amount FROM invoices WHERE id = ?", (invoice_id,)).fetchone()
                paid = Decimal(row["paid_amount"]) + amount
                status = "paid" if paid >= Decimal(row["amount"]) else "partial"
                conn.execute(
                    "UPDATE invoices SET paid_amount = ?, status = ?, paid_at = ? WHERE id = ?",
                    (str(paid.quantize(Decimal("0.01"))), status,
                     booking_date if status == "paid" else None, invoice_id),
                )

    def unmatched_payments(self) -> list[dict[str, Any]]:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT reference, amount, currency, booking_date, bank_reference FROM payments"
                " WHERE invoice_id IS NULL ORDER BY booking_date, id"
            ).fetchall()
        return [dict(row) for row in rows]

    # ---- helpers --------------------------------------------------------
    @staticmethod
    def _invoice(row: sqlite3.Row, today: date | None = None) -> dict[str, Any]:
        today = today or date.today()
        data = dict(row)
        data["creditor"] = json.loads(data.pop("creditor_json"))
        debtor = data.pop("debtor_json")
        data["debtor"] = json.loads(debtor) if debtor else None
        due = data.get("due_date")
        data["overdue"] = bool(due and data["status"] != "paid" and date.fromisoformat(due) < today)
        data["open_amount"] = str(max(Decimal(data["amount"]) - Decimal(data["paid_amount"]), Decimal("0")).quantize(Decimal("0.01")))
        return data
