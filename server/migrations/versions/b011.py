from pathlib import Path

from alembic import op

revision = "b011"
down_revision = "b010"


def upgrade():
    op.get_bind().exec_driver_sql(
        (Path(__file__).parents[1] / "sql/011_submissions.sql").read_text(encoding="utf-8")
    )


def downgrade():
    if op.get_bind().exec_driver_sql("SELECT EXISTS(SELECT 1 FROM submissions)").scalar_one():
        raise RuntimeError("Submission history exists; destructive downgrade refused.")
    op.drop_constraint("fk_submission_active_basis", "submissions", type_="foreignkey")
    op.drop_constraint("fk_basis_current_attempt", "result_bases", type_="foreignkey")
    op.drop_constraint("fk_basis_current_cycle", "result_bases", type_="foreignkey")
    for table in (
        "case_results",
        "queue_jobs",
        "attempts",
        "processing_cycles",
        "result_bases",
        "submissions",
        "admission_users",
        "capacity_control",
    ):
        op.drop_table(table)
    op.get_bind().exec_driver_sql("DROP FUNCTION protect_submission_identity()")
