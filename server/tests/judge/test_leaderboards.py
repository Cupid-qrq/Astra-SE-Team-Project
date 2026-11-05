from uuid import uuid4

import pytest
from sqlalchemy import text
from test_submission_worker import queued as queued

from app.modules.identity.domain import Fault
from app.shared.effects import TransactionalEffects
from app.shared.repository import SqlRepository
from tests.shared.conftest import database as database


def service(conn):
    from app.modules.community.leaderboards import Leaderboards

    repo = SqlRepository(conn)
    return repo, Leaderboards(repo, TransactionalEffects(repo, str(uuid4())))


def finish(engine):
    from app.modules.submissions.worker_store import SubmissionStore

    store = SubmissionStore(engine)
    claim = store.claim()
    for order in (1, 2):
        store.begin_case(claim, order)
        assert store.record_case(claim, order, "AC", 1, None)


def test_progress_is_current_formal_deduplicated_and_anonymous(queued):
    engine, ids, _, _ = queued
    finish(engine)
    with engine.begin() as conn:
        repo, board = service(conn)
        student = repo.required("users", ids["student"])
        teacher = repo.required("users", ids["teacher"])
        result = board.read(student, ids["course"], "progress")
        assert result["included_assignments"] == 1
        assert result["items"][0]["value"] == 1
        assert result["items"][0]["is_me"]
        assert ids["student"] not in str(result)
        assert student["display_name"] not in str(result)
        assert (
            board.read(teacher, ids["course"], "progress")["items"][0]["display_name"]
            == student["display_name"]
        )
        board.preference(student, ids["course"], {"show_name": True})
        assert (
            board.read(student, ids["course"], "progress")["items"][0]["display_name"]
            == student["display_name"]
        )
        # A stale AC on a superseded effective target cannot count.
        repo.change(
            "assignment_items",
            (ids["assignment"], ids["problem"]),
            effective_version_id=ids["version"],
        )
        assert board.read(student, ids["course"], "progress")["items"][0]["value"] == 0


def test_grades_use_only_published_current_epoch_snapshots(queued):
    from app.modules.grades.application import Grades

    engine, ids, _, _ = queued
    finish(engine)
    with engine.begin() as conn:
        repo, board = service(conn)
        teacher = repo.required("users", ids["teacher"])
        assert board.read(teacher, ids["course"], "grades")["included_assignments"] == 0
        conn.execute(text("UPDATE assignments SET due_at=clock_timestamp()-interval '1 second'"))
        grades = Grades(repo, board.effects)
        grades.publish(teacher, ids["assignment"], {"expected_revision": 1, "reason": "核验完成"})
        result = board.read(teacher, ids["course"], "grades")
        assert result["included_assignments"] == 1
        assert result["items"][0]["value"] == 100
        epoch = repo.required("assignments", ids["assignment"])["grade_epoch"]
        for changes in ({"fairness_review": "PENDING"}, {"grade_epoch": epoch + 1}):
            repo.change("assignments", ids["assignment"], **changes)
            result = board.read(teacher, ids["course"], "grades")
            assert result["included_assignments"] == 0
            assert result["items"][0]["value"] == 0
            repo.change("assignments", ids["assignment"], fairness_review="NONE", grade_epoch=epoch)


def test_course_access_and_archived_preference(queued):
    engine, ids, _, _ = queued
    with engine.begin() as conn:
        repo, board = service(conn)
        student = repo.required("users", ids["student"])
        for actor in (repo.required("users", ids["admin"]), {**student, "status": "DISABLED"}):
            with pytest.raises(Fault):
                board.read(actor, ids["course"], "progress")
        repo.change("courses", ids["course"], status="ARCHIVED", archived_at=repo.now())
        assert board.read(student, ids["course"], "progress")["items"]
        with pytest.raises(Fault) as error:
            board.preference(student, ids["course"], {"show_name": True})
        assert error.value.code == "COURSE_ARCHIVED"
        repo.change("course_members", (ids["course"], ids["student"]), status="DISABLED")
        with pytest.raises(Fault):
            board.read(student, ids["course"], "progress")


