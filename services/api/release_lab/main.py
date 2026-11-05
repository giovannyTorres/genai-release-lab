import hashlib
import hmac
import json
import logging
import os
import secrets
import time
from collections import Counter
from datetime import timedelta
from urllib.parse import urlsplit
from contextlib import asynccontextmanager
from fastapi import Depends, FastAPI, HTTPException, Request, Response
from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor, ConsoleSpanExporter
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from pydantic import BaseModel, ValidationError
from sqlalchemy import select, text
from sqlalchemy.exc import IntegrityError
from .evaluation import compare, digest
from .exports import export
from .models import (
    Audit,
    Configuration,
    Dataset,
    Endpoint,
    Job,
    MODE,
    Review,
    Session,
    SessionLocal,
    now,
    uid,
)
from .providers import readiness
from .security import verify_password
from .schemas import (
    Approval,
    Case,
    ConfigurationInput,
    DatasetImport,
    EndpointInput,
    HumanReview,
    JobInput,
    OutputRecord,
    ResultsImport,
)
from .seed import ROOT, seed
from .endpoints import resolve_public

logging.basicConfig(level=logging.INFO, format="%(message)s")
log = logging.getLogger("release.api")
provider = TracerProvider()
if os.getenv("OTEL_CONSOLE", "false") == "true":
    provider.add_span_processor(BatchSpanProcessor(ConsoleSpanExporter()))
trace.set_tracer_provider(provider)


@asynccontextmanager
async def lifespan(app):
    seed()
    yield


app = FastAPI(
    title="GenAI Release Lab",
    version="1.0.0",
    lifespan=lifespan,
    docs_url="/api/docs",
    openapi_url="/api/openapi.json",
)
FastAPIInstrumentor.instrument_app(app)


@app.middleware("http")
async def context(request: Request, call_next):
    correlation = request.headers.get("x-correlation-id", "")
    request.state.correlation = (
        correlation if correlation.replace("-", "").isalnum() and len(correlation) < 80 else uid()
    )
    start = time.monotonic()
    if request.method not in {"GET", "HEAD", "OPTIONS"}:
        origin = request.headers.get("origin")
        expected = os.getenv("PUBLIC_ORIGIN", "http://localhost:3103")
        if origin and origin != expected:
            return Response("Untrusted request origin", status_code=403)
        if request.headers.get("sec-fetch-site") == "cross-site":
            return Response("Cross-site mutations are forbidden", status_code=403)
        try:
            length = int(request.headers.get("content-length", "0"))
        except ValueError:
            return Response("Invalid content length", status_code=400)
        if length > 2_100_000:
            return Response("Payload too large", status_code=413)
        body = bytearray()
        async for chunk in request.stream():
            body.extend(chunk)
            if len(body) > 2_100_000:
                return Response("Payload too large", status_code=413)
        request._body = bytes(body)
    response = await call_next(request)
    response.headers["x-correlation-id"] = request.state.correlation
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["Cache-Control"] = "no-store"
    log.info(
        json.dumps(
            {
                "event": "http_request",
                "method": request.method,
                "path": request.url.path,
                "status": response.status_code,
                "correlation_id": request.state.correlation,
                "duration_ms": round((time.monotonic() - start) * 1000, 2),
            }
        )
    )
    return response


def database():
    with SessionLocal() as db:
        yield db


def auth(request: Request, db=Depends(database)):
    token = request.cookies.get("release_session")
    row = db.get(Session, hashlib.sha256((MODE + (token or "")).encode()).hexdigest())
    if not row or row.expires_at.replace(tzinfo=now().tzinfo) < now():
        raise HTTPException(401, "Sign in to continue")
    return {"username": row.username, "role": row.role}


def role(*roles):
    def allowed(user=Depends(auth)):
        if user["role"] not in roles:
            raise HTTPException(403, "Your role cannot perform this action")
        return user

    return allowed


def audit(db, request, user, event, target, details=None):
    db.add(
        Audit(
            mode=MODE,
            actor=user["username"],
            event=event,
            target=target,
            details=details or {},
            correlation_id=request.state.correlation,
        )
    )


def owned(db, cls, id):
    item = db.get(cls, id)
    if not item or getattr(item, "mode", MODE) != MODE:
        raise HTTPException(404, "Item not found in the active mode")
    return item


