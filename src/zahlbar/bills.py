"""Create, validate and render Swiss QR-bills (built on the MIT ``qrbill`` library)."""
from __future__ import annotations

import io
import warnings
from typing import Any

from pydantic import ValidationError
from qrbill import QRBill

from .models import BillRequest

__all__ = ["BillError", "build_bill", "validate_bill", "render_svg", "render_pdf", "bill_summary"]


class BillError(ValueError):
    """The bill data is not valid. ``errors`` holds human readable messages."""

    def __init__(self, errors: list[str]):
        super().__init__("; ".join(errors))
        self.errors = errors


def _address_dict(address) -> dict[str, Any] | None:
    if address is None:
        return None
    data = address.model_dump()
    return {k: v for k, v in data.items() if v not in (None, "")}


def build_bill(request: BillRequest | dict) -> QRBill:
    """Return a ``qrbill.QRBill`` or raise :class:`BillError`."""
    try:
        req = request if isinstance(request, BillRequest) else BillRequest.model_validate(request)
    except ValidationError as exc:
        raise BillError([_format_pydantic_error(e) for e in exc.errors()]) from exc
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            return QRBill(
                account=req.account.replace(" ", ""),
                creditor=_address_dict(req.creditor),
                amount=str(req.amount) if req.amount is not None else None,
                currency=req.currency,
                debtor=_address_dict(req.debtor),
                reference_number=req.reference.replace(" ", "") if req.reference else None,
                additional_information=req.message,
                language=req.language,
            )
    except ValueError as exc:
        raise BillError([str(exc)]) from exc


def validate_bill(request: dict) -> list[str]:
    """Return a list of problems (empty list = the bill is valid)."""
    try:
        build_bill(request)
    except BillError as exc:
        return exc.errors
    return []


def render_svg(bill: QRBill, full_page: bool = False) -> str:
    """Return the payment part (or a full A4 page) as an SVG string."""
    buffer = io.StringIO()
    bill.as_svg(buffer, full_page=full_page)
    return buffer.getvalue()


def render_pdf(bill: QRBill) -> bytes:
    """Return an A4 PDF page with the payment part at the bottom."""
    from reportlab.graphics import renderPDF
    from svglib.svglib import svg2rlg

    drawing = svg2rlg(io.BytesIO(render_svg(bill, full_page=True).encode("utf-8")))
    if drawing is None:  # pragma: no cover - svglib failure
        raise BillError(["Could not convert the QR-bill to PDF"])
    return renderPDF.drawToString(drawing)


def bill_summary(bill: QRBill) -> dict[str, Any]:
    """Machine friendly description of a bill (no image)."""
    return {
        "account": bill.account,
        "account_is_qr_iban": bill.account_is_qriban,
        "amount": bill.amount,
        "currency": bill.currency,
        "reference_type": bill.ref_type,
        "reference": bill.reference_number,
        "qr_payload": bill.qr_data(),
    }


def _format_pydantic_error(error: dict) -> str:
    location = ".".join(str(part) for part in error.get("loc", ()))
    return f"{location}: {error.get('msg')}" if location else str(error.get("msg"))
