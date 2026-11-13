"""Pure evaluators: only actual expectations and outputs determine results."""

import hashlib
import json
import re
from pydantic import ValidationError
from .schemas import Case, Output

EVALUATOR_VERSION = "deterministic-1.2.0"


def _shown(value, limit=160):
    text = json.dumps(value, sort_keys=True, ensure_ascii=False)
    return text if len(text) <= limit else text[: limit - 1] + "…"


def digest(value):
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()
    ).hexdigest()


def check(ok, detail, failure=""):
    # Failed checks name the concrete mismatch so a reviewer can see what was expected and observed.
    return {"status": "pass" if ok else "fail", "detail": detail if ok or not failure else f"{detail}. {failure}"}


def evaluate(case: dict, raw: dict | None):
    case = Case.model_validate(case)
    checks = {}
    if raw is None:
        return {
            "case_id": case.id,
            "split": case.split,
            "prompt": case.prompt,
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
            "prompt": case.prompt,
            "status": "fail",
            "checks": {"format": check(False, "Output schema validation failed")},
            "output": raw,
            "expected": case.expected,
        }
    expected = case.expected
    if case.kind == "rag":
        allowed = set(expected.get("allowed_citations", []))
        required = set(expected.get("required_citations", []))
        unexpected = sorted(set(output.citations) - allowed)
        missing = sorted(required - set(output.citations))
        checks["references"] = check(
            not unexpected and not missing,
            "Every citation must be allowed and required references present",
            f"Not allowed: {_shown(unexpected)}; missing required: {_shown(missing)}",
        )
        if expected.get("abstain"):
            checks["abstention"] = check(
                output.answer == expected["answer"],
                "Expected explicit abstention",
                f"Expected {_shown(expected['answer'])}; observed {_shown(output.answer)}",
            )
        else:
            absent = [
                x
                for x in expected.get("answer_contains", [])
                if re.search(r"(?<!\w)" + re.escape(x) + r"(?!\w)", output.answer, re.IGNORECASE) is None
            ]
            checks["answer"] = check(
                not absent,
                "Required fixture facts present; this is not a semantic model-quality score",
                f"Missing facts: {_shown(absent)}",
            )
    if case.kind == "agent":
        expected_calls = expected.get("tool_calls", [])
        actual = [c.model_dump() for c in output.tool_calls]
        expected_names, actual_names = [x["name"] for x in expected_calls], [x["name"] for x in actual]
        checks["tools"] = check(
            actual_names == expected_names,
            "Expected ordered tool names",
            f"Expected {_shown(expected_names)}; observed {_shown(actual_names)}",
        )
        position = next(
            (
                i
                for i in range(max(len(actual), len(expected_calls)))
                if i >= len(actual) or i >= len(expected_calls) or digest(actual[i]) != digest(expected_calls[i])
            ),
            None,
        )
        checks["arguments"] = check(
            digest(actual) == digest(expected_calls),
            "Exact typed arguments and tool sequence",
            ""
            if position is None
            else f"First difference at call {position + 1}: expected "
            f"{_shown(expected_calls[position] if position < len(expected_calls) else None)}; "
            f"observed {_shown(actual[position] if position < len(actual) else None)}",
        )
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
        "prompt": case.prompt,
        "status": status,
        "checks": checks,
        "output": output.model_dump(),
        "usage_tokens": output.tokens,
        "case_hash": digest(case.model_dump()),
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


def compare(baseline, candidate, baseline_cases=None, candidate_cases=None):
    """Pair only identical versioned case contracts; disclose unprocessed records."""
    left = {r["case_id"]: r for r in baseline}
    right = {r["case_id"]: r for r in candidate}
    invalid_cases = set()

    def validated_inventory(cases):
        result = {}
        for case in cases or []:
            try:
                result[case["id"]] = Case.model_validate(case).model_dump()
            except ValidationError:
                invalid_cases.add(case["id"])
                result[case["id"]] = case
        return result

    left_cases = validated_inventory(baseline_cases)
    right_cases = validated_inventory(candidate_cases)
    left_ids = set(left_cases) if baseline_cases is not None else set(left)
    right_ids = set(right_cases) if candidate_cases is not None else set(right)
    common = left_ids & right_ids
    incompatible = sorted(
        k
        for k in common
        if k in invalid_cases
        or (left_cases and right_cases and digest(left_cases[k]) != digest(right_cases[k]))
    )
    paired = sorted(common - set(incompatible))

    def status(rows, key):
        return rows.get(key, {}).get("status", "pending")

    return {
        "paired": len(paired),
        "total_baseline": len(left_ids),
        "total_candidate": len(right_ids),
        "missing_baseline": sorted(right_ids - left_ids),
        "missing_candidate": sorted(left_ids - right_ids),
        "unprocessed_baseline": sorted(left_ids - set(left)),
        "unprocessed_candidate": sorted(right_ids - set(right)),
        "incompatible_cases": incompatible,
        "pending_pairs": sum(status(left, k) == "pending" or status(right, k) == "pending" for k in paired),
        "regressions": [
            {"case_id": k, "baseline": status(left, k), "candidate": status(right, k)}
            for k in paired
            if status(left, k) == "pass" and status(right, k) == "fail"
        ],
        "improvements": [
            {"case_id": k, "baseline": status(left, k), "candidate": status(right, k)}
            for k in paired
            if status(left, k) == "fail" and status(right, k) == "pass"
        ],
        # A missing observation is not a failure or a measured quality movement.
        "delta_pass_rate": (
            (sum(status(right, k) == "pass" for k in paired) - sum(status(left, k) == "pass" for k in paired))
            / len(paired)
        )
        if paired and all(status(left, k) != "pending" and status(right, k) != "pending" for k in paired)
        else None,
    }
