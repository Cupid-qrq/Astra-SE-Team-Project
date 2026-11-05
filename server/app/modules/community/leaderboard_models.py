"""Course-scoped name visibility preferences; anonymous by default."""

from sqlalchemy import Boolean, Column, ForeignKeyConstraint, Table

from app.modules.identity.models import metadata, uid

preferences = Table(
    "leaderboard_preferences",
    metadata,
    uid("course_id", primary_key=True),
    uid("user_id", primary_key=True),
    Column("show_name", Boolean, nullable=False),
    ForeignKeyConstraint(
        ["course_id", "user_id"], ["course_members.course_id", "course_members.user_id"]
    ),
)
