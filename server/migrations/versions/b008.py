from pathlib import Path

from alembic import op

revision = "b008"
down_revision = "b007"


def upgrade():
    sql = (Path(__file__).parents[1] / "sql/008_hint_jobs.sql").read_text(encoding="utf-8")
    op.get_bind().exec_driver_sql(sql)


def downgrade():
    raise RuntimeError("Destructive downgrade disabled; use reviewed backup recovery.")
