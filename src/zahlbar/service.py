"""High level operations used by the API, the CLI and the MCP server."""
from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

from .bills import BillError, build_bill
from .camt import parse_camt
from .models import Address, BillRequest, InvoiceCreate
from .references import qrr_from_number, reference_type, scor_from_number, normalize_reference
from .store import Store

__all__ = ["Zahlbar", "default_db_path", "load_creditor_config", "config_path"]


def default_db_path() -> Path:
    env = os.environ.get("ZAHLBAR_DB")
    if env:
        return Path(env)
    return Path(os.environ.get("XDG_DATA_HOME", Path.home() / ".local" / "share")) / "zahlbar" / "zahlbar.sqlite3"


def config_path() -> Path:
    env = os.environ.get("ZAHLBAR_CONFIG")
    if env:
        return Path(env)
    return Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config")) / "zahlbar" / "config.json"


def load_creditor_config() -> dict[str, Any]:
    """Default creditor (name, address, account) from env vars or the config file.

    Env vars win: ZAHLBAR_ACCOUNT, ZAHLBAR_CREDITOR_NAME, ZAHLBAR_CREDITOR_STREET,
    ZAHLBAR_CREDITOR_HOUSE_NUM, ZAHLBAR_CREDITOR_PCODE, ZAHLBAR_CREDITOR_CITY,
    ZAHLBAR_CREDITOR_COUNTRY.
    """
    data: dict[str, Any] = {}
    path = config_path()
    if path.exists():
        data = json.loads(path.read_text(encoding="utf-8"))
    creditor = dict(data.get("creditor") or {})
    for field in ("name", "street", "house_num", "pcode", "city", "country"):
        value = os.environ.get(f"ZAHLBAR_CREDITOR_{field.upper()}")
        if value:
            creditor[field] = value
    account = os.environ.get("ZAHLBAR_ACCOUNT") or data.get("account")
    return {"account": account, "creditor": creditor or None}


class Zahlbar:
    """Facade over the store and the bill builder."""

    def __init__(self, store: Store | None = None):
        self.store = store or Store(default_db_path())

    # ---- invoices ---------------------------------------------------------
    def create_invoice(self, payload: InvoiceCreate | dict) -> dict[str, Any]:
        data = payload if isinstance(payload, InvoiceCreate) else InvoiceCreate.model_validate(payload)
        defaults = load_creditor_config()
        account = (data.account or defaults["account"] or "").replace(" ", "")
        creditor = data.creditor or (Address.model_validate(defaults["creditor"]) if defaults["creditor"] else None)
        if not account or creditor is None:
            raise BillError(["No creditor configured: pass account and creditor, or run `zahlbar config set-creditor`"])

        reference = normalize_reference(data.reference)
        if reference:
            ref_type = reference_type(reference)
        else:
            # A QR-IBAN needs a QRR reference, a normal IBAN gets an RF reference.
            if _is_qr_iban(account):
                reference = qrr_from_number(data.number, data.reference_prefix)
            else:
                reference = scor_from_number(data.number)
            ref_type = reference_type(reference)

        bill_request = BillRequest(
            account=account, creditor=creditor, amount=data.amount, currency=data.currency,
            debtor=data.debtor, reference=reference, message=data.message, language=data.language,
        )
        build_bill(bill_request)  # raises BillError when something is wrong
        return self.store.add_invoice(
            number=data.number, reference=reference, reference_type=ref_type, amount=data.amount,
            currency=data.currency, account=account, creditor=creditor.model_dump(exclude_none=True),
            debtor=data.debtor.model_dump(exclude_none=True) if data.debtor else None,
            message=data.message, language=data.language, due_date=data.due_date,
        )

    def bill_for_invoice(self, invoice_id: str):
        invoice = self.store.get_invoice(invoice_id)
        if invoice is None:
            return None
        return build_bill({
            "account": invoice["account"], "creditor": invoice["creditor"], "amount": invoice["amount"],
            "currency": invoice["currency"], "debtor": invoice["debtor"], "reference": invoice["reference"],
            "message": invoice["message"], "language": invoice["language"],
        })

    # ---- reconciliation ---------------------------------------------------
    def reconcile(self, camt_file: bytes | str) -> dict[str, Any]:
        """Import a camt.053/054 file and match payments to invoices (idempotent)."""
        summary: dict[str, Any] = {"credits": 0, "matched": [], "partial": [], "unmatched": [], "duplicates": 0}
        for credit in parse_camt(camt_file):
            summary["credits"] += 1
            if self.store.payment_exists(credit.entry_key):
                summary["duplicates"] += 1
                continue
            invoice = self.store.find_by_reference(credit.reference) if credit.reference else None
            if invoice and invoice["currency"] != credit.currency:
                invoice = None  # never mix currencies
            self.store.record_payment(
                entry_key=credit.entry_key, invoice_id=invoice["id"] if invoice else None,
                reference=credit.reference, amount=credit.amount, currency=credit.currency,
                booking_date=credit.booking_date, bank_reference=credit.bank_reference,
            )
            if invoice is None:
                summary["unmatched"].append(credit.as_dict())
                continue
            updated = self.store.get_invoice(invoice["id"])
            item = {"invoice_id": updated["id"], "number": updated["number"], "paid": str(credit.amount),
                    "open_amount": updated["open_amount"], "status": updated["status"]}
            (summary["matched"] if updated["status"] == "paid" else summary["partial"]).append(item)
        return summary


def _is_qr_iban(account: str) -> bool:
    # QR-IBAN: institution id (positions 5-9) between 30000 and 31999
    compact = account.replace(" ", "").upper()
    try:
        iid = int(compact[4:9])
    except ValueError:
        return False
    return 30000 <= iid <= 31999
