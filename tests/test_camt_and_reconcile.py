from datetime import date

import pytest

from zahlbar.camt import CamtError, parse_camt

from .conftest import CREDITOR, DEBTOR, IBAN, QR_IBAN, camt054


def _invoice(service, number, amount, **extra):
    payload = {"number": number, "amount": amount, "account": QR_IBAN, "creditor": CREDITOR, **extra}
    return service.create_invoice(payload)


def test_parse_camt054_batch_entries():
    xml = camt054([("000000000000000000000000016", "100.00", "TX-1"), (None, "5.00", "TX-2")])
    credits = parse_camt(xml)
    assert [str(c.amount) for c in credits] == ["100.00", "5.00"]
    assert credits[0].reference == "000000000000000000000000016"
    assert credits[1].reference is None
    assert credits[0].booking_date == "2026-11-20"
    # payer data is never extracted
    assert "Private Person" not in repr(credits)


def test_parse_ignores_pending_and_debits():
    assert parse_camt(camt054([("1", "10.00", "A")], status="PDNG")) == []
    debit = camt054([("1", "10.00", "A")]).replace("<CdtDbtInd>CRDT</CdtDbtInd>", "<CdtDbtInd>DBIT</CdtDbtInd>", 1)
    assert parse_camt(debit) == []


def test_parse_entry_without_details_uses_entry_amount():
    credits = parse_camt(camt054([(None, "42.00", "A")], batch=False))
    assert len(credits) == 1 and str(credits[0].amount) == "42.00"


def test_parse_camt053_statement():
    xml = camt054([("000000000000000000000000016", "10.00", "S-1")])
    xml = xml.replace("camt.054.001.08", "camt.053.001.08").replace("BkToCstmrDbtCdtNtfctn", "BkToCstmrStmt")
    xml = xml.replace("<Ntfctn>", "<Stmt>").replace("</Ntfctn>", "</Stmt>")
    assert len(parse_camt(xml)) == 1


@pytest.mark.parametrize("bad", [
    b"not xml",
    b"<Document><Other/></Document>",
    b'<?xml version="1.0"?><!DOCTYPE x [<!ENTITY a "b">]><Document/>',
])
def test_parse_rejects_bad_files(bad):
    with pytest.raises(CamtError):
        parse_camt(bad)


def test_full_flow_paid_partial_unmatched_and_idempotent(service):
    inv_paid = _invoice(service, "2026-0001", "100.00", debtor=DEBTOR, due_date="2026-11-30")
    inv_partial = _invoice(service, "2026-0002", "250.00", due_date="2026-10-31")
    xml = camt054([
        (inv_paid["reference"], "100.00", "TX-1"),
        (inv_partial["reference"], "50.00", "TX-2"),
        ("000000000000000000099999995", "9.00", "TX-3"),
    ])
    summary = service.reconcile(xml)
    assert summary["credits"] == 3
    assert [m["number"] for m in summary["matched"]] == ["2026-0001"]
    assert summary["partial"][0]["open_amount"] == "200.00"
    assert len(summary["unmatched"]) == 1

    again = service.reconcile(xml)
    assert again["duplicates"] == 3 and not again["matched"]

    assert service.store.get_invoice(inv_paid["id"])["status"] == "paid"
    overdue = service.store.list_invoices("overdue", today=date(2026, 11, 25))
    assert [i["number"] for i in overdue] == ["2026-0002"]
    assert len(service.store.unmatched_payments()) == 1


def test_currency_mismatch_is_not_matched(service):
    inv = _invoice(service, "7", "10.00")
    summary = service.reconcile(camt054([(inv["reference"], "10.00", "E-1")], currency="EUR"))
    assert summary["unmatched"] and not summary["matched"]


def test_invoice_reference_type_follows_iban(service):
    qr = _invoice(service, "11", "1.00")
    rf = service.create_invoice({"number": "12", "amount": "1.00", "account": IBAN, "creditor": CREDITOR})
    assert qr["reference_type"] == "QRR" and rf["reference_type"] == "SCOR"


def test_duplicate_invoice_number_is_refused(service):
    from zahlbar.store import StoreError

    _invoice(service, "99", "1.00")
    with pytest.raises(StoreError):
        _invoice(service, "99", "2.00")


def test_delete_invoice_removes_debtor_data(service):
    inv = _invoice(service, "5", "1.00", debtor=DEBTOR)
    assert service.store.delete_invoice(inv["id"]) is True
    assert service.store.get_invoice(inv["id"]) is None
