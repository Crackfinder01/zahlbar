"""MCP server so AI assistants (Claude, ChatGPT, Cursor, ...) can use Zahlbar.

Local use (Claude Code, Claude Desktop, Cursor):  ``zahlbar mcp``  (stdio)
Remote use:  ``zahlbar mcp --http``  (streamable HTTP, put it behind HTTPS + auth)
"""
from __future__ import annotations

import base64
from pathlib import Path
from typing import Literal, Optional

from mcp.server.mcpserver import MCPServer

from .bills import bill_summary, build_bill, render_pdf, render_svg, validate_bill
from .references import qrr_from_number, scor_from_number
from .service import Zahlbar

INSTRUCTIONS = (
    "Zahlbar creates Swiss QR-bills and tracks who paid. Typical flow: create_invoice -> "
    "get_invoice_bill (pdf) -> after the bank file arrives, reconcile_bank_file -> list_invoices(status='overdue'). "
    "Addresses must be structured (street, house number, postal code, city, country). Amounts use a dot, e.g. 120.50."
)

server = MCPServer(name="zahlbar", instructions=INSTRUCTIONS)
_service: Zahlbar | None = None


def _svc() -> Zahlbar:
    global _service
    if _service is None:
        _service = Zahlbar()
    return _service


def set_service(service: Zahlbar) -> None:
    """Inject a service (used by tests)."""
    global _service
    _service = service


@server.tool(description="Check QR-bill data and return the list of problems (empty = valid).")
def validate_qr_bill(bill: dict) -> dict:
    errors = validate_bill(bill)
    return {"valid": not errors, "errors": errors}


@server.tool(description="Create a QR reference from an invoice number: kind 'qrr' (QR-IBAN) or 'scor' (normal IBAN, RF...).")
def create_reference(kind: Literal["qrr", "scor"], number: str, prefix: str = "") -> dict:
    ref = qrr_from_number(number, prefix) if kind == "qrr" else scor_from_number(number)
    return {"reference": ref, "type": kind.upper()}


@server.tool(description="Render a one-off QR-bill. format: 'json' (QR payload), 'svg' or 'pdf'. "
                         "With output_path the file is written there; otherwise svg is returned as text and pdf as base64.")
def render_qr_bill(bill: dict, format: Literal["json", "svg", "pdf"] = "json", output_path: Optional[str] = None) -> dict:
    qr = build_bill(bill)
    return _output(qr, format, output_path)


@server.tool(description="Create a tracked invoice. The QR reference is generated automatically. "
                         "Uses the configured creditor unless account/creditor are given. due_date: YYYY-MM-DD.")
def create_invoice(number: str, amount: str, currency: Literal["CHF", "EUR"] = "CHF", due_date: Optional[str] = None,
                   message: str = "", language: Literal["en", "de", "fr", "it"] = "en",
                   debtor: Optional[dict] = None, account: Optional[str] = None, creditor: Optional[dict] = None) -> dict:
    payload = {"number": number, "amount": amount, "currency": currency, "due_date": due_date, "message": message,
               "language": language, "debtor": debtor, "account": account, "creditor": creditor}
    return _svc().create_invoice({k: v for k, v in payload.items() if v not in (None, "")})


@server.tool(description="List invoices. status: all, open, partial, paid, unpaid or overdue.")
def list_invoices(status: Literal["all", "open", "partial", "paid", "unpaid", "overdue"] = "unpaid") -> list[dict]:
    return _svc().store.list_invoices(status)


@server.tool(description="Get the QR-bill of a tracked invoice as 'pdf', 'svg' or 'json'. Use output_path to save the file.")
def get_invoice_bill(invoice_id: str, format: Literal["json", "svg", "pdf"] = "pdf", output_path: Optional[str] = None) -> dict:
    qr = _svc().bill_for_invoice(invoice_id)
    if qr is None:
        return {"error": "invoice not found"}
    return _output(qr, format, output_path)


@server.tool(description="Import a camt.054 or camt.053 bank file (path on disk or raw XML) and mark paid invoices. Safe to repeat.")
def reconcile_bank_file(path: Optional[str] = None, xml: Optional[str] = None) -> dict:
    if not path and not xml:
        return {"error": "give either path or xml"}
    data = Path(path).read_bytes() if path else xml.encode("utf-8")  # type: ignore[union-attr]
    return _svc().reconcile(data)


@server.tool(description="Payments received that could not be linked to an invoice.")
def list_unmatched_payments() -> list[dict]:
    return _svc().store.unmatched_payments()


def _output(qr, fmt: str, output_path: Optional[str]) -> dict:
    if fmt == "json":
        return bill_summary(qr)
    content = render_pdf(qr) if fmt == "pdf" else render_svg(qr).encode("utf-8")
    if output_path:
        Path(output_path).write_bytes(content)
        return {"written": output_path, "bytes": len(content)}
    if fmt == "svg":
        return {"svg": content.decode("utf-8")}
    return {"pdf_base64": base64.b64encode(content).decode("ascii")}


def main(http: bool = False, host: str = "127.0.0.1", port: int = 8090) -> None:
    if http:
        server.run("streamable-http", host=host, port=port)
    else:
        server.run("stdio")


if __name__ == "__main__":  # pragma: no cover
    main()
