from sqlalchemy import CheckConstraint, Column, ForeignKey, Index, Integer, String, Table

from app.modules.identity.models import metadata, timestamp, uid

courses = Table(
    "courses",
    metadata,
    uid("course_id", primary_key=True),
    uid("teacher_id", ForeignKey("users.user_id"), nullable=False),
    Column("title", String(100), nullable=False),
    Column("status", String(10), nullable=False),
    Column("revision", Integer, nullable=False),
    timestamp("archived_at"),
    timestamp("created_at", nullable=False),
    timestamp("updated_at", nullable=False),
    CheckConstraint("revision > 0", name="revision"),
    CheckConstraint("char_length(title) BETWEEN 1 AND 100", name="title"),
    CheckConstraint("(status='ARCHIVED') = (archived_at IS NOT NULL)", name="archive"),
    CheckConstraint("status IN ('ACTIVE','ARCHIVED')", name="status"),
    Index("ix_courses_teacher_status", "teacher_id", "status"),
)
course_members = Table(
    "course_members",
    metadata,
    uid("course_id", ForeignKey("courses.course_id"), primary_key=True),
    uid("user_id", ForeignKey("users.user_id"), primary_key=True),
    Column("status", String(10), nullable=False),
    timestamp("joined_at", nullable=False),
    CheckConstraint("status IN ('ACTIVE','DISABLED')", name="status"),
    Index("ix_members_user_course", "user_id", "course_id"),
)
