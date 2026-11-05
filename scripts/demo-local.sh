#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
for command in docker uv node npm; do
  command -v "$command" >/dev/null || { echo "Missing prerequisite: $command" >&2; exit 1; }
done
# Explicit offline installation avoids concealing registry failures or silently downloading packages.
uv sync --frozen --offline || { echo 'Python dependency cache missing. When networking is available, run uv sync --frozen first.' >&2; exit 1; }
(cd apps/web && npm ci --offline --no-audit --no-fund) || { echo 'npm cache missing. When networking is available, run cd apps/web && npm ci first.' >&2; exit 1; }
export APP_MODE=DEMO
export DATABASE_URL='postgresql+psycopg://release:release@127.0.0.1:5543/release'
export PUBLIC_ORIGIN='http://localhost:3103'
export COOKIE_SECURE=false
# Refuse to reuse arbitrary listeners; never kill a user's existing process.
.venv/bin/python - <<'PY'
import socket
for port in (3103,8103):
    with socket.socket() as listener:
        listener.setsockopt(socket.SOL_SOCKET,socket.SO_REUSEADDR,1)
        try:
            listener.bind(('127.0.0.1',port))
        except OSError:
            raise SystemExit(f'Port {port} is occupied. Stop the existing app before starting this demo.')
PY
docker compose -f compose.yaml -f infra/compose.local.yaml up -d --wait db
.venv/bin/alembic upgrade head
.venv/bin/python -m release_lab.seed
(cd apps/web && npm run build && mkdir -p .next/standalone/.next && cp -a .next/static .next/standalone/.next/ && cp -a public .next/standalone/)
mkdir -p .run
.venv/bin/uvicorn release_lab.main:app --host 127.0.0.1 --port 8103 >.run/api.log 2>&1 & api_pid=$!
.venv/bin/python -m release_lab.worker >.run/worker.log 2>&1 & worker_pid=$!
PORT=3103 HOSTNAME=127.0.0.1 API_URL=http://127.0.0.1:8103 node apps/web/.next/standalone/server.js >.run/web.log 2>&1 & web_pid=$!
cleanup() {
  kill "$api_pid" "$worker_pid" "$web_pid" 2>/dev/null || true
  wait "$api_pid" "$worker_pid" "$web_pid" 2>/dev/null || true
}
trap cleanup EXIT INT TERM
.venv/bin/python - <<'PY'
import time, urllib.request
for attempt in range(30):
    try:
        with urllib.request.urlopen('http://localhost:3103/api/health',timeout=2) as response:
            assert response.status==200
        break
    except Exception:
        time.sleep(1)
else:
    raise SystemExit('Startup did not become healthy. Inspect .run/*.log')
PY
printf 'DEMO ready: http://localhost:3103 — operator/reviewer/viewer, password demo-release\nCtrl+C stops application processes; PostgreSQL data persists.\n'
wait "$web_pid"
