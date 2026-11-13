import asyncio
import copy
import json
import subprocess
import sys
from datetime import timedelta
from pathlib import Path
from release_lab.evaluation import compare, evaluate, summarize
from release_lab.models import Job, SessionLocal, now
from release_lab.worker import claim, process
from release_lab.seed import ROOT

CASES = json.loads((ROOT / "fixtures/cases.json").read_text())
REFERENCE = json.loads((ROOT / "fixtures/reference.json").read_text())
REGRESSION = json.loads((ROOT / "fixtures/regression.json").read_text())


def submit(client, fixture="reference", config=0):
    return client.post(
        "/api/jobs",
        json={
            "dataset_id": client.get("/api/datasets").json()[0]["id"],
            "configuration_id": client.get("/api/configurations").json()[config]["id"],
            "label": "Test " + fixture,
            "source": "fixture",
            "fixture": fixture,
        },
    )


def run_job(id):
    worker = "test-worker"
    assert claim(worker) == id
    asyncio.run(process(id, worker))


def test_fixture_regression_is_calculated():
    good = [evaluate(c, r["output"]) for c, r in zip(CASES, REFERENCE)]
    bad = [evaluate(c, r["output"]) for c, r in zip(CASES, REGRESSION)]
    assert len(CASES) == 60
    assert summarize(good)["decision"] == "approved"
    assert summarize(bad)["decision"] == "rejected"
    assert summarize(bad)["failed"] == 30
    assert len(compare(good, bad)["regressions"]) == 30


def test_authorization_uses_expected_policy():
    case = copy.deepcopy(CASES[1])
    raw = copy.deepcopy(REFERENCE[1]["output"])
    case["expected"]["allowed_roles"] = ["supervisor"]
    assert evaluate(case, raw)["checks"]["authorization"]["status"] == "fail"
    raw["authorization"]["evidence_source"] = "model_claim"
    assert evaluate(case, raw)["checks"]["authorization"]["status"] == "pending"


def test_missing_and_invalid_outputs():
    assert evaluate(CASES[0], None)["status"] == "pending"
    assert evaluate(CASES[0], {"unexpected": "value"})["status"] == "fail"
    assert summarize([], total=60)["decision"] == "inconclusive"
    assert compare([{"case_id": "a", "status": "pass"}], [])["missing_candidate"] == ["a"]


def test_auth_roles_and_origin(client):
    assert client.get("/api/jobs").status_code == 401
    assert (
        client.post("/api/auth/login", json={"username": "operator", "password": "wrong"}).status_code == 401
    )
    client.post("/api/auth/login", json={"username": "viewer", "password": "demo-release"})
    assert submit(client).status_code == 403
    assert client.post("/api/auth/logout", headers={"Origin": "https://evil.example"}).status_code == 403


def test_full_persistent_gate_export_and_approval(operator):
    id = submit(operator).json()["id"]
    run_job(id)
    job = operator.get("/api/jobs/" + id).json()
    assert job["status"] == "completed" and job["decision"] == "approved" and job["summary"]["passed"] == 60
    assert operator.post(f"/api/jobs/{id}/approve", json={"comment": "Ready for release"}).status_code == 403
    operator.post("/api/auth/login", json={"username": "reviewer", "password": "demo-release"})
    assert (
        operator.post(
            f"/api/jobs/{id}/review",
            json={"case_id": "case-001", "verdict": "pass", "comment": "Grounded abstention reviewed"},
        ).status_code
        == 200
    )
    assert operator.post(f"/api/jobs/{id}/approve", json={"comment": "Ready for release"}).status_code == 200
    detail = operator.get(f"/api/jobs/{id}").json()
    assert len(detail["reviews"]) == 1
    assert [(a["actor"], a["comment"]) for a in detail["approvals"]] == [("reviewer", "Ready for release")]
    for fmt in ["json", "junit", "html"]:
        assert operator.get(f"/api/jobs/{id}/export?format={fmt}").status_code == 200
    assert any(a["event"] == "release.approve" for a in operator.get("/api/audit").json())


