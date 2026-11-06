import json
import sys

import pytest
from pydantic import ValidationError

from release_lab.semantic_benchmark import (
    ARMS,
    Arm,
    Observation,
    Plan,
    SqlExpectation,
    SqlResult,
    call_command,
    run,
    sha256,
    sql_check,
    verify,
)


def case(case_id="synonym"):
    return {
        "id": case_id,
        "kind": "rag",
        "split": "final",
        "prompt": "What is the allowance?",
        "context": "source-v1: Meals are limited to 650 MXN.",
        "expected": {
            "allowed_citations": ["source-v1"],
            "required_citations": ["source-v1"],
            "answer_contains": ["650"],
        },
    }


def observation(answer="650 MXN"):
    return {
        "status": "completed",
        "execution": "fixture",
        "output": {"answer": answer, "citations": ["source-v1"]},
        "trace": [],
    }


def prepare(tmp_path, records=None):
    (tmp_path / "dataset.json").write_text(json.dumps([case(), case("missing")]), encoding="utf-8")
    for name in ARMS:
        rows = records or [{"case_id": "synonym", "observation": observation()}]
        (tmp_path / f"{name}.jsonl").write_text("\n".join(json.dumps(row) for row in rows), encoding="utf-8")
    plan = {
        "dataset": "dataset.json",
        "strata": {"synonym": "paraphrase", "missing": "isolation"},
        "arms": [{"name": name, "execution": "fixture", "records": f"{name}.jsonl"} for name in ARMS],
    }
    path = tmp_path / "plan.json"
    path.write_text(json.dumps(plan), encoding="utf-8")
    return path, plan


def test_fixture_and_missing_never_claim_live_improvement_and_import_stays_compatible(tmp_path):
    path, _ = prepare(tmp_path)
    report = run(path, tmp_path / "run")
    assert report["conclusion"] == "inconclusive"
    assert report["arms"]["baseline"]["summary"]["pending"] == 1
    assert report["arms"]["baseline"]["strata"]["isolation"]["decision"] == "inconclusive"
    assert report["arms"]["baseline"]["summary"]["known_tokens"] is None
    assert report["arms"]["baseline"]["summary"]["p95_ms"] is None
    assert all(value["comparison"] is None for value in report["comparisons"].values())
    imported = json.loads((tmp_path / "run/baseline/import.jsonl").read_text())
    from release_lab.schemas import OutputRecord, Output

    Output.model_validate(OutputRecord.model_validate(imported).output)
    assert set(imported) == {"case_id", "output"}
    assert verify(tmp_path / "run")


def test_tampering_and_output_overwrite_are_detected(tmp_path):
    path, _ = prepare(tmp_path)
    destination = tmp_path / "run"
    run(path, destination)
    (destination / "baseline/import.jsonl").write_text("tampered", encoding="utf-8")
    assert not verify(destination)
    with pytest.raises(FileExistsError):
        run(path, destination)


def test_snapshot_drift_is_rejected_before_execution(tmp_path):
    path, plan = prepare(tmp_path)
    snapshot = tmp_path / "source.json"
    snapshot.write_text('{"revision":1}', encoding="utf-8")
    plan["snapshots"] = {"corpus": {"path": "source.json", "sha256": sha256(snapshot)}}
    path.write_text(json.dumps(plan), encoding="utf-8")
    snapshot.write_text('{"revision":2}', encoding="utf-8")
    with pytest.raises(ValueError, match="digest"):
        run(path, tmp_path / "run")
    assert not (tmp_path / "run").exists()


