"""Submission identity, processing history and admission counters."""

from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    Column,
    ForeignKey,
    ForeignKeyConstraint,
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


def identifier(name, *args, **kwargs):
    return Column(name, UUID(as_uuid=False), *args, **kwargs)


def timestamp(name, **kwargs):
    return Column(name, TIMESTAMP(timezone=True, precision=3), **kwargs)


submissions = Table(
    "submissions",
    metadata,
    identifier("submission_id", primary_key=True),
    identifier("user_id", ForeignKey("users.user_id"), nullable=False),
    identifier("assignment_id", nullable=False),
    identifier("problem_id", nullable=False),
    identifier("version_id", ForeignKey("problem_versions.version_id"), nullable=False),
    Column("language_key", String(10), nullable=False),
    Column("code", LargeBinary, nullable=False),
    Column("code_sha256", String(64), nullable=False),
    Column("intent", String(8), nullable=False),
    Column("mode", String(8), nullable=False),
    timestamp("accepted_at", nullable=False),
    identifier("idempotency_key", nullable=False),
    Column("request_digest", String(64), nullable=False),
    Column("original_receipt", JSONB, nullable=False),
    identifier("active_basis_id"),
    Column("revision", Integer, nullable=False),
    ForeignKeyConstraint(
        ["assignment_id", "problem_id"],
        ["assignment_items.assignment_id", "assignment_items.problem_id"],
    ),
    UniqueConstraint("user_id", "idempotency_key", name="uq_submissions_idempotency"),
    CheckConstraint("language_key IN ('cpp17','python3')", name="language"),
    CheckConstraint("intent IN ('FORMAL','PRACTICE') AND mode=intent", name="intent"),
    CheckConstraint("octet_length(code) BETWEEN 1 AND 65536", name="code_size"),
    CheckConstraint(
        "code_sha256 ~ '^[0-9a-f]{64}$' AND request_digest ~ '^[0-9a-f]{64}$'", name="digest"
    ),
    CheckConstraint("revision>0", name="revision"),
)
Index(
    "ix_submissions_history",
    submissions.c.assignment_id,
    submissions.c.user_id,
    submissions.c.accepted_at,
    submissions.c.submission_id,
)
bases = Table(
    "result_bases",
    metadata,
    identifier("basis_id", primary_key=True),
    identifier("submission_id", ForeignKey("submissions.submission_id"), nullable=False),
    identifier("batch_id"),
    identifier("target_version_id", ForeignKey("problem_versions.version_id"), nullable=False),
    identifier("current_attempt_id"),
    identifier("current_cycle_id"),
    Column("processing_state", String(12), nullable=False),
    UniqueConstraint("submission_id", "basis_id", name="uq_basis_owner"),
    UniqueConstraint("batch_id", "submission_id", name="uq_basis_batch"),
    CheckConstraint(
        "processing_state IN ('QUEUED','RUNNING','RETRY_WAIT','FINISHED')", name="state"
    ),
)
Index(
    "uq_original_basis",
    bases.c.submission_id,
    unique=True,
    postgresql_where=text("batch_id IS NULL"),
)
cycles = Table(
    "processing_cycles",
    metadata,
    identifier("cycle_id", primary_key=True),
    identifier("basis_id", nullable=False),
    identifier("submission_id", nullable=False),
    timestamp("started_at", nullable=False),
    timestamp("finished_at"),
    Column("auto_retry_count", Integer, nullable=False),
    Column("capacity_held", Boolean, nullable=False),
    Column("trigger", String(8), nullable=False),
    Column("reason", String(500)),
    ForeignKeyConstraint(
        ["submission_id", "basis_id"], ["result_bases.submission_id", "result_bases.basis_id"]
    ),
    UniqueConstraint("submission_id", "basis_id", "cycle_id", name="uq_cycle_owner"),
    CheckConstraint("auto_retry_count IN (0,1)", name="retry"),
    CheckConstraint("trigger IN ('INITIAL','REJUDGE','MANUAL')", name="trigger"),
    CheckConstraint("capacity_held=(finished_at IS NULL)", name="capacity"),
)
Index(
    "uq_cycle_capacity", cycles.c.submission_id, unique=True, postgresql_where=text("capacity_held")
)
attempts = Table(
    "attempts",
    metadata,
    identifier("attempt_id", primary_key=True),
    identifier("submission_id", nullable=False),
    identifier("basis_id", nullable=False),
    identifier("cycle_id", nullable=False),
    Column("generation", Integer, nullable=False),
    Column("state", String(12), nullable=False),
    Column("verdict", String(3)),
    Column("reason_code", String(60)),
    timestamp("started_at"),
    timestamp("finished_at"),
    Column("time_ms", BigInteger),
    Column("memory_bytes", BigInteger),
    Column("engine_meta", JSONB, nullable=False),
    identifier("feedback_version_id", ForeignKey("feedback_versions.version_id")),
    ForeignKeyConstraint(
        ["submission_id", "basis_id", "cycle_id"],
        [
            "processing_cycles.submission_id",
            "processing_cycles.basis_id",
            "processing_cycles.cycle_id",
        ],
    ),
    UniqueConstraint("submission_id", "generation", name="uq_attempt_generation"),
    UniqueConstraint("submission_id", "basis_id", "attempt_id", name="uq_attempt_owner"),
    CheckConstraint("generation>0", name="generation"),
    CheckConstraint("state IN ('QUEUED','RUNNING','RETRY_WAIT','FINISHED')", name="state"),
    CheckConstraint(
        "(state='FINISHED')=(verdict IS NOT NULL) AND (state='FINISHED')=(finished_at IS NOT NULL)",
        name="finished",
    ),
    CheckConstraint("verdict IN ('AC','WA','CE','TLE','RE','SE')", name="verdict"),
    CheckConstraint("time_ms>=0 AND memory_bytes>=0", name="metrics"),
)
for table, columns, targets, name in [
    (
        submissions,
        ["submission_id", "active_basis_id"],
        ["result_bases.submission_id", "result_bases.basis_id"],
        "fk_submission_active_basis",
    ),
    (
        bases,
        ["submission_id", "basis_id", "current_cycle_id"],
        [
            "processing_cycles.submission_id",
            "processing_cycles.basis_id",
            "processing_cycles.cycle_id",
        ],
        "fk_basis_current_cycle",
    ),
    (
        bases,
        ["submission_id", "basis_id", "current_attempt_id"],
        ["attempts.submission_id", "attempts.basis_id", "attempts.attempt_id"],
        "fk_basis_current_attempt",
    ),
]:
    table.append_constraint(
        ForeignKeyConstraint(
            columns, targets, name=name, deferrable=True, initially="DEFERRED", use_alter=True
        )
    )
