> Entries record separate executions and retain their original counts and limitations. See [VERIFICATION.md](VERIFICATION.md) for hosted CI evidence and [audit.md](audit.md) for the historical local audit.

# Progress and decisions

- 2026-11-05: Independent repository created; no pre-existing user files. Chose PostgreSQL single API + worker with Next same-origin web.
- Implemented immutable imports/configurations, hashes, role sessions, durable jobs, deterministic evaluators, optional structured judge, CLI and exports.
- Created60 original cases with development/final split and30 deliberate altered outputs. No version-name scoring conditions.
- Implemented official OpenAI/Gemini SDK integrations and registered endpoint public-IP pinning. DEMO is explicitly inference-free.
- Security review improved expected-policy authorization checks, mode-scoped sessions, salted LIVE password hashing and bounded request bodies.
- Local backend tests, frontend checks, production build, browser workflows and deployment compilation are recorded in VERIFICATION.md after execution.
- Final security regression suite expanded to33 passing tests on real PostgreSQL;2 external LIVE smoke tests intentionally skipped. Independent endpoint transport review adds explicit Host/SNI pinning and redirect/size checks.
- Frontend verified with4 Playwright workflows,3 unit tests, type checking and lint. Mobile overflow found visually and corrected; configuration creation and runtime same-origin proxy finalized for Azure host portability.
- Managed workspace VFS exhausted disk during parallel image builds; unused build caches were cleaned without deleting repository data, and validation was serialized. This was an environment capacity issue, not a skipped application check.
- Final validation: 33 backend tests passed (including real PostgreSQL), 2 LIVE smokes skipped; 6 frontend unit tests, lint, types and production build passed; 5 Playwright workflows passed against the one-command local fallback. Actual desktop/mobile production screenshots captured and reviewed.
- Full application-container rebuild remains externally blocked by the managed proxy returning HTTP503 across PyPI/Docker Hub/GitHub around00:19UTC. No TLS/proxy bypass attempted. `scripts/demo-local.sh` was added and executed successfully using frozen offline caches and a fresh persistent Compose PostgreSQL volume.
- Azure runtime proxy host configuration and non-root Docker file ownership were corrected. Bicep compiled without warnings. No external repository, deployment, paid model call or cloud resource was created.

## Technical audit — 2026-11-05

- Preserved clean initial `main` at `a158658`; audited source, SDK contracts, permissions, imports, comparisons, exports, workers, sessions, frontend and infrastructure.
- Reproduced and corrected fifteen findings, including terminal model status, incompatible comparisons, unsafe test-database selection, session revocation, LIVE login, cancellation and sensitive validation/log output.
- Final 112 backend tests on dedicated PostgreSQL passed, two LIVE smokes skipped; lint/types, six frontend units and production build passed. Eleven final Docker browser scenarios passed (eight actual journeys, three mocked UI contracts).
- Fresh uncached/pulled API and web builds, blank audit volume migration and healthchecks passed. The earlier registry503 blocker is resolved. Final backend rebuilt again after validation-response redaction.
- Real stop/restart retained a 23/1000 checkpoint, session and input hash, then completed1000 unique deterministic cases; record and repeatable script committed.
- Refreshed actual screenshots and compiled Bicep locally. No paid call, external model acceptance, cloud deployment or hosted CI execution claimed.
- Stopped audit stack without deleting volumes and removed only generated audit application images/cache to share limited disk with the other two audits. Original data/history preserved.

## First-run documentation — 2026-11-05

- Added a clone-to-DEMO route with healthcheck waiting, public local roles, exact UI actions, expected synthetic outcomes, persistence and troubleshooting.
- Added `make quickcheck`, reusing five existing behavioral tests and forcing a disposable SQLite database. Verified five passing tests even when an unusable application-style `TEST_DATABASE_URL` was inherited; no external database or inference was used.
- Verified frozen Python installation and the documented console entrypoint: reference export returned exit 0 with 60/60 deterministic cases approved. Compose configuration, Make command expansion and local documentation links validated.
- Documented the full suite, Chromium installation, host-development PostgreSQL setup and credential-free LIVE review boundaries. No application source changed or Docker image rebuild was needed for these documentation/Makefile changes.

## Hosted CI evidence — 2026-11-10 (UTC)

- [Run 42730793669](https://github.com/giovannyTorres/genai-release-lab/actions/runs/42730793669), workflow `verified-demo`, run 11 / attempt 1, completed successfully for all three jobs on PR #2. Recorded head: `d46515fe392a597440cdbb2deb12edf514a397c3`; actual tested checkout: temporary PR merge `a7771f0df521f2204699995166557b326619f21c` into base `115374b4e3738d488b570a1b08430d11198234f6`.
- Backend: **113 passed, 2 LIVE smokes skipped** on PostgreSQL; migrations, Ruff and the expected fixture CLI rejection passed. Frontend: **8 unit tests passed**, lint, types and production build passed. Docker/Playwright: **11 passed**, with eight actual-backend scenarios and three mocked browser mode/authentication contracts.
- These later results supplement the 2026-11-05 local audit's **112 backend / 6 frontend** counts. The old statement that hosted CI had not been executed applies only to that earlier audit; [VERIFICATION.md](VERIFICATION.md#hosted-github-actions--2026-11-10-utc) contains job-level evidence and scope.
- No browser artifact was uploaded: the e2e upload step found no files at its configured path. Manual restart/Bicep checks remain local-audit evidence. OpenAI/Gemini smokes remained skipped, no real-model quality result was measured, and no Azure deployment is established.
