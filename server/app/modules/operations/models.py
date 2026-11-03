from sqlalchemy import Boolean, CheckConstraint, Column, ForeignKey, Integer, String, Table, Text
from sqlalchemy.dialects.postgresql import JSONB

from app.modules.identity.models import metadata
from app.modules.submissions.models import identifier, timestamp

incidents = Table(
    "fairness_incidents",
    metadata,
    identifier("incident_id", primary_key=True),
    timestamp("started_at", nullable=False),
    timestamp("recovered_at"),
    Column("reason_code", String(60), nullable=False),
    Column("rejected_count", Integer, nullable=False),
    Column("evidence_refs", JSONB, nullable=False),
    Column("evidence_incomplete", Boolean, nullable=False),
    timestamp("detected_at", nullable=False),
    timestamp("displayed_at", nullable=False),
    timestamp("persisted_at", nullable=False),
    timestamp("recovery_started_at"),
    Column("revision", Integer, nullable=False),
    CheckConstraint("recovered_at IS NULL OR recovered_at>=started_at", name="interval"),
)
assignments = Table(
    "incident_assignments",
    metadata,
    identifier("incident_id", ForeignKey("fairness_incidents.incident_id"), primary_key=True),
    identifier("assignment_id", ForeignKey("assignments.assignment_id"), primary_key=True),
    Column("decision", String(12), nullable=False),
    timestamp("old_due", nullable=False),
    timestamp("new_due"),
    identifier("approved_by", ForeignKey("users.user_id")),
    timestamp("approved_at"),
    Column("overlap_ms", Integer),
    Column("reason", String(500)),
    CheckConstraint("decision IN ('PENDING','EXTEND','NO_IMPACT')", name="decision"),
)
requests = Table(
    "incident_requests",
    metadata,
    identifier("incident_id", ForeignKey("fairness_incidents.incident_id"), primary_key=True),
    identifier("request_id", primary_key=True),
    identifier("assignment_id", ForeignKey("assignments.assignment_id")),
    Column("reason_code", String(60), nullable=False),
    timestamp("observed_at", nullable=False),
)
notifications = Table(
    "notifications",
    metadata,
    identifier("notification_id", primary_key=True),
    identifier("user_id", ForeignKey("users.user_id"), nullable=False),
    Column("event_key", String(140), nullable=False, unique=True),
    Column("title", String(100), nullable=False),
    Column("body", Text, nullable=False),
    timestamp("created_at", nullable=False),
    timestamp("read_at"),
)
holds = Table(
    "course_holds",
    metadata,
    identifier("hold_id", primary_key=True),
    identifier("course_id", ForeignKey("courses.course_id"), nullable=False),
    Column("reason", String(500), nullable=False),
    identifier("created_by", ForeignKey("users.user_id"), nullable=False),
    timestamp("created_at", nullable=False),
    timestamp("released_at"),
)
cleanup = Table(
    "course_cleanup",
    metadata,
    identifier("course_id", ForeignKey("courses.course_id"), primary_key=True),
    timestamp("cleaned_at", nullable=False),
    timestamp("purge_due_at", nullable=False),
    timestamp("purged_at"),
    identifier("confirmed_by", ForeignKey("users.user_id"), nullable=False),
)


plans = Table(
    "retention_plans",
    metadata,
    identifier("plan_id", primary_key=True),
    identifier("course_id", ForeignKey("courses.course_id"), nullable=False),
    Column("object_digest", String(64), nullable=False),
    Column("state", String(12), nullable=False),
    Column("revision", Integer, nullable=False),
    timestamp("created_at", nullable=False),
)
confirmations = Table(
    "retention_confirmations",
    metadata,
    identifier("confirmation_id", primary_key=True),
    identifier("plan_id", ForeignKey("retention_plans.plan_id"), nullable=False),
    identifier("teacher_id", ForeignKey("users.user_id"), nullable=False),
    Column("object_digest", String(64), nullable=False),
    Column("reason", String(500), nullable=False),
    timestamp("confirmed_at", nullable=False),
)
grants = Table(
    "emergency_grants",
    metadata,
    identifier("grant_id", primary_key=True),
    identifier("admin_id", ForeignKey("users.user_id"), nullable=False),
    identifier("incident_id", ForeignKey("fairness_incidents.incident_id"), nullable=False),
    Column("scope", JSONB, nullable=False),
    timestamp("expires_at", nullable=False),
    timestamp("revoked_at"),
    Column("reason", String(500), nullable=False),
)
runtime = Table(
    "runtime_config_versions",
    metadata,
    identifier("config_version", primary_key=True),
    Column("payload", JSONB, nullable=False),
    Column("checksum", String(64), nullable=False),
    identifier("created_by", ForeignKey("users.user_id"), nullable=False),
    Column("reason", String(500), nullable=False),
    timestamp("created_at", nullable=False),
    Column("revision", Integer, nullable=False, unique=True),
)
