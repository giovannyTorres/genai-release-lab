"""Reproducible three-arm experiments. External callers never receive the goldens.

This is a local opt-in runner, not the application's generic endpoint transport.
It does not authenticate imported traces or turn fixtures into live measurements.
"""

import argparse
import hashlib
import json
import math
import subprocess
import sys
import time
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Literal

from pydantic import Field, model_validator

from .evaluation import EVALUATOR_VERSION, compare, digest, evaluate, summarize
from .json_contract import strict_loads
from .schemas import Case, Output, Strict

VERSION = "semantic-benchmark-1"
ARMS = ("baseline", "glossary", "auto_ontology")
Execution = Literal["live", "fixture", "transport_mock"]


class Column(Strict):
    name: str = Field(min_length=1)
    kind: Literal["text", "integer", "number", "boolean", "date", "datetime"]


class SqlResult(Strict):
    columns: list[Column] = Field(min_length=1, max_length=100)
    rows: list[list] = Field(max_length=500)

    @model_validator(mode="after")
    def typed_rows(self):
        if len({c.name for c in self.columns}) != len(self.columns):
            raise ValueError("Duplicate SQL column names")
        for row in self.rows:
            if len(row) != len(self.columns):
                raise ValueError("SQL row width does not match columns")
            for cell, column in zip(row, self.columns):
                if cell is None:
                    continue
                kind = column.kind
                if kind == "integer":
                    valid = type(cell) is int
                elif kind == "number":
                    valid = type(cell) in (int, float) and math.isfinite(cell)
                elif kind == "boolean":
                    valid = type(cell) is bool
                elif kind == "date":
                    try:
                        from datetime import date

                        valid = isinstance(cell, str) and date.fromisoformat(cell).isoformat() == cell
                    except ValueError:
                        valid = False
                elif kind == "datetime":
                    try:
                        parsed = datetime.fromisoformat(cell) if isinstance(cell, str) else None
                        valid = parsed is not None and parsed.tzinfo is not None
                    except ValueError:
                        valid = False
                else:
                    valid = isinstance(cell, str)
                if not valid:
                    raise ValueError("SQL cell does not match declared type")
        return self


class SqlExpectation(SqlResult):
    ordered: bool = False
    absolute_tolerance: float = Field(default=0, ge=0)
    relative_tolerance: float = Field(default=0, ge=0)


class Observation(Strict):
    status: Literal["completed", "skipped", "error"]
    execution: Execution
    output: Output | None = None
    trace: list[dict] = Field(default_factory=list, max_length=1000)
    sql_result: SqlResult | None = None
    detail: str = Field(default="", max_length=1000)
    provenance: dict[str, str] = Field(default_factory=dict)

    @model_validator(mode="after")
    def completed_output(self):
        if self.status == "completed" and self.output is None:
            raise ValueError("Completed observation requires Output")
        if self.status != "completed" and (self.output is not None or self.sql_result is not None):
            raise ValueError("Skipped/error observations cannot carry results")
        return self


class ObservationRecord(Strict):
    case_id: str
    observation: Observation


class CallerCase(Strict):
    id: str
    kind: Literal["rag", "agent"]
    prompt: str
    context: str


class CallerRequest(Strict):
    case: CallerCase
    arm: Literal["baseline", "glossary", "auto_ontology"]
    options: dict = Field(default_factory=dict)


class Arm(Strict):
    name: Literal["baseline", "glossary", "auto_ontology"]
    execution: Execution
    command: list[str] | None = None
    records: str | None = None
    cwd: str | None = None
    timeout_seconds: float = Field(default=120, gt=0, le=3600)
    options: dict = Field(default_factory=dict)
    provenance: dict[str, str] = Field(default_factory=dict)

    @model_validator(mode="after")
    def one_caller(self):
        if (self.command is None) == (self.records is None):
            raise ValueError("Choose exactly one caller: command or records")
        if self.command is not None and (not self.command or any(not s for s in self.command)):
            raise ValueError("Command must be a nonempty argv array")
        return self


