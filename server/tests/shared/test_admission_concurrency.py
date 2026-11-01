from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from threading import Event
from time import monotonic, sleep
from uuid import uuid4

import pytest
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError
from teaching_fixtures import identity, seed

from app.modules.assignments.application import Assignments
from app.modules.courses.application import Courses
from app.modules.identity.domain import Fault
from app.shared.effects import TransactionalEffects
from app.shared.repository import SqlRepository
from app.shared.uow import UnitOfWork


@pytest.fixture
def teaching(database):
    return database, seed(database, Path(__file__).parents[2] / "alembic.ini")


def admit(repo, ids):
    actor = identity(repo).actor(ids["token"], activity=False)
    return Assignments(repo, TransactionalEffects(repo, str(uuid4()))).admission(
        actor, ids["assignment"], ids["problem"], "python3", "FORMAL"
    )


def wait_for_lock(connection, pid):
    end = monotonic() + 5
    while monotonic() < end:
        if (
            connection.scalar(
                text("SELECT wait_event_type FROM pg_stat_activity WHERE pid=:pid"), {"pid": pid}
            )
            == "Lock"
        ):
            return
        connection.execute(text("SELECT pg_stat_clear_snapshot()"))
        sleep(0.01)
    raise AssertionError("Worker did not block on a database lock")


def waiting(engine, work, started, pid):
    with UnitOfWork(engine) as conn:
        conn.execute(text("SET LOCAL statement_timeout='8000ms'"))
        pid.append(conn.scalar(text("SELECT pg_backend_pid()")))
        started.set()
        repo = SqlRepository(conn)
        repo.guard()
        return work(repo)


@pytest.mark.parametrize("kind", ["member", "account"])
def test_disable_commits_before_waiting_admission(teaching, kind):
    engine, ids = teaching
    started, pid = Event(), []
    with ThreadPoolExecutor(max_workers=1) as pool:
        with UnitOfWork(engine) as first:
            repo = SqlRepository(first)
            repo.guard()
            effects = TransactionalEffects(repo, str(uuid4()))
            if kind == "member":
                Courses(repo, effects).member(
                    repo.get("users", ids["teacher"]),
                    ids["course"],
                    ids["student"],
                    {"status": "DISABLED", "expected_revision": 1},
                )
            else:
                identity(repo).update_user(
                    repo.get("users", ids["admin"]),
                    ids["student"],
                    {
                        "status": "DISABLED",
                        "expected_revision": 1,
                        "reason": "Testing disable atomicity",
                    },
                )
            future = pool.submit(waiting, engine, lambda r: admit(r, ids), started, pid)
            assert started.wait(3)
            wait_for_lock(first, pid[0])
        with pytest.raises(Fault) as failure:
            future.result(timeout=10)
    assert failure.value.status == (404 if kind == "member" else 401)


def test_admission_then_member_disable_is_serial(teaching):
    engine, ids = teaching
    started, pid = Event(), []
    with ThreadPoolExecutor(max_workers=1) as pool:
        with UnitOfWork(engine) as first:
            repo = SqlRepository(first)
            repo.guard()
            assert admit(repo, ids)["mode"] == "FORMAL"

            def disable(r):
                return Courses(r, TransactionalEffects(r, str(uuid4()))).member(
                    r.get("users", ids["teacher"]),
                    ids["course"],
                    ids["student"],
                    {"status": "DISABLED", "expected_revision": 1},
                )

            future = pool.submit(waiting, engine, disable, started, pid)
            assert started.wait(3)
            wait_for_lock(first, pid[0])
        assert future.result(timeout=10)["status"] == "DISABLED"


def test_lock_wait_crossing_deadline_uses_current_database_time(teaching):
    engine, ids = teaching
    started, pid = Event(), []
    with ThreadPoolExecutor(max_workers=1) as pool:
        with UnitOfWork(engine) as first:
            repo = SqlRepository(first)
            repo.guard()
            first.execute(
                text(
                    "UPDATE assignments SET due_at=clock_timestamp()+interval '500 milliseconds' WHERE assignment_id=:id"
                ),
                {"id": ids["assignment"]},
            )
            future = pool.submit(waiting, engine, lambda r: admit(r, ids), started, pid)
            assert started.wait(3)
            wait_for_lock(first, pid[0])
            first.execute(
                text(
                    "SELECT pg_sleep(GREATEST(0,EXTRACT(epoch FROM (due_at-clock_timestamp())))+.05) FROM assignments WHERE assignment_id=:id"
                ),
                {"id": ids["assignment"]},
            )
        with pytest.raises(Fault) as failure:
            future.result(timeout=10)
    assert failure.value.code == "DEADLINE_PASSED"


@pytest.mark.parametrize("kind", ["member", "account"])
@pytest.mark.parametrize("table", ["audit_events", "outbox_events"])
def test_real_disable_effect_failure_rolls_back_all(teaching, kind, table):
    engine, ids = teaching
    with engine.begin() as conn:
        conn.exec_driver_sql(f"ALTER TABLE {table} ADD CONSTRAINT inject_failure CHECK (false)")
    with pytest.raises(IntegrityError):
        with UnitOfWork(engine) as conn:
            repo = SqlRepository(conn)
            repo.guard()
            if kind == "member":
                Courses(repo, TransactionalEffects(repo, str(uuid4()))).member(
                    repo.get("users", ids["teacher"]),
                    ids["course"],
                    ids["student"],
                    {"status": "DISABLED", "expected_revision": 1},
                )
            else:
                identity(repo).update_user(
                    repo.get("users", ids["admin"]),
                    ids["student"],
                    {
                        "status": "DISABLED",
                        "expected_revision": 1,
                        "reason": "Testing rollback of disable",
                    },
                )
    with UnitOfWork(engine) as conn:
        repo = SqlRepository(conn)
        assert repo.get("users", ids["student"])["status"] == "ACTIVE"
        assert repo.get("course_members", (ids["course"], ids["student"]))["status"] == "ACTIVE"
        assert repo.get("sessions", ids["session"])["revoked_at"] is None
        assert repo.get("courses", ids["course"])["revision"] == 1
        assignment = repo.get("assignments", ids["assignment"])
        assert (assignment["revision"], assignment["grade_epoch"]) == (1, 1)