def test_command_receives_inputs_without_goldens_and_fixture_is_explicit(tmp_path):
    script = tmp_path / "adapter.py"
    script.write_text(
        "import json,sys\nrequest=json.load(sys.stdin)\n"
        "assert set(request['case']) == {'id','kind','prompt','context'}\n"
        "assert request['arm'] == 'baseline'\n"
        "print(json.dumps({'status':'completed','execution':'fixture',"
        "'output':{'answer':'650 MXN','citations':['source-v1']},'trace':[request]}))\n",
        encoding="utf-8",
    )
    arm = Arm(name="baseline", execution="fixture", command=[sys.executable, str(script)])
    result, elapsed = call_command(arm, case(), tmp_path, False)
    assert result.status == "completed" and result.execution == "fixture"
    assert elapsed > 0
    assert "expected" not in result.trace[0]["case"]


def test_spanish_python_caller_forces_utf8_over_parent_cp1252(tmp_path, monkeypatch):
    monkeypatch.setenv("PYTHONIOENCODING", "cp1252")
    monkeypatch.setenv("PYTHONUTF8", "0")
    script = tmp_path / "spanish.py"
    script.write_text(
        "import json,os,sys\nrequest=json.load(sys.stdin)\n"
        "assert request['case']['prompt'] == '¿Cuáles son los viáticos?'\n"
        "assert os.environ['PYTHONIOENCODING'] == 'utf-8'\n"
        "assert os.environ['PYTHONUTF8'] == '1'\n"
        "print(json.dumps({'status':'completed','execution':'fixture',"
        "'output':{'answer':'Los viáticos están aquí: á.'}},ensure_ascii=False))\n",
        encoding="utf-8",
    )
    arm = Arm(name="baseline", execution="fixture", command=[sys.executable, str(script)])
    subject = {**case(), "prompt": "¿Cuáles son los viáticos?"}
    result, _ = call_command(arm, subject, tmp_path, False)
    assert result.status == "completed"
    assert result.output.answer == "Los viáticos están aquí: á."


def test_invalid_utf8_is_per_case_error_and_remaining_cases_finish(tmp_path):
    path, plan = prepare(tmp_path)
    script = tmp_path / "invalid_utf8.py"
    script.write_text(
        "import json,sys\nrequest=json.load(sys.stdin)\n"
        "if request['case']['id'] == 'synonym':\n"
        "    sys.stdout.buffer.write(b'\\xff')\n"
        "else:\n"
        "    print(json.dumps({'status':'completed','execution':'fixture',"
        "'output':{'answer':'650 MXN','citations':['source-v1']}}))\n",
        encoding="utf-8",
    )
    for arm in plan["arms"]:
        arm.pop("records")
        arm["command"] = [sys.executable, str(script)]
    path.write_text(json.dumps(plan), encoding="utf-8")
    destination = tmp_path / "run"
    report = run(path, destination)
    for arm in report["arms"].values():
        first, second = arm["results"]
        assert first["observation_status"] == "error" and first["status"] == "pending"
        assert second["observation_status"] == "completed" and second["status"] == "pass"
    trace = json.loads((destination / "baseline/trace.json").read_text(encoding="utf-8"))
    assert trace[0]["observation"]["detail"] == "Adapter timeout, invalid response or execution failure"
    assert verify(destination)


def test_command_stdout_limit_counts_utf8_bytes(tmp_path):
    script = tmp_path / "oversized.py"
    script.write_text(
        "import json\n"
        "print(json.dumps({'status':'completed','execution':'fixture','output':{'answer':'ok'},"
        "'trace':[{'payload':'á'*1000001}]},ensure_ascii=False))\n",
        encoding="utf-8",
    )
    arm = Arm(name="baseline", execution="fixture", command=[sys.executable, str(script)])
    result, _ = call_command(arm, case(), tmp_path, False)
    assert result.status == "error" and result.output is None
    assert result.detail == "Adapter failed or exceeded output limit"


def test_live_is_opt_in_and_invalid_execution_cannot_be_relabelled(tmp_path):
    arm = Arm(name="auto_ontology", execution="live", command=["never-execute"])
    result, elapsed = call_command(arm, case(), tmp_path, False)
    assert result.status == "skipped" and elapsed is None
    arm = Arm(
        name="baseline",
        execution="live",
        command=[sys.executable, "-c", 'print(\'{"status":"skipped","execution":"transport_mock"}\')'],
    )
    result, _ = call_command(arm, case(), tmp_path, True)
    assert result.status == "error"