class Snapshot(Strict):
    path: str
    sha256: str = Field(pattern=r"^[0-9a-f]{64}$")


class Plan(Strict):
    dataset: str
    arms: list[Arm]
    strata: dict[str, str] = Field(default_factory=dict)
    sql_expectations: dict[str, SqlExpectation] = Field(default_factory=dict)
    snapshots: dict[str, Snapshot] = Field(default_factory=dict)
    provenance: dict[str, str] = Field(default_factory=dict)
    threshold: float = Field(default=1, ge=0, le=1)

    @model_validator(mode="after")
    def three_arms(self):
        if Counter(arm.name for arm in self.arms) != Counter(ARMS):
            raise ValueError("Exactly baseline, glossary and auto_ontology are required")
        return self


def sql_check(expected: SqlExpectation, actual: SqlResult | None) -> dict:
    if actual is None:
        return {"status": "pending", "detail": "SQL result missing"}
    if expected.columns != actual.columns or len(expected.rows) != len(actual.rows):
        return {"status": "fail", "detail": "SQL columns, types or row multiplicity differ"}

    def matches(left, right):
        for a, b, column in zip(left, right, expected.columns):
            if a is None or b is None:
                if a is not b:
                    return False
            elif column.kind == "number":
                if not math.isclose(
                    a, b, abs_tol=expected.absolute_tolerance, rel_tol=expected.relative_tolerance
                ):
                    return False
            elif column.kind == "datetime":
                if datetime.fromisoformat(a) != datetime.fromisoformat(b):
                    return False
            elif a != b:
                return False
        return True

    if expected.ordered:
        passed = all(matches(a, b) for a, b in zip(expected.rows, actual.rows))
    else:
        # Maximum bipartite matching preserves duplicates and avoids greedy tolerance errors.
        assignments = {}

        def assign(left_index, seen):
            for right_index, row in enumerate(actual.rows):
                if right_index in seen or not matches(expected.rows[left_index], row):
                    continue
                seen.add(right_index)
                if right_index not in assignments or assign(assignments[right_index], seen):
                    assignments[right_index] = left_index
                    return True
            return False

        passed = all(assign(index, set()) for index in range(len(expected.rows)))
    return {"status": "pass" if passed else "fail", "detail": "Typed SQL result comparison"}


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read_json(path: Path):
    return strict_loads(path.read_text(encoding="utf-8"))


def resolve(base: Path, value: str) -> Path:
    path = Path(value)
    return path.resolve() if path.is_absolute() else (base / path).resolve()


def safe_observation(arm: Arm, status: str, detail: str) -> Observation:
    return Observation(status=status, execution=arm.execution, detail=detail)


def call_command(arm: Arm, case: dict, base: Path, allow_live: bool) -> tuple[Observation, float | None]:
    if arm.execution == "live" and not allow_live:
        return safe_observation(arm, "skipped", "Live execution requires --allow-live"), None
    request = CallerRequest(
        case=CallerCase(**{k: case[k] for k in ("id", "kind", "prompt", "context")}),
        arm=arm.name,
        options=arm.options,
    ).model_dump()
    start = time.perf_counter()
    try:
        process = subprocess.run(
            arm.command,
            input=json.dumps(request),
            capture_output=True,
            text=True,
            encoding="utf-8",
            cwd=resolve(base, arm.cwd) if arm.cwd else base,
            timeout=arm.timeout_seconds,
            check=False,
            shell=False,
        )
        elapsed = (time.perf_counter() - start) * 1000
        if process.returncode or len(process.stdout) > 2_000_000:
            return safe_observation(arm, "error", "Adapter failed or exceeded output limit"), elapsed
        observation = Observation.model_validate(strict_loads(process.stdout))
        if observation.execution != arm.execution:
            raise ValueError("Execution kind does not match plan")
        return observation, elapsed
    except (OSError, ValueError, subprocess.TimeoutExpired):
        # Never echo command stderr, which can contain credentials or provider bodies.
        return safe_observation(arm, "error", "Adapter timeout, invalid response or execution failure"), (
            time.perf_counter() - start
        ) * 1000


