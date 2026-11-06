# Three-arm semantic evaluation

`release_lab.semantic_benchmark` runs the **same versioned cases** against baseline, a reviewed glossary and Auto Ontology. It keeps product calls outside Release Lab's generic endpoint transport; the existing public-HTTPS allowlist, timeout, DEMO restrictions and deterministic release gates are unchanged.

The included example is a **contract fixture**, not measured product/model quality. It deliberately leaves NVIDIA unavailable. Its exit code is **3, inconclusive**. No inference or HTTP request is made:

```powershell
uv run python -m release_lab.semantic_benchmark --plan fixtures/semantic-benchmark/plan.json --output-dir .run/contract-run-01
uv run python -m release_lab.semantic_benchmark --verify --output-dir .run/contract-run-01
```

Use a new output directory per experiment; existing evidence is never overwritten. Codes: 0 completed live comparison passing deterministic checks, 2 completed live comparison with a rejected arm, 3 inconclusive, 4 invalid inputs/artifacts. A passing contract check is not proof of semantic correctness.

## Caller contract

The plan supplies exactly `baseline`, `glossary`, `auto_ontology`. Each uses either a `records` JSONL path or a `command` argv array. Relative paths/cwd are resolved against the plan directory. Commands run without a shell and inherit the local environment; keep credentials in the environment or a protected credential store, never in argv/options/provenance. Plans, dataset and observations are saved as evidence.

Commands declared `execution: "live"` require `--allow-live`. The runner does not acquire credentials, start NVIDIA, or substitute a fixture when a live caller fails. An adapter can report `skipped` when its required service is unavailable. `fixture` and `transport_mock` executions are explicit and never eligible for measured live improvement. `live` is an adapter declaration; a response from a fake transport must be marked `transport_mock`, even if its request uses HTTP.

Example arm, to customize for an actual product adapter:

```json
{
  "name": "glossary",
  "execution": "live",
  "command": ["C:/path/product/.venv/Scripts/python.exe", "C:/path/product/scripts/benchmark_adapter.py"],
  "cwd": "C:/path/product",
  "timeout_seconds": 180,
  "options": {"snapshot_path": "C:/path/frozen-corpus.json"},
  "provenance": {"product_commit": "reviewed commit", "scope": "retrieval_only", "model_config": "reviewed model/config revision"}
}
```

One UTF-8 JSON request goes to stdin per case. Stdout must contain one UTF-8 JSON observation, capped at 2,000,000 bytes. The runner uses binary pipes and forces `PYTHONIOENCODING=utf-8` / `PYTHONUTF8=1` for Python callers, including Windows. Invalid UTF-8 becomes a sanitized per-case adapter error; subsequent cases continue. **Expected answers, citations, SQL rows and split are omitted**, so the adapter must obtain evidence from the product, not the goldens:

```json
{"case":{"id":"case-01","kind":"rag","prompt":"Question","context":"Authorized context"},"arm":"glossary","options":{}}
```

The command must return exactly one JSON `Observation` on stdout. Send diagnostic logs to stderr; failures are sanitized and the runner does not persist stderr. Public typed models are `CallerRequest`, `Observation`, `Plan` in `services/api/release_lab/semantic_benchmark.py`.

```json
{
  "status": "completed",
  "execution": "live",
  "output": {"answer": "650 MXN", "citations": ["actual-document-version-chunk"], "tokens": null},
  "trace": [{"event": "retrieval", "source": "backend", "chunk_ids": ["actual-document-version-chunk"]}],
  "provenance": {"scope": "retrieval_only", "source_snapshot": "actual digest", "ontology_snapshot": "actual digest"}
}
```

`output` uses the existing strict `Output` model; metadata belongs outside it. Completed observations require output. Skipped/error observations cannot carry results. `sql_result` is optional. Recorded input JSONL uses `{"case_id":"...","observation":{...}}`. Missing case records become pending, not failures or successes. Duplicate/unknown IDs or inconsistent execution kinds are rejected.

Choose the same evaluated action contract for all arms. The existing agent evaluator compares ordered tool names and exact arguments; adding a semantic read only to one arm would otherwise create an artificial regression. Preserve complete read/effect traces even when the common evaluated contract covers effects only. A changed case contract requires rerunning every arm.

## Reproducibility and source trust

