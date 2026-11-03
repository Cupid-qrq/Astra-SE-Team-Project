"""A-owned hint jobs, quota and CNY budget accounts."""

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Column,
    Date,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Table,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB

from app.modules.identity.models import metadata, timestamp, uid


def string(name, size, nullable=False):
    return Column(name, String(size), nullable=nullable)


def money(name, nullable=False):
    return Column(name, Numeric(), nullable=nullable)


def integer(name):
    return Column(name, Integer, nullable=False)


configs = Table(
    "model_configs",
    metadata,
    uid("config_id", primary_key=True),
    string("provider", 80),
    string("model_id", 120),
    string("version_label", 120),
    string("terms_review_ref", 500),
    timestamp("price_verified_at", nullable=False),
    money("input_price"),
    money("output_price"),
    integer("max_input_tokens"),
    integer("max_output_tokens"),
    Column("enabled", Boolean, nullable=False),
    CheckConstraint(
        "input_price >= 0 AND output_price >= 0 AND input_price + output_price > 0 AND max_input_tokens > 0 AND max_output_tokens > 0",
        name="model_limits",
    ),
)

hints = Table(
    "ai_hints",
    metadata,
    uid("hint_id", primary_key=True),
    uid("user_id", ForeignKey("users.user_id"), nullable=False),
    uid("course_id", ForeignKey("courses.course_id"), nullable=False),
    uid("submission_id", nullable=False),
    uid("request_key", nullable=False),
    string("request_digest", 64),
    string("question", 500),
    Column("accepted_date", Date, nullable=False),
    string("status", 8),
    string("reason_code", 80, True),
    uid("template_version_id", ForeignKey("template_versions.version_id"), nullable=False),
    uid("model_config_id", ForeignKey("model_configs.config_id"), nullable=False),
    uid("feedback_version_id", ForeignKey("feedback_versions.version_id"), nullable=False),
    string("accepted_policy_digest", 64),
    string("dispatch_policy_digest", 64, True),
    timestamp("authorized_at"),
    timestamp("consented_at", nullable=False),
    timestamp("created_at", nullable=False),
    Column("source_snapshot", JSONB(none_as_null=True)),
    Column("sections", JSONB(none_as_null=True)),
    Column("usage", JSONB(none_as_null=True)),
    string("provider_request_id", 128, True),
    Index("ix_ai_hints_user_history", "user_id", "created_at", "hint_id"),
    UniqueConstraint("user_id", "request_key"),
    CheckConstraint(
        "status IN ('PENDING','READY','FAILED','BLOCKED') AND ((status = 'READY') = (sections IS NOT NULL))",
        name="hint_status",
    ),
    Index(
        "uq_personal_pending_hint",
        "user_id",
        unique=True,
        postgresql_where=text("status = 'PENDING'"),
    ),
)

jobs = Table(
    "hint_jobs",
    metadata,
    uid("hint_id", ForeignKey("ai_hints.hint_id"), primary_key=True),
    string("state", 8),
    timestamp("queued_at", nullable=False),
    timestamp("started_at"),
    timestamp("deadline_at", nullable=False),
    integer("lease_epoch"),
    CheckConstraint("state IN ('WAITING','RUNNING','DONE') AND lease_epoch >= 0", name="job_state"),
    Index("ix_hint_jobs_queue", "state", "queued_at", "hint_id"),
)

feedback = Table(
    "hint_feedback",
    metadata,
    uid("hint_id", ForeignKey("ai_hints.hint_id"), primary_key=True),
    uid("user_id", ForeignKey("users.user_id"), nullable=False),
    string("rating", 12),
    string("comment", 500),
    timestamp("updated_at", nullable=False),
    CheckConstraint("rating IN ('USEFUL','NOT_USEFUL','ERROR')", name="hint_rating"),
)

quota = Table(
    "quota_ledger",
    metadata,
    uid("user_id", ForeignKey("users.user_id"), primary_key=True),
    Column("accepted_date", Date, primary_key=True),
    integer("ready"),
    integer("reserved"),
    CheckConstraint(
        "ready >= 0 AND reserved >= 0 AND ready + reserved <= 20", name="personal_quota"
    ),
)

accounts = Table(
    "budget_accounts",
    metadata,
    Column("scope_key", String(20), primary_key=True),
    money("limit_amount"),
    money("settled_amount"),
    money("reserved_amount"),
    money("uncertain_amount"),
    integer("revision"),
    CheckConstraint(
        "limit_amount > 0 AND settled_amount >= 0 AND reserved_amount >= 0 AND uncertain_amount >= 0 AND revision > 0",
        name="budget_amounts",
    ),
)


reservations = Table(
    "budget_reservations",
    metadata,
    uid("hint_id", ForeignKey("ai_hints.hint_id"), primary_key=True),
    Column("accepted_date", Date, nullable=False),
    money("cost_upper"),
    money("actual", True),
    string("state", 10),
    CheckConstraint(
        "cost_upper > 0 AND state IN ('RESERVED','RELEASED','UNCERTAIN','SETTLED') AND ((state='SETTLED')=(actual IS NOT NULL)) AND (actual IS NULL OR actual>=0)",
        name="reservation_state",
    ),
)