def percentile(values: list[float], fraction: float) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    return ordered[max(0, math.ceil(len(ordered) * fraction) - 1)]


def metrics(rows: list[dict], threshold: float) -> dict:
    values = [row["latency_ms"] for row in rows if row["latency_ms"] is not None]
    tokens = [row["usage_tokens"] for row in rows if row.get("usage_tokens") is not None]
    return {
        **summarize(rows, threshold),
        "p50_ms": percentile(values, 0.5),
        "p95_ms": percentile(values, 0.95),
        "latency_observations": len(values),
        "known_tokens": sum(tokens) if tokens else None,
        "known_token_cases": len(tokens),
        "tokens_complete": len(tokens) == len(rows),
        "cost": None,
    }


def write_json(path: Path, value):
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False, allow_nan=False) + "\n", encoding="utf-8")


def run(plan_path: Path, output_dir: Path, *, allow_live: bool = False) -> dict:
    plan_path = plan_path.resolve()
    base = plan_path.parent
    plan_bytes = plan_path.read_bytes()
    plan = Plan.model_validate(strict_loads(plan_bytes))
    dataset_path = resolve(base, plan.dataset)
    dataset_bytes = dataset_path.read_bytes()
    cases = [Case.model_validate(case).model_dump() for case in strict_loads(dataset_bytes)]
    ids = {case["id"] for case in cases}
    if not 1 <= len(cases) <= 1000 or len(ids) != len(cases):
        raise ValueError("Dataset must contain 1-1000 unique cases")
    if (set(plan.strata) | set(plan.sql_expectations)) - ids:
        raise ValueError("Strata or SQL expectations contain unknown case IDs")
    snapshot_payloads = {}
    source_fingerprints = {
        "plan": (plan_path, hashlib.sha256(plan_bytes).hexdigest()),
        "dataset": (dataset_path, hashlib.sha256(dataset_bytes).hexdigest()),
    }
    for name, snapshot in plan.snapshots.items():
        source_path = resolve(base, snapshot.path)
        payload = source_path.read_bytes()
        if hashlib.sha256(payload).hexdigest() != snapshot.sha256:
            raise ValueError("Snapshot digest mismatch")
        snapshot_payloads[name] = payload
        source_fingerprints[f"snapshot:{name}"] = (source_path, snapshot.sha256)
    records_payloads = {}
    for arm in plan.arms:
        records_path = resolve(base, arm.records) if arm.records else None
        if records_path and records_path.exists():
            payload = records_path.read_bytes()
            records_payloads[arm.name] = payload
            source_fingerprints[f"records:{arm.name}"] = (records_path, hashlib.sha256(payload).hexdigest())
    # Never overwrite evidence from an earlier experiment.
    output_dir.mkdir(parents=True, exist_ok=False)
    inputs_dir = output_dir / "inputs"
    inputs_dir.mkdir()
    (inputs_dir / "plan.json").write_bytes(plan_bytes)
    (inputs_dir / "dataset.json").write_bytes(dataset_bytes)
    artifacts = {
        "inputs/plan.json": sha256(inputs_dir / "plan.json"),
        "inputs/dataset.json": sha256(inputs_dir / "dataset.json"),
    }
    frozen_snapshots = {}
    snapshot_dir = inputs_dir / "snapshots"
    snapshot_dir.mkdir()
    for index, (name, payload) in enumerate(snapshot_payloads.items()):
        snapshot_path = snapshot_dir / f"snapshot-{index:04d}.bin"
        snapshot_path.write_bytes(payload)
        if sha256(snapshot_path) != plan.snapshots[name].sha256:
            raise ValueError("Frozen snapshot digest mismatch")
        artifact = snapshot_path.relative_to(output_dir).as_posix()
        artifacts[artifact] = sha256(snapshot_path)
        frozen_snapshots[name] = {**plan.snapshots[name].model_dump(), "artifact": artifact}
    arms = {}
    manifest_arms = {}
    for arm in plan.arms:
        observed = {}
        records_path = resolve(base, arm.records) if arm.records else None
        if arm.name in records_payloads:
            records_bytes = records_payloads[arm.name]
            records_hash = source_fingerprints[f"records:{arm.name}"][1]
            frozen_records = inputs_dir / f"records-{arm.name}.jsonl"
            frozen_records.write_bytes(records_bytes)
            artifacts[frozen_records.relative_to(output_dir).as_posix()] = records_hash
            for line in records_bytes.decode("utf-8").splitlines():
                if not line.strip():
                    continue
                record = ObservationRecord.model_validate(strict_loads(line))
                if record.case_id in observed or record.case_id not in ids:
                    raise ValueError("Duplicate or unknown observation case ID")
                if record.observation.execution != arm.execution:
                    raise ValueError("Records execution kind does not match plan")
                observed[record.case_id] = record.observation
        results, imports, traces = [], [], []
        for case in cases:
            if arm.command:
                observation, elapsed = call_command(arm, case, base, allow_live)
            else:
                observation = observed.get(
                    case["id"], safe_observation(arm, "skipped", "Observation missing")
                )
                elapsed = None  # Import time is not model or application latency.
            raw = observation.output.model_dump() if observation.output else None
            if (
                raw
                and raw.get("authorization")
                and raw["authorization"]["evidence_source"] == "backend_trace"
            ):
                # The adapter's label is not authentication. Preserve raw trace and only accept
                # structured backend events with matching values, under declared source trust.
                authorization = raw["authorization"]
                corroborated = any(
                    event.get("event") == "authorization"
                    and event.get("origin") == "backend"
                    and all(
                        event.get(key) == authorization[key]
                        for key in ("actor_role", "allowed_roles", "action", "authorized")
                    )
                    for event in observation.trace
                )
                if not corroborated:
                    authorization["evidence_source"] = "model_claim"
            result = evaluate(case, raw)
            if case["id"] in plan.sql_expectations:
                result["checks"]["sql_result"] = sql_check(
                    plan.sql_expectations[case["id"]], observation.sql_result
                )
                statuses = [check["status"] for check in result["checks"].values()]
                result["status"] = (
                    "pending" if "pending" in statuses else "fail" if "fail" in statuses else "pass"
                )
            result.update(
                {
                    "execution": observation.execution,
                    "observation_status": observation.status,
                    "latency_ms": elapsed,
                    "stratum": plan.strata.get(case["id"], "unspecified"),
                }
            )
            results.append(result)
            if raw is not None:
                imports.append({"case_id": case["id"], "output": raw})
            traces.append(
                {
                    "case_id": case["id"],
                    "observation": observation.model_dump(),
                    "latency_ms": elapsed,
                    "authorization_trust": "adapter supplied; not authenticated by runner",
                }
            )
        arm_dir = output_dir / arm.name
        arm_dir.mkdir()
        import_path = arm_dir / "import.jsonl"
        import_path.write_text(
            "".join(json.dumps(row, ensure_ascii=False) + "\n" for row in imports), encoding="utf-8"
        )
        write_json(arm_dir / "trace.json", traces)
        live_complete = all(
            row["execution"] == "live"
            and row["observation_status"] == "completed"
            and row["status"] != "pending"
            for row in results
        )
        arms[arm.name] = {
            "summary": metrics(results, plan.threshold),
            "results": results,
            "strata": {
                stratum: metrics([r for r in results if r["stratum"] == stratum], plan.threshold)
                for stratum in sorted({r["stratum"] for r in results})
            },
            "live_complete": live_complete,
        }
        manifest_arms[arm.name] = {
            "execution": arm.execution,
            "caller": "command" if arm.command else "records",
            "provenance": arm.provenance,
            "source_records_sha256": source_fingerprints.get(f"records:{arm.name}", (None, None))[1],
        }
        for path in (import_path, arm_dir / "trace.json"):
            artifacts[str(path.relative_to(output_dir)).replace("\\", "/")] = sha256(path)
    source_drift = [
        name
        for name, (path, expected) in source_fingerprints.items()
        if not path.exists() or sha256(path) != expected
    ]
    if source_drift:
        for arm in arms.values():
            arm["live_complete"] = False
            for result in arm["results"]:
                result["checks"]["source_integrity"] = {
                    "status": "pending",
                    "detail": "Source changed during run",
                }
                result["status"] = "pending"
            arm["summary"] = metrics(arm["results"], plan.threshold)
            arm["strata"] = {
                stratum: metrics([r for r in arm["results"] if r["stratum"] == stratum], plan.threshold)
                for stratum in sorted({r["stratum"] for r in arm["results"]})
            }
    eligible = all(arm["live_complete"] for arm in arms.values())
    comparisons = {}
    for name in ("glossary", "auto_ontology"):
        pair_eligible = arms["baseline"]["live_complete"] and arms[name]["live_complete"]
        comparisons[name] = {
            "eligible": pair_eligible,
            "reason": "Complete live observations"
            if pair_eligible
            else "Source drift, fixture, mock, missing or pending observations; no measured live improvement for this pair",
            "comparison": compare(arms["baseline"]["results"], arms[name]["results"], cases, cases)
            if pair_eligible
            else None,
        }
    report = {
        "version": VERSION,
        "arms": arms,
        "comparisons": comparisons,
        "conclusion": "measured" if eligible else "inconclusive",
        "source_drift": source_drift,
        "scope": "Deterministic contract/SQL checks; no automatic proof of semantic truth or trace authenticity",
    }
    write_json(output_dir / "report.json", report)
    artifacts["report.json"] = sha256(output_dir / "report.json")
    manifest = {
        "version": VERSION,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "plan_sha256": artifacts["inputs/plan.json"],
        "dataset_file_sha256": artifacts["inputs/dataset.json"],
        "dataset_hash": digest(cases),
        "configuration_hash": digest(
            {"threshold": plan.threshold, "sql_expectations": plan.model_dump()["sql_expectations"]}
        ),
        "evaluator_version": EVALUATOR_VERSION,
        "provenance": plan.provenance,
        "snapshots": frozen_snapshots,
        "arms": manifest_arms,
        "artifacts": artifacts,
        "import_scope": "JSONL contains existing RAG/agent Output only. Server imports do not enforce external SQL checks or this manifest.",
    }
    write_json(output_dir / "manifest.json", manifest)
    (output_dir / "manifest.sha256").write_text(sha256(output_dir / "manifest.json") + "\n", encoding="ascii")
    return report