def dataset_dict(item, full=False):
    result = {k: getattr(item, k) for k in ["id", "name", "version", "hash", "created_at"]}
    result.update(case_count=len(item.cases), split_counts=dict(Counter(c["split"] for c in item.cases)))
    if full:
        result["cases"] = item.cases
    return result


def job_dict(job, full=False):
    keys = [
        "id",
        "dataset_id",
        "configuration_id",
        "label",
        "status",
        "progress",
        "total",
        "decision",
        "created_at",
        "mode",
        "source",
        "summary",
        "input_hash",
        "error",
    ]
    result = {k: getattr(job, k) for k in keys}
    if full:
        result["results"] = job.results
        result["provenance"] = {k: v for k, v in job.inputs.items() if k != "outputs"}
    return result


def parse(content, format, model):
    try:
        rows = (
            json.loads(content)
            if format == "json"
            else [json.loads(line) for line in content.splitlines() if line.strip()]
        )
        if not isinstance(rows, list) or not 1 <= len(rows) <= 1000:
            raise ValueError("Expected 1–1000 records")
        records = [model.model_validate(row).model_dump() for row in rows]
        key = "id" if model is Case else "case_id"
        if len({r[key] for r in records}) != len(records):
            raise ValueError("Duplicate record identifiers")
        return records
    except (ValueError, TypeError, ValidationError) as exc:
        raise HTTPException(
            422, "Invalid import: records must match the schema and have unique identifiers"
        ) from exc


class Login(BaseModel):
    username: str
    password: str


@app.get("/api/health")
def health(db=Depends(database)):
    db.execute(text("select 1"))
    return {"status": "ok"}


@app.get("/api/status")
def status():
    live = readiness(os.getenv("MODEL_PROVIDER", "openai"))
    if MODE == "LIVE" and os.getenv("LIVE_USERS_JSON", "{}").strip() in {"", "{}"}:
        live["missing"].append("LIVE_USERS_JSON")
        live["ready"] = False
    return {
        "mode": MODE,
        "live": live,
        "fixture_notice": "Original synthetic fixtures. Fixture outcomes are not model performance.",
    }


@app.post("/api/auth/login")
def login(body: Login, response: Response, db=Depends(database)):
    users = (
        {"operator": "operator", "reviewer": "reviewer", "viewer": "viewer"}
        if MODE == "DEMO"
        else json.loads(os.getenv("LIVE_USERS_JSON", "{}"))
    )
    if MODE == "LIVE":
        record = users.get(body.username, {})
        valid = verify_password(body.password, record.get("password_hash", ""))
        user_role = record.get("role")
    else:
        valid = hmac.compare_digest(body.password, "demo-release")
        user_role = users.get(body.username)
    if not valid or user_role not in {"operator", "reviewer", "viewer"}:
        raise HTTPException(401, "Invalid sign-in details")
    token = secrets.token_urlsafe(32)
    db.add(
        Session(
            token_hash=hashlib.sha256((MODE + token).encode()).hexdigest(),
            username=body.username,
            role=user_role,
            expires_at=now() + timedelta(hours=8),
        )
    )
    db.commit()
    response.set_cookie(
        "release_session",
        token,
        httponly=True,
        secure=os.getenv("COOKIE_SECURE", "false") == "true",
        samesite="strict",
        max_age=28800,
    )
    return {"username": body.username, "role": user_role}


@app.get("/api/auth/me")
def me(user=Depends(auth)):
    return user


@app.post("/api/auth/logout")
def logout(request: Request, response: Response, db=Depends(database)):
    row = db.get(
        Session, hashlib.sha256((MODE + request.cookies.get("release_session", "")).encode()).hexdigest()
    )
    if row:
        db.delete(row)
        db.commit()
    response.delete_cookie("release_session")
    return {"ok": True}


@app.get("/api/datasets")
def datasets(user=Depends(auth), db=Depends(database)):
    return [
        dataset_dict(x)
        for x in db.scalars(select(Dataset).where(Dataset.mode == MODE).order_by(Dataset.created_at))
    ]


@app.get("/api/datasets/{id}")
def dataset(id: str, user=Depends(auth), db=Depends(database)):
    return dataset_dict(owned(db, Dataset, id), True)


@app.post("/api/datasets/import", status_code=201)
def import_dataset(
    body: DatasetImport, request: Request, user=Depends(role("operator")), db=Depends(database)
):
    cases = parse(body.content, body.format, Case)
    item = Dataset(mode=MODE, name=body.name, version=body.version, hash=digest(cases), cases=cases)
    db.add(item)
    try:
        db.flush()
        audit(db, request, user, "dataset.import", item.id, {"hash": item.hash})
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(409, "Dataset name and version already exist") from None
    return dataset_dict(item)


