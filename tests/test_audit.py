"""Defect regressions from the release-candidate audit, independent of fixture names."""

import asyncio
import copy
import json
import os
import subprocess
import sys
from xml.etree import ElementTree

import pytest
from pydantic import ValidationError

from release_lab.evaluation import compare, evaluate
from release_lab.models import Configuration, Job, SessionLocal
from release_lab.schemas import Case
from release_lab.seed import ROOT
from release_lab.worker import RunAborted, claim, process, while_owned

CASES = json.loads((ROOT / "fixtures/cases.json").read_text())
OUTPUTS = json.loads((ROOT / "fixtures/reference.json").read_text())


def submit(client, dataset=None):
    return client.post(
        "/api/jobs",
        json={
            "dataset_id": dataset or client.get("/api/datasets").json()[0]["id"],
            "configuration_id": client.get("/api/configurations").json()[0]["id"],
            "label": "Independent audit run",
            "source": "fixture",
            "fixture": "reference",
        },
    )


def finish(job_id):
    assert claim("audit-worker") == job_id
    asyncio.run(process(job_id, "audit-worker"))


def test_comparison_excludes_changed_contract_and_keeps_unprocessed_denominator(operator):
    left = submit(operator).json()["id"]
    right = submit(operator).json()["id"]
    pending = operator.get("/api/compare", params={"baseline": left, "candidate": right}).json()
    assert pending["total_baseline"] == pending["total_candidate"] == pending["paired"] == 60
    assert len(pending["unprocessed_baseline"]) == len(pending["unprocessed_candidate"]) == 60
    assert pending["pending_pairs"] == 60 and pending["delta_pass_rate"] is None
    finish(left)
    finish(right)
    changed = copy.deepcopy(CASES)
    changed[0]["context"] = "A different source changes the experimental case contract."
    new_dataset = operator.post(
        "/api/datasets/import",
        json={
            "name": "Changed inputs",
            "version": "1",
            "format": "json",
            "content": json.dumps(changed),
        },
    ).json()["id"]
    third = submit(operator, new_dataset).json()["id"]
    finish(third)
    actual = operator.get("/api/compare", params={"baseline": left, "candidate": third}).json()
    assert actual["paired"] == 59 and actual["incompatible_cases"] == [CASES[0]["id"]]
    assert actual["delta_pass_rate"] == 0


def test_pending_is_not_reported_as_measured_regression():
    actual = compare([{"case_id": "a", "status": "pass"}], [{"case_id": "a", "status": "pending"}])
    assert actual["regressions"] == [] and actual["pending_pairs"] == 1
    assert actual["delta_pass_rate"] is None


@pytest.mark.parametrize("mutation", ["empty_facts", "contradictory_citations", "empty_abstention"])
def test_expectations_cannot_vacuously_pass(mutation):
    case = copy.deepcopy(next(c for c in CASES if c["kind"] == "rag" and not c["expected"].get("abstain")))
    if mutation == "empty_facts":
        case["expected"]["answer_contains"] = []
    elif mutation == "contradictory_citations":
        case["expected"]["required_citations"] = ["absent-source"]
    else:
        case["expected"].update(abstain=True, answer="", required_citations=[])
    with pytest.raises(ValidationError):
        Case.model_validate(case)


def test_tool_argument_boolean_does_not_equal_integer():
    index = next(i for i, c in enumerate(CASES) if c["kind"] == "agent")
    case = copy.deepcopy(CASES[index])
    raw = copy.deepcopy(OUTPUTS[index]["output"])
    case["expected"]["tool_calls"][0]["arguments"] = {"amount": 1}
    raw["tool_calls"][0]["arguments"] = {"amount": True}
    assert evaluate(case, raw)["checks"]["arguments"]["status"] == "fail"


@pytest.mark.parametrize(
    "content", ['[{"case_id":"a","case_id":"b","output":{}}]', '[{"case_id":"a","output":{"tokens":NaN}}]']
)
def test_ambiguous_or_nonfinite_json_is_rejected_atomically(operator, content):
    before = len(operator.get("/api/jobs").json())
    body = {
        "dataset_id": operator.get("/api/datasets").json()[0]["id"],
        "configuration_id": operator.get("/api/configurations").json()[0]["id"],
        "label": "ambiguous import",
        "format": "json",
        "content": content,
    }
    assert operator.post("/api/jobs/import", json=body).status_code == 422
    assert len(operator.get("/api/jobs").json()) == before


