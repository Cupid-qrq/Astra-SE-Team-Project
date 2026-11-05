"""Persist each student's course leaderboard name visibility."""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import UUID

revision = "b018"
down_revision = "b017"


def upgrade():
    op.create_table(
        "leaderboard_preferences",
        sa.Column("course_id", UUID(as_uuid=False), nullable=False),
        sa.Column("user_id", UUID(as_uuid=False), nullable=False),
        sa.Column("show_name", sa.Boolean(), nullable=False),
        sa.PrimaryKeyConstraint("course_id", "user_id"),
        sa.ForeignKeyConstraint(
            ["course_id", "user_id"], ["course_members.course_id", "course_members.user_id"]
        ),
    )


def downgrade():
    if (
        op.get_bind()
        .exec_driver_sql("SELECT EXISTS (SELECT 1 FROM leaderboard_preferences)")
        .scalar_one()
    ):
        raise RuntimeError("Retain leaderboard preferences or restore a compatible backup.")
    op.drop_table("leaderboard_preferences")
