from typing import Protocol

from app.modules.identity.ports import Record, Repository


class FeedbackSubmissions(Protocol):
    """B queries the authorized submission/current attempt in this SAME transaction.

    Returns user_id, course_id, state, verdict, feedback_version_id, or None.
    Never return code, hidden cases or raw executor output. A rechecks course/owner.
    The reference is frozen by B at terminalization using Learning.resolve().
    """

    def feedback(self, repo: Repository, actor: Record, submission_id: str) -> Record | None: ...