def test_regression_rejected_and_mandatory_llm_pending(operator, monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    id = submit(operator, "regression").json()["id"]
    run_job(id)
    rejected = operator.get("/api/jobs/" + id).json()
    assert rejected["decision"] == "rejected" and rejected["approvals"] == []
    pending = submit(operator, "reference", 1).json()["id"]
    run_job(pending)
    job = operator.get("/api/jobs/" + pending).json()
    assert job["decision"] == "inconclusive" and job["summary"]["pending"] == 60
    assert "tokens" not in job["summary"]
    operator.post("/api/auth/login", json={"username": "reviewer", "password": "demo-release"})
    assert (
        operator.post(
            f"/api/jobs/{pending}/approve", json={"comment": "Try bypassing pending check"}
        ).status_code
        == 409
    )


def test_resume_after_expired_worker_lease_and_cancel(operator):
    id = submit(operator).json()["id"]
    assert claim("dead-worker") == id
    with SessionLocal.begin() as db:
        job = db.get(Job, id)
        job.lease_until = now() - timedelta(seconds=1)
        job.results = [evaluate(CASES[0], REFERENCE[0]["output"])]
        job.progress = 1
    run_job(id)
    result = operator.get("/api/jobs/" + id).json()
    assert len(result["results"]) == 60 and len({r["case_id"] for r in result["results"]}) == 60
    second = submit(operator).json()["id"]
    assert operator.post(f"/api/jobs/{second}/cancel").status_code == 200
    assert claim("no-work") is None
    assert operator.post(f"/api/jobs/{second}/retry").status_code == 200
    run_job(second)


def test_validated_import_versions_and_mode_separation(operator):
    d = operator.get("/api/datasets").json()[0]
    c = operator.get("/api/configurations").json()[0]
    body = {"name": "Imported", "version": "2", "format": "json", "content": json.dumps(CASES)}
    assert operator.post("/api/datasets/import", json=body).status_code == 201
    assert operator.post("/api/datasets/import", json=body).status_code == 409
    body["version"] = "3"
    body["content"] = json.dumps([CASES[0], CASES[0]])
    assert operator.post("/api/datasets/import", json=body).status_code == 422
    output = operator.post(
        "/api/jobs/import",
        json={
            "dataset_id": d["id"],
            "configuration_id": c["id"],
            "label": "Partial import",
            "format": "jsonl",
            "content": json.dumps(REFERENCE[0]),
        },
    )
    id = output.json()["id"]
    run_job(id)
    assert operator.get("/api/jobs/" + id).json()["summary"]["pending"] == 59
    with SessionLocal.begin() as db:
        db.get(Job, id).mode = "LIVE"
    assert operator.get("/api/jobs/" + id).status_code == 404
    assert all(j["id"] != id for j in operator.get("/api/jobs").json())


def test_cli_exit_codes(tmp_path):
    for file, extra, expected in [
        ("reference", [], 0),
        ("regression", [], 2),
        ("reference", ["--require-llm"], 3),
    ]:
        result = subprocess.run(
            [
                sys.executable,
                "-m",
                "release_lab.cli",
                "--dataset",
                str(ROOT / "fixtures/cases.json"),
                "--outputs",
                str(ROOT / f"fixtures/{file}.json"),
                "--export",
                str(tmp_path / "out.json"),
                *extra,
            ],
            capture_output=True,
        )
        assert result.returncode == expected, result.stderr
        assert Path(tmp_path / "out.json").exists()


def test_live_session_namespace_and_passwords(operator, monkeypatch):
    from release_lab import main
    from release_lab.security import hash_password, verify_password

    assert operator.get("/api/auth/me").status_code == 200
    monkeypatch.setattr(main, "MODE", "LIVE")
    assert operator.get("/api/auth/me").status_code == 401
    encoded = hash_password("an-original-test-password")
    assert encoded != hash_password("an-original-test-password")
    assert verify_password("an-original-test-password", encoded)
    assert not verify_password("incorrect-password", encoded)
    assert not verify_password("password", "sha256$unsupported")


def test_demo_judge_never_invokes_sdk_even_with_configured_key(operator, monkeypatch):
    from release_lab import worker

    monkeypatch.setenv("OPENAI_API_KEY", "test-key-must-not-be-used")

    def prohibited(*args, **kwargs):
        raise AssertionError("DEMO must not call a model provider")

    monkeypatch.setattr(worker, "ModelProvider", prohibited)
    id = submit(operator, "reference", 1).json()["id"]
    run_job(id)
    assert operator.get("/api/jobs/" + id).json()["decision"] == "inconclusive"


def test_request_size_limit_and_expectation_validation(operator):
    assert operator.post("/api/jobs/import", content=b"x" * 2_100_001).status_code == 413
    bad = copy.deepcopy(CASES[1])
    bad["expected"] = {"allowed_roles": "not-a-list"}
    assert (
        operator.post(
            "/api/datasets/import",
            json={"name": "bad", "version": "1", "format": "json", "content": json.dumps([bad])},
        ).status_code
        == 422
    )


def test_pending_authorization_blocks_even_tolerant_gate():
    raw = copy.deepcopy(REFERENCE[1]["output"])
    raw["authorization"] = None
    raw["tool_calls"] = []
    result = evaluate(CASES[1], raw)
    assert result["status"] == "pending"
    assert summarize([result], threshold=0)["decision"] == "inconclusive"


def test_failed_checks_explain_the_concrete_mismatch():
    by_id = {c["id"]: c for c in CASES}
    results = {r["case_id"]: evaluate(by_id[r["case_id"]], r["output"]) for r in REGRESSION}
    rag = results["case-001"]
    assert rag["prompt"] == by_id["case-001"]["prompt"]
    assert rag["checks"]["references"]["status"] == "fail"
    assert 'Not allowed: ["missing-document#invented"]' in rag["checks"]["references"]["detail"]
    failed_tools = [r for r in results.values() if r["checks"].get("arguments", {}).get("status") == "fail"]
    assert failed_tools and all("First difference at call" in r["checks"]["arguments"]["detail"] for r in failed_tools)
    # Passing checks keep the original, stable wording.
    good = evaluate(by_id["case-001"], REFERENCE[0]["output"])
    assert good["checks"]["references"] == {
        "status": "pass",
        "detail": "Every citation must be allowed and required references present",
    }
