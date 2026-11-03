"""Synthetic browser publication data must satisfy the formal reference rules."""

from pathlib import Path
from uuid import uuid4

from http_fixtures import profile
from teaching_fixtures import seed

from app.modules.assignments.application import Assignments
from app.shared.effects import TransactionalEffects
from app.shared.repository import SqlRepository
from app.shared.uow import UnitOfWork


def test_browser_published_fixture_is_linked_and_can_be_selected_for_new_assignment(database):
    ids = seed(database, Path(__file__).parents[2] / "alembic.ini", profile=profile(), browser=True)
    with UnitOfWork(database) as conn:
        repo = SqlRepository(conn)
        repo.guard()
        version = repo.get("problem_versions", ids["version"])
        assert version["published_preflight_id"] is not None
        run = repo.get("preflight_runs", version["published_preflight_id"])
        assert run["version_id"] == ids["version"] and run["state"] == "PASSED"
        result = Assignments(repo, TransactionalEffects(repo, str(uuid4()))).create(
            repo.get("users", ids["teacher"]),
            {
                "course_id": ids["course"],
                "title": "synthetic assignment",
                "open_at": "2020-01-01T00:00:00.000Z",
                "due_at": "2030-01-01T00:00:00.000Z",
                "ai_policy": "DISABLED",
                "items": [
                    {"problem_id": ids["problem"], "version_id": ids["version"], "points": 100}
                ],
            },
        )
        assert result["assignment_id"]
