"""Standalone A validation migration; B assigns the integrated revision."""

from pathlib import Path
from alembic import op

revision = "a001"
down_revision = None


def upgrade():
    sql = (Path(__file__).parents[1] / "sql/001_identity_courses.sql").read_text(encoding="utf-8")
    op.get_bind().exec_driver_sql(sql)


def downgrade():
    raise RuntimeError("Destructive downgrade disabled; recreate an isolated test schema instead.")
