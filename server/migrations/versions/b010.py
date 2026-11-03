from pathlib import Path

from alembic import op

revision = "b010"
down_revision = "b009"


def upgrade():
    op.get_bind().exec_driver_sql(
        (Path(__file__).parents[1] / "sql/010_preflight_worker.sql").read_text(encoding="utf-8")
    )


def downgrade():
    connection = op.get_bind()
    used = connection.exec_driver_sql(
        "SELECT EXISTS(SELECT 1 FROM execution_slots WHERE state<>'FREE' OR lease_epoch<>0) OR EXISTS(SELECT 1 FROM preflight_jobs WHERE lease_epoch<>0 OR current_execution IS NOT NULL)"
    ).scalar_one()
    if used:
        raise RuntimeError("Worker lease history requires reviewed recovery; downgrade refused.")
    op.drop_table("execution_slots")
    op.drop_table("scheduler_control")
    op.drop_constraint("ck_preflight_jobs_execution", "preflight_jobs", type_="check")
    op.drop_constraint("ck_preflight_jobs_epoch", "preflight_jobs", type_="check")
    for column in ("current_execution", "claimed_by", "deadline", "lease_until", "lease_epoch"):
        op.drop_column("preflight_jobs", column)
