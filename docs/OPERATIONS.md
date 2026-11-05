# Operation and LIVE activation

## Local DEMO

`docker compose up --build -d` runs database, migration/seed, API, worker and web with healthchecks. Compose exposes only the web port 3103. `docker compose logs -f api worker` shows operational events. `docker compose restart worker` preserves job progress; expired leases are reclaimed within 120 seconds. Migrations are explicit Alembic revision 001; seed is idempotent.

In managed workspaces whose package HTTPS traffic uses a custom trusted CA, build with:

```bash
docker compose -f compose.yaml -f infra/compose.cloud.yaml build
```

The optional override mounts `$CODEX_PROXY_CERT` as a BuildKit secret, never as a repository file. TLS verification stays enabled. Normal hosts use standard trusted certificate roots and the main Compose file.

## One-command local-process fallback

`./scripts/demo-local.sh` is verified in this workspace and starts the same application without building API/web container images. It runs cached PostgreSQL17.6 through Compose, installs the frozen Python/npm dependencies strictly offline, migrates/seeds, builds Next production output and launches the API/worker/web. Missing caches fail with a clear prerequisite message. The script forces DEMO and refuses occupied web/API ports. Ctrl+C stops only processes it created; the named PostgreSQL volume remains. Logs are ignored in `.run/`. To stop the local database later: `docker compose -f compose.yaml -f infra/compose.local.yaml down` (without `-v`).

## LIVE, explicit opt-in

1. Copy `.env.example` to `.env` (Git-ignored), set `APP_MODE=LIVE`, correct `PUBLIC_ORIGIN`, and `COOKIE_SECURE=true` when serving HTTPS.
2. Generate a salted password hash with `uv run python -m release_lab.security`. Configure `LIVE_USERS_JSON` as JSON, e.g. `{"operator-live":{"role":"operator","password_hash":"scrypt$<salt>$<derived-hash>"},"reviewer-live":{"role":"reviewer","password_hash":"scrypt$<salt>$<derived-hash>"}}`. DEMO credentials are disabled in LIVE.
3. Set backend-only `OPENAI_API_KEY` and/or `GEMINI_API_KEY`. Do not put credentials in `NEXT_PUBLIC_*` variables. `MODEL_PROVIDER` controls displayed readiness. Each versioned evaluation configuration selects its actual provider and model. Gemini example: create a configuration with provider `gemini`, model `gemini-2.5-flash`. OpenAI default is `gpt-4.1-mini`.
4. Recreate services with `docker compose up --build -d`. Sign in with a configured LIVE account. The mode indicator and status endpoint expose readiness without exposing secrets. Create/import a LIVE dataset and configuration; seeded datasets use a separate mode partition. API execution (`POST /api/jobs`, `source: "api"`) requires provider credentials. Missing configuration returns an actionable error, never DEMO output.
5. Configure `require_llm: true`, a rubric, rubric_version, provider and model to enable the optional structured judge. Without credentials, imported outputs still run deterministic checks but remain inconclusive when the judge is mandatory. DEMO always leaves the judge pending regardless of environment keys.
6. Optional registered endpoint: set `ENDPOINT_ALLOWED_HOSTS=your.public.example`, then authenticated operator POST `/api/endpoints` with `{name,url}`. Exact HTTPS hosts on port443 only. DNS must contain exclusively globally routable addresses. Each invocation revalidates and pins a resolved IP with original TLS SNI and Host. Redirects, private/mapped networks and responses over256KB are blocked. Endpoint receives `{case_id,prompt,context}` and must return the Output JSON schema in OpenAPI. No per-endpoint authentication is currently supported; deploy a narrowly accessible evaluation endpoint or extend explicit credential references before connecting a protected service.

Real smoke commands (may incur provider charges; **not run during construction**):

```bash
RUN_LIVE=1 uv run pytest -q -m live tests/test_live.py -k openai
RUN_LIVE=1 uv run pytest -q -m live tests/test_live.py -k gemini
```

Request controls: `MODEL_TIMEOUT_SECONDS` (1–25 seconds per attempt), `MODEL_MAX_OUTPUT_TOKENS` (1–8192), `MODEL_MAX_RETRIES` (0–1), and `MODEL_CONCURRENCY` (default2). An overall55-second deadline bounds each structured request; no unbounded retries. Only structured generation is exposed because this product does not need tool execution or token streaming.

Provider models can change availability. `LIVE_SMOKE_MODEL` overrides the test model for the selected provider. Normal tests use simulated transports and skip these tests. No external credentials are needed by CI.

## Azure Container Apps configuration

`infra/main.bicep` targets an **existing** Container Apps environment and an **existing** PostgreSQL database. It defines internal API, worker and external web. It is a deployment configuration, not evidence of a deployment. No Azure resources have been created.

Build/push images only in a future authorized deployment. The web server reads `API_URL` at request time through its same-origin server proxy. The template sets this to the internal API’s exact HTTPS ingress FQDN, so the same web image can run in Compose and Azure without a baked host or redirect to an internal hostname. Run `az bicep build --file infra/main.bicep` to compile locally. Then, when separately authorized, supply environmentName, apiImage, webImage, publicOrigin and secure databaseUrl parameters; use a Key Vault / secure parameter injection workflow for keys and liveUsersJson. Never commit a parameter file containing secrets. The API performs migration before serving; worker retries until schema is available. One API replica avoids concurrent migration race. Managed PostgreSQL requires TLS connection parameters in databaseUrl.

Review network egress/firewall, ingress identity, retention, backups, central OTLP collector and organizational secret rotation before production. Those operational integrations are not claimed as completed by this local portfolio project.
