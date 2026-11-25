# syntax=docker/dockerfile:1
FROM python:3.12-slim AS base

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    ZAHLBAR_DB=/data/zahlbar.sqlite3 \
    ZAHLBAR_CONFIG=/data/config.json \
    ZAHLBAR_HOST=0.0.0.0 \
    ZAHLBAR_PORT=8080

WORKDIR /app
COPY pyproject.toml README.md LICENSE ./
COPY src ./src
RUN pip install ".[mcp]" && useradd --create-home --uid 10001 zahlbar && mkdir /data && chown zahlbar /data

USER zahlbar
VOLUME ["/data"]
EXPOSE 8080
HEALTHCHECK --interval=30s --timeout=3s CMD python -c "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8080/health').status==200 else 1)"
CMD ["zahlbar", "serve"]
