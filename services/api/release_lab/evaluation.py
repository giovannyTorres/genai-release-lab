"""Pure evaluators: only actual expectations and outputs determine results."""

import hashlib
import json
from pydantic import ValidationError
from .schemas import Case, Output

EVALUATOR_VERSION = "deterministic-1.0.0"


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def check(ok, detail):
    return {"status": "pass" if ok else "fail", "detail": detail}


def evaluate(case: dict, raw: dict | None):
    case = Case.model_validate(case)
    checks = {}
    if raw is None:
        return {
            "case_id": case.id,
            "split": case.split,
            "status": "pending",
            "checks": {"output": {"status": "pending", "detail": "Output missing"}},
            "output": None,
            "expected": case.expected,
        }
    try:
        output = Output.model_validate(raw)
        checks["format"] = check(True, "Validated Output schema")
    except ValidationError:
        return {
            "case_id": case.id,
            "split": case.split,
            "status": "fail",
            "checks": {"format": check(False, "Output schema validation failed")},
            "output": raw,
            "expected": case.expected,
        }
    expected = case.expected
    if case.kind == "rag":
        allowed = set(expected.get("allowed_citations", []))
        required = set(expected.get("required_citations", []))
        checks["references"] = check(
            set(output.citations) <= allowed and required <= set(output.citations),
            "Every citation must be allowed and required references present",
        )
        if expected.get("abstain"):
            checks["abstention"] = check(output.answer == expected["answer"], "Expected explicit abstention")
        else:
            checks["answer"] = check(
                all(x.casefold() in output.answer.casefold() for x in expected.get("answer_contains", [])),
                "Required fixture facts present; this is not a semantic model-quality score",
            )
    if case.kind == "agent":
        expected_calls = expected.get("tool_calls", [])
        actual = [c.model_dump() for c in output.tool_calls]
        checks["tools"] = check(
            [x["name"] for x in actual] == [x["name"] for x in expected_calls], "Expected ordered tool names"
        )
        checks["arguments"] = check(actual == expected_calls, "Exact typed arguments and tool sequence")
        if expected.get("authorization_required"):
            auth = output.authorization
            if not auth or auth.evidence_source != "backend_trace":
                checks["authorization"] = {
                    "status": "pending",
                    "detail": "No trusted backend authorization trace supplied; a model claim is insufficient",
                }
            else:
                checks["authorization"] = check(
                    auth.actor_role in expected.get("allowed_roles", [])
                    and set(auth.allowed_roles) == set(expected.get("allowed_roles", []))
                    and auth.authorized
                    and auth.action == expected.get("action"),
                    "Imported backend trace role, action, authorization checked; authenticity depends on source trust",
                )
    statuses = [v["status"] for v in checks.values()]
    status = "pending" if "pending" in statuses else "fail" if "fail" in statuses else "pass"
    return {
        "case_id": case.id,
        "split": case.split,
        "status": status,
        "checks": checks,
        "output": raw,
        "expected": expected,
    }


def summarize(results, threshold=1.0, total=None):
    total = len(results) if total is None else total
    passed = sum(r["status"] == "pass" for r in results)
    failed = sum(r["status"] == "fail" for r in results)
    pending = total - passed - failed
    # Any missing mandatory evaluation blocks approval, even if observed failures also exist.
    decision = (
        "inconclusive" if pending or not total else "approved" if passed / total >= threshold else "rejected"
    )
    return {
        "passed": passed,
        "failed": failed,
        "pending": pending,
        "total": total,
        "pass_rate": passed / total if total else None,
        "decision": decision,
        "splits": {
            split: {
                "passed": sum(r["status"] == "pass" and r["split"] == split for r in results),
                "total": sum(r["split"] == split for r in results),
            }
            for split in ["development", "final"]
        },
    }


def compare(baseline, candidate):
    left = {r["case_id"]: r for r in baseline}
    right = {r["case_id"]: r for r in candidate}
    paired = sorted(left.keys() & right.keys())
    return {
        "paired": len(paired),
        "total_baseline": len(left),
        "total_candidate": len(right),
        "missing_baseline": sorted(right.keys() - left.keys()),
        "missing_candidate": sorted(left.keys() - right.keys()),
        "regressions": [
            {"case_id": k, "baseline": left[k]["status"], "candidate": right[k]["status"]}
            for k in paired
            if left[k]["status"] == "pass" and right[k]["status"] != "pass"
        ],
        "improvements": [
            {"case_id": k, "baseline": left[k]["status"], "candidate": right[k]["status"]}
            for k in paired
            if left[k]["status"] != "pass" and right[k]["status"] == "pass"
        ],
        "delta_pass_rate": (
            sum(right[k]["status"] == "pass" for k in paired)
            - sum(left[k]["status"] == "pass" for k in paired)
        )
        / len(paired)
        if paired
        else None,
    }
