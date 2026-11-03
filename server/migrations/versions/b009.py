from pathlib import Path

from alembic import op

revision = "b009"
down_revision = "b008"


def upgrade():
    sql = (Path(__file__).parents[1] / "sql/009_preflight_publication.sql").read_text(
        encoding="utf-8"
    )
    op.get_bind().exec_driver_sql(sql)


def downgrade():
    # Constraint-only reversal, no historical rows are deleted or changed.
    op.drop_constraint("fk_versions_published_preflight", "problem_versions", type_="foreignkey")
    op.drop_constraint("uq_preflight_version_run", "preflight_runs", type_="unique")
