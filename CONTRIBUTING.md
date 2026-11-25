# Contributing to Zahlbar

Thanks for helping! Zahlbar is small on purpose: one Python package, one SQLite file, no external service.

## Set up

```bash
git clone https://github.com/Crackfinder01/zahlbar && cd zahlbar
python -m venv .venv && . .venv/bin/activate
pip install -e ".[dev]"
pytest
```

n8n node: `cd integrations/n8n/n8n-nodes-zahlbar && npm install && npm run build && npm test`.

## Rules

- One pull request = one change, with tests.
- Never commit real IBANs, names or bank files. Use the SIX example accounts (`CH44 3199 9123 0008 8901 2`, `CH58 0079 1123 0008 8901 2`) and the generator in `tests/conftest.py`.
- Keep the privacy promise: nothing from bank files except reference, amount, currency, dates and bank transaction id.
- Code, commits and docs in English; README sections in German and French are welcome.

## Where to start

See [docs/good-first-issues.md](docs/good-first-issues.md).
