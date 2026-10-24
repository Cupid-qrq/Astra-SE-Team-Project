"""A-owned relational metadata. Merge into B metadata without changing table contracts."""

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Column,
    ForeignKey,
    Index,
    Integer,
    MetaData,
    String,
    Table,
)
from sqlalchemy.dialects.postgresql import TIMESTAMP, UUID

metadata = MetaData(
    naming_convention={
        "ix": "ix_%(table_name)s_%(column_0_name)s",
        "uq": "uq_%(table_name)s_%(column_0_name)s",
        "ck": "ck_%(table_name)s_%(constraint_name)s",
        "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
        "pk": "pk_%(table_name)s",
    }
)


def uid(name, *args, **kwargs):
    return Column(name, UUID(as_uuid=False), *args, **kwargs)


def timestamp(name, **kwargs):
    return Column(name, TIMESTAMP(timezone=True, precision=3), **kwargs)


users = Table(
    "users",
    metadata,
    uid("user_id", primary_key=True),
    Column("login_name", String(32), nullable=False, unique=True),
    Column("display_name", String(40), nullable=False),
    Column("role", String(10), nullable=False),
    Column("status", String(10), nullable=False),
    Column("password_hash", String(256), nullable=False),
    Column("must_change_password", Boolean, nullable=False),
    Column("revision", Integer, nullable=False),
    timestamp("created_at", nullable=False),
    timestamp("updated_at", nullable=False),
    CheckConstraint("role IN ('STUDENT','TEACHER','ADMIN')", name="role"),
    CheckConstraint("status IN ('ACTIVE','DISABLED')", name="status"),
    CheckConstraint("login_name ~ '^[A-Za-z0-9_]{3,32}$'", name="login"),
    CheckConstraint("char_length(display_name) BETWEEN 1 AND 40", name="display"),
    CheckConstraint("revision > 0", name="revision"),
)
sessions = Table(
    "sessions",
    metadata,
    uid("session_id", primary_key=True),
    uid("user_id", ForeignKey("users.user_id")),
    Column("token_hash", String(64), nullable=False, unique=True),
    Column("csrf_hash", String(64), nullable=False),
    timestamp("created_at", nullable=False),
    timestamp("last_seen_at", nullable=False),
    timestamp("expires_at", nullable=False),
    timestamp("revoked_at"),
    Index("ix_sessions_user_expiry", "user_id", "expires_at"),
)
login_attempts = Table(
    "login_attempts",
    metadata,
    uid("attempt_id", primary_key=True),
    Column("login_digest", String(64), nullable=False),
    Column("source_digest", String(64), nullable=False),
    Column("succeeded", Boolean, nullable=False),
    timestamp("attempted_at", nullable=False),
    Index("ix_login_attempts_login_time", "login_digest", "attempted_at"),
    Index("ix_login_attempts_source_time", "source_digest", "attempted_at"),
)
