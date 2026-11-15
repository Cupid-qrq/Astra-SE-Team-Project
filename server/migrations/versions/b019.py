"""Persistent course/version-scoped discussions; bodies are plain text."""

from alembic import op
from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Column,
    ForeignKey,
    ForeignKeyConstraint,
    Index,
    Integer,
    MetaData,
    String,
    Table,
    Text,
)
from sqlalchemy.dialects.postgresql import TIMESTAMP, UUID

revision = "b019"
down_revision = "b018"
metadata = MetaData(
    naming_convention={
        "ck": "ck_%(table_name)s_%(constraint_name)s",
        "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
        "pk": "pk_%(table_name)s",
    }
)


def uid(name, *args, **kwargs):
    return Column(name, UUID(as_uuid=False), *args, **kwargs)


def timestamp(name, **kwargs):
    return Column(name, TIMESTAMP(timezone=True, precision=3), **kwargs)


# Referenced tables exist in earlier immutable migrations.
Table("users", metadata, uid("user_id", primary_key=True))
Table("courses", metadata, uid("course_id", primary_key=True))
Table("problems", metadata, uid("problem_id", primary_key=True))
Table("problem_versions", metadata, uid("problem_id"), uid("version_id", primary_key=True))

threads = Table(
    "discussion_threads",
    metadata,
    uid("thread_id", primary_key=True),
    uid("course_id", ForeignKey("courses.course_id"), nullable=False),
    uid("problem_id", ForeignKey("problems.problem_id"), nullable=False),
    uid("version_id", nullable=False),
    uid("author_id", ForeignKey("users.user_id"), nullable=False),
    Column("title", String(120), nullable=False),
    Column("body", Text, nullable=False),
    Column("resolved", Boolean, nullable=False),
    Column("locked", Boolean, nullable=False),
    Column("pinned", Boolean, nullable=False),
    Column("hidden", Boolean, nullable=False),
    Column("revision", Integer, nullable=False),
    timestamp("created_at", nullable=False),
    timestamp("updated_at", nullable=False),
    ForeignKeyConstraint(
        ["problem_id", "version_id"],
        ["problem_versions.problem_id", "problem_versions.version_id"],
        name="fk_discussion_version",
    ),
    CheckConstraint("revision > 0", name="revision"),
    CheckConstraint("char_length(title) BETWEEN 1 AND 120", name="title"),
    CheckConstraint("char_length(body) BETWEEN 1 AND 4000", name="body"),
    Index("ix_discussion_scope", "course_id", "problem_id", "version_id", "thread_id"),
    Index("ix_discussion_author_time", "author_id", "created_at"),
)
replies = Table(
    "discussion_replies",
    metadata,
    uid("reply_id", primary_key=True),
    uid("thread_id", ForeignKey("discussion_threads.thread_id"), nullable=False),
    uid("author_id", ForeignKey("users.user_id"), nullable=False),
    Column("body", Text, nullable=False),
    Column("hidden", Boolean, nullable=False),
    Column("revision", Integer, nullable=False),
    timestamp("created_at", nullable=False),
    CheckConstraint("revision > 0", name="revision"),
    CheckConstraint("char_length(body) BETWEEN 1 AND 4000", name="body"),
    Index("ix_discussion_reply_thread", "thread_id", "reply_id"),
    Index("ix_discussion_reply_author_time", "author_id", "created_at"),
)


def upgrade():
    threads.create(op.get_bind())
    replies.create(op.get_bind())


def downgrade():
    if (
        op.get_bind()
        .exec_driver_sql("SELECT EXISTS (SELECT 1 FROM discussion_threads)")
        .scalar_one()
    ):
        raise RuntimeError(
            "Discussion history must be retained; restore a compatible backup instead."
        )
    replies.drop(op.get_bind())
    threads.drop(op.get_bind())
