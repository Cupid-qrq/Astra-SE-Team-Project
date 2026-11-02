from sqlalchemy import (
    CheckConstraint,
    Column,
    ForeignKey,
    ForeignKeyConstraint,
    Integer,
    String,
    Table,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB

import app.modules.learning.hint_tables  # noqa: F401
from app.modules.identity.models import metadata, timestamp, uid

catalogs = Table(
    "feedback_catalogs",
    metadata,
    uid("catalog_id", primary_key=True),
    Column("scope_key", String(43), nullable=False),
    Column("verdict", String(3), nullable=False),
    Column("language_key", String(7), nullable=False),
    Column("draft_payload", JSONB, nullable=False),
    Column("draft_revision", Integer, nullable=False),
    uid("active_version_id"),
    UniqueConstraint("scope_key", "verdict", "language_key", name="uq_feedback_scope"),
    CheckConstraint("verdict IN ('CE','WA','TLE','RE','SE')", name="feedback_verdict"),
    CheckConstraint("language_key IN ('ALL','cpp17','python3')", name="feedback_language"),
    CheckConstraint("draft_revision > 0", name="feedback_revision"),
    ForeignKeyConstraint(
        ["catalog_id", "active_version_id"],
        ["feedback_versions.catalog_id", "feedback_versions.version_id"],
        name="fk_feedback_active",
        use_alter=True,
    ),
)
versions = Table(
    "feedback_versions",
    metadata,
    uid("version_id", primary_key=True),
    uid("catalog_id", ForeignKey("feedback_catalogs.catalog_id"), nullable=False),
    Column("version_no", Integer, nullable=False),
    Column("title", String(100), nullable=False),
    Column("explanation", String(2000), nullable=False),
    Column("checklist", JSONB, nullable=False),
    uid("author_id", ForeignKey("users.user_id"), nullable=False),
    timestamp("published_at", nullable=False),
    Column("checksum", String(64), nullable=False),
    UniqueConstraint("catalog_id", "version_no", name="uq_feedback_version_no"),
    UniqueConstraint("catalog_id", "version_id", name="uq_feedback_version_owner"),
    CheckConstraint("version_no > 0", name="feedback_version_positive"),
)

template_catalogs = Table(
    "template_catalogs",
    metadata,
    uid("template_id", primary_key=True),
    Column("scope_key", String(43), nullable=False),
    Column("draft_payload", JSONB, nullable=False),
    Column("draft_revision", Integer, nullable=False),
    uid("published_version_id"),
    uid("active_version_id"),
    UniqueConstraint("scope_key", name="uq_template_scope"),
    *[
        ForeignKeyConstraint(
            ["template_id", pointer + "_version_id"],
            ["template_versions.template_id", "template_versions.version_id"],
            name="fk_template_" + pointer,
            use_alter=True,
        )
        for pointer in ("published", "active")
    ],
)
template_versions = Table(
    "template_versions",
    metadata,
    uid("version_id", primary_key=True),
    uid("template_id", ForeignKey("template_catalogs.template_id"), nullable=False),
    Column("version_no", Integer, nullable=False),
    Column("body", Text, nullable=False),
    Column("allowed_placeholders", JSONB, nullable=False),
    Column("schema_version", String(40), nullable=False),
    uid("author_id", ForeignKey("users.user_id"), nullable=False),
    timestamp("published_at", nullable=False),
    Column("checksum", String(64), nullable=False),
    UniqueConstraint("template_id", "version_no", name="uq_template_version_no"),
    UniqueConstraint("template_id", "version_id", name="uq_template_version_owner"),
)
