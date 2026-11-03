from pathlib import Path

from alembic import op

revision = "b016"
down_revision = "b015"


def upgrade():
    op.get_bind().exec_driver_sql(
        (Path(__file__).parents[1] / "sql/016_retention.sql").read_text(encoding="utf-8")
    )


def downgrade():
    raise RuntimeError("Retention and access history must be retained.")
