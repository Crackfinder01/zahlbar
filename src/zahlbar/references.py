"""Payment reference helpers.

* QRR  - 27-digit QR reference (only valid together with a QR-IBAN).
* SCOR - ISO 11649 creditor reference ("RF..."), valid with a normal IBAN.
"""
from __future__ import annotations

import re

from stdnum import iso11649
from stdnum.ch import esr
from stdnum.iso7064 import mod_97_10

__all__ = [
    "qrr_from_number",
    "scor_from_number",
    "normalize_reference",
    "reference_type",
    "ReferenceError_",
]


class ReferenceError_(ValueError):
    """Raised when a reference cannot be built or is invalid."""


_DIGITS = re.compile(r"\D")
_ALNUM = re.compile(r"[^0-9A-Za-z]")


def qrr_from_number(number: str, prefix: str = "") -> str:
    """Build a QRR reference from an invoice number.

    Non-digit characters are dropped. ``prefix`` (digits only) is an optional
    bank customer id that some banks require at the start of the reference.
    The result is 26 digits (left-padded with zeros) plus a recursive
    modulo-10 check digit.
    """
    digits = _DIGITS.sub("", str(prefix)) + _DIGITS.sub("", str(number)).lstrip("0")
    if not digits:
        raise ReferenceError_("The invoice number must contain at least one digit for a QRR reference")
    if len(digits) > 26:
        raise ReferenceError_("Prefix + invoice number are too long for a QRR reference (max 26 digits)")
    body = digits.zfill(26)
    return body + esr.calc_check_digit(body)


def scor_from_number(number: str) -> str:
    """Build an ISO 11649 creditor reference (``RFxx...``) from an invoice number."""
    body = _ALNUM.sub("", str(number)).upper()
    if not body:
        raise ReferenceError_("The invoice number must contain letters or digits")
    if len(body) > 21:
        raise ReferenceError_("The invoice number is too long for an ISO 11649 reference (max 21 characters)")
    check = mod_97_10.calc_check_digits(body + "RF")
    reference = f"RF{check}{body}"
    if not iso11649.is_valid(reference):  # defensive, should never happen
        raise ReferenceError_("Could not build a valid ISO 11649 reference")
    return reference


def normalize_reference(reference: str | None) -> str | None:
    """Remove spaces and upper-case a reference so it can be compared."""
    if reference is None:
        return None
    cleaned = re.sub(r"\s+", "", str(reference)).upper()
    return cleaned or None


def reference_type(reference: str | None) -> str:
    """Return ``QRR``, ``SCOR`` or ``NON`` for a reference (raises if invalid)."""
    ref = normalize_reference(reference)
    if not ref:
        return "NON"
    if ref.startswith("RF"):
        if iso11649.is_valid(ref):
            return "SCOR"
        raise ReferenceError_("Invalid ISO 11649 (SCOR) reference")
    if ref.isdigit() and len(ref) == 27 and esr.is_valid(ref):
        return "QRR"
    raise ReferenceError_("Invalid reference: expected a 27-digit QRR or an RF creditor reference")