def test_claimed_backend_authorization_without_matching_trace_remains_pending(tmp_path):
    agent_case = {
        "id": "authorize",
        "kind": "agent",
        "split": "final",
        "prompt": "Resolve",
        "context": "",
        "expected": {
            "tool_calls": [],
            "authorization_required": True,
            "allowed_roles": ["supervisor"],
            "action": "resolve",
        },
    }
    (tmp_path / "dataset.json").write_text(json.dumps([agent_case]), encoding="utf-8")
    raw = {
        "answer": "Done",
        "authorization": {
            "actor_role": "supervisor",
            "allowed_roles": ["supervisor"],
            "action": "resolve",
            "authorized": True,
            "evidence_source": "backend_trace",
        },
    }
    rows = [
        {
            "case_id": "authorize",
            "observation": {"status": "completed", "execution": "fixture", "output": raw, "trace": []},
        }
    ]
    (tmp_path / "records.jsonl").write_text(json.dumps(rows[0]), encoding="utf-8")
    plan = {
        "dataset": "dataset.json",
        "arms": [{"name": name, "execution": "fixture", "records": "records.jsonl"} for name in ARMS],
    }
    path = tmp_path / "plan.json"
    path.write_text(json.dumps(plan), encoding="utf-8")
    report = run(path, tmp_path / "run")
    result = report["arms"]["baseline"]["results"][0]
    assert result["status"] == "pending"
    assert result["output"]["authorization"]["evidence_source"] == "model_claim"
    trace = json.loads((tmp_path / "run/baseline/trace.json").read_text())
    assert trace[0]["observation"]["output"]["authorization"]["evidence_source"] == "backend_trace"


def test_sql_uses_multiset_grain_types_nulls_and_order():
    columns = [{"name": "group", "kind": "text"}, {"name": "amount", "kind": "number"}]
    expected = SqlExpectation(columns=columns, rows=[["a", 1], ["a", 1], [None, 2]])
    assert (
        sql_check(expected, SqlResult(columns=columns, rows=[[None, 2], ["a", 1], ["a", 1]]))["status"]
        == "pass"
    )
    assert (
        sql_check(expected, SqlResult(columns=columns, rows=[["a", 1], ["b", 1], [None, 2]]))["status"]
        == "fail"
    )
    assert sql_check(expected, SqlResult(columns=columns, rows=[["a", 2], [None, 2]]))["status"] == "fail"
    expected.ordered = True
    assert (
        sql_check(expected, SqlResult(columns=columns, rows=[[None, 2], ["a", 1], ["a", 1]]))["status"]
        == "fail"
    )
    assert sql_check(expected, None)["status"] == "pending"
    with pytest.raises(ValidationError):
        SqlResult(columns=[{"name": "amount", "kind": "integer"}], rows=[[True]])


def test_sql_tolerance_matching_is_not_greedy_and_timezone_is_explicit():
    columns = [{"name": "value", "kind": "number"}]
    expected = SqlExpectation(columns=columns, rows=[[1], [0]], absolute_tolerance=1)
    assert sql_check(expected, SqlResult(columns=columns, rows=[[0], [2]]))["status"] == "pass"
    columns = [{"name": "when", "kind": "datetime"}]
    expected = SqlExpectation(columns=columns, rows=[["2026-11-06T12:00:00+00:00"]])
    assert (
        sql_check(expected, SqlResult(columns=columns, rows=[["2026-11-06T06:00:00-06:00"]]))["status"]
        == "pass"
    )
    with pytest.raises(ValidationError):
        SqlResult(columns=columns, rows=[["2026-11-06T12:00:00"]])


