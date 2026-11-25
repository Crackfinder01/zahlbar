import asyncio
import json

from zahlbar import mcp_server
from zahlbar.cli import main
from zahlbar.service import Zahlbar
from zahlbar.store import Store

from .conftest import QR_IBAN, camt054


def run(capsys, *argv):
    code = main(list(argv))
    out = capsys.readouterr()
    return code, out.out, out.err


def test_cli_end_to_end(tmp_path, capsys):
    code, out, _ = run(capsys, "config", "set-creditor", "--account", QR_IBAN, "--creditor-name", "Muster AG",
                       "--creditor-street", "Bahnhofstrasse", "--creditor-house-num", "1",
                       "--creditor-pcode", "8001", "--creditor-city", "Zürich")
    assert code == 0 and json.loads(out)["account"] == QR_IBAN

    code, out, _ = run(capsys, "invoice", "create", "--number", "2026-7", "--amount", "120.50", "--due", "2026-01-01")
    invoice = json.loads(out)
    assert code == 0 and invoice["reference_type"] == "QRR"

    pdf = tmp_path / "bill.pdf"
    code, out, _ = run(capsys, "invoice", "bill", invoice["id"], "-o", str(pdf))
    assert code == 0 and pdf.read_bytes().startswith(b"%PDF")

    code, out, _ = run(capsys, "invoice", "list", "--status", "overdue")
    assert [i["number"] for i in json.loads(out)] == ["2026-7"]

    camt = tmp_path / "camt.xml"
    camt.write_text(camt054([(invoice["reference"], "120.50", "X1")]), encoding="utf-8")
    code, out, _ = run(capsys, "reconcile", str(camt))
    assert json.loads(out)["matched"][0]["status"] == "paid"


def test_cli_reference_and_bill_json(capsys):
    code, out, _ = run(capsys, "reference", "scor", "42")
    assert json.loads(out)["reference"].startswith("RF")
    code, out, _ = run(capsys, "bill", "--account", "CH5800791123000889012", "--creditor-name", "A",
                       "--creditor-pcode", "1000", "--creditor-city", "Lausanne", "--format", "json")
    assert code == 0 and json.loads(out)["reference_type"] == "NON"


def test_cli_reports_errors_as_json(capsys):
    code, _, err = run(capsys, "bill", "--account", "CH00", "--creditor-name", "A", "--creditor-pcode", "1",
                       "--creditor-city", "B", "--format", "json")
    assert code == 2 and json.loads(err)["error"] == "invalid input"


def test_mcp_tools_are_listed_and_work(tmp_path):
    mcp_server.set_service(Zahlbar(Store(tmp_path / "mcp.sqlite3")))
    tools = asyncio.run(mcp_server.server.list_tools())
    names = {t.name for t in tools}
    assert {"create_invoice", "list_invoices", "get_invoice_bill", "reconcile_bank_file",
            "render_qr_bill", "validate_qr_bill", "create_reference", "list_unmatched_payments"} <= names

    creditor = {"name": "Muster AG", "pcode": "8001", "city": "Zürich", "country": "CH"}
    invoice = mcp_server.create_invoice(number="M-1", amount="15.00", account=QR_IBAN, creditor=creditor)
    out = tmp_path / "m.pdf"
    assert mcp_server.get_invoice_bill(invoice["id"], "pdf", str(out))["written"] == str(out)
    result = mcp_server.reconcile_bank_file(xml=camt054([(invoice["reference"], "15.00", "Z")]))
    assert result["matched"][0]["number"] == "M-1"
    assert mcp_server.list_invoices("paid")[0]["number"] == "M-1"
