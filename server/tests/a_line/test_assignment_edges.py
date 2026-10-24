from datetime import timedelta

import pytest
from app.modules.assignments.application import Assignments
from app.modules.identity.domain import Fault, utc
from astra_a.app import create_app
from astra_a.storage import SqlRepository
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError
from test_assignments import make_assignment, publish


def test_missing_coordination_port_fails_closed(env):
    teacher, _, _, _, aid, _ = make_assignment(env)
    publish(teacher, aid)
    env.app = create_app(
        env.engine,
        env.effects,
        secret=b"test-only-session-key-32-bytes-long",
        origin="https://testserver",
        clock=env.clock,
    )
    response = env.login("teacher_a").patch(
        f"/api/v1/assignments/{aid}/deadline",
        json={
            "expected_revision": 2,
            "new_due_at": utc(env.clock() + timedelta(days=1)),
            "reason": "未接入成绩和公平协调器不能静默延期",
        },
    )
    assert response.status_code == 503


def test_database_cannot_rewrite_published_assignment_content(env):
    teacher, _, _, _, aid, _ = make_assignment(env)
    publish(teacher, aid)
    for sql in [
        "UPDATE assignments SET title='改写' WHERE assignment_id=:aid",
        "DELETE FROM assignment_items WHERE assignment_id=:aid",
        "UPDATE assignment_items SET points=99 WHERE assignment_id=:aid",
    ]:
        with pytest.raises(IntegrityError):
            with env.engine.begin() as conn:
                conn.execute(text(sql), {"aid": aid})


def test_admission_port_checks_actor_membership_language_and_current_clock(env):
    teacher, _, pid, vid, aid, _ = make_assignment(env)
    publish(teacher, aid)
    env.clock.advance(timedelta(hours=1))
    with env.engine.begin() as conn:
        repo = SqlRepository(conn, env.clock)
        repo.guard()
        service = Assignments(repo, env.effects, env.coordination)
        student = repo.get("users", env.users["student_a"])
        result = service.admission(student, aid, pid, "python3", "FORMAL")
        assert result["version_id"] == vid and result["mode"] == "FORMAL"
        with pytest.raises(Fault):
            service.admission(student, aid, pid, "ruby", "FORMAL")
        with pytest.raises(Fault):
            service.admission(
                repo.get("users", env.users["teacher_a"]), aid, pid, "python3", "FORMAL"
            )
        env.clock.advance(timedelta(hours=1))
        with pytest.raises(Fault):
            service.admission(student, aid, pid, "python3", "FORMAL")
        assert service.admission(student, aid, pid, "python3", "PRACTICE")["mode"] == "PRACTICE"
