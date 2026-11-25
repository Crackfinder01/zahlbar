from __future__ import annotations

import pytest

from zahlbar.service import Zahlbar
from zahlbar.store import Store

QR_IBAN = "CH4431999123000889012"      # SIX example QR-IBAN (needs a QRR reference)
IBAN = "CH5800791123000889012"         # normal IBAN (SCOR or no reference)

CREDITOR = {"name": "Muster AG", "street": "Bahnhofstrasse", "house_num": "1",
            "pcode": "8001", "city": "Zürich", "country": "CH"}
DEBTOR = {"name": "Beispiel GmbH", "street": "Rue du Lac", "house_num": "12",
          "pcode": "1003", "city": "Lausanne", "country": "CH"}


@pytest.fixture(autouse=True)
def isolated_env(tmp_path, monkeypatch):
    """Never touch the real home directory or a real API key during tests."""
    monkeypatch.setenv("ZAHLBAR_CONFIG", str(tmp_path / "config.json"))
    monkeypatch.setenv("ZAHLBAR_DB", str(tmp_path / "zahlbar.sqlite3"))
    for var in ("ZAHLBAR_API_KEY", "ZAHLBAR_API_URL", "ZAHLBAR_ACCOUNT"):
        monkeypatch.delenv(var, raising=False)
    yield


@pytest.fixture
def service(tmp_path) -> Zahlbar:
    return Zahlbar(Store(tmp_path / "test.sqlite3"))


def camt054(credits: list[tuple[str | None, str, str]], *, currency: str = "CHF", status: str = "BOOK",
            batch: bool = True) -> str:
    """Build a minimal camt.054.001.08 notification.

    ``credits`` = list of (reference, amount, bank_ref).
    """
    txs = []
    for ref, amount, bank_ref in credits:
        rmt = (f"<RmtInf><Strd><CdtrRefInf><Tp><CdOrPrtry><Prtry>QRR</Prtry></CdOrPrtry></Tp>"
               f"<Ref>{ref}</Ref></CdtrRefInf></Strd></RmtInf>") if ref else "<RmtInf><Ustrd>Thanks</Ustrd></RmtInf>"
        txs.append(
            f"<TxDtls><Refs><AcctSvcrRef>{bank_ref}</AcctSvcrRef></Refs>"
            f"<Amt Ccy=\"{currency}\">{amount}</Amt><CdtDbtInd>CRDT</CdtDbtInd>"
            f"<RltdPties><Dbtr><Pty><Nm>Private Person</Nm></Pty></Dbtr></RltdPties>{rmt}</TxDtls>"
        )
    total = sum(float(a) for _, a, _ in credits)
    details = f"<NtryDtls>{''.join(txs)}</NtryDtls>" if batch else ""
    return f"""<?xml version="1.0" encoding="UTF-8"?>
<Document xmlns="urn:iso:std:iso:20022:tech:xsd:camt.054.001.08">
  <BkToCstmrDbtCdtNtfctn>
    <GrpHdr><MsgId>MSG-1</MsgId><CreDtTm>2026-11-20T08:00:00</CreDtTm></GrpHdr>
    <Ntfctn>
      <Id>NTF-1</Id>
      <Acct><Id><IBAN>{QR_IBAN}</IBAN></Id></Acct>
      <Ntry>
        <Amt Ccy="{currency}">{total:.2f}</Amt>
        <CdtDbtInd>CRDT</CdtDbtInd>
        <Sts><Cd>{status}</Cd></Sts>
        <BookgDt><Dt>2026-11-20</Dt></BookgDt>
        <ValDt><Dt>2026-11-20</Dt></ValDt>
        <AcctSvcrRef>ENTRY-1</AcctSvcrRef>
        {details}
      </Ntry>
    </Ntfctn>
  </BkToCstmrDbtCdtNtfctn>
</Document>"""