Freeze the source corpus, dataset split, model configuration and reviewed ontology **before** the run. The plan supports `snapshots` mapping names to `{path, sha256}`; the runner checks the bytes before execution, copies them into generated safe filenames under `inputs/snapshots`, and includes the copies in artifact verification. It checks source files again after all callers finish; a change makes every result pending and blocks measured comparisons. Add product commits, model/configuration revisions, ontology adapter commit, embedding identity/dimensions and certification-set digest to provenance. Source metadata is adapter/operator supplied, not remotely attested. Use the same generator, context budget and data where applicable; record deviations. Retrieval-only results must not be described as answer-generation quality.

Each run saves copied plan/dataset inputs, per-arm `import.jsonl`, complete observations/traces, report and manifest. `manifest.sha256` checks the manifest; its artifact hashes detect local edits. This proves file integrity relative to the recorded digest, not the authenticity of the upstream service. Store/distribute the digest independently when relying on it.

An imported `backend_trace` label is not authorization. If it lacks a matching structured trace event (`event: authorization`, `origin: backend`, matching `actor_role`, `allowed_roles`, `action`, `authorized`), the runner downgrades it to `model_claim`, leaving required authorization pending. Matching events remain **adapter-supplied evidence whose authenticity depends on source trust**. Never synthesize them from a model's answer. The original observation remains in the trace so the normalization is inspectable.

## Results and import boundary

The report includes case results, strata, aggregate/stratum pass/fail/pending, and paired comparisons only when **both arms in that pair** have complete live observations and no mandatory check pending. A complete live baseline/glossary pair can be measured even when NVIDIA is unavailable; its Auto Ontology comparison and the overall three-arm conclusion remain inconclusive. Fixture/mock/missing observations produce no live quality delta for the affected pair. Latency for command callers is measured process wall time, including startup and product work; imported records have unknown latency. p50/p95 are observed nearest-rank percentiles. Tokens remain null when unavailable; known partial tokens are not a total. Cost is unknown rather than estimated from missing usage. Metrics inherit the existing deterministic checks, which do not establish semantic truth.

Nonempty per-arm `import.jsonl` is accepted by the existing `/api/jobs/import` and offline `release-lab` CLI; an entirely skipped arm has an empty file and should not be imported as a run. Supply that arm's exact dataset/configuration, record returned `job_id`, and keep an external receipt linking `job_id` to `manifest.sha256`, outputs digest and dataset/config hashes. **The server currently does not bind or validate this manifest, nor enforce the runner's external SQL checks.** Do not use a plain server import as a SQL release gate; inspect the runner report or implement a first-class server contract before doing so. No provider keys or extra fields are inserted into `Output`.

## Optional SQL result checks

For a case ID, `sql_expectations` in the plan specifies `columns` (`name`, `kind`), `rows`, optional `ordered`, `absolute_tolerance`, `relative_tolerance`. Kinds: text, integer, number, boolean, date, datetime. Observations return `sql_result` with columns/rows only. Numeric tolerance applies to `number`; integers are exact. Datetimes require an offset and compare as instants. Columns and types must match, duplicates are preserved, null differs from zero, order matters only when declared. Unordered numeric rows use full matching instead of greedy pairing. Limit: 500 rows/100 columns per result; aggregate/sampled results need an explicitly matching expectation.

```json
{"sql_expectations":{"case-01":{"columns":[{"name":"amount","kind":"number"}],"rows":[[650]],"absolute_tolerance":0.01}}}
```

Missing SQL output is pending; a valid SQL string or matching total at the wrong grain cannot pass a typed result check. Goldens should come from independently reviewed queries over the frozen snapshot. The runner still applies the case's existing RAG/agent checks as well. SQL checks affect the **external report gate**; the existing server import remains limited as described above.

## Validation

```powershell
uv run pytest tests/test_semantic_benchmark.py -q
uv run ruff check services/api/release_lab/semantic_benchmark.py tests/test_semantic_benchmark.py
```

Tests cover no golden leakage, unavailable/live opt-in, fixture/missing conclusions, hash drift/tampering, unchanged import shape, unsupported authorization claims, and SQL duplicate/grain/null/type/timezone/tolerance behavior. Transport fixtures validate contracts, not NVIDIA acceptance or improvement in a real product.