@app.get("/api/configurations")
def configurations(user=Depends(auth), db=Depends(database)):
    return [
        {"id": x.id, "hash": x.hash, **x.spec}
        for x in db.scalars(select(Configuration).where(Configuration.mode == MODE))
    ]


@app.post("/api/configurations", status_code=201)
def configuration(
    body: ConfigurationInput, request: Request, user=Depends(role("operator")), db=Depends(database)
):
    item = Configuration(
        mode=MODE,
        name=body.name,
        version=body.version,
        hash=digest(body.model_dump()),
        spec=body.model_dump(),
    )
    db.add(item)
    try:
        db.flush()
        audit(db, request, user, "configuration.create", item.id)
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(409, "Configuration version already exists") from None
    return {"id": item.id, "hash": item.hash, **item.spec}


def create_job(body, inputs, source, user, request, db):
    dataset = owned(db, Dataset, body.dataset_id)
    config = owned(db, Configuration, body.configuration_id)
    unknown = set(inputs.get("outputs", {})) - {c["id"] for c in dataset.cases}
    if unknown:
        raise HTTPException(422, "Output contains case IDs outside this dataset")
    provenance = {
        "dataset_hash": dataset.hash,
        "configuration_hash": config.hash,
        "evaluator_version": "deterministic-1.0.0",
        **inputs,
    }
    job = Job(
        mode=MODE,
        dataset_id=dataset.id,
        configuration_id=config.id,
        label=body.label,
        source=source,
        input_hash=digest(provenance),
        inputs=provenance,
        total=len(dataset.cases),
        created_by=user["username"],
    )
    db.add(job)
    db.flush()
    audit(db, request, user, "job.create", job.id, {"input_hash": job.input_hash})
    db.commit()
    return job_dict(job)


@app.post("/api/jobs", status_code=201)
def new_job(body: JobInput, request: Request, user=Depends(role("operator")), db=Depends(database)):
    if body.source == "fixture":
        if MODE != "DEMO":
            raise HTTPException(422, "Fixture execution belongs to DEMO only")
        rows = json.loads((ROOT / "fixtures" / f"{body.fixture}.json").read_text())
        inputs = {
            "outputs": {r["case_id"]: r["output"] for r in rows},
            "fixture": body.fixture,
            "provenance": "original synthetic fixture",
        }
    else:
        if MODE != "LIVE":
            raise HTTPException(422, "API and endpoint execution require LIVE mode")
        config = owned(db, Configuration, body.configuration_id)
        if body.source == "api" and not readiness(config.spec["provider"])["ready"]:
            raise HTTPException(422, "Provider credentials are missing; no DEMO fallback")
        if body.source == "endpoint" and not db.get(Endpoint, body.endpoint_id):
            raise HTTPException(422, "Register an authorized endpoint first")
        inputs = {"endpoint_id": body.endpoint_id, "provenance": "LIVE execution"}
    return create_job(body, inputs, body.source, user, request, db)


@app.post("/api/jobs/import", status_code=201)
def import_results(
    body: ResultsImport, request: Request, user=Depends(role("operator")), db=Depends(database)
):
    rows = parse(body.content, body.format, OutputRecord)
    return create_job(
        body,
        {
            "outputs": {r["case_id"]: r["output"] for r in rows},
            "provenance": "operator import; trace authenticity depends on source",
        },
        "import",
        user,
        request,
        db,
    )


@app.get("/api/jobs")
def jobs(user=Depends(auth), db=Depends(database)):
    return [
        job_dict(j) for j in db.scalars(select(Job).where(Job.mode == MODE).order_by(Job.created_at.desc()))
    ]


@app.get("/api/jobs/{id}")
def job(id: str, user=Depends(auth), db=Depends(database)):
    result = job_dict(owned(db, Job, id), True)
    result["reviews"] = [
        {
            "case_id": r.case_id,
            "verdict": r.verdict,
            "comment": r.comment,
            "actor": r.actor,
            "created_at": r.created_at,
        }
        for r in db.scalars(select(Review).where(Review.job_id == id).order_by(Review.created_at))
    ]
    return result


