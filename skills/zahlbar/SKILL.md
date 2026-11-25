---
name: zahlbar
description: Create Swiss QR-bill invoices (QR-Rechnung / QR-facture), import camt.054 or camt.053 bank files to see who paid, and list overdue invoices. Use when the user wants to bill a client in Switzerland or Liechtenstein, needs a QR-bill PDF, or asks which invoices are still unpaid.
---

# Zahlbar - Swiss QR-bills that tell you who paid

Zahlbar is an open-source CLI (and REST API / MCP server). All commands print JSON.

## Install

```bash
pipx install zahlbar        # not yet on PyPI: pip install "git+https://github.com/Crackfinder01/zahlbar"
zahlbar --version
```

Remote server instead of local files: export `ZAHLBAR_API_URL` and `ZAHLBAR_API_KEY` (never print the key).

## First time: save the creditor (who gets paid)

```bash
zahlbar config set-creditor --account "CH44 3199 9123 0008 8901 2" \
  --creditor-name "Muster AG" --creditor-street "Bahnhofstrasse" --creditor-house-num 1 \
  --creditor-pcode 8001 --creditor-city "Zürich"
zahlbar config show
```

- Addresses are **structured** (street, house number, postal code, city, country). Two-line addresses are not allowed on QR-bills since 21 Nov 2025.
- A **QR-IBAN** (bank id 30000-31999) gets a 27-digit QRR reference; a normal IBAN gets an `RF...` reference. Zahlbar picks the right one.

## Bill a client

```bash
zahlbar invoice create --number 2026-0042 --amount 1949.75 --due 2026-12-31 --language de \
  --message "Invoice 2026-0042" \
  --debtor-name "Beispiel GmbH" --debtor-street "Rue du Lac" --debtor-house-num 12 \
  --debtor-pcode 1003 --debtor-city Lausanne
zahlbar invoice bill <id> -o invoice-2026-0042.pdf     # A4 page with the QR payment slip
```

Amounts use a dot (`120.50`). The debtor is optional: only add it if the user gives it.

## Who paid?

The user downloads the **camt.054** (or camt.053) file from their e-banking, then:

```bash
zahlbar reconcile ~/Downloads/camt054.xml    # safe to run twice on the same file
zahlbar invoice list --status overdue         # who still has to pay (due date passed)
zahlbar invoice list --status unpaid          # open + partially paid
zahlbar unmatched                             # money received with an unknown reference
```

## Other commands

```bash
zahlbar reference qrr 2026-0042          # build a QRR reference
zahlbar reference scor 2026-0042         # build an RF creditor reference
zahlbar bill --json bill.json --format pdf -o bill.pdf   # one-off bill, nothing stored
zahlbar invoice delete <id>              # remove an invoice and its debtor data
zahlbar serve                            # REST API on http://127.0.0.1:8080 (docs at /docs)
zahlbar mcp                              # MCP server over stdio
```

## Rules for agents

- Never invent an IBAN, amount or address: ask the user.
- Do not send invoices or e-mails yourself unless the user explicitly asks.
- On error the CLI exits with code 2 and prints `{"error": ..., "details": [...]}`: show the details to the user.
