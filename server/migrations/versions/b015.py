from pathlib import Path

from alembic import op

revision = "b015"
down_revision = "b014"


def upgrade():
    op.get_bind().exec_driver_sql(
        (Path(__file__).parents[1] / "sql/015_operations.sql").read_text(encoding="utf-8")
    )


def downgrade():
    raise RuntimeError("Operational history must be retained; use a reviewed forward migration.")