def verify(output_dir: Path) -> bool:
    manifest_path = output_dir / "manifest.json"
    if sha256(manifest_path) != (output_dir / "manifest.sha256").read_text().strip():
        return False
    manifest = read_json(manifest_path)
    for name, expected in manifest["artifacts"].items():
        path = (output_dir / name).resolve()
        if not path.is_relative_to(output_dir.resolve()) or sha256(path) != expected:
            return False
    return True


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--plan", type=Path)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--allow-live", action="store_true", help="Opt in to local commands declared live")
    parser.add_argument(
        "--verify", action="store_true", help="Verify saved artifact hashes without executing callers"
    )
    args = parser.parse_args()
    try:
        if args.verify:
            return 0 if verify(args.output_dir) else 4
        if not args.plan:
            parser.error("--plan is required unless --verify is set")
        report = run(args.plan, args.output_dir, allow_live=args.allow_live)
        print(json.dumps({"conclusion": report["conclusion"], "output_dir": str(args.output_dir)}))
        if report["conclusion"] == "inconclusive":
            return 3
        return 2 if any(arm["summary"]["decision"] == "rejected" for arm in report["arms"].values()) else 0
    except (OSError, ValueError, KeyError, TypeError):
        print(
            json.dumps({"error": "Invalid plan, observation, snapshot or artifact destination"}),
            file=sys.stderr,
        )
        return 4


if __name__ == "__main__":
    raise SystemExit(main())
