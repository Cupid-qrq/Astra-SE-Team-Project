"""Synthetic teaching rows only. No code is compiled or executed."""

from datetime import timedelta
from uuid import uuid4

from alembic import command
from alembic.config import Config

from app.modules.identity.application import Identity
from app.shared.effects import TransactionalEffects
from app.shared.repository import SqlRepository
from app.shared.uow import UnitOfWork

SECRET = b"test-only-secret-at-least-32-bytes"


class UnusedPasswords:
    def hash(self, password):
        raise AssertionError("Password hashing is not part of this fixture")

    def verify(self, password, encoded):
        raise AssertionError("Password verification is not part of this fixture")


def identity(repo):
    return Identity(repo, UnusedPasswords(), TransactionalEffects(repo, str(uuid4())), SECRET)


def seed(engine, config_path, *, due_seconds=3600, profile=None, browser=False):
    config = Config(str(config_path))
    with engine.begin() as conn:
        config.attributes["connection"] = conn
        command.upgrade(config, "head")
    ids = {
        key: str(uuid4())
        for key in (
            "teacher",
            "student",
            "admin",
            "course",
            "family",
            "problem",
            "version",
            "assignment",
        )
    }
    if browser:
        ids.update(
            teacher="10000000-0000-4000-8000-000000000001",
            student="10000000-0000-4000-8000-000000000003",
            admin="10000000-0000-4000-8000-000000000004",
        )
    with UnitOfWork(engine) as conn:
        repo = SqlRepository(conn)
        now = repo.now()
        for key, role in [("teacher", "TEACHER"), ("student", "STUDENT"), ("admin", "ADMIN")]:
            repo.add(
                "users",
                dict(
                    user_id=ids[key],
                    login_name=key + "_a" if browser else key,
                    display_name=key + "_a" if browser else key,
                    role=role,
                    status="ACTIVE",
                    password_hash="test-only",
                    must_change_password=False,
                    revision=1,
                    created_at=now,
                    updated_at=now,
                ),
            )
        repo.add(
            "courses",
            dict(
                course_id=ids["course"],
                teacher_id=ids["teacher"],
                title="编辑器测试课程" if browser else "course",
                status="ACTIVE",
                archived_at=None,
                revision=1,
                created_at=now,
                updated_at=now,
            ),
        )
        repo.add(
            "course_members",
            dict(course_id=ids["course"], user_id=ids["student"], status="ACTIVE", joined_at=now),
        )
        repo.add(
            "problem_families",
            dict(canonical_problem_id=ids["family"], owner_teacher_id=ids["teacher"], label="test"),
        )
        repo.add(
            "problems",
            dict(
                problem_id=ids["problem"],
                canonical_problem_id=ids["family"],
                owner_course_id=ids["course"],
                practice_released=False,
                practice_version_id=None,
                created_at=now,
                updated_at=now,
                revision=1,
            ),
        )
        repo.add(
            "problem_versions",
            dict(
                version_id=ids["version"],
                problem_id=ids["problem"],
                version_no=1,
                title="两数之和" if browser else "test",
                statement="test",
                samples=[{"input": "1", "output": "1"}],
                tags=[],
                profile=profile or {"languages": [{"language_key": "python3"}]},
                source_ref="synthetic",
                checksum="a" * 64,
                published_at=now,
                published_preflight_id=str(uuid4()),
                revision=1,
                created_at=now,
                updated_at=now,
            ),
        )
        repo.add(
            "assignments",
            dict(
                assignment_id=ids["assignment"],
                course_id=ids["course"],
                title="编辑器固定作业" if browser else "test",
                open_at=now - timedelta(hours=1),
                due_at=now + timedelta(seconds=due_seconds),
                ai_policy="DISABLED",
                published_at=None,
                revision=1,
                grade_epoch=1,
                fairness_review="NONE",
                active_grade_version=None,
                active_rejudge_batch_id=None,
                created_at=now,
                updated_at=now,
            ),
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
        repo.change("assignments", ids["assignment"], published_at=now)
        ids["token"], session = identity(repo).issue(ids["student"])
        ids["session"] = session["session_id"]
    return ids
