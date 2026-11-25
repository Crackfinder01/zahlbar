# Changelog

## 0.1.0 — unreleased

First public version.

- QR-bill generation (SVG, A4 PDF, JSON payload) with structured addresses only
- QRR and ISO 11649 (RF) reference generation
- Tracked invoices in SQLite; statuses open / partial / paid / overdue
- camt.054 and camt.053 import with idempotent matching; unmatched payments list
- REST API (FastAPI, OpenAPI docs, API-key auth), CLI with JSON output, MCP server, agent skill
- n8n community node and two workflow templates
- Dockerfile and docker-compose