jobs = Table(
    "queue_jobs",
    metadata,
    identifier("job_id", primary_key=True),
    identifier("attempt_id", ForeignKey("attempts.attempt_id"), nullable=False, unique=True),
    Column("kind", String(8), nullable=False),
    Column("state", String(8), nullable=False),
    timestamp("ready_at", nullable=False),
    timestamp("created_at", nullable=False),
    timestamp("lease_until"),
    timestamp("deadline"),
    Column("lease_epoch", BigInteger, nullable=False),
    identifier("worker_id"),
    Column("current_execution", String(64)),
    CheckConstraint("kind IN ('NORMAL','REJUDGE')", name="kind"),
    CheckConstraint("state IN ('READY','LEASED','DONE')", name="state"),
    CheckConstraint("lease_epoch>=0", name="epoch"),
    CheckConstraint(
        "current_execution IS NULL OR current_execution ~ '^[0-9a-f]{64}$'", name="execution"
    ),
)
Index(
    "ix_queue_ready", jobs.c.kind, jobs.c.state, jobs.c.ready_at, jobs.c.created_at, jobs.c.job_id
)
case_results = Table(
    "case_results",
    metadata,
    identifier("attempt_id", ForeignKey("attempts.attempt_id"), primary_key=True),
    Column("order", Integer, primary_key=True),
    identifier("testcase_id", ForeignKey("testcases.testcase_id"), nullable=False),
    Column("verdict", String(7), nullable=False),
    Column("cpu_ms", BigInteger),
    Column("memory_bytes", BigInteger),
    Column("engine_meta", JSONB, nullable=False),
    CheckConstraint('"order" BETWEEN 1 AND 10', name="order"),
    CheckConstraint("verdict IN ('AC','WA','CE','TLE','RE','SE','SKIPPED')", name="verdict"),
    CheckConstraint("cpu_ms>=0 AND memory_bytes>=0", name="metrics"),
)
admission_users = Table(
    "admission_users",
    metadata,
    identifier("user_id", ForeignKey("users.user_id"), primary_key=True),
    timestamp("last_accepted_at"),
    Column("pending_count", Integer, nullable=False),
    CheckConstraint("pending_count BETWEEN 0 AND 3", name="pending"),
)
capacity = Table(
    "capacity_control",
    metadata,
    Column("control_id", Integer, primary_key=True),
    Column("pending_count", Integer, nullable=False),
    CheckConstraint("control_id=1", name="singleton"),
    CheckConstraint("pending_count BETWEEN 0 AND 100", name="pending"),
)
