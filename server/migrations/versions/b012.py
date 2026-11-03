from alembic import op

revision = "b012"
down_revision = "b011"


def upgrade():
    op.get_bind().exec_driver_sql("""
ALTER TABLE execution_slots ADD COLUMN submission_job_id uuid CONSTRAINT uq_execution_slots_submission_job_id UNIQUE REFERENCES queue_jobs(job_id);
ALTER TABLE execution_slots DROP CONSTRAINT ck_execution_slots_binding;
ALTER TABLE execution_slots ADD CONSTRAINT ck_execution_slots_binding CHECK(
 (state='FREE')=(job_id IS NULL AND submission_job_id IS NULL)
 AND NOT(job_id IS NOT NULL AND submission_job_id IS NOT NULL));
""")


def downgrade():
    if (
        op.get_bind()
        .exec_driver_sql(
            "SELECT EXISTS(SELECT 1 FROM execution_slots WHERE submission_job_id IS NOT NULL)"
        )
        .scalar_one()
    ):
        raise RuntimeError("Submission slot is owned; downgrade refused.")
    op.drop_constraint("ck_execution_slots_binding", "execution_slots", type_="check")
    op.drop_column("execution_slots", "submission_job_id")
    op.create_check_constraint(
        "ck_execution_slots_binding", "execution_slots", "(state='FREE')=(job_id IS NULL)"
    )
