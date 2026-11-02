"""Immutable hint-template publications."""

from pathlib import Path

from alembic import op

revision = "a005"
down_revision = "a004"


def upgrade():
    op.get_bind().exec_driver_sql(
        (Path(__file__).parents[1] / "sql/006_templates.sql").read_text(encoding="utf-8")
    )


def downgrade():
    raise RuntimeError("Destructive downgrade disabled; recreate an isolated test schema instead.")
