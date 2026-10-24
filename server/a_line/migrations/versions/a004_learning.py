"""A immutable fixed help and explicit administrator-attributed seeds."""

from pathlib import Path

from alembic import op

revision = "a004"
down_revision = "a003"


def upgrade():
    op.get_bind().exec_driver_sql(
        (Path(__file__).parents[1] / "sql/004_learning.sql").read_text(encoding="utf-8")
    )


def downgrade():
    raise RuntimeError("Destructive downgrade disabled; recreate an isolated test schema instead.")
