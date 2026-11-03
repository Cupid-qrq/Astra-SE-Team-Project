from sqlalchemy import (
    CheckConstraint,
    Column,
    ForeignKey,
    ForeignKeyConstraint,
    Index,
    Integer,
    String,
    Table,
    text,
)

from app.modules.identity.models import metadata
from app.modules.submissions.models import bases, identifier, timestamp

batches = Table(
    "rejudge_batches",
    metadata,
    identifier("batch_id", primary_key=True),
    identifier("assignment_id", ForeignKey("assignments.assignment_id"), nullable=False),
    identifier("problem_id", ForeignKey("problems.problem_id"), nullable=False),
    identifier("new_version_id", ForeignKey("problem_versions.version_id"), nullable=False),
    Column("assignment_revision", Integer, nullable=False),
    Column("revision", Integer, nullable=False),
    Column("state", String(12), nullable=False),
    Column("reason", String(500), nullable=False),
    Column("range_checksum", String(64), nullable=False),
    Column("affected_count", Integer, nullable=False),
    timestamp("created_at", nullable=False),
    CheckConstraint(
        "state IN ('QUEUED','RUNNING','READY','FAILED','CANCELLED','ACTIVE')", name="state"
    ),
)
Index(
    "uq_rejudge_open_assignment",
    batches.c.assignment_id,
    unique=True,
    postgresql_where=text("state IN ('QUEUED','RUNNING','READY','FAILED')"),
)
members = Table(
    "rejudge_members",
    metadata,
    identifier("batch_id", ForeignKey("rejudge_batches.batch_id"), primary_key=True),
    identifier("submission_id", ForeignKey("submissions.submission_id"), primary_key=True),
    identifier("basis_id", ForeignKey("result_bases.basis_id")),
    Column("state", String(8), nullable=False),
    CheckConstraint("state IN ('WAITING','RUNNING','FINISHED')", name="state"),
)
bases.append_constraint(
    ForeignKeyConstraint(
        ["batch_id"], ["rejudge_batches.batch_id"], name="fk_basis_rejudge_batch", use_alter=True
    )
)