def test_unvalidated_usage_cannot_crash_worker_or_create_cost(operator):
    raw = copy.deepcopy(OUTPUTS[0])
    raw["output"]["tokens"] = "not-an-integer"
    body = {
        "dataset_id": operator.get("/api/datasets").json()[0]["id"],
        "configuration_id": operator.get("/api/configurations").json()[0]["id"],
        "label": "malformed usage",
        "format": "json",
        "content": json.dumps([raw]),
    }
    job_id = operator.post("/api/jobs/import", json=body).json()["id"]
    finish(job_id)
    result = operator.get("/api/jobs/" + job_id).json()
    assert result["status"] == "completed" and result["summary"]["failed"] == 1
    assert result["summary"]["pending"] == 59 and "tokens" not in result["summary"]


def test_partial_cancelled_export_contains_every_expected_case(operator):
    job_id = submit(operator).json()["id"]
    operator.post("/api/jobs/" + job_id + "/cancel")
    xml = ElementTree.fromstring(operator.get(f"/api/jobs/{job_id}/export?format=junit").text)
    assert xml.attrib["tests"] == xml.attrib["skipped"] == "60"
    assert len(xml.findall("testcase")) == len(xml.findall("testcase/skipped")) == 60
    html = operator.get(f"/api/jobs/{job_id}/export?format=html").text
    assert "Total: 60" in html and "Pending: 60" in html
    with SessionLocal.begin() as db:
        db.get(Job, job_id).label = '<script>alert("import")</script>'
    safe = operator.get(f"/api/jobs/{job_id}/export?format=html").text
    assert "<script>" not in safe and "&lt;script&gt;" in safe


def test_versioned_input_tampering_fails_closed(operator):
    job_id = submit(operator).json()["id"]
    with SessionLocal.begin() as db:
        config = db.get(Configuration, db.get(Job, job_id).configuration_id)
        config.spec = {**config.spec, "threshold": 0.0}
    finish(job_id)
    actual = operator.get("/api/jobs/" + job_id).json()
    assert actual["status"] == "failed" and actual["decision"] == "inconclusive"
    assert actual["results"] == []


@pytest.mark.asyncio
async def test_cancel_stops_inflight_operation(operator):
    job_id = submit(operator).json()["id"]
    assert claim("audit-worker") == job_id
    started, cancelled = asyncio.Event(), asyncio.Event()

    async def blocked():
        started.set()
        try:
            await asyncio.Future()
        finally:
            cancelled.set()

    task = asyncio.create_task(while_owned(blocked(), job_id, "audit-worker"))
    await started.wait()
    assert operator.post("/api/jobs/" + job_id + "/cancel").status_code == 200
    with pytest.raises(RunAborted):
        await asyncio.wait_for(task, timeout=1)
    assert cancelled.is_set()


def test_login_expiry_and_job_admission_limits(operator):
    for _ in range(5):
        assert submit(operator).status_code == 201
    assert submit(operator).status_code == 429
    for _ in range(29):
        assert (
            operator.post("/api/auth/login", json={"username": "operator", "password": "wrong"}).status_code
            == 401
        )
    assert (
        operator.post("/api/auth/login", json={"username": "operator", "password": "wrong"}).status_code
        == 429
    )


def test_cli_hash_covers_rules_and_invalid_input_exit(tmp_path):
    hashes = []
    for threshold in ["1.0", "0.5"]:
        out = tmp_path / "run.json"
        command = [
            sys.executable,
            "-m",
            "release_lab.cli",
            "--dataset",
            str(ROOT / "fixtures/cases.json"),
            "--outputs",
            str(ROOT / "fixtures/reference.json"),
            "--threshold",
            threshold,
            "--export",
            str(out),
        ]
        completed = subprocess.run(command, capture_output=True)
        assert completed.returncode == 0, completed.stderr
        hashes.append(json.loads(out.read_text())["input_hash"])
    assert hashes[0] != hashes[1]
    invalid = tmp_path / "invalid.json"
    invalid.write_text("null")
    completed = subprocess.run(
        [
            sys.executable,
            "-m",
            "release_lab.cli",
            "--dataset",
            str(ROOT / "fixtures/cases.json"),
            "--outputs",
            str(invalid),
        ],
        capture_output=True,
    )
    assert completed.returncode == 4 and b"Traceback" not in completed.stderr


