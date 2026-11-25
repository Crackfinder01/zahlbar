"""Data models shared by the library, the REST API, the CLI and the MCP server."""
from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Literal, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator

Language = Literal["en", "de", "fr", "it"]
Currency = Literal["CHF", "EUR"]


class Address(BaseModel):
    """Structured address (type "S").

    Since 21 November 2025 the Swiss Implementation Guidelines only allow
    structured addresses on QR-bills, so the old two-line "combined" address
    is deliberately not supported.
    """

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    name: str = Field(..., min_length=1, max_length=70, examples=["Muster AG"])
    street: Optional[str] = Field(None, max_length=70, examples=["Bahnhofstrasse"])
    house_num: Optional[str] = Field(None, max_length=16, examples=["1"])
    pcode: str = Field(..., min_length=1, max_length=16, examples=["8001"])
    city: str = Field(..., min_length=1, max_length=35, examples=["Zürich"])
    country: str = Field("CH", min_length=2, max_length=2, examples=["CH"])

    @field_validator("country")
    @classmethod
    def _upper_country(cls, value: str) -> str:
        return value.upper()


class BillRequest(BaseModel):
    """Everything needed to draw one Swiss QR-bill."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    account: str = Field(..., description="IBAN or QR-IBAN of the creditor (CH or LI)", examples=["CH4431999123000889012"])
    creditor: Address
    amount: Optional[Decimal] = Field(None, ge=Decimal("0.01"), le=Decimal("999999999.99"), description="Leave empty for an open amount")
    currency: Currency = "CHF"
    debtor: Optional[Address] = Field(None, description="Optional. Only add it if you need it on the slip.")
    reference: Optional[str] = Field(None, description="QRR (27 digits, QR-IBAN only) or SCOR (RF...) reference")
    message: str = Field("", max_length=140, description="Unstructured message shown on the slip")
    language: Language = "en"

    @field_validator("amount")
    @classmethod
    def _two_decimals(cls, value: Optional[Decimal]) -> Optional[Decimal]:
        if value is None:
            return None
        if value.as_tuple().exponent < -2:  # type: ignore[operator]
            raise ValueError("amount must have at most 2 decimals")
        return value.quantize(Decimal("0.01"))


class ReferenceRequest(BaseModel):
    kind: Literal["qrr", "scor"]
    number: str = Field(..., min_length=1, max_length=40, description="Your invoice number")
    prefix: str = Field("", max_length=12, description="QRR only: optional bank customer id (digits)")


class InvoiceCreate(BaseModel):
    """A tracked invoice. The reference is generated when not given."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    number: str = Field(..., min_length=1, max_length=40, examples=["2026-0042"])
    amount: Decimal = Field(..., ge=Decimal("0.01"), le=Decimal("999999999.99"))
    currency: Currency = "CHF"
    due_date: Optional[date] = None
    account: Optional[str] = Field(None, description="Defaults to the configured creditor account")
    creditor: Optional[Address] = Field(None, description="Defaults to the configured creditor")
    debtor: Optional[Address] = None
    message: str = Field("", max_length=140)
    reference: Optional[str] = None
    reference_prefix: str = Field("", max_length=12)
    language: Language = "en"

    @field_validator("amount")
    @classmethod
    def _two_decimals(cls, value: Decimal) -> Decimal:
        if value.as_tuple().exponent < -2:  # type: ignore[operator]
            raise ValueError("amount must have at most 2 decimals")
        return value.quantize(Decimal("0.01"))
