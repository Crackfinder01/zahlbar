# Self-hosting Zahlbar

## Docker compose

1. `cp .env.example .env`
2. Set `ZAHLBAR_API_KEY` to a long random value (`openssl rand -hex 32`).
3. Optionally set your default creditor (`ZAHLBAR_ACCOUNT`, `ZAHLBAR_CREDITOR_*`).
4. `docker compose up -d` — the API listens on `127.0.0.1:8080`.
5. To reach it from outside (n8n in the cloud, phone…), put a reverse proxy with HTTPS in front
   (Caddy, Traefik, nginx). Do **not** expose port 8080 directly.

Data lives in the `zahlbar-data` volume (`/data/zahlbar.sqlite3`). Back it up like any database.

## Without Docker

```bash
pip install "git+https://github.com/Crackfinder01/zahlbar"
ZAHLBAR_API_KEY=... zahlbar serve --host 127.0.0.1 --port 8080
```

## Environment variables

| Variable | Default | Meaning |
|---|---|---|
| `ZAHLBAR_API_KEY` | (empty = open API) | Bearer token required by the REST API |
| `ZAHLBAR_DB` | `~/.local/share/zahlbar/zahlbar.sqlite3` | SQLite file |
| `ZAHLBAR_CONFIG` | `~/.config/zahlbar/config.json` | Default creditor file |
| `ZAHLBAR_ACCOUNT`, `ZAHLBAR_CREDITOR_*` | — | Default creditor (override the config file) |
| `ZAHLBAR_HOST`, `ZAHLBAR_PORT` | `127.0.0.1`, `8080` | `zahlbar serve` bind address |
| `ZAHLBAR_API_URL` | — | CLI remote mode: URL of a Zahlbar server |
