# syntax=docker/dockerfile:1
FROM python:3.12.14-slim-bookworm
COPY --from=ghcr.io/astral-sh/uv:0.13.4 /uv /usr/local/bin/uv
WORKDIR /app
COPY --chown=10001:10001 pyproject.toml uv.lock alembic.ini ./
COPY --chown=10001:10001 services ./services
COPY --chown=10001:10001 fixtures ./fixtures
COPY --chown=10001:10001 migrations ./migrations
RUN --mount=type=secret,id=proxy_ca if [ -f /run/secrets/proxy_ca ]; then export SSL_CERT_FILE=/run/secrets/proxy_ca; fi; uv sync --frozen --no-dev && useradd -r -u 10001 release
USER release
ENV PATH=/app/.venv/bin:$PATH PYTHONUNBUFFERED=1
EXPOSE 8103
CMD ["uvicorn", "release_lab.main:app", "--host", "0.0.0.0", "--port", "8103"]
