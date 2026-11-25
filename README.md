<h1 align="center">Zahlbar</h1>

<p align="center"><strong>Swiss QR-bills that tell you who paid.</strong><br/>
Open-source, self-hostable QR-bill API + bank-file reconciliation, built for n8n and AI agents.</p>

<p align="center">
  <a href="LICENSE"><img alt="License: AGPL-3.0" src="https://img.shields.io/badge/license-AGPL--3.0-blue.svg"></a>
  <img alt="Python 3.10+" src="https://img.shields.io/badge/python-3.10%2B-blue">
  <img alt="QR-bill IG 2.3+ (structured addresses)" src="https://img.shields.io/badge/QR--bill-structured%20addresses-red">
</p>

<p align="center">
  <a href="#quick-start">Quick start</a> ·
  <a href="#rest-api">REST API</a> ·
  <a href="#cli-for-humans-and-agents">CLI</a> ·
  <a href="#ai-agents-mcp-and-skill">AI agents (MCP / skill)</a> ·
  <a href="#n8n">n8n</a> ·
  <a href="#deutsch">Deutsch</a> ·
  <a href="#français">Français</a>
</p>

---

Sending a QR-bill is easy. Knowing **who paid** is the boring part: open the e-banking, download the
camt file, compare references by hand, chase the late ones.

**Zahlbar does the whole loop:**

1. **Create** an invoice → Zahlbar generates a valid QR reference (QRR for a QR-IBAN, `RF…` otherwise).
2. **Print** the QR-bill → A4 PDF or SVG, in German, French, Italian or English.
3. **Reconcile** → drop in the **camt.054 / camt.053** file from your bank; invoices are marked *paid* or *partially paid*.
4. **Follow up** → `GET /v1/invoices?status=overdue` tells you who still has to pay.

Everything runs on your own machine or server. No account, no tracking, no data sent anywhere.

> Zahlbar is an open-source alternative to the invoice-tracking part of tools like bexio, Klara or the
> QR-bill APIs offered by banks — for people who automate.

## Features