def test_progress_dedup_practice_old_cycle_and_unopened_assignment(queued):
    from datetime import timedelta

    from test_submissions import accept

    from app.modules.submissions.processing import start_cycle

    engine, ids, _, _ = queued
    finish(engine)
    with engine.begin() as conn:
        SqlRepository(conn).change("admission_users", ids["student"], last_accepted_at=None)
    accept((engine, ids), str(uuid4()))
    finish(engine)
    with engine.begin() as conn:
        SqlRepository(conn).change("admission_users", ids["student"], last_accepted_at=None)
    accept((engine, ids), str(uuid4()), intent="PRACTICE")
    finish(engine)
    with engine.begin() as conn:
        repo, board = service(conn)
        actor = repo.required("users", ids["student"])
        assert board.read(actor, ids["course"], "progress")["items"][0]["value"] == 1
        submissions = repo.rows("submissions", user_id=ids["student"])
        # Practice AC remains, but both formal AC attempts are superseded by new cycles.
        for formal in submissions:
            if formal["mode"] == "FORMAL":
                start_cycle(
                    repo, formal, formal["active_basis_id"], "NORMAL", "MANUAL", "retry fixture"
                )
        assert board.read(actor, ids["course"], "progress")["items"][0]["value"] == 0
        assignment = repo.required("assignments", ids["assignment"])
        repo.add(
            "assignments",
            {
                **assignment,
                "assignment_id": str(uuid4()),
                "open_at": repo.now() + timedelta(minutes=5),
            },
        )
        repo.add("assignments", {**assignment, "assignment_id": str(uuid4()), "published_at": None})
        assert board.read(actor, ids["course"], "progress")["included_assignments"] == 1


def test_zero_ties_stable_ids_visibility_and_disabled_roster(queued):
    engine, ids, _, _ = queued
    with engine.begin() as conn:
        repo, board = service(conn)
        actor = repo.required("users", ids["student"])
        others = []
        for index in range(2):
            user = repo.add(
                "users",
                {
                    **actor,
                    "user_id": str(uuid4()),
                    "login_name": f"peer_{index}",
                    "display_name": f"同学{index}",
                },
            )
            repo.add(
                "course_members",
                {
                    "course_id": ids["course"],
                    "user_id": user["user_id"],
                    "status": "ACTIVE",
                    "joined_at": repo.now(),
                },
            )
            others.append(user)
        result = board.read(actor, ids["course"], "progress")
        assert [row["rank"] for row in result["items"]] == [1, 1, 1]
        assert [row["value"] for row in result["items"]] == [0, 0, 0]
        entries = [row["entry_id"] for row in result["items"]]
        assert entries == sorted(entries)
        assert sum(row["is_me"] for row in result["items"]) == 1
        board.preference(others[0], ids["course"], {"show_name": True})
        visible = board.read(actor, ids["course"], "progress")
        assert [row["entry_id"] for row in visible["items"]] == entries
        assert others[0]["display_name"] in str(visible)
        assert others[1]["display_name"] not in str(visible)
        assert all(user["user_id"] not in str(visible) for user in others)
        repo.change("users", others[1]["user_id"], status="DISABLED")
        assert len(board.read(actor, ids["course"], "progress")["items"]) == 2
        with pytest.raises(Fault):
            board.preference(
                actor, ids["course"], {"show_name": True, "user_id": others[0]["user_id"]}
            )


def test_rejudge_excludes_published_grade_until_activation(queued):
    from test_rejudge import replacement

    from app.modules.grades.application import Grades
    from app.modules.rejudge.application import Rejudges

    engine, ids, _, _ = queued
    finish(engine)
    target = replacement(engine, ids)
    with engine.begin() as conn:
        repo, board = service(conn)
        actor = repo.required("users", ids["teacher"])
        conn.execute(text("UPDATE assignments SET due_at=clock_timestamp()-interval '1 second'"))
        Grades(repo, board.effects).publish(
            actor, ids["assignment"], {"expected_revision": 1, "reason": "已核验"}
        )
        rejudge = Rejudges(repo, board.effects)
        preview = rejudge.preview(
            actor,
            ids["assignment"],
            {"problem_id": ids["problem"], "new_version_id": target, "expected_revision": 1},
        )
        rejudge.create(
            actor,
            ids["assignment"],
            {
                "new_version_id": target,
                "range_checksum": preview["range_checksum"],
                "expected_revision": 1,
                "reason": "fix fixture",
            },
        )
        result = board.read(actor, ids["course"], "grades")
        assert result["included_assignments"] == 0
        assert result["items"][0]["value"] == 0


def test_foreign_course_teacher_and_student_cannot_read_or_set_preference(queued):
    from app.modules.courses.application import Courses

    engine, ids, _, _ = queued
    with engine.begin() as conn:
        repo, board = service(conn)
        teacher = repo.required("users", ids["teacher"])
        student = repo.required("users", ids["student"])
        outsider = repo.add(
            "users", {**teacher, "user_id": str(uuid4()), "login_name": "outsider_teacher"}
        )
        foreign = Courses(repo, board.effects).create(outsider, {"title": "other course"})[
            "course_id"
        ]
        for actor in (teacher, student):
            with pytest.raises(Fault):
                board.read(actor, foreign, "progress")
        with pytest.raises(Fault):
            board.preference(teacher, ids["course"], {"show_name": True})
        with pytest.raises(Fault):
            board.preference(student, foreign, {"show_name": True})
        with pytest.raises(Fault):
            board.read(student, ids["course"], "unknown")