def test_sql_missing_is_inconclusive_even_when_text_passes(tmp_path):
    path, plan = prepare(tmp_path)
    plan["sql_expectations"] = {
        "synonym": {"columns": [{"name": "amount", "kind": "integer"}], "rows": [[650]]}
    }
    path.write_text(json.dumps(plan), encoding="utf-8")
    result = run(path, tmp_path / "run")["arms"]["baseline"]["results"][0]
    assert result["checks"]["answer"]["status"] == "pass"
    assert result["checks"]["sql_result"]["status"] == "pending"
    assert result["status"] == "pending"


def test_plan_requires_identical_named_arms_and_records_do_not_allow_duplicates(tmp_path):
    path, plan = prepare(tmp_path)
    plan["arms"][1]["name"] = "baseline"
    with pytest.raises(ValidationError):
        Plan.model_validate(plan)
    (tmp_path / "baseline.jsonl").write_text(
        "\n".join([json.dumps({"case_id": "synonym", "observation": observation()})] * 2)
    )
    with pytest.raises(ValueError, match="Duplicate"):
        run(path, tmp_path / "run")


def test_observation_rejects_outputs_for_skipped_calls():
    with pytest.raises(ValidationError):
        Observation(status="skipped", execution="fixture", output={"answer": "fabricated"})


def test_pairwise_live_comparison_survives_unavailable_nvidia(tmp_path):
    # Synthetic input tests eligibility logic only; it is not evidence of a live service call.
    path, plan = prepare(tmp_path)
    for name in ARMS:
        plan["arms"][list(ARMS).index(name)]["execution"] = "live"
        rows = []
        for case_id in ("synonym", "missing"):
            observed = observation()
            observed["execution"] = "live"
            if name == "auto_ontology":
                observed = {"status": "skipped", "execution": "live", "detail": "Unavailable"}
            rows.append({"case_id": case_id, "observation": observed})
        (tmp_path / f"{name}.jsonl").write_text("\n".join(json.dumps(row) for row in rows), encoding="utf-8")
    path.write_text(json.dumps(plan), encoding="utf-8")
    report = run(path, tmp_path / "run")
    assert report["conclusion"] == "inconclusive"
    assert report["comparisons"]["glossary"]["eligible"]
    assert report["comparisons"]["glossary"]["comparison"]["paired"] == 2
    assert report["comparisons"]["auto_ontology"]["comparison"] is None


def test_sources_are_frozen_and_mid_run_drift_blocks_measurement(tmp_path, monkeypatch):
    path, plan = prepare(tmp_path)
    source = tmp_path / "source.json"
    original = b'{"policy":"v1"}'
    source.write_bytes(original)
    plan["snapshots"] = {"../../unsafe-label": {"path": "source.json", "sha256": sha256(source)}}
    for arm in plan["arms"]:
        arm.pop("records")
        arm.update({"command": ["unused"], "execution": "live"})
    path.write_text(json.dumps(plan), encoding="utf-8")

    def mutate(*args):
        source.write_bytes(b'{"policy":"v2"}')
        observed = observation()
        observed["execution"] = "live"
        return Observation.model_validate(observed), 1.0

    monkeypatch.setattr("release_lab.semantic_benchmark.call_command", mutate)
    destination = tmp_path / "run"
    report = run(path, destination, allow_live=True)
    assert report["conclusion"] == "inconclusive"
    assert "snapshot:../../unsafe-label" in report["source_drift"]
    assert all(not pair["eligible"] for pair in report["comparisons"].values())
    assert report["arms"]["baseline"]["summary"]["pending"] == 2
    manifest = json.loads((destination / "manifest.json").read_text())
    frozen = destination / manifest["snapshots"]["../../unsafe-label"]["artifact"]
    assert frozen.is_relative_to(destination) and frozen.read_bytes() == original
    assert verify(destination)
    frozen.write_bytes(b"tampered")
    assert not verify(destination)
