# Verification record

Executed locally on 2026-11-05. No model API key was supplied and no paid inference call or cloud deployment was performed.

| Check | Observed result |
|---|---|
| Python lint | `uv run ruff check services tests migrations` passed |
| Backend suite | 33 passed, 2 LIVE smoke tests skipped intentionally |
| Real PostgreSQL suite | 33 passed, 2 skipped against dedicated PostgreSQL 17.6 test database |
| Official SDK transport contracts | OpenAI and Gemini structured generation, actual SDK HTTP serialization and usage parsing, and sanitized errors passed using simulated HTTP transports |
| Endpoint transport review | 4 independent tests passed: DNS-pinned IP + Host/SNI, redirect rejection, response size limit, invalid JSON |
| Deterministic fixtures | Reference 60/60 approved; deliberately changed outputs 30/60 rejected; required LLM 60 pending/inconclusive |
| CLI | Tests verified exit 0 approved, 2 rejected, 3 inconclusive; invalid input exits 4 |
| Data/permissions | Authenticated roles, mode isolation, scrypt password hashes, strict imports, missing outputs, expired lease recovery, cancel/retry, approvals and exports passed |
| Frontend checks | Production build, TypeScript, ESLint, and 6 Vitest tests passed, including runtime proxy contracts |
| Production browser | 5 Playwright workflows passed against built standalone Next, actual FastAPI, worker and PostgreSQL; configuration creation, imports, comparisons, approvals, mandatory-pending state, keyboard focus and mobile overflow checked |
| One-command local DEMO | `./scripts/demo-local.sh` verified: frozen offline dependencies, Compose PostgreSQL healthcheck, migrations, idempotent seed, production build, API/worker startup and same-origin health |
| Azure configuration | Bicep v0.48.1 compiled locally without warnings; no resource provisioning or Azure what-if performed |
| Full-container path | Compose configuration validated. Final all-container image rebuild/boot is **not verified**: an environment-wide proxy outage returned HTTP 503 from PyPI and Docker Hub on 2026-11-05 around 00:19 UTC |

An earlier managed-workspace VFS disk shortage was resolved with unused build-cache cleanup and smaller image layers. The final blocker was distinct: `jiter==0.18.0` wheel download from `files.pythonhosted.org` returned 503, followed by Docker frontend manifest HEAD returning 503. Direct PyPI/GitHub requests also failed with the proxy message “upstream connect error … envoy://cloudflare_https_tunnel”. Environment status remained connected with unrestricted policy; no proxy or TLS protections were disabled. Final Dockerfiles include non-root application ownership fixes but require a successful rebuild/boot after this external outage clears.

The verified fallback uses the same application code and production web output, with actual PostgreSQL in Docker. It does not establish that the complete application-container deployment was tested. Screenshots in `docs/screenshots/` are actual production-browser captures with synthetic data; accessibility checks cover keyboard focus, responsive overflow and labeled controls, not a WCAG certification.

## Pending external verification

OpenAI/Gemini real service authentication, quotas, model availability, structured-output behavior and actual quality evaluations require explicitly supplied credentials and LIVE smoke opt-in. Public endpoint evaluation is implemented and tested with transport simulations; no external endpoint owner was contacted. Azure Container Apps networking/identity, PostgreSQL managed-service connectivity, registry image pull and deployment remain unverified until an authorized future deployment.

CI YAML was exercised through equivalent local commands; no GitHub remote was created and no hosted Actions run is claimed. Runtime fixture outcomes are illustrative verification, not model benchmark metrics or business impact.
