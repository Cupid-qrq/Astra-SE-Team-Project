from pathlib import Path

from alembic import op

revision = "b006"
down_revision = "b005"


def upgrade():
    sql = (Path(__file__).parents[1] / "sql/006_templates.sql").read_text(encoding="utf-8")
    op.get_bind().exec_driver_sql(sql)


def downgrade():
    raise RuntimeError("Destructive downgrade disabled; use reviewed backup recovery.")