def test_test_runner_refuses_regular_database_before_connecting():
    env = {**os.environ, "TEST_DATABASE_URL": "postgresql+psycopg://invalid:invalid@127.0.0.1:1/release"}
    result = subprocess.run(
        [sys.executable, "-m", "pytest", "--collect-only", "-q"], env=env, capture_output=True
    )
    assert result.returncode != 0 and b"ending in _test" in result.stderr


def test_expired_session_and_invalid_live_config_fail_safely(operator, monkeypatch):
    from datetime import timedelta
    from release_lab import main
    from release_lab.models import Session, now

    with SessionLocal.begin() as db:
        for row in db.query(Session):
            row.expires_at = now() - timedelta(seconds=1)
    assert operator.get("/api/jobs").status_code == 401
    monkeypatch.setattr(main, "MODE", "LIVE")
    monkeypatch.setenv("LIVE_USERS_JSON", '{"private-config-should-not-echo":')
    result = operator.post("/api/auth/login", json={"username": "operator", "password": "wrong"})
    assert result.status_code == 503 and "private-config" not in result.text
    assert main.status()["live"]["ready"] is False


@pytest.mark.asyncio
async def test_graceful_worker_stop_preserves_progress_and_relinquishes_lease(operator, monkeypatch):
    from release_lab import worker
    from release_lab.evaluation import digest

    job_id = submit(operator).json()["id"]
    assert claim("audit-worker") == job_id
    with SessionLocal.begin() as db:
        item = db.get(Job, job_id)
        item.source = "api"
        item.inputs = {**item.inputs, "source": "api"}
        item.input_hash = digest(item.inputs)
        item.results = [evaluate(CASES[0], OUTPUTS[0]["output"])]
        item.progress = 1
    started, closed = asyncio.Event(), asyncio.Event()

    class BlockedProvider:
        def __init__(self, *args):
            pass

        async def structured(self, *args):
            started.set()
            await asyncio.Future()

        async def close(self):
            closed.set()

    monkeypatch.setattr(worker, "MODE", "LIVE")
    monkeypatch.setattr(worker, "ModelProvider", BlockedProvider)
    task = asyncio.create_task(process(job_id, "audit-worker"))
    await started.wait()
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task
    with SessionLocal() as db:
        item = db.get(Job, job_id)
        assert item.status == "queued" and item.worker_id is None and item.progress == 1
        assert len(item.results) == 1
    assert closed.is_set()


def test_unexpected_worker_failure_is_bounded_and_redacted(operator, monkeypatch, caplog):
    from release_lab import worker

    job_id = submit(operator).json()["id"]

    def broken(*args):
        raise RuntimeError("private-value-must-not-appear")

    monkeypatch.setattr(worker, "evaluate", broken)
    finish(job_id)
    result = operator.get("/api/jobs/" + job_id).json()
    assert result["status"] == "failed" and result["decision"] == "inconclusive"
    assert "private-value" not in result["error"] and "private-value" not in caplog.text


def test_query_is_removed_from_trace_and_access_logging():
    import logging
    from release_lab.main import safe_request_span

    class Span:
        def __init__(self):
            self.attributes = {"http.url": "https://example.test/api/health?key=private-query"}

        def is_recording(self):
            return True

        def set_attribute(self, key, value):
            self.attributes[key] = value

    span = Span()
    safe_request_span(span, {"path": "/api/health", "query_string": b"key=private-query"})
    assert all("private-query" not in str(v) for v in span.attributes.values())
    assert logging.getLogger("uvicorn.access").disabled


