"""A problem/version tables; no B preflight tables."""

from pathlib import Path

from alembic import op

revision = "a002"
down_revision = "a001"


def upgrade():
    sql = (Path(__file__).parents[1] / "sql/002_problems.sql").read_text(encoding="utf-8")
    op.get_bind().exec_driver_sql(sql)


def downgrade():
    raise RuntimeError("Destructive downgrade disabled; recreate an isolated test schema instead.")
