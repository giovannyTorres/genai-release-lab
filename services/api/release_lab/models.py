import os
import uuid
from datetime import datetime, timezone
from sqlalchemy import JSON, DateTime, ForeignKey, Integer, String, UniqueConstraint, create_engine
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, sessionmaker


def uid():
    return str(uuid.uuid4())


def now():
    return datetime.now(timezone.utc)


class Base(DeclarativeBase):
    pass


class Dataset(Base):
    __tablename__ = "datasets"
    __table_args__ = (UniqueConstraint("mode", "name", "version"),)
    id: Mapped[str] = mapped_column(String, primary_key=True, default=uid)
    mode: Mapped[str] = mapped_column(String)
    name: Mapped[str] = mapped_column(String)
    version: Mapped[str] = mapped_column(String)
    hash: Mapped[str] = mapped_column(String)
    cases: Mapped[list] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


class Configuration(Base):
    __tablename__ = "configurations"
    __table_args__ = (UniqueConstraint("mode", "name", "version"),)
    id: Mapped[str] = mapped_column(String, primary_key=True, default=uid)
    mode: Mapped[str] = mapped_column(String)
    name: Mapped[str] = mapped_column(String)
    version: Mapped[str] = mapped_column(String)
    hash: Mapped[str] = mapped_column(String)
    spec: Mapped[dict] = mapped_column(JSON)


class Job(Base):
    __tablename__ = "jobs"
    id: Mapped[str] = mapped_column(String, primary_key=True, default=uid)
    mode: Mapped[str] = mapped_column(String, index=True)
    dataset_id: Mapped[str] = mapped_column(ForeignKey("datasets.id"))
    configuration_id: Mapped[str] = mapped_column(ForeignKey("configurations.id"))
    label: Mapped[str] = mapped_column(String)
    status: Mapped[str] = mapped_column(String, default="queued")
    source: Mapped[str] = mapped_column(String)
    input_hash: Mapped[str] = mapped_column(String)
    inputs: Mapped[dict] = mapped_column(JSON)
    results: Mapped[list] = mapped_column(JSON, default=list)
    progress: Mapped[int] = mapped_column(Integer, default=0)
    total: Mapped[int] = mapped_column(Integer)
    decision: Mapped[str] = mapped_column(String, default="inconclusive")
    summary: Mapped[dict] = mapped_column(JSON, default=dict)
    error: Mapped[str | None] = mapped_column(String, nullable=True)
    lease_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    worker_id: Mapped[str | None] = mapped_column(String, nullable=True)
    created_by: Mapped[str] = mapped_column(String)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


class Session(Base):
    __tablename__ = "sessions"
    token_hash: Mapped[str] = mapped_column(String, primary_key=True)
    username: Mapped[str] = mapped_column(String)
    role: Mapped[str] = mapped_column(String)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class Audit(Base):
    __tablename__ = "audit"
    id: Mapped[str] = mapped_column(String, primary_key=True, default=uid)
    mode: Mapped[str] = mapped_column(String)
    actor: Mapped[str] = mapped_column(String)
    event: Mapped[str] = mapped_column(String)
    target: Mapped[str] = mapped_column(String)
    details: Mapped[dict] = mapped_column(JSON, default=dict)
    correlation_id: Mapped[str] = mapped_column(String)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


class Review(Base):
    __tablename__ = "reviews"
    id: Mapped[str] = mapped_column(String, primary_key=True, default=uid)
    job_id: Mapped[str] = mapped_column(ForeignKey("jobs.id"))
    case_id: Mapped[str] = mapped_column(String)
    actor: Mapped[str] = mapped_column(String)
    verdict: Mapped[str] = mapped_column(String)
    comment: Mapped[str] = mapped_column(String)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


class Endpoint(Base):
    __tablename__ = "endpoints"
    id: Mapped[str] = mapped_column(String, primary_key=True, default=uid)
    name: Mapped[str] = mapped_column(String)
    url: Mapped[str] = mapped_column(String)
    created_by: Mapped[str] = mapped_column(String)


engine = create_engine(
    os.getenv("DATABASE_URL", "postgresql+psycopg://release:release@localhost:5543/release"),
    pool_pre_ping=True,
)
SessionLocal = sessionmaker(engine, expire_on_commit=False)
MODE = os.getenv("APP_MODE", "DEMO").upper()
if MODE not in {"DEMO", "LIVE"}:
    raise RuntimeError("APP_MODE must be DEMO or LIVE")
