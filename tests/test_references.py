import pytest
from stdnum import iso11649
from stdnum.ch import esr

from zahlbar.references import (ReferenceError_, normalize_reference, qrr_from_number, reference_type,
                                scor_from_number)


def test_qrr_is_27_digits_with_valid_check_digit():
    ref = qrr_from_number("2026-0042")
    assert len(ref) == 27 and ref.isdigit()
    assert esr.is_valid(ref)
    assert ref[:26] == "20260042".zfill(26)


def test_qrr_with_bank_prefix():
    ref = qrr_from_number("42", prefix="210000")
    assert esr.is_valid(ref)
    assert ref[:26].lstrip("0").startswith("21000042")


def test_qrr_rejects_too_long_and_empty():
    with pytest.raises(ReferenceError_):
        qrr_from_number("9" * 27)
    with pytest.raises(ReferenceError_):
        qrr_from_number("ABC")


def test_scor_reference_is_valid_iso11649():
    ref = scor_from_number("INV 2026/42")
    assert ref.startswith("RF")
    assert iso11649.is_valid(ref)
    assert ref.endswith("INV202642")


def test_scor_rejects_too_long():
    with pytest.raises(ReferenceError_):
        scor_from_number("A" * 22)


def test_reference_type_detection():
    assert reference_type(None) == "NON"
    assert reference_type(qrr_from_number("1")) == "QRR"
    assert reference_type(scor_from_number("1")) == "SCOR"
    with pytest.raises(ReferenceError_):
        reference_type("123")


def test_normalize_reference():
    assert normalize_reference(" rf18 5390 0754 7034 ") == "RF18539007547034"
    assert normalize_reference("   ") is None
