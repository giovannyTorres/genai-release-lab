# GenAI Release Lab

A working release-evaluation workbench for the fictional **Aster Systems** organization. Import or execute outputs, inspect failures, compare paired cases, and enforce evidence-based release gates. Every included case and response is original synthetic material. This is a portfolio product, not a claim of financial or regulatory compliance.

![Actual paired comparison with synthetic fixture outputs](docs/screenshots/comparison-desktop.png)

## Run DEMO

```bash
docker compose up --build -d
```

Open **http://localhost:3103**. Sign in as `operator`, `reviewer` or `viewer` with password `demo-release`. DEMO never calls model APIs, including when keys happen to be configured. PostgreSQL migrations and seed run automatically. Stop with `docker compose down`; named data volumes persist. `docker compose down -v` deliberately deletes local demonstration data.

The operator can version datasets/configurations, import JSON/JSONL outputs and run jobs. The reviewer can append human corrections and approve an eligible release. The viewer has read access. Session cookies are HttpOnly/SameSite=Strict, checked on the server. See [Spanish guide](docs/GUIA_ES.md), [architecture](docs/ARCHITECTURE.md), [operations and LIVE](docs/OPERATIONS.md), [trust model](docs/SECURITY.md), [verification evidence](docs/VERIFICATION.md) and [two-minute walkthrough](docs/DEMO.md).

## What works

- Sixty original cases: 40 development, 20 final; standalone RAG and agent contexts. Immutable dataset/configuration versions with canonical SHA-256 hashes.
- Persistent queued/running/completed/failed/cancelled jobs. A separate worker leases jobs transactionally, persists each case, and resumes expired leases after restart. Cancel/retry preserves completed evidence.
- Deterministic schema, citation, tool, argument and authorization evidence checks. The reference fixture yields 60/60; the deliberately changed fixture yields 30/60. These are fixture-validation results, **not model-quality measurements**.
- Mandatory LLM evaluations without LIVE credentials remain pending and block release approval. No invented scores, usage or costs. Optional dated pricing applies only when token usage exists.
- Paired comparisons expose missing cases and denominators. Human corrections are append-only and preserve automated gate evidence. Release approvals bind input and results hashes.
- JSON, JUnit and self-contained HTML exports; offline CLI with explicit exit codes.
- Real OpenAI Responses and Google Gemini SDK adapters with bounded requests, structured-output validation and transport-fixture tests. LIVE endpoint execution uses operator allowlists, public-IP pinning and redirect rejection.

## Verified local-process fallback

The final full-container rebuild was blocked by a managed-environment proxy outage (HTTP503 from PyPI and Docker Hub). With dependencies and the PostgreSQL image already cached in this workspace, the entire DEMO can also start with:

```bash
./scripts/demo-local.sh
```

This runs PostgreSQL through Compose and the API, durable worker and production Next server as local processes. It installs only from the existing frozen caches, and reports missing prerequisites explicitly. If starting on a new machine with working networking, prime caches with `uv sync --frozen`, `cd apps/web && npm ci`, and `docker pull postgres:17.6-bookworm` first. Ports3103/8103/5543 must be free. Ctrl+C stops application processes; database data persists. Logs are in ignored `.run/`. The standard all-container command above remains the intended portable deployment path; see precise verification status below.

## Local development and checks

Requirements: Python 3.12, uv 0.13.4, Node 24.22.1, Docker Compose. Exact dependencies: `uv.lock` and `apps/web/package-lock.json`.

```bash
uv sync --frozen
# Start a local PostgreSQL database, then set DATABASE_URL (default localhost:5543).
uv run alembic upgrade head
uv run python -m release_lab.seed
uv run uvicorn release_lab.main:app --port 8103
# Separate terminal
uv run python -m release_lab.worker
# Separate terminal
cd apps/web && npm ci && npm run dev
```

```bash
make lint types test build
cd apps/web && npm run test:e2e
```

Tests default to a disposable SQLite database for fast domain tests; run the same tests against a **dedicated disposable PostgreSQL** database by setting `DATABASE_URL`. Tests recreate schema. CI uses PostgreSQL and includes the expected rejected gate as a successful assertion, plus browser workflows. The application itself defaults to PostgreSQL. OpenAPI: `/api/docs` and `/api/openapi.json` through the same-origin frontend.

```bash
uv run release-lab --dataset fixtures/cases.json --outputs fixtures/reference.json --export /tmp/reference.json
uv run release-lab --dataset fixtures/cases.json --outputs fixtures/regression.json --format junit --export /tmp/regression.xml
# exits 2 intentionally: expected rejected fixture
```

CLI exit codes: **0 approved**, **2 rejected**, **3 inconclusive**, **4 invalid input**. `--require-llm` marks the mandatory check pending; the offline CLI never performs inference.

LIVE has been implemented and tested with simulated HTTP transports. Real provider connectivity, billing, model behavior and Azure deployment have **not** been verified. No credentials or cloud resources are required for DEMO. See exact opt-in steps in [operations](docs/OPERATIONS.md).