@app.post("/api/jobs/{id}/cancel")
def cancel(id: str, request: Request, user=Depends(role("operator")), db=Depends(database)):
    item = db.scalar(select(Job).where(Job.id == id, Job.mode == MODE).with_for_update())
    if not item:
        raise HTTPException(404, "Job not found")
    if item.status not in {"queued", "running"}:
        raise HTTPException(409, "Only queued or running jobs can be cancelled")
    item.status = "cancelled"
    item.decision = "inconclusive"
    audit(db, request, user, "job.cancel", id)
    db.commit()
    return job_dict(item)


@app.post("/api/jobs/{id}/retry")
def retry(id: str, request: Request, user=Depends(role("operator")), db=Depends(database)):
    item = db.scalar(select(Job).where(Job.id == id, Job.mode == MODE).with_for_update())
    if not item or item.status not in {"failed", "cancelled"}:
        raise HTTPException(409, "Only failed or cancelled jobs can resume")
    item.status = "queued"
    item.error = None
    item.worker_id = None
    audit(db, request, user, "job.retry", id)
    db.commit()
    return job_dict(item)


@app.post("/api/jobs/{id}/review")
def review(
    id: str, body: HumanReview, request: Request, user=Depends(role("reviewer")), db=Depends(database)
):
    item = owned(db, Job, id)
    if item.status != "completed" or body.case_id not in {r["case_id"] for r in item.results}:
        raise HTTPException(409, "Review requires an evaluated case in a completed job")
    db.add(
        Review(
            job_id=id,
            case_id=body.case_id,
            actor=user["username"],
            verdict=body.verdict,
            comment=body.comment,
        )
    )
    audit(db, request, user, "human.review", id, body.model_dump())
    db.commit()
    return {
        "recorded": True,
        "note": "Human correction is append-only; original automated gate evidence is preserved",
    }


@app.post("/api/jobs/{id}/approve")
def approve(id: str, body: Approval, request: Request, user=Depends(role("reviewer")), db=Depends(database)):
    item = owned(db, Job, id)
    if item.status != "completed" or item.decision != "approved":
        raise HTTPException(409, "All mandatory evaluations must pass the configured gate before approval")
    audit(
        db,
        request,
        user,
        "release.approve",
        id,
        {"comment": body.comment, "input_hash": item.input_hash, "results_hash": digest(item.results)},
    )
    db.commit()
    return {"approved": True, "input_hash": item.input_hash}


@app.get("/api/compare")
def comparison(baseline: str, candidate: str, user=Depends(auth), db=Depends(database)):
    a, b = owned(db, Job, baseline), owned(db, Job, candidate)
    return {"baseline_id": a.id, "candidate_id": b.id, **compare(a.results, b.results)}


@app.get("/api/jobs/{id}/export")
def export_job(id: str, format: str = "json", user=Depends(auth), db=Depends(database)):
    if format not in {"json", "junit", "html"}:
        raise HTTPException(422, "Choose json, junit or html")
    content, mime = export(job_dict(owned(db, Job, id), True), format)
    return Response(
        content,
        media_type=mime,
        headers={
            "Content-Disposition": f'attachment; filename="release-{id}.{format}"',
            "Content-Security-Policy": "default-src 'none'; style-src 'unsafe-inline'",
        },
    )


@app.post("/api/endpoints", status_code=201)
async def endpoint(
    body: EndpointInput, request: Request, user=Depends(role("operator")), db=Depends(database)
):
    if MODE != "LIVE":
        raise HTTPException(422, "Endpoint registration is available in LIVE")
    try:
        await resolve_public(body.url)
    except (ValueError, OSError):
        raise HTTPException(422, "Endpoint destination is not permitted") from None
    item = Endpoint(name=body.name, url=body.url, created_by=user["username"])
    db.add(item)
    db.flush()
    audit(db, request, user, "endpoint.register", item.id, {"host": urlsplit(body.url).hostname})
    db.commit()
    return {"id": item.id, "name": item.name, "url": item.url}


@app.get("/api/audit")
def audit_list(user=Depends(role("operator", "reviewer")), db=Depends(database)):
    return [
        {
            "id": a.id,
            "actor": a.actor,
            "event": a.event,
            "target": a.target,
            "details": a.details,
            "correlation_id": a.correlation_id,
            "created_at": a.created_at,
        }
        for a in db.scalars(
            select(Audit).where(Audit.mode == MODE).order_by(Audit.created_at.desc()).limit(200)
        )
    ]
