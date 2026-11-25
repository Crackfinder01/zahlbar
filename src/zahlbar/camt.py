"""Read incoming payments from ISO 20022 bank files (camt.053 statements and camt.054 notifications).

Privacy by design: only what is needed to match a payment is extracted
(reference, amount, currency, dates, bank reference). Payer names, addresses
and IBANs are ignored and never stored.
"""
from __future__ import annotations

import hashlib
import xml.etree.ElementTree as ET
from dataclasses import dataclass, asdict
from decimal import Decimal, InvalidOperation
from typing import Iterator

from .references import normalize_reference

__all__ = ["CamtError", "Credit", "parse_camt", "MAX_FILE_BYTES"]

MAX_FILE_BYTES = 10 * 1024 * 1024  # 10 MB is far above a normal daily file


class CamtError(ValueError):
    """The file is not a readable camt.053/054 document."""


@dataclass(frozen=True)
class Credit:
    """One incoming payment."""

    entry_key: str  # stable id used to avoid counting the same payment twice
    reference: str | None
    amount: Decimal
    currency: str
    booking_date: str | None
    bank_reference: str | None

    def as_dict(self) -> dict:
        data = asdict(self)
        data["amount"] = str(self.amount)
        return data


def _local(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


def _child(element: ET.Element | None, *path: str) -> ET.Element | None:
    """Namespace-agnostic child lookup following ``path``."""
    current = element
    for name in path:
        if current is None:
            return None
        current = next((c for c in current if _local(c.tag) == name), None)
    return current


def _children(element: ET.Element | None, name: str) -> list[ET.Element]:
    if element is None:
        return []
    return [c for c in element if _local(c.tag) == name]


def _text(element: ET.Element | None, *path: str) -> str | None:
    node = _child(element, *path)
    if node is None or node.text is None:
        return None
    value = node.text.strip()
    return value or None


def _amount(element: ET.Element | None) -> tuple[Decimal, str] | None:
    node = _child(element, "Amt")
    if node is None or not node.text:
        return None
    try:
        return Decimal(node.text.strip()), node.attrib.get("Ccy", "")
    except InvalidOperation:
        return None


def _status(entry: ET.Element) -> str | None:
    # camt v4: <Sts>BOOK</Sts> ; camt v8: <Sts><Cd>BOOK</Cd></Sts>
    return _text(entry, "Sts", "Cd") or _text(entry, "Sts")


def _date(element: ET.Element | None, name: str) -> str | None:
    return _text(element, name, "Dt") or (_text(element, name, "DtTm") or "")[:10] or None


def parse_camt(data: bytes | str) -> list[Credit]:
    """Return booked incoming payments (credits) found in a camt.053/054 file."""
    raw = data.encode("utf-8") if isinstance(data, str) else data
    if len(raw) > MAX_FILE_BYTES:
        raise CamtError("File too large (max 10 MB)")
    if b"<!DOCTYPE" in raw[:2048].upper() or b"<!ENTITY" in raw.upper():
        raise CamtError("DOCTYPE/ENTITY declarations are not allowed")
    try:
        root = ET.fromstring(raw)
    except ET.ParseError as exc:
        raise CamtError(f"Not valid XML: {exc}") from exc

    message = next(iter(root), None)
    if message is None or _local(message.tag) not in {"BkToCstmrDbtCdtNtfctn", "BkToCstmrStmt"}:
        raise CamtError("Not a camt.053 or camt.054 document")

    credits: list[Credit] = []
    for report in list(message):
        if _local(report.tag) not in {"Ntfctn", "Stmt"}:
            continue
        for entry in _children(report, "Ntry"):
            credits.extend(_entry_credits(entry))
    return credits


def _entry_credits(entry: ET.Element) -> Iterator[Credit]:
    if _text(entry, "CdtDbtInd") != "CRDT":
        return
    status = _status(entry)
    if status and status != "BOOK":
        return
    booking_date = _date(entry, "BookgDt") or _date(entry, "ValDt")
    entry_ref = _text(entry, "AcctSvcrRef")
    entry_amount = _amount(entry)

    transactions = [tx for details in _children(entry, "NtryDtls") for tx in _children(details, "TxDtls")]
    if not transactions and entry_amount:
        transactions = [entry]  # entry without details: use the entry itself

    for index, tx in enumerate(transactions):
        indicator = _text(tx, "CdtDbtInd")
        if indicator and indicator != "CRDT":
            continue
        amount = _amount(tx) or (_amount(_child(tx, "AmtDtls", "TxAmt")) if tx is not entry else None)
        if amount is None and len(transactions) == 1:
            amount = entry_amount
        if amount is None:
            continue
        value, currency = amount
        reference = normalize_reference(_text(tx, "RmtInf", "Strd", "CdtrRefInf", "Ref"))
        bank_ref = _text(tx, "Refs", "AcctSvcrRef") or entry_ref
        key_source = "|".join([bank_ref or "", entry_ref or "", str(index), reference or "", str(value), currency, booking_date or ""])
        yield Credit(
            entry_key=hashlib.sha256(key_source.encode("utf-8")).hexdigest()[:32],
            reference=reference,
            amount=value,
            currency=currency,
            booking_date=booking_date,
            bank_reference=bank_ref,
        )
