# ruff: noqa: E402
"""Isolated browser-only course; publication facts are synthetic, never production."""

import json
import sys
from datetime import timedelta
from pathlib import Path
from uuid import UUID, uuid4

SERVER = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(SERVER), str(SERVER / "tests/shared")]
from sqlalchemy import create_engine
from teaching_fixtures import _publish_synthetic_browser_version
from web_harness import scope

from app.shared.repository import SqlRepository
from app.shared.uow import UnitOfWork


def main():
    url, schema, marker = scope()
    if json.loads(marker.read_text(encoding="utf-8")) != {
        "schema": schema,
        "database": url.database,
    }:
        raise RuntimeError("Browser fixture scope mismatch")
    engine = create_engine(
        url, hide_parameters=True, connect_args={"options": "-csearch_path=" + schema}
    )
    try:
        with UnitOfWork(engine) as conn:
            repo = SqlRepository(conn)
            now = repo.now()
            if sys.argv[1:]:
                assignment_id = str(UUID(sys.argv[1]))
                assignment = repo.required("assignments", assignment_id)
                if assignment["title"] != "管理联调作业":
                    raise RuntimeError("Not an operations browser fixture")
                repo.change("assignments", assignment_id, due_at=now - timedelta(minutes=5))
                return
            teacher = "10000000-0000-4000-8000-000000000001"
            student = "10000000-0000-4000-8000-000000000003"
            original_course = repo.rows("courses", title="编辑器测试课程")[0]
            original_problem = repo.rows("problems", owner_course_id=original_course["course_id"])[
                0
            ]
            original_version = repo.rows(
                "problem_versions", problem_id=original_problem["problem_id"]
            )[0]
            original_assignment = repo.rows("assignments", course_id=original_course["course_id"])[
                0
            ]
            ids = {key: str(uuid4()) for key in ("course", "problem", "version", "assignment")}
            ids["teacher"] = teacher
            repo.add(
                "courses",
                {
                    **original_course,
                    "course_id": ids["course"],
                    "title": "管理联调课程 " + ids["course"][:8],
                },
            )
            repo.add(
                "course_members",
                dict(course_id=ids["course"], user_id=student, status="ACTIVE", joined_at=now),
            )
            repo.add(
                "problems",
                {
                    **original_problem,
                    "problem_id": ids["problem"],
                    "owner_course_id": ids["course"],
                },
            )
            repo.add(
                "problem_versions",
                {
                    **original_version,
                    "problem_id": ids["problem"],
                    "version_id": ids["version"],
                    "published_at": None,
                    "published_preflight_id": None,
                    "checksum": None,
                },
            )
            _publish_synthetic_browser_version(repo, ids, original_version["profile"], now)
            repo.add(
                "assignments",
                {
                    **original_assignment,
                    "assignment_id": ids["assignment"],
                    "course_id": ids["course"],
                    "title": "管理联调作业",
                    "published_at": None,
                    "due_at": now + timedelta(hours=1),
                    "open_at": now - timedelta(hours=1),
                },
            )
            repo.add(
                "assignment_items",
                dict(
                    assignment_id=ids["assignment"],
                    problem_id=ids["problem"],
                    original_version_id=ids["version"],
                    effective_version_id=ids["version"],
                    points=100,
                ),
            )
            repo.change("assignments", ids["assignment"], published_at=now - timedelta(hours=1))
        print(json.dumps(ids))
    finally:
        engine.dispose()


if __name__ == "__main__":
    main()
