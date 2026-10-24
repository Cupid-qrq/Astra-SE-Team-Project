from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Column,
    ForeignKey,
    Index,
    Integer,
    LargeBinary,
    String,
    Table,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB

from app.modules.identity.models import metadata, timestamp, uid

families = Table(
    "problem_families",
    metadata,
    uid("canonical_problem_id", primary_key=True),
    uid("owner_teacher_id", ForeignKey("users.user_id"), nullable=False),
    Column("label", String(100), nullable=False),
)
problems = Table(
    "problems",
    metadata,
    uid("problem_id", primary_key=True),
    uid(
        "canonical_problem_id", ForeignKey("problem_families.canonical_problem_id"), nullable=False
    ),
    uid("owner_course_id", ForeignKey("courses.course_id"), nullable=False),
    Column("practice_released", Boolean, nullable=False),
    uid(
        "practice_version_id",
        ForeignKey(
            "problem_versions.version_id", use_alter=True, name="fk_problems_practice_version"
        ),
    ),
    Column("revision", Integer, nullable=False),
    timestamp("created_at", nullable=False),
    timestamp("updated_at", nullable=False),
    CheckConstraint("revision > 0", name="revision"),
    CheckConstraint(
        "NOT practice_released OR practice_version_id IS NOT NULL", name="practice_version"
    ),
    Index("ix_problems_course", "owner_course_id"),
    Index("ix_problems_family", "canonical_problem_id"),
)
versions = Table(
    "problem_versions",
    metadata,
    uid("version_id", primary_key=True),
    uid("problem_id", ForeignKey("problems.problem_id"), nullable=False),
    Column("version_no", Integer, nullable=False),
    Column("title", String(100), nullable=False),
    Column("statement", Text, nullable=False),
    Column("samples", JSONB, nullable=False),
    Column("tags", JSONB, nullable=False),
    Column("profile", JSONB, nullable=False),
    Column("source_ref", String(500), nullable=False),
    Column("checksum", String(64)),
    timestamp("published_at"),
    Column("revision", Integer, nullable=False),
    uid("published_preflight_id"),
    timestamp("created_at", nullable=False),
    timestamp("updated_at", nullable=False),
    UniqueConstraint("problem_id", "version_no"),
    UniqueConstraint("problem_id", "version_id", name="uq_problem_versions_problem_version"),
    CheckConstraint("revision > 0 AND version_no > 0", name="revision"),
    CheckConstraint("octet_length(statement) BETWEEN 1 AND 32768", name="statement_bytes"),
    CheckConstraint("jsonb_array_length(samples) BETWEEN 1 AND 3", name="samples_count"),
    CheckConstraint("jsonb_array_length(tags) <= 5", name="tags_count"),
    CheckConstraint("(published_at IS NULL) = (checksum IS NULL)", name="publication"),
)
testcases = Table(
    "testcases",
    metadata,
    uid("testcase_id", primary_key=True),
    uid("version_id", ForeignKey("problem_versions.version_id"), nullable=False),
    Column("order", Integer, nullable=False),
    Column("input_blob", LargeBinary, nullable=False),
    Column("answer_blob", LargeBinary, nullable=False),
    Column("input_sha256", String(64), nullable=False),
    Column("answer_sha256", String(64), nullable=False),
    UniqueConstraint("version_id", "order"),
    CheckConstraint('"order" BETWEEN 1 AND 10', name="order_range"),
    CheckConstraint(
        "octet_length(input_blob) <= 65536 AND octet_length(answer_blob) <= 65536", name="bytes"
    ),
)
references = Table(
    "reference_programs",
    metadata,
    uid("reference_id", primary_key=True),
    uid("version_id", ForeignKey("problem_versions.version_id"), nullable=False),
    Column("language_key", String(10), nullable=False),
    Column("code", LargeBinary, nullable=False),
    Column("code_sha256", String(64), nullable=False),
    UniqueConstraint("version_id", "language_key"),
    CheckConstraint("language_key IN ('cpp17','python3')", name="language"),
    CheckConstraint("octet_length(code) BETWEEN 1 AND 65536", name="bytes"),
)
