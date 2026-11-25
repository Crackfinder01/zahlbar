# Good first issues

Copy each block into a GitHub issue (label: `good first issue`).

1. **Payment reminder PDF (Mahnung / rappel)** — `GET /v1/invoices/{id}/reminder.pdf` with the QR-bill and the open amount, in DE/FR/IT/EN.
2. **EPC QR code for EUR invoices** — optional SEPA "GiroCode" output for clients outside Switzerland.
3. **CSV export** — `GET /v1/invoices.csv` for accounting.
4. **bexio CSV import** — create tracked invoices from a bexio export.
5. **Due-date reminders in n8n** — a third workflow template that e-mails a draft reminder (draft only).
6. **Italian README section.**
7. **Real bank samples** — anonymised camt.054 samples from PostFinance, UBS, Raiffeisen, ZKB to extend the tests (no personal data!).
8. **Multiple creditors** — support several companies/accounts in one installation.
9. **`zahlbar login`** — store the remote URL and key with the OS keyring instead of env vars.
10. **Publish the Docker image** on GitHub Container Registry with a release workflow.
