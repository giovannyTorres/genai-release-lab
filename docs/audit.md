# Release-candidate technical audit — 2026-11-05

## Baseline and scope

Initial state: branch `main`, commit `a158658`, no pending Git changes. Applicable instruction: `apps/web/AGENTS.md`; the installed Next.js 16.4.5 Server/Client Components guide was read before UI changes. Existing demonstration data and Git history were preserved. No model credentials, paid inference, publishing, remote Git operation, or Azure deployment were used.

The review checked source, actual HTTP requests, official SDK HTTP contracts, executable CLI behavior, real PostgreSQL, and Chromium. Old passing counts were not used as acceptance evidence. All numerical fixture results below are deterministic software checks, not model-quality results.

## Findings and corrections

| ID / severity | Concrete defect and reproduction at baseline | Correction and regression evidence |
|---|---|---|
| RL-01 **High** | `providers.py`: real official SDKs with HTTP fixtures accepted OpenAI `status=incomplete` / `max_output_tokens` and Gemini `MAX_TOKENS` when text happened to parse as valid JSON. The baseline module loaded from `git show a158658:.../providers.py` returned `pass` in both cases. | Require completed OpenAI messages and Gemini `STOP`, reject refusals, blocks, unexpected tool calls, empty/thought-only responses and malformed JSON. `tests/test_providers.py` uses documented envelopes and error responses, not only the implementation's happy shape. |
| RL-02 **High** | `evaluation.compare` paired identical IDs even when context/expectations changed, and compared two unprocessed 60-case jobs as zero-size samples. Baseline execution returned one pair for changed contracts and denominator zero for empty running results. | Compare canonical full case contracts; changed or invalid legacy cases are excluded and listed. Use dataset inventories for denominators; show unprocessed/pending cases, suppress measured deltas while evidence is pending. Before/after reproduction: changed pair **1→0**, unprocessed denominator **0→60**. `test_comparison_excludes_changed_contract_and_keeps_unprocessed_denominator`, actual-browser audit comparisons. |
| RL-03 **High** | `tests/conftest.py` called `drop_all(engine)` using ordinary `DATABASE_URL`, which could erase a demonstration database when following the old PostgreSQL test instructions. | Tests default to a unique temporary database. PostgreSQL requires separate `TEST_DATABASE_URL` whose database name ends `_test`; refusal occurs before connecting. CI uses `release_test`. `test_test_runner_refuses_regular_database_before_connecting`. |
| RL-04 **High** | Vacuous RAG expectations (`answer_contains=[]`) passed arbitrary answers; required references could be outside the allowlist. Python equality treated tool argument `true` as integer `1`. | Validate nonempty fact/abstention contracts and authorization policies; canonical JSON comparison preserves argument types. Token-boundary fact matching prevents expected `260` passing the substring `1260`. Reject nonfinite JSON and duplicate object keys on API, CLI, provider and endpoint boundaries. `test_expectations_cannot_vacuously_pass`, `test_tool_argument_boolean_does_not_equal_integer`, import and transport regressions. |
| RL-05 **High** | Worker usage accounting read unvalidated raw `tokens`; importing a string could raise `TypeError` after evaluation and leave a job repeatedly reclaimable. Cancellation only changed status, leaving an in-flight call running until its deadline. | Only validated integer usage is counted. Unexpected job failures become safe, explicit failed/inconclusive results. Poll persisted ownership during calls and cancel the task; graceful worker stop relinquishes its lease while preserving completed results. `test_unvalidated_usage_cannot_crash_worker_or_create_cost`, `test_cancel_stops_inflight_operation`, `test_graceful_worker_stop_preserves_progress_and_relinquishes_lease`, redacted failure test. |
| RL-06 **Medium** | CLI input hashes omitted threshold, mandatory-judge flag and evaluator version. Workers did not check versioned payload integrity before execution/resume. | Hash source, dataset/configuration hashes, evaluator version and inputs; verify hashes before processing. CLI hashes all gate settings and reports argument-parser failures as invalid-input exit 4 rather than rejected-gate exit 2. Evaluator version is now `deterministic-1.1.0`; unfinished jobs from an older evaluator must be recreated instead of mixing results. `test_cli_hash_covers_rules_and_invalid_input_exit`, `test_versioned_input_tampering_fails_closed`. |
| RL-07 **Medium** | A cancelled 60-case job exported JUnit `tests=60` but no `<testcase>` nodes; HTML omitted those missing rows and denominators. | Materialize every expected case as pending until observed. JSON/JUnit/HTML expose the same inventory; escape all imported labels/checks. `test_partial_cancelled_export_contains_every_expected_case` checks 60 testcase/skipped nodes and malicious-label escaping. |
| RL-08 **Medium** | Gemini's synchronous HTTP client remained open after closing the async facade. Chained provider exceptions could reveal response bodies in tracebacks. Endpoint DNS/slow-drip response had no overall deadline. | Close both SDK-owned facades and injected HTTP client; redact chained errors; 5-second DNS and 25-second total endpoint timeout, including body iteration. Enforce explicit Gemini API-key routing (`vertexai=False`). Provider/endpoint tests verify close, cancellation, queued deadlines, bounded retries and secret-marker absence. |
| RL-09 **Medium** | Unlimited login attempts/queued evaluations; malformed LIVE account JSON became a 500. | Bounded per-process login throttle (30/minute per address/account, bounded key storage), five active jobs per operator on submission and retry with a transactional PostgreSQL admission lock, bounded credential fields and safe 503 configuration error. Direct backend tests cover admission, expiry, throttling and invalid configuration. This is not a distributed abuse-control service. |
| RL-10 **Medium** | Alternative launcher passed backend keys/configuration to npm/Next and only monitored web after startup. Root Docker context admitted `.env.*` and runtime logs. Cloud override supplied trust only at build time. | Strip backend secrets from frontend install/build/runtime environment; monitor all three application processes and stop siblings on failure. Exclude environment files/logs/caches from context. Bind the public-credential DEMO web port to loopback by default. Optional combined CA bundle is mounted read-only at build and backend runtime, with TLS verification enabled. |
| RL-11 **Medium** | Mobile import validation errors were above the viewport after submit; `toBeVisible` had falsely suggested the message was visible to the user. Muted text lacked normal-text contrast on white. | Focus/scroll the modal error into view and assert `toBeInViewport` in the browser. Darken the muted text token. New real screenshots follow the corrected flows; this is not a WCAG certification. |
| RL-12 **High** | `page.tsx` always submitted a DEMO role as username, so documented custom LIVE usernames could never sign in. Failed status discovery mislabeled the mode DEMO. | LIVE now uses blank username/password fields; only confirmed DEMO receives its role picker and preset. Failed/invalid mode discovery shows UNKNOWN with retry. Three browser contract tests mock only status/auth responses; `test_live_custom_account_and_demo_credentials_are_separate` checks actual backend credentials separately. |
| RL-13 **High** | Session authorization trusted the stored role for eight hours even after a LIVE account was removed, downgraded or had its password rotated. | Bind token lookup to canonical active LIVE account configuration. Any such configuration change revokes all LIVE sessions after the process loads it; editing an environment file requires service recreation. Four direct-backend regressions cover removal, removing all accounts, downgrade and password rotation; logout still clears its cookie after invalid configuration. |
| RL-14 **Medium** | Built-in Uvicorn access lines and default span URL attributes could retain query strings even though the application's structured log omitted them. | Disable query-bearing access logger, suppress HTTP-client URL logs, and replace span URL attributes with the path. An actual mocked HTTP transport verifies endpoint query redaction while operational logging remains available. Regression checks both controls; fresh-process canary verification is recorded below. |
| RL-15 **Medium** | FastAPI's default 422 validation response echoed the entire invalid password when its length exceeded 256 characters. A real HTTP request containing a repeated canary reproduced the exposure. | A global validation handler preserves only documented field locations, messages and types; raw input/context are excluded. `test_login_validation_never_echoes_invalid_password` verifies the actual route response. |

