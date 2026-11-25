import pytest

from zahlbar.bills import BillError, bill_summary, build_bill, render_pdf, render_svg, validate_bill
from zahlbar.references import qrr_from_number, scor_from_number

from .conftest import CREDITOR, DEBTOR, IBAN, QR_IBAN


def base(**overrides):
    data = {"account": QR_IBAN, "creditor": CREDITOR, "amount": "1949.75", "currency": "CHF",
            "debtor": DEBTOR, "reference": qrr_from_number("2026-0042"), "message": "Invoice 2026-0042",
            "language": "de"}
    data.update(overrides)
    return data


def test_qr_payload_follows_swiss_payment_code():
    summary = bill_summary(build_bill(base()))
    lines = summary["qr_payload"].split("\r\n")
    assert lines[0:3] == ["SPC", "0200", "1"]
    assert lines[3] == QR_IBAN
    assert lines[4] == "S"  # structured address only
    assert "1949.75" in lines and "CHF" in lines
    assert summary["reference_type"] == "QRR"
    assert lines[-1] == "EPD" or "EPD" in lines


def test_svg_and_pdf_rendering():
    bill = build_bill(base())
    svg = render_svg(bill)
    assert svg.startswith("<?xml") and "<svg" in svg
    pdf = render_pdf(bill)
    assert pdf.startswith(b"%PDF") and len(pdf) > 1000


def test_open_amount_and_no_debtor_are_allowed():
    bill = build_bill(base(amount=None, debtor=None))
    assert bill.amount is None and bill.debtor is None


def test_scor_reference_with_normal_iban():
    summary = bill_summary(build_bill(base(account=IBAN, reference=scor_from_number("42"))))
    assert summary["reference_type"] == "SCOR"


@pytest.mark.parametrize("override,expected", [
    ({"account": "CH0000000000000000000"}, "IBAN"),
    ({"account": IBAN}, "QRR"),  # QRR reference with a normal IBAN
    ({"reference": None}, "QR-IBAN"),  # QR-IBAN without QRR reference
    ({"amount": "12.345"}, "decimals"),
    ({"currency": "USD"}, "currency"),
    ({"message": "x" * 141}, "message"),
])
def test_invalid_bills_are_rejected_with_a_reason(override, expected):
    errors = validate_bill(base(**override))
    assert errors, "should be invalid"
    assert expected.lower() in " ".join(errors).lower()


def test_combined_two_line_addresses_are_refused():
    creditor = {"name": "Muster AG", "line1": "Bahnhofstrasse 1", "line2": "8001 Zürich", "country": "CH"}
    with pytest.raises(BillError):
        build_bill(base(creditor=creditor))


def test_valid_bill_has_no_errors():
    assert validate_bill(base()) == []
