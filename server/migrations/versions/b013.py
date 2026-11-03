from pathlib import Path

from alembic import op

revision = "b013"
down_revision = "b012"


def upgrade():
    op.get_bind().exec_driver_sql(
        (Path(__file__).parents[1] / "sql/013_grades.sql").read_text(encoding="utf-8")
    )


def downgrade():
    if op.get_bind().exec_driver_sql("SELECT EXISTS(SELECT 1 FROM grade_versions)").scalar_one():
        raise RuntimeError("Grade history exists; downgrade refused.")
    for table in ("grade_items", "grade_students", "grade_versions"):
        op.drop_table(table)
    op.get_bind().exec_driver_sql("DROP FUNCTION protect_grade_snapshot()")