## Repeatable installation and validation

Normal installation requires Python 3.12, uv 0.13.4, Node 24.22.1 and Docker Compose v2. Exact dependencies are in `uv.lock` and `apps/web/package-lock.json`. `uv sync --frozen` and `npm ci` install them; no package is required from another portfolio repository. The offline local launcher deliberately requires previously populated package caches, and reports that prerequisite rather than claiming a clean installation.

A fresh audit installation uses an explicit new project and named volume, leaving existing `genai-release-lab` state untouched:

```sh
IMAGE_TAG=audit docker compose -p audit-release-clean -f compose.yaml -f infra/compose.audit.yaml -f infra/compose.cloud.yaml build --no-cache --pull api web
IMAGE_TAG=audit docker compose -p audit-release-clean -f compose.yaml -f infra/compose.audit.yaml -f infra/compose.cloud.yaml up -d --no-build --wait
# Browser: http://localhost:3203; audit API: 8203; PostgreSQL: 5643.
```

For another blank installation, replace `audit-release-clean` with an unused project name in every command; the recorded audit volume is intentionally retained. Do not delete existing volumes merely to rerun verification.

The cloud override is specific to an HTTPS interception environment and uses the normal public+proxy CA bundle. Omit it on a normal host. `--no-build` in the second command is only startup after a separately recorded rebuild, not rebuild evidence. Audit ports can be changed in the override. All backend services use the same image, avoiding three redundant image builds.

