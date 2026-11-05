# Verification record — audit candidate, 2026-11-05

Current evidence supersedes the initial construction report. No model key, paid inference call, remote publication or cloud deployment was used. See [audit.md](audit.md) for reproduced defects, severity, exact commands, tested image IDs and limits.

| Check | Observed result |
|---|---|
| Backend | **112 passed, 2 LIVE smokes skipped**, on a dedicated PostgreSQL 17.6 test database; ordinary application `DATABASE_URL` cannot select the destructive test database |
| Provider/endpoint contracts | 70 tests, including official SDK HTTP serialization, completed/incomplete/refused/blocked responses, strict JSON, cancellation, bounded retries, connection closure, secret redaction and pinned public endpoint transport |
| Frontend | ESLint, TypeScript, **6 unit tests**, and production Next build passed |
| Final Docker browser | **11 passed**: eight actual-backend journeys plus three explicitly mocked browser authentication/status contracts; desktop, 390×844 mobile, focus, empty/loading/error/recovery states |
| Fresh Docker | API and web rebuilt using `--no-cache --pull`; final backend rebuilt again after validation-error redaction. New `audit-release-clean_release-data` volume, migration revision 001, idempotent seed, non-root API/worker/web and four healthy services |
| Real restart | Actual worker interrupted at 23/1000 persisted cases; API session survived restart; worker resumed to 1000 unique results with unchanged input hash. [Record](audit-runtime.json), [reproduction script](../scripts/audit-recovery.py) |
| Independent HTTP checks | Unauthenticated requests 401; hostile-origin and unauthorized-role writes 403; rejected or mandatory-pending approvals 409; OpenAPI 200; invalid password validation does not echo its input |
| Deterministic gate evidence | Renamed imported regression contents rejected at 30/60; reference plus mandatory unconfigured judge inconclusive with 60/60 pending. No version-name shortcut. These are synthetic software checks, not model-quality results |
| CLI | Actual subprocess exit 0 approved, 2 rejected, 3 inconclusive, 4 invalid input; argument errors also exit 4 |
| Logging/TLS | Actual canary query absent from API logs/spans, correlation/path retained. Public official Gemini documentation HTTPS200 from final API container with verified runtime proxy CA; no inference endpoint contacted |
| Infrastructure | Compose configuration and local Bicep v0.48.1 compilation passed; no Azure resource or hosted GitHub Actions execution |

The final audit application containers were stopped with `down` without `-v`; generated audit application images/cache were removed to reclaim shared workspace disk. Original and both audit data volumes remain. The application is not left running, and these image IDs are historical verification evidence rather than a claim that images remain cached. Rebuild using the commands in the audit.

Real screenshots in `docs/screenshots/audit-*.png` were captured after the final Docker build and visually reviewed. Browser contracts that mock LIVE status/auth responses are identified in `tests/e2e/auth-contract.spec.ts`; actual LIVE account authentication and revocation are also tested directly against the backend, without model credentials. Accessibility checks are focused tests, not certification.

## Historical construction evidence

The earlier delivery had 33 backend tests, five browser journeys and a successful cached local-process launcher run. Its final container rebuild was blocked around 00:19 UTC by HTTP503 downloading the `jiter==0.18.0` wheel from `files.pythonhosted.org`, then a Docker Hub frontend manifest HEAD failed with the managed proxy's upstream connection error. That was a concrete external failure, **resolved during this audit**. It is not a current Docker blocker.

The alternative launcher uses frozen caches and the same repository code; the audit inspected its prerequisites, secret isolation, occupied-port behavior and process supervision. The new portable-installation evidence comes from clean Docker builds and volumes, not manually installed dependencies or another repository's assets.

## Remaining external verification

OpenAI/Gemini authentication, quotas, model availability, live structured-output acceptance and actual quality evaluation require future explicit LIVE smoke execution with credentials. Endpoint evaluation is transport-tested, requires an authorized public destination and direct egress; proxy CONNECT support is not implemented. Imported trace authenticity remains the operator's trust boundary.

Azure networking, identity, managed PostgreSQL, registry pull and deployment remain unverified. Equivalent CI commands ran locally, but no hosted Actions run is claimed. Distributed abuse protection, production load, comprehensive security assessment and full accessibility review remain outside this portfolio audit. This candidate is ready for portfolio review within those limits, not declared production-ready.
