"""REST API. Run with ``zahlbar serve`` or ``uvicorn zahlbar.api:app``.

Authentication: set ``ZAHLBAR_API_KEY`` and send it as ``Authorization: Bearer <key>``
(or ``X-API-Key: <key>``). Without the variable the API is open: only do this
on your own machine.
"""
from __future__ import annotations

import hmac
import logging
import os
from typing import Literal, Optional

from fastapi import Depends, FastAPI, HTTPException, Query, Request, Response
from fastapi.responses import JSONResponse

from . import __version__
from .bills import BillError, bill_summary, build_bill, render_pdf, render_svg, validate_bill
from .camt import CamtError, MAX_FILE_BYTES
from .models import BillRequest, InvoiceCreate, ReferenceRequest
from .references import ReferenceError_, qrr_from_number, scor_from_number
from .service import Zahlbar
from .store import Store, StoreError

log = logging.getLogger("zahlbar")

DESCRIPTION = """
**Zahlbar** creates Swiss QR-bills and tells you who paid.

1. `POST /v1/invoices` creates an invoice with a valid QR reference.
2. `GET /v1/invoices/{id}/bill.pdf` returns the printable QR-bill.
3. `POST /v1/reconcile` takes the camt.054 / camt.053 file from your bank and marks invoices as paid.
4. `GET /v1/invoices?status=overdue` lists who still has to pay.

Open source (AGPL-3.0) · self-hostable · built for n8n and AI agents.
"""

TAGS = [
    {"name": "bills", "description": "Stateless QR-bill generation and validation"},
    {"name": "invoices", "description": "Tracked invoices"},
    {"name": "reconciliation", "description": "Match bank payments with invoices"},
]


def create_app(service: Zahlbar | None = None) -> FastAPI:
    app = FastAPI(title="Zahlbar API", version=__version__, description=DESCRIPTION, openapi_tags=TAGS)
    app.state.service = service

    def get_service() -> Zahlbar:
        if app.state.service is None:
            app.state.service = Zahlbar()
        return app.state.service

    api_key = os.environ.get("ZAHLBAR_API_KEY")
    if not api_key:
        log.warning("ZAHLBAR_API_KEY is not set: the API accepts requests without authentication")

    def require_key(request: Request) -> None:
        if not api_key:
            return
        supplied = request.headers.get("x-api-key") or ""
        auth = request.headers.get("authorization") or ""
        if auth.lower().startswith("bearer "):
            supplied = auth[7:].strip()
        if not hmac.compare_digest(supplied.encode(), api_key.encode()):
            raise HTTPException(status_code=401, detail="Missing or invalid API key")

    protected = [Depends(require_key)]

    @app.exception_handler(BillError)
    async def _bill_error(_: Request, exc: BillError):
        return JSONResponse(status_code=422, content={"detail": exc.errors})

    @app.get("/health", include_in_schema=False)
    def health() -> dict:
        return {"status": "ok", "version": __version__}

    # ---- stateless --------------------------------------------------------
    @app.post("/v1/bills", tags=["bills"], dependencies=protected,
              responses={200: {"content": {"image/svg+xml": {}, "application/pdf": {}, "application/json": {}}}})
    def create_bill(body: BillRequest, format: Literal["svg", "pdf", "json"] = Query("svg")):
        """Render a QR-bill. `format=json` returns the QR payload without an image."""
        bill = build_bill(body)
        return _render(bill, format)

    @app.post("/v1/validate", tags=["bills"], dependencies=protected)
    def validate(body: dict) -> dict:
        """Check bill data without rendering it. Returns the list of problems."""
        errors = validate_bill(body)
        return {"valid": not errors, "errors": errors}

    @app.post("/v1/references", tags=["bills"], dependencies=protected)
    def create_reference(body: ReferenceRequest) -> dict:
        """Build a QRR (for a QR-IBAN) or an RF creditor reference from an invoice number."""
        try:
            ref = qrr_from_number(body.number, body.prefix) if body.kind == "qrr" else scor_from_number(body.number)
        except ReferenceError_ as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
        return {"reference": ref, "type": body.kind.upper()}

    # ---- invoices ---------------------------------------------------------
    @app.post("/v1/invoices", tags=["invoices"], dependencies=protected, status_code=201)
    def create_invoice(body: InvoiceCreate, svc: Zahlbar = Depends(get_service)) -> dict:
        try:
            return svc.create_invoice(body)
        except (StoreError, ReferenceError_) as exc:
            raise HTTPException(status_code=409 if isinstance(exc, StoreError) else 422, detail=str(exc)) from exc

    @app.get("/v1/invoices", tags=["invoices"], dependencies=protected)
    def list_invoices(status: Optional[Literal["all", "open", "partial", "paid", "unpaid", "overdue"]] = None,
                      svc: Zahlbar = Depends(get_service)) -> list[dict]:
        return svc.store.list_invoices(status)

    @app.get("/v1/invoices/{invoice_id}", tags=["invoices"], dependencies=protected)
    def get_invoice(invoice_id: str, svc: Zahlbar = Depends(get_service)) -> dict:
        invoice = svc.store.get_invoice(invoice_id)
        if invoice is None:
            raise HTTPException(status_code=404, detail="Invoice not found")
        return invoice

    @app.get("/v1/invoices/{invoice_id}/bill.{fmt}", tags=["invoices"], dependencies=protected)
    def invoice_bill(invoice_id: str, fmt: Literal["svg", "pdf", "json"], svc: Zahlbar = Depends(get_service)):
        bill = svc.bill_for_invoice(invoice_id)
        if bill is None:
            raise HTTPException(status_code=404, detail="Invoice not found")
        return _render(bill, fmt)

    @app.delete("/v1/invoices/{invoice_id}", tags=["invoices"], dependencies=protected, status_code=204)
    def delete_invoice(invoice_id: str, svc: Zahlbar = Depends(get_service)) -> Response:
        if not svc.store.delete_invoice(invoice_id):
            raise HTTPException(status_code=404, detail="Invoice not found")
        return Response(status_code=204)

    # ---- reconciliation ---------------------------------------------------
    @app.post("/v1/reconcile", tags=["reconciliation"], dependencies=protected,
              openapi_extra={"requestBody": {"content": {"application/xml": {"schema": {"type": "string"}}}, "required": True}})
    async def reconcile(request: Request, svc: Zahlbar = Depends(get_service)) -> dict:
        """Send the raw camt.054 or camt.053 XML as the request body. Importing the same file twice is safe."""
        body = await request.body()
        if len(body) > MAX_FILE_BYTES:
            raise HTTPException(status_code=413, detail="File too large")
        try:
            return svc.reconcile(body)
        except CamtError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc

    @app.get("/v1/payments/unmatched", tags=["reconciliation"], dependencies=protected)
    def unmatched(svc: Zahlbar = Depends(get_service)) -> list[dict]:
        """Payments that could not be linked to an invoice (wrong or missing reference)."""
        return svc.store.unmatched_payments()

    return app


def _render(bill, fmt: str):
    if fmt == "pdf":
        return Response(render_pdf(bill), media_type="application/pdf")
    if fmt == "json":
        return bill_summary(bill)
    return Response(render_svg(bill), media_type="image/svg+xml")


app = create_app()


def build_test_app(db_path: str) -> FastAPI:  # used by the test-suite
    return create_app(Zahlbar(Store(db_path)))
