"""Initial versioned schema. Immutable initial table definitions."""

from alembic import op
import sqlalchemy as sa

revision = "001"
down_revision = None


def upgrade():
    # Explicit snapshot, independent of future ORM changes.
    op.create_table(
        "datasets",
        sa.Column("id", sa.String, primary_key=True),
        sa.Column("mode", sa.String, nullable=False),
        sa.Column("name", sa.String, nullable=False),
        sa.Column("version", sa.String, nullable=False),
        sa.Column("hash", sa.String, nullable=False),
        sa.Column("cases", sa.JSON, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("mode", "name", "version"),
    )
    op.create_table(
        "configurations",
        sa.Column("id", sa.String, primary_key=True),
        sa.Column("mode", sa.String, nullable=False),
        sa.Column("name", sa.String, nullable=False),
        sa.Column("version", sa.String, nullable=False),
        sa.Column("hash", sa.String, nullable=False),
        sa.Column("spec", sa.JSON, nullable=False),
        sa.UniqueConstraint("mode", "name", "version"),
    )
    op.create_table(
        "jobs",
        sa.Column("id", sa.String, primary_key=True),
        sa.Column("mode", sa.String, nullable=False),
        sa.Column("dataset_id", sa.String, sa.ForeignKey("datasets.id"), nullable=False),
        sa.Column("configuration_id", sa.String, sa.ForeignKey("configurations.id"), nullable=False),
        sa.Column("label", sa.String, nullable=False),
        sa.Column("status", sa.String, nullable=False),
        sa.Column("source", sa.String, nullable=False),
        sa.Column("input_hash", sa.String, nullable=False),
        sa.Column("inputs", sa.JSON, nullable=False),
        sa.Column("results", sa.JSON, nullable=False),
        sa.Column("progress", sa.Integer, nullable=False),
        sa.Column("total", sa.Integer, nullable=False),
        sa.Column("decision", sa.String, nullable=False),
        sa.Column("summary", sa.JSON, nullable=False),
        sa.Column("error", sa.String),
        sa.Column("lease_until", sa.DateTime(timezone=True)),
        sa.Column("worker_id", sa.String),
        sa.Column("created_by", sa.String, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_jobs_mode", "jobs", ["mode"])
    op.create_table(
        "sessions",
        sa.Column("token_hash", sa.String, primary_key=True),
        sa.Column("username", sa.String, nullable=False),
        sa.Column("role", sa.String, nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_table(
        "audit",
        sa.Column("id", sa.String, primary_key=True),
        sa.Column("mode", sa.String, nullable=False),
        sa.Column("actor", sa.String, nullable=False),
        sa.Column("event", sa.String, nullable=False),
        sa.Column("target", sa.String, nullable=False),
        sa.Column("details", sa.JSON, nullable=False),
        sa.Column("correlation_id", sa.String, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_table(
        "reviews",
        sa.Column("id", sa.String, primary_key=True),
        sa.Column("job_id", sa.String, sa.ForeignKey("jobs.id"), nullable=False),
        sa.Column("case_id", sa.String, nullable=False),
        sa.Column("actor", sa.String, nullable=False),
        sa.Column("verdict", sa.String, nullable=False),
        sa.Column("comment", sa.String, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_table(
        "endpoints",
        sa.Column("id", sa.String, primary_key=True),
        sa.Column("name", sa.String, nullable=False),
        sa.Column("url", sa.String, nullable=False),
        sa.Column("created_by", sa.String, nullable=False),
    )


def downgrade():
    for table in ["endpoints", "reviews", "audit", "sessions", "jobs", "configurations", "datasets"]:
        op.drop_table(table)
