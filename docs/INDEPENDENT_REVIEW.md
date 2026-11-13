> Historical construction review. The subsequent local HTTP checks and corrections are recorded in [audit.md](audit.md). Later hosted CI evidence is recorded separately in [VERIFICATION.md](VERIFICATION.md#hosted-github-actions--2026-11-10-utc); it does not establish real-model quality or repeat every manual review check below.

# Independent local review

Session date: 2026-11-05. All data used in these checks is original and synthetic. No model service was contacted and no cloud resource was created.

- Direct HTTP verification against the running FastAPI/PostgreSQL application: unauthenticated protected reads returned 401; authenticated reads succeeded; an explicitly hostile Origin on a mutation returned 403.
- Azure Bicep compiled successfully with CLI 0.48.1. This validates local template compilation, not Azure deployment, networking, identity, or runtime operation.
- The real Playwright screenshots in `screenshots/` were visually inspected. This is not an accessibility certification.

## Registered endpoint boundary

`tests/test_endpoint_transport_review.py`: four passing MockTransport tests check public-IP pinning with original Host/TLS identity, reject redirect to the metadata address without following it, bound response size, and sanitize malformed JSON failures. DNS validation tests are separate. No external endpoint was contacted.

Review findings addressed by implementation: role evaluation uses expected policy rather than self-declared allowed roles; DEMO sessions cannot cross into LIVE; salted scrypt provisions LIVE passwords; DEMO judges do not call APIs even if credentials exist; mandatory pending evidence blocks approval.

The comparison screenshot shows computed fixture regressions, not measured performance of any model.
