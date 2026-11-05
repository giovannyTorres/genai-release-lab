"""Offline deterministic gates and authenticated server export. No hidden network inference."""

import argparse
import json
from pathlib import Path
from .evaluation import evaluate, summarize, digest
from .exports import export
from .schemas import Case, OutputRecord


def main():
    parser = argparse.ArgumentParser(
        description="Evaluate supplied outputs against a versioned dataset. Exit 0 approved, 2 rejected, 3 inconclusive, 4 invalid input."
    )
    parser.add_argument("--dataset", required=True)
    parser.add_argument("--outputs", required=True)
    parser.add_argument("--threshold", type=float, default=1.0)
    parser.add_argument(
        "--require-llm",
        action="store_true",
        help="Mark mandatory LLM check pending; offline CLI never calls a provider",
    )
    parser.add_argument("--format", choices=["json", "junit", "html"], default="json")
    parser.add_argument("--export")
    args = parser.parse_args()
    try:
        if not 0 <= args.threshold <= 1:
            raise ValueError("threshold must be between zero and one")
        cases = [Case.model_validate(c).model_dump() for c in json.loads(Path(args.dataset).read_text())]
        text = Path(args.outputs).read_text()
        rows = (
            json.loads(text)
            if Path(args.outputs).suffix != ".jsonl"
            else [json.loads(line) for line in text.splitlines() if line.strip()]
        )
        rows = [OutputRecord.model_validate(row).model_dump() for row in rows]
        ids = {c["id"] for c in cases}
        if (
            len(ids) != len(cases)
            or len({r["case_id"] for r in rows}) != len(rows)
            or any(r["case_id"] not in ids for r in rows)
        ):
            raise ValueError("duplicate or unknown case IDs")
        outputs = {r["case_id"]: r["output"] for r in rows}
        results = [evaluate(c, outputs.get(c["id"])) for c in cases]
        if args.require_llm:
            for r in results:
                r["status"] = "pending"
                r["checks"]["llm"] = {
                    "status": "pending",
                    "detail": "Offline CLI does not execute optional model judges",
                }
        summary = summarize(results, args.threshold, len(cases))
        payload = {
            "label": "CLI evaluation",
            "mode": "IMPORTED",
            "source": "local files",
            "input_hash": digest({"cases": cases, "outputs": rows}),
            "total": len(cases),
            "results": results,
            "summary": summary,
            "decision": summary["decision"],
        }
        content, _ = export(payload, args.format)
        if args.export:
            Path(args.export).write_text(content)
        else:
            print(content)
        return {"approved": 0, "rejected": 2, "inconclusive": 3}[summary["decision"]]
    except (ValueError, OSError) as exc:
        print(json.dumps({"error": str(exc)}))
        return 4


if __name__ == "__main__":
    raise SystemExit(main())
