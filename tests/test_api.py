import pytest
from fastapi.testclient import TestClient

from zahlbar.api import create_app
from zahlbar.references import qrr_from_number
from zahlbar.service import Zahlbar
from zahlbar.store import Store

from .conftest import CREDITOR, QR_IBAN, camt054


@pytest.fixture
def client(tmp_path):
    return TestClient(create_app(Zahlbar(Store(tmp_path / "api.sqlite3"))))


def test_health(client):
    assert client.get("/health").json()["status"] == "ok"


def test_openapi_documents_all_endpoints(client):
    paths = client.get("/openapi.json").json()["paths"]
    for path in ["/v1/bills", "/v1/validate", "/v1/references", "/v1/invoices", "/v1/reconcile",
                 "/v1/payments/unmatched", "/v1/invoices/{invoice_id}/bill.{fmt}"]:
        assert path in paths


def test_bill_formats(client):
    body = {"account": QR_IBAN, "creditor": CREDITOR, "amount": "10", "reference": qrr_from_number("1")}
    svg = client.post("/v1/bills?format=svg", json=body)
    assert svg.status_code == 200 and svg.headers["content-type"].startswith("image/svg+xml")
    pdf = client.post("/v1/bills?format=pdf", json=body)
    assert pdf.content.startswith(b"%PDF")
    js = client.post("/v1/bills?format=json", json=body).json()
    assert js["reference_type"] == "QRR" and js["amount"] == "10.00"


def test_invalid_bill_returns_422_with_reason(client):
    r = client.post("/v1/bills", json={"account": "CH00", "creditor": CREDITOR})
    assert r.status_code == 422
    assert "IBAN" in str(r.json()["detail"])


def test_validate_and_reference(client):
    assert client.post("/v1/validate", json={"account": "x"}).json()["valid"] is False
    ref = client.post("/v1/references", json={"kind": "scor", "number": "42"}).json()
    assert ref["reference"].startswith("RF")


def test_invoice_lifecycle(client):
    created = client.post("/v1/invoices", json={"number": "A-1", "amount": "80.00", "account": QR_IBAN,
                                                "creditor": CREDITOR, "due_date": "2026-01-31"})
    assert created.status_code == 201
    inv = created.json()
    assert client.post("/v1/invoices", json={"number": "A-1", "amount": "1", "account": QR_IBAN,
                                             "creditor": CREDITOR}).status_code == 409
    assert client.get(f"/v1/invoices/{inv['id']}/bill.pdf").content.startswith(b"%PDF")
    assert [i["id"] for i in client.get("/v1/invoices?status=overdue").json()] == [inv["id"]]

    r = client.post("/v1/reconcile", content=camt054([(inv["reference"], "80.00", "T1")]),
                    headers={"Content-Type": "application/xml"})
    assert r.status_code == 200 and r.json()["matched"][0]["status"] == "paid"
    assert client.get("/v1/invoices?status=overdue").json() == []
    assert client.delete(f"/v1/invoices/{inv['id']}").status_code == 204
    assert client.get(f"/v1/invoices/{inv['id']}").status_code == 404


def test_reconcile_rejects_garbage(client):
    assert client.post("/v1/reconcile", content=b"<x/>").status_code == 422


def test_api_key_is_enforced(tmp_path, monkeypatch):
    monkeypatch.setenv("ZAHLBAR_API_KEY", "s3cret-test-key")
    app = create_app(Zahlbar(Store(tmp_path / "k.sqlite3")))
    c = TestClient(app)
    assert c.get("/health").status_code == 200  # health stays public
    assert c.get("/v1/invoices").status_code == 401
    assert c.get("/v1/invoices", headers={"Authorization": "Bearer wrong"}).status_code == 401
    assert c.get("/v1/invoices", headers={"Authorization": "Bearer s3cret-test-key"}).status_code == 200
    assert c.get("/v1/invoices", headers={"X-API-Key": "s3cret-test-key"}).status_code == 200
