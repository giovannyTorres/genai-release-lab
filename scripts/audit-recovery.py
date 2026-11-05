"""Reproduce durable-worker recovery on an isolated audit Compose installation.

Creates one synthetic dataset/job; retains them as reviewable evidence. No inference.
"""

import argparse
import copy
import http.cookiejar
import json
from pathlib import Path
import subprocess
import time
import urllib.error
import urllib.request
import uuid

parser = argparse.ArgumentParser()
parser.add_argument("--base-url", default="http://localhost:3203")
parser.add_argument("--project", default="audit-release-clean")
parser.add_argument("--cloud", action="store_true", help="Use the managed-workspace CA override")
parser.add_argument("--record", type=Path, default=Path("docs/audit-runtime.json"))
args = parser.parse_args()
root = Path(__file__).resolve().parents[1]
compose = ["docker", "compose", "-p", args.project, "-f", "compose.yaml", "-f", "infra/compose.audit.yaml"]
if args.cloud:
    compose += ["-f", "infra/compose.cloud.yaml"]
client = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar()))


def request(path, body=None):
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(
        args.base_url + path, data=data, headers={"Content-Type": "application/json"}
    )
    with client.open(req, timeout=10) as response:
        return json.load(response)


def run(*command):
    result = subprocess.run(compose + list(command), cwd=root, capture_output=True, text=True, timeout=60)
    if result.returncode:
        raise SystemExit(f"Compose {command[0]} failed: {result.stderr[-1000:]}")


def wait_for(predicate, timeout=90):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        try:
            result = predicate()
            if result:
                return result
        except (urllib.error.URLError, TimeoutError):
            pass
        time.sleep(0.1)
    raise SystemExit("Timed out waiting for the audit state transition")


request("/api/auth/login", {"username": "operator", "password": "demo-release"})
assert request("/api/status")["mode"] == "DEMO", "This audit never runs in LIVE"
cases = json.loads((root / "fixtures/cases.json").read_text())
outputs = json.loads((root / "fixtures/reference.json").read_text())
case = cases[16]
output = next(row["output"] for row in outputs if row["case_id"] == case["id"])
inventory, imported = [], []
for number in range(1000):
    entry = copy.deepcopy(case)
    entry["id"] = f"recovery-{number:04d}"
    inventory.append(entry)
    imported.append({"case_id": entry["id"], "output": output})
suite = request(
    "/api/datasets/import",
    {
        "name": "Worker recovery audit " + str(uuid.uuid4()),
        "version": "1",
        "format": "json",
        "content": json.dumps(inventory),
    },
)
config = next(c for c in request("/api/configurations") if c["name"] == "Deterministic gate")
job = request(
    "/api/jobs/import",
    {
        "dataset_id": suite["id"],
        "configuration_id": config["id"],
        "label": "1000 synthetic cases: real container restart",
        "format": "json",
        "content": json.dumps(imported),
    },
)
path = "/api/jobs/" + job["id"]


def in_progress():
    value = request(path)
    return value if value["status"] == "running" and 0 < value["progress"] < value["total"] else None


before = wait_for(in_progress)
run("stop", "worker")
stopped = request(path)
assert stopped["status"] == "queued" and 0 < stopped["progress"] < 1000, stopped["status"]
run("restart", "api")
wait_for(lambda: request("/api/auth/me")["username"] == "operator")
run("up", "-d", "--no-build", "--wait", "worker")


def completed():
    value = request(path)
    return value if value["status"] == "completed" else None


finished = wait_for(completed)
assert finished["progress"] == finished["total"] == len(finished["results"]) == 1000
assert len({row["case_id"] for row in finished["results"]}) == 1000
assert finished["input_hash"] == stopped["input_hash"] == before["input_hash"]
assert finished["decision"] == "approved"
record = {
    "kind": "Actual Docker restart with synthetic deterministic inputs; no model calls",
    "project": args.project,
    "job_id": job["id"],
    "input_hash": finished["input_hash"],
    "observed_running_progress": before["progress"],
    "checkpoint_after_stop": stopped["progress"],
    "checkpoint_status": stopped["status"],
    "api_session_survived_restart": True,
    "final_status": finished["status"],
    "final_progress": finished["progress"],
    "unique_results": len({row["case_id"] for row in finished["results"]}),
    "final_decision": finished["decision"],
}
args.record.write_text(json.dumps(record, indent=2) + "\n")
print(json.dumps(record, indent=2))
