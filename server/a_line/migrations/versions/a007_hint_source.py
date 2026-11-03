"""Freeze hint provenance; legacy rows remain unverifiable."""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision = "a007"
down_revision = "a006"


def upgrade():
    op.add_column("ai_hints", sa.Column("source_snapshot", JSONB(none_as_null=True), nullable=True))


def downgrade():
    if (
        op.get_bind()
        .exec_driver_sql("SELECT EXISTS (SELECT 1 FROM ai_hints WHERE source_snapshot IS NOT NULL)")
        .scalar_one()
    ):
        raise RuntimeError("Hint provenance must be retained; restore a compatible backup instead.")
    op.drop_column("ai_hints", "source_snapshot")
