import html
import json
from xml.etree.ElementTree import Element, SubElement, tostring


def export(payload, format):
    payload = dict(payload)
    if "expected_cases" in payload:
        observed = {row["case_id"]: row for row in payload["results"]}
        inventory = payload.pop("expected_cases")
        payload["results"] = [
            observed.get(
                case["id"],
                {
                    "case_id": case["id"],
                    "split": case["split"],
                    "status": "pending",
                    "checks": {"output": {"status": "pending", "detail": "This case has not been evaluated"}},
                    "output": None,
                },
            )
            for case in inventory
        ]
        payload["total"] = len(inventory)
        payload["summary"] = {
            **payload["summary"],
            "passed": sum(r["status"] == "pass" for r in payload["results"]),
            "failed": sum(r["status"] == "fail" for r in payload["results"]),
            "pending": sum(r["status"] == "pending" for r in payload["results"]),
            "total": len(inventory),
        }
    if format == "json":
        return json.dumps(payload, indent=2, default=str), "application/json"
    if format == "junit":
        suite = Element(
            "testsuite",
            name=payload["label"],
            tests=str(payload["total"]),
            failures=str(payload["summary"].get("failed", 0)),
            skipped=str(payload["summary"].get("pending", 0)),
        )
        for row in payload["results"]:
            case = SubElement(suite, "testcase", name=row["case_id"], classname=row["split"])
            if row["status"] in {"fail", "pending"}:
                SubElement(
                    case, "failure" if row["status"] == "fail" else "skipped", message=row["status"]
                ).text = json.dumps(row["checks"])
        return tostring(suite, encoding="unicode"), "application/xml"
    rows = "".join(
        f"<tr><td>{html.escape(r['case_id'])}</td><td>{html.escape(r['split'])}</td><td>{html.escape(r['status'])}</td><td><pre>{html.escape(json.dumps(r['checks'], indent=2))}</pre></td></tr>"
        for r in payload["results"]
    )
    return (
        f"<!doctype html><html lang=en><meta charset=utf-8><title>Release evidence</title><style>body{{font:16px system-ui;margin:3rem;color:#17263c}}table{{border-collapse:collapse;width:100%}}td,th{{text-align:left;border-bottom:1px solid #ccc;padding:1rem}}pre{{white-space:pre-wrap}}</style><h1>{html.escape(payload['label'])}</h1><p>{html.escape(payload['mode'])} · {html.escape(payload['source'])} · {html.escape(payload['decision'])}</p><p>Total: {payload['total']} · Passed: {payload['summary'].get('passed', 0)} · Failed: {payload['summary'].get('failed', 0)} · Pending: {payload['summary'].get('pending', 0)}</p><p>Provenance: {html.escape(payload['input_hash'])}</p><table><tr><th>Case</th><th>Split</th><th>Status</th><th>Evidence</th></tr>{rows}</table></html>",
        "text/html",
    )
