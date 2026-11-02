"""Preflight facts; physical execution slots and leases arrive with the Worker."""

from sqlalchemy import (
    CheckConstraint,
    Column,
    ForeignKey,
    Index,
    Integer,
    LargeBinary,
    String,
    Table,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB, TIMESTAMP, UUID

from app.modules.identity.models import metadata

runs = Table(
    "preflight_runs",
    metadata,
    Column("preflight_id", UUID(as_uuid=False), primary_key=True),
    Column(
        "version_id", UUID(as_uuid=False), ForeignKey("problem_versions.version_id"), nullable=False
    ),
    Column("version_revision", Integer, nullable=False),
    Column("content_digest", String(64), nullable=False),
    Column("profile_hash", String(64), nullable=False),
    Column("frozen_blob", LargeBinary, nullable=False),
    Column("case_manifest", JSONB, nullable=False),
    Column("state", String(10), nullable=False),
    Column("created_by", UUID(as_uuid=False), ForeignKey("users.user_id"), nullable=False),
    Column("created_at", TIMESTAMP(timezone=True, precision=3), nullable=False),
    Column("started_at", TIMESTAMP(timezone=True, precision=3)),
    Column("finished_at", TIMESTAMP(timezone=True, precision=3)),
    CheckConstraint("version_revision>0", name="revision"),
    CheckConstraint("content_digest ~ '^[0-9a-f]{64}$'", name="content_digest"),
    CheckConstraint("profile_hash ~ '^[0-9a-f]{64}$'", name="profile_hash"),
    CheckConstraint("octet_length(frozen_blob) BETWEEN 1 AND 16777216", name="snapshot_size"),
    CheckConstraint(
        "jsonb_typeof(case_manifest)='array' AND jsonb_array_length(case_manifest) BETWEEN 2 AND 26",
        name="case_manifest",
    ),
    CheckConstraint("state IN ('QUEUED','RUNNING','PASSED','FAILED')", name="state"),
    CheckConstraint("(state IN ('PASSED','FAILED')) = (finished_at IS NOT NULL)", name="finished"),
    CheckConstraint(
        "(state='QUEUED' AND started_at IS NULL) OR (state<>'QUEUED' AND started_at IS NOT NULL)",
        name="started",
    ),
)
Index("ix_preflight_version", runs.c.version_id)
Index("ix_preflight_author", runs.c.created_by)
Index(
    "uq_preflight_active",
    runs.c.version_id,
    runs.c.content_digest,
    runs.c.profile_hash,
    unique=True,
    postgresql_where=text("state IN ('QUEUED','RUNNING')"),
)
cases = Table(
    "preflight_cases",
    metadata,
    Column(
        "preflight_id",
        UUID(as_uuid=False),
        ForeignKey("preflight_runs.preflight_id"),
        primary_key=True,
    ),
    Column("language_key", String(10), primary_key=True),
    Column("case_kind", String(6), primary_key=True),
    Column("case_order", Integer, primary_key=True),
    Column("state", String(10), nullable=False),
    Column("verdict", String(3)),
    Column("engine_meta", JSONB, nullable=False),
    CheckConstraint("language_key IN ('cpp17','python3')", name="language"),
    CheckConstraint("case_kind IN ('SAMPLE','HIDDEN')", name="kind"),
    CheckConstraint(
        "case_order BETWEEN 1 AND CASE WHEN case_kind='SAMPLE' THEN 3 ELSE 10 END",
        name="case_order",
    ),
    CheckConstraint("state IN ('QUEUED','RUNNING','FINISHED','SKIPPED')", name="state"),
    CheckConstraint("(state='FINISHED') = (verdict IS NOT NULL)", name="finished"),
    CheckConstraint("verdict IN ('AC','WA','CE','TLE','RE','SE')", name="verdict"),
)
jobs = Table(
    "preflight_jobs",
    metadata,
    Column("job_id", UUID(as_uuid=False), primary_key=True),
    Column(
        "preflight_id",
        UUID(as_uuid=False),
        ForeignKey("preflight_runs.preflight_id"),
        nullable=False,
    ),
    Column("state", String(10), nullable=False),
    Column("ready_at", TIMESTAMP(timezone=True, precision=3), nullable=False),
    UniqueConstraint("preflight_id"),
    CheckConstraint("state IN ('READY','DONE')", name="state"),
)
Index("ix_preflight_job_ready", jobs.c.state, jobs.c.ready_at, jobs.c.job_id)
