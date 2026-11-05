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
