# Verification record

Evidence is scoped to the execution and source revision that produced it. The hosted CI results below supplement the historical local audit; they do not replace its counts or imply that every manual audit check was repeated. These records establish software behavior with synthetic inputs and simulated provider transports. They contain no real-model quality benchmark.

## Hosted GitHub Actions — 2026-11-10 (UTC)

[Run 42730793669](https://github.com/giovannyTorres/genai-release-lab/actions/runs/42730793669) of `verified-demo` completed with **success** for all three jobs. This was run **11**, attempt **1**, triggered by `pull_request` for [PR #2](https://github.com/giovannyTorres/genai-release-lab/pull/2). GitHub records creation at `2026-11-10T00:45:59Z` and the final update at `2026-11-10T00:49:00Z`.

- Source branch: `claude/portfolio-projects-audit-g8d5rs`.
- Recorded PR head: [`d46515fe392a597440cdbb2deb12edf514a397c3`](https://github.com/giovannyTorres/genai-release-lab/commit/d46515fe392a597440cdbb2deb12edf514a397c3).
- Actual checkout in all three job logs: [`a7771f0df521f2204699995166557b326619f21c`](https://github.com/giovannyTorres/genai-release-lab/commit/a7771f0df521f2204699995166557b326619f21c), GitHub's temporary PR merge of that head into base `115374b4e3738d488b570a1b08430d11198234f6`. This verifies that merge checkout, not an isolated head checkout or a merge into `main`.
- [Workflow at the recorded head](https://github.com/giovannyTorres/genai-release-lab/blob/d46515fe392a597440cdbb2deb12edf514a397c3/.github/workflows/ci.yml). Results are specific to this run; later commits need their own CI evidence.

| Job | Observed result | Evidence |
|---|---|---|
| Backend | **113 passed, 2 skipped in 12.83s** on the dedicated PostgreSQL 17.6 `release_test` database. Alembic migration and Ruff passed. The separate fixture CLI check confirmed the expected rejection exit code `2`. | [backend log](https://github.com/giovannyTorres/genai-release-lab/actions/runs/42730793669/job/129547943222), `uv run pytest -q` summary at `00:46:40Z` |
| Frontend | **8 unit tests passed in 2 test files**. ESLint, TypeScript checking and the production Next build also passed. | [web log](https://github.com/giovannyTorres/genai-release-lab/actions/runs/42730793669/job/129547943553), Vitest summary at `00:47:15Z` |
| Docker/browser | `docker compose up --build -d --wait` completed, followed by **11 Playwright tests passed in 25.6s**. Eight scenarios exercise the actual DEMO backend; three cover explicitly mocked browser mode/authentication contracts. | [e2e log](https://github.com/giovannyTorres/genai-release-lab/actions/runs/42730793669/job/129547943551), Playwright summary at `00:48:57Z` |

### Scope and limitations of this run

- The two skipped tests are the OpenAI and Gemini cases of [`test_live_smoke`](https://github.com/giovannyTorres/genai-release-lab/blob/d46515fe392a597440cdbb2deb12edf514a397c3/tests/test_live.py). The workflow does not opt into `RUN_LIVE=1` or configure provider credentials. No successful real OpenAI/Gemini inference or LLM-judge execution is established by this run. Even a future passing smoke would check connectivity and a structured response, not representative model quality.
- Provider/endpoint contract tests use simulated transports. The [browser authentication contract tests](https://github.com/giovannyTorres/genai-release-lab/blob/d46515fe392a597440cdbb2deb12edf514a397c3/tests/e2e/auth-contract.spec.ts) intercept mode/login responses; a passing scenario whose name contains `LIVE` is not a provider smoke. Fixture gate results, including the deliberately rejected regression and pending mandatory judge, are deterministic workflow checks, not model-quality benchmarks.
- The e2e artifact-upload step reported that no files were found at `apps/web/test-results/`; **no browser evidence artifact was uploaded**. The linked job logs establish the test counts. Committed screenshots are separate evidence and are not claimed to have been captured or uploaded by this hosted run.
- This workflow did not run the manual container-restart experiment or Bicep compilation described below. Their observations remain evidence from the earlier local audit. Hosted CI success does not establish an Azure deployment, production readiness, security certification or accessibility certification.

The [Codex review summary](https://github.com/giovannyTorres/genai-release-lab/pull/2#issuecomment-6755576352) reports a completed code review with no findings for `37fa0599d13c0a1045b4d939130e5cb1d5a842ca`, the parent of `d46515f`. That review is separate from CI and does not establish review coverage for the later commit or real-model quality. PR #2 was open and unmerged when these records were checked, before this documentation update.

## Historical local audit — 2026-11-05

The following observations belong to the earlier local audit, not to the hosted run above. Its **112 backend / 6 frontend** counts are retained as recorded; the later CI run reports **113 / 8**. No model key, paid inference call, remote publication or cloud deployment was used during that local audit. See [audit.md](audit.md) for reproduced defects, severity, exact commands, tested image IDs and limits, and the [pre-update verification document](https://github.com/giovannyTorres/genai-release-lab/blob/d46515fe392a597440cdbb2deb12edf514a397c3/docs/VERIFICATION.md) for the original record.

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
| Infrastructure | Compose configuration and local Bicep v0.48.1 compilation passed; no Azure resource or hosted GitHub Actions execution was part of this local audit |

The final audit application containers were stopped with `down` without `-v`; generated audit application images/cache were removed to reclaim shared workspace disk. Original and both audit data volumes remain. The application is not left running, and these image IDs are historical verification evidence rather than a claim that images remain cached. Rebuild using the commands in the audit.

Real screenshots in `docs/screenshots/audit-*.png` were captured after the final Docker build and visually reviewed. Browser contracts that mock LIVE status/auth responses are identified in `tests/e2e/auth-contract.spec.ts`; actual LIVE account authentication and revocation are also tested directly against the backend, without model credentials. Accessibility checks are focused tests, not certification.

## Historical construction evidence

The earlier delivery had 33 backend tests, five browser journeys and a successful cached local-process launcher run. Its final container rebuild was blocked around 00:19 UTC by HTTP503 downloading the `jiter==0.18.0` wheel from `files.pythonhosted.org`, then a Docker Hub frontend manifest HEAD failed with the managed proxy's upstream connection error. That was a concrete external failure, **resolved during this audit**. It is not a current Docker blocker.

The alternative launcher uses frozen caches and the same repository code; the audit inspected its prerequisites, secret isolation, occupied-port behavior and process supervision. The new portable-installation evidence comes from clean Docker builds and volumes, not manually installed dependencies or another repository's assets.

## Remaining external verification

OpenAI/Gemini authentication, quotas, model availability and live structured-output acceptance require future explicit LIVE verification with credentials. Actual model quality requires a separate evaluation with real model outputs and a suitable dataset and rubric; a connectivity smoke or passing fixture suite cannot establish it. Endpoint evaluation is transport-tested, requires an authorized public destination and direct egress; proxy CONNECT support is not implemented. Imported trace authenticity remains the operator's trust boundary.

Azure networking, identity, managed PostgreSQL, registry pull and deployment remain unverified. Hosted Actions execution is now established for the specific run and merge checkout above; it does not resolve those Azure or LIVE boundaries. Distributed abuse protection, production load, comprehensive security assessment and full accessibility review remain outside this portfolio audit. This candidate is ready for portfolio review within those limits, not declared production-ready.