def test_expected_numeric_fact_does_not_match_a_different_number():
    raw = copy.deepcopy(OUTPUTS[16]["output"])
    raw["answer"] = "The purchase limit is 1260 credits."
    assert evaluate(CASES[16], raw)["checks"]["answer"]["status"] == "fail"


def test_live_custom_account_and_demo_credentials_are_separate(client, monkeypatch):
    from release_lab import main
    from release_lab.security import hash_password

    monkeypatch.setattr(main, "MODE", "LIVE")
    monkeypatch.setenv(
        "LIVE_USERS_JSON",
        json.dumps({"operator-live": {"role": "operator", "password_hash": hash_password("live-test-pass")}}),
    )
    assert (
        client.post("/api/auth/login", json={"username": "operator", "password": "demo-release"}).status_code
        == 401
    )
    signed_in = client.post(
        "/api/auth/login", json={"username": "operator-live", "password": "live-test-pass"}
    )
    assert signed_in.status_code == 200 and signed_in.json()["username"] == "operator-live"
    assert client.get("/api/auth/me").json()["role"] == "operator"
    assert client.get("/api/datasets").json() == []  # DEMO records never become LIVE data.


def test_cli_usage_error_cannot_be_confused_with_rejected_gate():
    result = subprocess.run(
        [sys.executable, "-m", "release_lab.cli", "--unknown-argument"], capture_output=True
    )
    assert result.returncode == 4


def test_concurrent_job_admission_cannot_exceed_postgres_limit(operator):
    from concurrent.futures import ThreadPoolExecutor
    from release_lab.models import engine

    if engine.dialect.name != "postgresql":
        pytest.skip("Transactional admission must be checked on PostgreSQL")
    with ThreadPoolExecutor(max_workers=8) as pool:
        codes = list(pool.map(lambda _: submit(operator).status_code, range(8)))
    assert codes.count(201) == 5 and codes.count(429) == 3
    assert len(operator.get("/api/jobs").json()) == 5


def test_retry_cannot_bypass_active_job_limit(operator):
    cancelled = submit(operator).json()["id"]
    assert operator.post(f"/api/jobs/{cancelled}/cancel").status_code == 200
    for _ in range(5):
        assert submit(operator).status_code == 201
    assert operator.post(f"/api/jobs/{cancelled}/retry").status_code == 429
    assert operator.get(f"/api/jobs/{cancelled}").json()["status"] == "cancelled"


def test_login_validation_never_echoes_invalid_password(client):
    marker = "AUDIT_INVALID_PASSWORD_" * 15
    response = client.post("/api/auth/login", json={"username": "operator", "password": marker})
    assert response.status_code == 422
    assert marker not in response.text
    assert response.json()["detail"][0]["loc"] == ["body", "password"]
    assert set(response.json()["detail"][0]) == {"loc", "msg", "type"}


@pytest.mark.parametrize("change", ["remove", "remove_all", "downgrade", "password"])
def test_live_account_configuration_change_revokes_sessions(client, monkeypatch, change):
    from release_lab import main
    from release_lab.security import hash_password

    monkeypatch.setattr(main, "MODE", "LIVE")
    users = {"operator-live": {"role": "operator", "password_hash": hash_password("live-test-pass")}}
    monkeypatch.setenv("LIVE_USERS_JSON", json.dumps(users))
    assert (
        client.post(
            "/api/auth/login", json={"username": "operator-live", "password": "live-test-pass"}
        ).status_code
        == 200
    )
    if change == "remove":
        users = {"viewer-live": {"role": "viewer", "password_hash": hash_password("viewer-test-pass")}}
    elif change == "remove_all":
        users = {}
    elif change == "downgrade":
        users["operator-live"]["role"] = "viewer"
    else:
        users["operator-live"]["password_hash"] = hash_password("changed-password")
    monkeypatch.setenv("LIVE_USERS_JSON", json.dumps(users))
    assert client.get("/api/auth/me").status_code == 401
    assert client.post("/api/configurations", json={"name": "Forbidden", "version": "1"}).status_code == 401
    assert client.post("/api/auth/logout").status_code == 200
    assert "release_session" not in client.cookies
