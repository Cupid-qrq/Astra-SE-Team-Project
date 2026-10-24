"""A assignments; B supplies grade/rejudge foreign keys when integrating."""

from pathlib import Path

from alembic import op

revision = "a003"
down_revision = "a002"


def upgrade():
    op.get_bind().exec_driver_sql(
        (Path(__file__).parents[1] / "sql/003_assignments.sql").read_text(encoding="utf-8")
    )


def downgrade():
    raise RuntimeError("Destructive downgrade disabled; recreate an isolated test schema instead.")
