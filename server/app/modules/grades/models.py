"""Immutable, whole-assignment grade snapshots."""

from sqlalchemy import (
    CheckConstraint,
    Column,
    ForeignKey,
    ForeignKeyConstraint,
    Integer,
    String,
    Table,
)

from app.modules.identity.models import metadata
from app.modules.submissions.models import identifier, timestamp

versions = Table(
    "grade_versions",
    metadata,
    identifier("grade_version", primary_key=True),
    identifier("assignment_id", ForeignKey("assignments.assignment_id"), nullable=False),
    Column("assignment_revision", Integer, nullable=False),
    Column("grade_epoch", Integer, nullable=False),
    Column("state", String(12), nullable=False),
    timestamp("published_at"),
    timestamp("created_at", nullable=False),
    CheckConstraint("state IN ('PROVISIONAL','PUBLISHED')", name="state"),
)
students = Table(
    "grade_students",
    metadata,
    identifier("grade_version", ForeignKey("grade_versions.grade_version"), primary_key=True),
    identifier("student_id", ForeignKey("users.user_id"), primary_key=True),
    Column("total", Integer, nullable=False),
    Column("state", String(8), nullable=False),
    CheckConstraint("total BETWEEN 0 AND 100", name="total"),
    CheckConstraint("state IN ('READY','PENDING')", name="state"),
)
items = Table(
    "grade_items",
    metadata,
    identifier("grade_version", primary_key=True),
    identifier("student_id", primary_key=True),
    identifier("problem_id", ForeignKey("problems.problem_id"), primary_key=True),
    Column("points", Integer, nullable=False),
    Column("score", Integer, nullable=False),
    identifier("source_attempt_id", ForeignKey("attempts.attempt_id")),
    identifier("target_version_id", ForeignKey("problem_versions.version_id"), nullable=False),
    ForeignKeyConstraint(
        ["grade_version", "student_id"],
        ["grade_students.grade_version", "grade_students.student_id"],
    ),
    CheckConstraint("points BETWEEN 1 AND 100 AND score IN (0,points)", name="score"),
)
