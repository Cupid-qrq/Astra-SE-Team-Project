"""Synthetic teaching rows only. No code is compiled or executed."""

import hashlib
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
    if browser and profile is None:
        raise ValueError("Browser fixture requires an explicit synthetic profile.")
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
                checksum=None if browser else "a" * 64,
                published_at=None if browser else now,
                published_preflight_id=None,  # Browser-only synthetic publication is linked below.
                revision=1,
                created_at=now,
                updated_at=now,
            ),
        )
        if browser:
            _publish_synthetic_browser_version(repo, ids, profile, now)
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


def _publish_synthetic_browser_version(repo, ids, profile, now):
    """Only isolated test schemas: synthesize AC facts, never execute code.

    A real application startup never imports or calls this fixture. Keeping the
    full link lets browser assignment tests retain the production publication guard.
    """
    from app.adapters.judge_profiles import SnapshotCatalog
    from app.modules.judging.domain import freeze_snapshot
    from app.modules.problems.application import Problems

    repo.add(
        "testcases",
        dict(
            testcase_id=str(uuid4()),
            version_id=ids["version"],
            order=1,
            input_blob=b"1",
            answer_blob=b"1",
            input_sha256=hashlib.sha256(b"1").hexdigest(),
            answer_sha256=hashlib.sha256(b"1").hexdigest(),
        ),
    )
    for language in profile["languages"]:
        code = (
            b"// SYNTHETIC BROWSER FIXTURE: never executed\n#include <iostream>\nint main(){int n;std::cin>>n;std::cout<<n;}"
            if language["language_key"] == "cpp17"
            else b"# SYNTHETIC BROWSER FIXTURE: never executed\nprint(input().strip())"
        )
        repo.add(
            "reference_programs",
            dict(
                reference_id=str(uuid4()),
                version_id=ids["version"],
                language_key=language["language_key"],
                code=code,
                code_sha256=hashlib.sha256(code).hexdigest(),
            ),
        )
    plan = freeze_snapshot(
        Problems(repo, TransactionalEffects(repo, str(uuid4()))).snapshot(ids["version"]),
        SnapshotCatalog([profile]),
    )
    pid = str(uuid4())
    repo.add(
        "preflight_runs",
        dict(
            preflight_id=pid,
            version_id=ids["version"],
            version_revision=1,
            content_digest=plan.content_digest,
            profile_hash=plan.profile_hash,
            frozen_blob=plan.blob,
            case_manifest=[
                dict(language_key=language, case_kind=kind, case_order=order)
                for language, kind, order in plan.cases
            ],
            state="QUEUED",
            created_by=ids["teacher"],
            created_at=now,
            started_at=None,
            finished_at=None,
        ),
    )
    for language, kind, order in plan.cases:
        repo.add(
            "preflight_cases",
            dict(
                preflight_id=pid,
                language_key=language,
                case_kind=kind,
                case_order=order,
                state="FINISHED",
                verdict="AC",
                engine_meta={"fixture": "synthetic-browser-no-execution"},
            ),
        )
    repo.change("preflight_runs", pid, state="PASSED", started_at=now, finished_at=now)
    repo.add(
        "preflight_jobs", dict(job_id=str(uuid4()), preflight_id=pid, state="DONE", ready_at=now)
    )
    repo.change(
        "problem_versions",
        ids["version"],
        published_at=now,
        checksum=plan.content_digest,
        published_preflight_id=pid,
    )