```sh
docker exec audit-release-clean-db-1 createdb -U release release_audit_test
TEST_DATABASE_URL=postgresql+psycopg://release:release@localhost:5643/release_audit_test uv run pytest -q
uv run ruff check services tests migrations
cd apps/web
npm run lint && npm run typecheck && npm test && npm run build
E2E_URL=http://localhost:3203 npm run test:e2e
```

Do not set `TEST_DATABASE_URL` to an application database. Test code recreates its dedicated schema. `docker compose down` preserves named volumes; no audit command deletes preexisting data.

## Model and trust boundaries

Official references reviewed during this audit:

- [OpenAI structured outputs](https://platform.openai.com/docs/guides/structured-outputs): completed/incomplete/refusal handling and schema limitations.
- [Gemini generateContent API](https://ai.google.dev/api/generate-content): `finishReason`, `promptFeedback.blockReason` and safety ratings.
- [Gemini structured output](https://ai.google.dev/gemini-api/docs/structured-output).
- Installed official OpenAI **3.45.0** and Google GenAI **2.34.0** SDK source for serialized requests, custom transports and client ownership.

This application needs structured generation, not streaming or real tool execution. Agent tool calls are evaluation artifacts; tool-name/argument checks do not execute them. OpenAI requests use non-strict JSON schema because arbitrary recorded tool-argument dictionaries do not fit the strict schema subset; local Pydantic validation remains mandatory. Schema serialization and terminal/error handling are tested; acceptance by the live provider/model is **not** verified without credentials.

DEMO never constructs a model provider, even if keys exist. LIVE API/endpoint execution cannot use fixtures. Missing mandatory judges stay pending and block approval. Imported `backend_trace` authenticity depends on the authorized operator's source; checking its role/action is not cryptographic proof or a guarantee against prompt injection. Sessions are mode-scoped, bind the loaded LIVE account configuration, expire after eight hours, and use HttpOnly/SameSite cookies. Secure cookies require HTTPS configuration. Roles are an application allowlist, not SSO.

Endpoint invocation enforces exact operator HTTPS host allowlists, public DNS, IP pinning with original TLS SNI/Host, no redirect and bounded response bytes/time. It uses **direct egress** (`trust_env=False`) because audited proxy CONNECT support is not implemented; an environment requiring an outbound HTTP proxy cannot verify these external endpoint calls without an approved egress design. Provider SDKs use the configured proxy normally. No external endpoint was contacted.

Tokens are included only from validated observations. Costs require dated configured pricing and remain estimates, including their observed-case denominator. Fixtures carry no invented usage. The 60 synthetic examples exercise repeated patterns, not a representative financial benchmark. Manually inspected cases **001, 002, 017, 042, 060**: absent-phone abstention; analyst proposal authorization with integer amounts 16/56/74 SYN; and the cited 260-credit purchase limit all match their supplied original contexts. Development/final splits do not establish generalization.

## Execution record and candidacy

The final code passed **112 backend tests on a dedicated PostgreSQL 17.6 test database**, with **two credential-dependent LIVE smokes skipped**. This includes 70 provider/endpoint tests. Ruff, frontend ESLint/TypeScript, six Vitest tests and the production Next build passed. Local Bicep compilation with v0.48.1 passed without creating resources.

**Fresh Docker rebuild and boot passed.** Both API and web were built with `--no-cache --pull`; after the validation-error correction, the final backend was rebuilt with the same flags and all backend containers recreated. `audit-release-clean_release-data` was newly created during this audit. Alembic revision `001`, migration exit zero, idempotent seed (one named suite, two named policies), non-root application users and all four running-service healthchecks were observed. The prior HTTP503 registry failure is resolved; no old application image was used as rebuild evidence.

Final tested image IDs:

- API/worker/migration: `sha256:175482d01ef8b1f9aa90ea0a38fe2fc151b43ae622d5c112d5f95a6676906447`.
- Web: `sha256:080434b0b3cea0ed40ec3f9d15963cae260a89905bbde7cfe84319f4d6861a31`.

Run `IMAGE_TAG=audit python scripts/audit-recovery.py --cloud` after the documented isolated startup. The actual [compact recovery record](audit-runtime.json) shows **15/1000 running → 23/1000 queued after worker stop → 1000 unique completed results after API/worker restart**, with unchanged input hash and surviving session. This is deterministic processing of synthetic inputs, not an inference benchmark. The script creates and retains a new audit dataset/job and does not remove existing data. Abrupt lease recovery is separately covered by backend tests; the real container restart used graceful shutdown.

**Eleven Playwright scenarios passed against the final container stack**: eight actual-backend journeys and three explicitly mocked browser status/login contracts. The latter establish UI handling, not real provider calls. Actual journeys cover import, reference/regression comparison, source evidence, reviewer approval, mandatory pending evaluation, viewer restrictions, invalid import recovery, policy versioning, incompatible contracts and missing outputs. Keyboard focus and a 390×844 mobile viewport were checked. Real screenshots were refreshed after the final build and visually inspected:

- [Changed contracts excluded](screenshots/audit-incompatible-comparison.png).
- [Pending comparison with denominator](screenshots/audit-pending-comparison.png).
- [Mobile empty state](screenshots/audit-mobile-empty-comparison.png), [loading](screenshots/audit-mobile-loading.png), [visible validation error](screenshots/audit-mobile-validation-error.png), [recovery](screenshots/audit-mobile-recovered.png).

An independent root-agent HTTP review of the final stack observed unauthenticated access 401, hostile-origin mutation 403, viewer dataset writes 403, operator approvals 403, reviewer attempts to approve rejected/pending runs 409, and same-origin OpenAPI 200. Importing regression contents with an arbitrary label still produced **30/60 rejected**; importing reference contents with a mandatory unconfigured judge produced **60/60 pending/inconclusive**. Both persisted after API restart. Independent executable CLI checks returned 0/2/3/4 for approved/rejected/inconclusive/invalid input; unknown arguments also returned 4.

The final container returned a sanitized invalid-password 422. A query canary was absent from actual API logs and console OpenTelemetry spans while correlation/path events remained present. HTTPS retrieval of official Gemini documentation returned 200 inside the final API container using the configured proxy and verified combined CA bundle; this proves public-document TLS connectivity, **not** model-service acceptance.

After verification, the isolated stack was stopped with `down` **without `-v`**, and only the generated audit application images/cache were removed to make room for the other portfolio audit. The original `genai-release-lab_release-data`, earlier `audit-release_release-data` and new `audit-release-clean_release-data` volumes were retained. This report does not claim the application remains running or its generated images remain cached; rebuild with the commands above.

**Ready for portfolio review within the documented local demonstration scope.** Remaining boundaries: no real OpenAI/Gemini call or quality measurement; endpoint transport contracts only and direct-egress requirement; no Azure deployment or hosted GitHub Actions run; no distributed abuse controls, production load, comprehensive penetration test or accessibility certification. Some pale secondary UI labels remain outside the focused contrast correction. The reproduced baseline failures and fifteen findings above justify the review through behavior and evidence, not just a passing count.
