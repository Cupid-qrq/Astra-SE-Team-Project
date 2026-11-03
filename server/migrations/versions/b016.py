from pathlib import Path

from alembic import op

revision = "b016"
down_revision = "b015"


def upgrade():
    op.get_bind().exec_driver_sql(
        (Path(__file__).parents[1] / "sql/016_retention.sql").read_text(encoding="utf-8")
    )


def downgrade():
    tables = (
        "runtime_config_versions",
        "emergency_grants",
        "retention_confirmations",
        "retention_plans",
    )
    connection = op.get_bind()
    if any(
        connection.exec_driver_sql('SELECT EXISTS(SELECT 1 FROM "' + table + '")').scalar_one()
        for table in tables
    ):
        raise RuntimeError("Retention and access history must be retained.")
    for table in tables:
        op.drop_table(table)