- ✅ Swiss QR-bill generation (CHF / EUR, CH and LI IBANs, QR-IBAN + QRR, IBAN + SCOR or no reference)
- ✅ **Structured addresses only** — the two-line "combined" address is no longer allowed on QR-bills since 21 Nov 2025 ([SIX factsheet](https://six-group.com/dam/download/banking-services/standardization/qr-bill/factsheet-qr-bill-transition-period-erp-en.pdf))
- ✅ Validation with human-readable errors (bad IBAN, QRR used with a normal IBAN, too many decimals…)
- ✅ camt.054 (v4 and v8) and camt.053 import, **idempotent** (import the same file twice, nothing is counted twice)
- ✅ Paid / partial / overdue / unmatched payments
- ✅ REST API with OpenAPI docs (`/docs`), API-key auth
- ✅ CLI with JSON output, MCP server, agent skill, n8n node and workflow templates
- ✅ Docker image, SQLite storage, no external service
- ✅ Privacy by design: payer names and IBANs from bank files are **never stored**

## Quick start

### Docker (recommended for a server)

```bash
git clone https://github.com/Crackfinder01/zahlbar && cd zahlbar
cp .env.example .env            # set ZAHLBAR_API_KEY (openssl rand -hex 32) and your creditor
docker compose up -d
open http://localhost:8080/docs # interactive API documentation
```

### Python (local, no server)

```bash
pip install "git+https://github.com/Crackfinder01/zahlbar"     # PyPI release coming soon
zahlbar config set-creditor --account "CH44 3199 9123 0008 8901 2" \
  --creditor-name "Muster AG" --creditor-street Bahnhofstrasse --creditor-house-num 1 \
  --creditor-pcode 8001 --creditor-city Zürich
zahlbar invoice create --number 2026-0042 --amount 1949.75 --due 2026-12-31 --language de
zahlbar invoice bill <id> -o invoice.pdf
zahlbar reconcile ~/Downloads/camt054.xml
zahlbar invoice list --status overdue
```

## REST API

| Method | Path | What it does |
|---|---|---|
| `POST` | `/v1/bills?format=svg\|pdf\|json` | Render a one-off QR-bill (nothing stored) |
| `POST` | `/v1/validate` | Check bill data, returns the list of problems |
| `POST` | `/v1/references` | Build a QRR or `RF` reference from an invoice number |
| `POST` | `/v1/invoices` | Create a tracked invoice (reference generated) |
| `GET` | `/v1/invoices?status=all\|open\|partial\|paid\|unpaid\|overdue` | List invoices |
| `GET` | `/v1/invoices/{id}` | One invoice |
| `GET` | `/v1/invoices/{id}/bill.pdf` (`.svg`, `.json`) | The QR-bill of an invoice |
| `DELETE` | `/v1/invoices/{id}` | Delete an invoice (and its debtor data) |
| `POST` | `/v1/reconcile` | Body = raw camt.054/053 XML → paid / partial / unmatched |
| `GET` | `/v1/payments/unmatched` | Money received with an unknown reference |

Full schema: [`docs/openapi.json`](docs/openapi.json) or `http://localhost:8080/docs` once running.
Authentication: `Authorization: Bearer $ZAHLBAR_API_KEY` (or `X-API-Key`). If `ZAHLBAR_API_KEY` is not set the API is open — only acceptable on your own laptop.

```bash
curl -X POST http://localhost:8080/v1/invoices \
  -H "Authorization: Bearer $ZAHLBAR_API_KEY" -H "Content-Type: application/json" \
  -d '{"number":"2026-0042","amount":"1949.75","due_date":"2026-12-31"}'

curl -X POST http://localhost:8080/v1/reconcile \
  -H "Authorization: Bearer $ZAHLBAR_API_KEY" -H "Content-Type: application/xml" \
  --data-binary @camt054.xml
```

## CLI for humans and agents

Short commands, JSON output, exit code `2` + JSON error on bad input. Works locally (SQLite in
`~/.local/share/zahlbar`) or against a server when `ZAHLBAR_API_URL` and `ZAHLBAR_API_KEY` are set — the
key stays in the environment, never in a prompt.

```text
zahlbar config set-creditor|show
zahlbar invoice create|list|bill|delete
zahlbar reconcile <camt.xml>
zahlbar unmatched
zahlbar reference qrr|scor <number>
zahlbar bill --json bill.json --format pdf|svg|json -o file
zahlbar serve            # REST API
zahlbar mcp [--http]     # MCP server
```

## AI agents (MCP and skill)

**Claude Code / Claude Desktop / Cursor (local, stdio):**

```json
{ "mcpServers": { "zahlbar": { "command": "zahlbar", "args": ["mcp"] } } }
```

Tools: `create_invoice`, `list_invoices`, `get_invoice_bill`, `reconcile_bank_file`,
`list_unmatched_payments`, `render_qr_bill`, `validate_qr_bill`, `create_reference`.

**Skill** (Claude Code, OpenClaw and other agents that read `SKILL.md`): [`skills/zahlbar/SKILL.md`](skills/zahlbar/SKILL.md).

Example prompt: *"Bill Beispiel GmbH 1'949.75 CHF for the November work, due end of December, and save the PDF on my desktop."*
Then, once a month: *"Here is the camt.054 file from my bank — who still owes me money?"*

## n8n

- **Community node** `n8n-nodes-zahlbar`: [`integrations/n8n/n8n-nodes-zahlbar`](integrations/n8n/n8n-nodes-zahlbar) (create invoice, list, get PDF, reconcile, unmatched).
- **Workflow templates** (use the built-in HTTP Request node, no install needed):
  - [`daily-overdue-digest.json`](integrations/n8n/templates/daily-overdue-digest.json) — every weekday, list overdue invoices.
  - [`camt-email-to-reconcile.json`](integrations/n8n/templates/camt-email-to-reconcile.json) — when your bank e-mails a camt.054, mark invoices as paid.

## Privacy and security

- Bank files contain payer names and IBANs: Zahlbar reads **only** reference, amount, currency, dates and the bank's own transaction id. Nothing else is stored.
- The debtor address is optional; `DELETE /v1/invoices/{id}` removes it.
- XML files with `DOCTYPE`/`ENTITY` declarations are refused; size limit 10 MB.
- No telemetry. No outgoing network calls.
- Found a vulnerability? Please open a private security advisory on GitHub.

## How it works

Zahlbar stands on the shoulders of [`qrbill`](https://github.com/claudep/swiss-qr-bill) (MIT) for drawing the
payment part, and adds references, storage, camt parsing, matching, the API, CLI, MCP server and n8n node.

## Roadmap (ideas — vote in the issues)

- Payment reminders (Mahnungen / rappels) as PDF
- EPC QR code (SEPA "GiroCode") for EUR invoices outside Switzerland
- Import from bexio / CSV, export for accounting
- Hosted version for people who do not want to run a server

## Contributing

Issues and pull requests are welcome — see [CONTRIBUTING.md](CONTRIBUTING.md) and the
[good first issues](docs/good-first-issues.md). Run the tests with `pip install -e ".[dev]" && pytest`.

## License

[AGPL-3.0](LICENSE). You can self-host and modify Zahlbar freely; if you offer a modified version as a
network service, you must publish your changes.

---

## Deutsch

**Zahlbar: QR-Rechnungen, die Ihnen sagen, wer bezahlt hat.** Open Source, selbst hostbar.

1. Rechnung erstellen → gültige QR-Referenz (QRR bei QR-IBAN, sonst `RF…`).
2. QR-Rechnung als PDF/SVG (DE, FR, IT, EN).
3. camt.054- bzw. camt.053-Datei aus dem E-Banking einlesen → Rechnungen werden als *bezahlt* oder *teilweise bezahlt* markiert.
4. `zahlbar invoice list --status overdue` zeigt, wer noch nicht bezahlt hat.

Nur strukturierte Adressen (seit dem 21. November 2025 Pflicht). Namen und IBAN der Zahlenden aus den
Bankdateien werden nicht gespeichert. REST-API, CLI, MCP-Server für KI-Agenten und n8n-Node inklusive.
Lizenz: AGPL-3.0.

## Français

**Zahlbar : des factures QR qui vous disent qui a payé.** Open source, auto-hébergeable.

1. Créez une facture → référence QR valide (QRR avec un QR-IBAN, sinon `RF…`).
2. Imprimez la QR-facture en PDF/SVG (FR, DE, IT, EN).
3. Importez le fichier camt.054 ou camt.053 de votre e-banking → les factures passent en *payée* ou *partiellement payée*.
4. `zahlbar invoice list --status overdue` liste les retards de paiement.

Adresses structurées uniquement (obligatoires depuis le 21 novembre 2025). Les noms et IBAN des payeurs
contenus dans les fichiers bancaires ne sont jamais enregistrés. API REST, CLI, serveur MCP pour agents IA
et nœud n8n inclus. Licence : AGPL-3.0.
