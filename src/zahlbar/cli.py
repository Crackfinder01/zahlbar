"""Command line interface - short commands, JSON output, made for humans *and* AI agents.

Local mode (default): works on the local SQLite database (``ZAHLBAR_DB``).
Remote mode: set ``ZAHLBAR_API_URL`` (and ``ZAHLBAR_API_KEY``) to talk to a Zahlbar server.
The API key is read from the environment so it never has to appear in a prompt.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any

from . import __version__
from .bills import BillError, bill_summary, build_bill, render_pdf, render_svg
from .camt import CamtError
from .references import ReferenceError_, qrr_from_number, scor_from_number
from .service import Zahlbar, _is_qr_iban, config_path
from .store import StoreError


def _print(data: Any) -> None:
    print(json.dumps(data, indent=2, ensure_ascii=False, default=str))


def _address(args: argparse.Namespace, prefix: str) -> dict | None:
    fields = ("name", "street", "house_num", "pcode", "city", "country")
    values = {f: getattr(args, f"{prefix}_{f}", None) for f in fields}
    if not any(values.values()):
        return None
    return {k: v for k, v in values.items() if v}


def _add_address_args(parser: argparse.ArgumentParser, prefix: str, required: bool = False) -> None:
    group = parser.add_argument_group(f"{prefix} address (structured)")
    group.add_argument(f"--{prefix}-name", required=required)
    group.add_argument(f"--{prefix}-street")
    group.add_argument(f"--{prefix}-house-num", dest=f"{prefix}_house_num")
    group.add_argument(f"--{prefix}-pcode", required=required)
    group.add_argument(f"--{prefix}-city", required=required)
    group.add_argument(f"--{prefix}-country", default=None)


def _write_bill(bill, fmt: str, output: str | None) -> None:
    if fmt == "json":
        _print(bill_summary(bill))
        return
    content: bytes = render_pdf(bill) if fmt == "pdf" else render_svg(bill).encode("utf-8")
    if output:
        Path(output).write_bytes(content)
        _print({"written": output, "bytes": len(content)})
    else:
        sys.stdout.buffer.write(content)


class RemoteClient:
    def __init__(self, url: str, key: str | None):
        import httpx  # imported lazily: only needed in remote mode

        headers = {"Authorization": f"Bearer {key}"} if key else {}
        self.http = httpx.Client(base_url=url.rstrip("/"), headers=headers, timeout=30)

    def call(self, method: str, path: str, **kwargs) -> Any:
        response = self.http.request(method, path, **kwargs)
        if response.status_code >= 400:
            raise SystemExit(json.dumps({"error": response.status_code, "detail": _safe_json(response)}))
        if response.headers.get("content-type", "").startswith("application/json"):
            return response.json()
        return response.content


def _safe_json(response) -> Any:
    try:
        return response.json()
    except ValueError:
        return response.text


def _remote() -> RemoteClient | None:
    url = os.environ.get("ZAHLBAR_API_URL")
    return RemoteClient(url, os.environ.get("ZAHLBAR_API_KEY")) if url else None


# ---- commands -------------------------------------------------------------
def cmd_bill(args: argparse.Namespace) -> None:
    request = json.loads(Path(args.json).read_text(encoding="utf-8")) if args.json else {
        "account": args.account,
        "creditor": _address(args, "creditor"),
        "amount": args.amount,
        "currency": args.currency,
        "debtor": _address(args, "debtor"),
        "reference": args.reference,
        "message": args.message or "",
        "language": args.language,
    }
    request = {k: v for k, v in request.items() if v is not None}
    _write_bill(build_bill(request), args.format, args.output)


def cmd_reference(args: argparse.Namespace) -> None:
    ref = qrr_from_number(args.number, args.prefix) if args.kind == "qrr" else scor_from_number(args.number)
    _print({"reference": ref, "type": args.kind.upper()})


def cmd_config(args: argparse.Namespace) -> None:
    path = config_path()
    data = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}
    if args.action == "show":
        _print({"path": str(path), **data})
        return
    creditor = _address(args, "creditor") or {}
    creditor.setdefault("country", "CH")
    probe = {"account": args.account, "creditor": creditor}
    if args.account and _is_qr_iban(args.account):
        probe["reference"] = qrr_from_number("1")  # a QR-IBAN is only valid together with a QRR reference
    build_bill(probe)  # validate before saving
    data.update({"account": args.account.replace(" ", ""), "creditor": creditor})
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
    _print({"saved": str(path), **data})


def cmd_invoice(args: argparse.Namespace) -> None:
    remote = _remote()
    if args.action == "create":
        payload = {
            "number": args.number, "amount": args.amount, "currency": args.currency,
            "due_date": args.due, "message": args.message or "", "language": args.language,
            "debtor": _address(args, "debtor"), "reference_prefix": args.prefix or "",
        }
        payload = {k: v for k, v in payload.items() if v not in (None, "")}
        _print(remote.call("POST", "/v1/invoices", json=payload) if remote else Zahlbar().create_invoice(payload))
    elif args.action == "list":
        if remote:
            _print(remote.call("GET", "/v1/invoices", params={"status": args.status} if args.status else None))
        else:
            _print(Zahlbar().store.list_invoices(args.status))
    elif args.action == "bill":
        if remote:
            content = remote.call("GET", f"/v1/invoices/{args.id}/bill.{args.format}")
            if args.format == "json":
                _print(content)
            else:
                Path(args.output or f"{args.id}.{args.format}").write_bytes(content)
                _print({"written": args.output or f"{args.id}.{args.format}"})
            return
        bill = Zahlbar().bill_for_invoice(args.id)
        if bill is None:
            raise SystemExit(json.dumps({"error": "invoice not found"}))
        _write_bill(bill, args.format, args.output or (None if args.format == "json" else f"{args.id}.{args.format}"))
    elif args.action == "delete":
        if remote:
            remote.call("DELETE", f"/v1/invoices/{args.id}")
            _print({"deleted": args.id})
        else:
            _print({"deleted": Zahlbar().store.delete_invoice(args.id)})


def cmd_reconcile(args: argparse.Namespace) -> None:
    data = Path(args.file).read_bytes()
    remote = _remote()
    if remote:
        _print(remote.call("POST", "/v1/reconcile", content=data, headers={"Content-Type": "application/xml"}))
    else:
        _print(Zahlbar().reconcile(data))


def cmd_unmatched(_: argparse.Namespace) -> None:
    remote = _remote()
    _print(remote.call("GET", "/v1/payments/unmatched") if remote else Zahlbar().store.unmatched_payments())


def cmd_serve(args: argparse.Namespace) -> None:
    import uvicorn

    uvicorn.run("zahlbar.api:app", host=args.host, port=args.port)


def cmd_mcp(args: argparse.Namespace) -> None:
    from .mcp_server import main as mcp_main

    mcp_main(http=args.http, host=args.host, port=args.port)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="zahlbar", description="Swiss QR-bills that tell you who paid.")
    parser.add_argument("--version", action="version", version=f"zahlbar {__version__}")
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("bill", help="Render a one-off QR-bill (svg, pdf or json payload)")
    p.add_argument("--json", help="Read the bill request from a JSON file")
    p.add_argument("--account")
    _add_address_args(p, "creditor")
    _add_address_args(p, "debtor")
    p.add_argument("--amount")
    p.add_argument("--currency", default="CHF", choices=["CHF", "EUR"])
    p.add_argument("--reference")
    p.add_argument("--message")
    p.add_argument("--language", default="en", choices=["en", "de", "fr", "it"])
    p.add_argument("--format", default="pdf", choices=["svg", "pdf", "json"])
    p.add_argument("-o", "--output")
    p.set_defaults(func=cmd_bill)

    p = sub.add_parser("reference", help="Build a QRR or RF reference from an invoice number")
    p.add_argument("kind", choices=["qrr", "scor"])
    p.add_argument("number")
    p.add_argument("--prefix", default="", help="QRR only: bank customer id")
    p.set_defaults(func=cmd_reference)

    p = sub.add_parser("config", help="Save or show your default creditor")
    p.add_argument("action", choices=["set-creditor", "show"])
    p.add_argument("--account")
    _add_address_args(p, "creditor")
    p.set_defaults(func=cmd_config)

    p = sub.add_parser("invoice", help="Create, list, print or delete tracked invoices")
    p.add_argument("action", choices=["create", "list", "bill", "delete"])
    p.add_argument("id", nargs="?", help="Invoice id (for bill/delete)")
    p.add_argument("--number")
    p.add_argument("--amount")
    p.add_argument("--currency", default="CHF", choices=["CHF", "EUR"])
    p.add_argument("--due", help="Due date YYYY-MM-DD")
    p.add_argument("--message")
    p.add_argument("--prefix", help="QRR only: bank customer id")
    p.add_argument("--language", default="en", choices=["en", "de", "fr", "it"])
    p.add_argument("--status", choices=["all", "open", "partial", "paid", "unpaid", "overdue"])
    p.add_argument("--format", default="pdf", choices=["svg", "pdf", "json"])
    p.add_argument("-o", "--output")
    _add_address_args(p, "debtor")
    p.set_defaults(func=cmd_invoice)

    p = sub.add_parser("reconcile", help="Import a camt.054/camt.053 bank file and mark paid invoices")
    p.add_argument("file")
    p.set_defaults(func=cmd_reconcile)

    p = sub.add_parser("unmatched", help="Payments that could not be linked to an invoice")
    p.set_defaults(func=cmd_unmatched)

    p = sub.add_parser("serve", help="Start the REST API")
    p.add_argument("--host", default=os.environ.get("ZAHLBAR_HOST", "127.0.0.1"))
    p.add_argument("--port", type=int, default=int(os.environ.get("ZAHLBAR_PORT", "8080")))
    p.set_defaults(func=cmd_serve)

    p = sub.add_parser("mcp", help="Start the MCP server (stdio by default)")
    p.add_argument("--http", action="store_true", help="Serve MCP over streamable HTTP instead of stdio")
    p.add_argument("--host", default="127.0.0.1")
    p.add_argument("--port", type=int, default=8090)
    p.set_defaults(func=cmd_mcp)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.command == "invoice":
        if args.action == "create" and (not args.number or not args.amount):
            raise SystemExit(json.dumps({"error": "--number and --amount are required"}))
        if args.action in ("bill", "delete") and not args.id:
            raise SystemExit(json.dumps({"error": "invoice id is required"}))
    try:
        args.func(args)
    except (BillError, CamtError, ReferenceError_, StoreError, ValueError) as exc:
        errors = getattr(exc, "errors", None) or [str(exc)]
        print(json.dumps({"error": "invalid input", "details": errors}, ensure_ascii=False), file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
