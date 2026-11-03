from pathlib import Path

from alembic import op

revision = "b015"
down_revision = "b014"


def upgrade():
    op.get_bind().exec_driver_sql(
        (Path(__file__).parents[1] / "sql/015_operations.sql").read_text(encoding="utf-8")
    )


def downgrade():
    tables = (
        "course_cleanup",
        "course_holds",
        "notifications",
        "incident_requests",
        "incident_assignments",
        "fairness_incidents",
    )
    connection = op.get_bind()
    if any(
        connection.exec_driver_sql('SELECT EXISTS(SELECT 1 FROM "' + table + '")').scalar_one()
        for table in tables
    ):
        raise RuntimeError(
            "Operational history must be retained; use a reviewed forward migration."
        )
    for table in tables:
        op.drop_table(table)
