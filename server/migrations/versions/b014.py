from pathlib import Path

from alembic import op

revision = "b014"
down_revision = "b013"


def upgrade():
    op.get_bind().exec_driver_sql(
        (Path(__file__).parents[1] / "sql/014_rejudge.sql").read_text(encoding="utf-8")
    )


def downgrade():
    if op.get_bind().exec_driver_sql("SELECT EXISTS(SELECT 1 FROM rejudge_batches)").scalar_one():
        raise RuntimeError("Rejudge history exists; downgrade refused.")
    op.drop_constraint("fk_basis_rejudge_batch", "result_bases", type_="foreignkey")
    op.drop_table("rejudge_members")
    op.drop_table("rejudge_batches")
    op.drop_column("scheduler_control", "cursor")
    op.drop_column("scheduler_control", "previous_queue_mode")
