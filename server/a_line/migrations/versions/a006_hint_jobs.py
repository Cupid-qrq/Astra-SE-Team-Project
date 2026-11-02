"""Hint jobs and quota ledgers."""

from pathlib import Path

from alembic import op

revision = "a006"
down_revision = "a005"


def upgrade():
    op.get_bind().exec_driver_sql(
        (Path(__file__).parents[1] / "sql/007_hint_jobs.sql").read_text(encoding="utf-8")
    )


def downgrade():
    raise RuntimeError("Destructive downgrade disabled; recreate an isolated test schema instead.")
