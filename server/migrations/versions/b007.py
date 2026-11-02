from pathlib import Path

from alembic import op

revision = "b007"
down_revision = "b006"


def upgrade():
    sql = (Path(__file__).parents[1] / "sql/007_hint_jobs.sql").read_text(encoding="utf-8")
    op.get_bind().exec_driver_sql(sql)


def downgrade():
    raise RuntimeError("Destructive downgrade disabled; use reviewed backup recovery.")
