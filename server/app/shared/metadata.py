"""Unified runtime metadata; migrations never import current table definitions."""

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    Column,
    ForeignKey,
    Index,
    Integer,
    String,
    Table,
    Text,
)
from sqlalchemy.dialects.postgresql import JSONB, TIMESTAMP, UUID

import app.modules.assignments.models  # noqa: F401
import app.modules.courses.models  # noqa: F401
import app.modules.grades.models  # noqa: F401
import app.modules.judging.models  # noqa: F401
import app.modules.learning.models  # noqa: F401
import app.modules.problems.models  # noqa: F401
import app.modules.submissions.models  # noqa: F401
from app.modules.identity.models import metadata as metadata

policy_guard = Table(
    "policy_guard",
    metadata,
    Column("guard_id", Integer, primary_key=True),
    Column("revision", Integer, nullable=False),
)
audit_events = Table(
    "audit_events",
    metadata,
    Column("event_id", UUID(as_uuid=False), primary_key=True),
    Column("actor_id", UUID(as_uuid=False), ForeignKey("users.user_id")),
    Column("actor_kind", String(10), nullable=False),
    Column("action", String(80), nullable=False),
    Column("object_type", String(40), nullable=False),
    Column("object_id", UUID(as_uuid=False), nullable=False),
    Column("before_after_digest", String(64), nullable=False),
    Column("reason", Text, nullable=False),
    Column("timestamp", TIMESTAMP(timezone=True, precision=3), nullable=False),
    Column("request_id", UUID(as_uuid=False), nullable=False),
)
outbox_events = Table(
    "outbox_events",
    metadata,
    Column("event_id", UUID(as_uuid=False), primary_key=True),
    Column("event_key", String(100), nullable=False, unique=True),
    Column("event_type", String(80), nullable=False),
    Column("payload", JSONB, nullable=False),
    Column("state", String(10), nullable=False),
    Column("tries", BigInteger, nullable=False),
    Column("next_at", TIMESTAMP(timezone=True, precision=3), nullable=False),
    Column("created_at", TIMESTAMP(timezone=True, precision=3), nullable=False),
)

policy_guard.append_constraint(CheckConstraint("guard_id=1", name="singleton"))
policy_guard.append_constraint(CheckConstraint("revision>0", name="revision"))
audit_events.append_constraint(
    CheckConstraint("actor_kind IN ('USER','SYSTEM')", name="actor_kind")
)
audit_events.append_constraint(
    CheckConstraint(
        "(actor_kind='USER' AND actor_id IS NOT NULL) OR (actor_kind='SYSTEM' AND actor_id IS NULL)",
        name="actor_required",
    )
)
Index("ix_audit_time", audit_events.c.timestamp)
Index("ix_audit_object", audit_events.c.object_type, audit_events.c.object_id)
Index("ix_audit_actor", audit_events.c.actor_id, audit_events.c.timestamp)
outbox_events.append_constraint(
    CheckConstraint("state IN ('READY','SENDING','SENT','FAILED')", name="state")
)
outbox_events.append_constraint(CheckConstraint("tries>=0", name="tries"))
Index("ix_outbox_ready", outbox_events.c.state, outbox_events.c.next_at)

# A004 already creates this index; declare it in unified metadata as well.
Index("ix_feedback_versions_author", metadata.tables["feedback_versions"].c.author_id)
