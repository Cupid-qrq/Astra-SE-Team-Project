from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from uuid import uuid4

import pytest
from sqlalchemy import text
from teaching_fixtures import seed

from app.modules.identity.domain import Fault
from app.shared.effects import TransactionalEffects
from app.shared.repository import SqlRepository
from app.shared.uow import UnitOfWork


@pytest.fixture
def lesson(database):
    ids = seed(database, Path(__file__).parents[2] / "alembic.ini")
    return database, ids


def accept(lesson, key, code="print(1)", intent="FORMAL", effects_type=TransactionalEffects):
    from app.modules.submissions.application import Submissions

    engine, ids = lesson
    with UnitOfWork(engine) as connection:
        repo = SqlRepository(connection)
        request_id = str(uuid4())
        effects = effects_type(repo, request_id)
        return Submissions(repo, effects).accept(
            {"user_id": ids["student"], "role": "STUDENT"},
            {
                "assignment_id": ids["assignment"],
                "problem_id": ids["problem"],
                "language_key": "python3",
                "code": code,
            },
            key,
            intent,
            request_id,
        )


def test_ten_concurrent_replays_create_one_durable_submission(lesson):
    key = str(uuid4())
    with ThreadPoolExecutor(max_workers=10) as pool:
        results = list(pool.map(lambda _: accept(lesson, key), range(10)))
    assert len({receipt["submission_id"] for receipt, _ in results}) == 1
    assert sum(not replay for _, replay in results) == 1
    with lesson[0].connect() as conn:
        for table in ["submissions", "result_bases", "processing_cycles", "attempts", "queue_jobs"]:
            assert conn.scalar(text("SELECT count(*) FROM " + table)) == 1
        assert conn.scalar(text("SELECT pending_count FROM capacity_control")) == 1
        assert conn.scalar(text("SELECT pending_count FROM admission_users")) == 1
        assert (
            conn.scalar(
                text("SELECT count(*) FROM outbox_events WHERE event_type='SUBMISSION_ACCEPTED'")
            )
            == 1
        )


def test_replay_after_deadline_retains_original_formal_receipt(lesson):
    key = str(uuid4())
    receipt, _ = accept(lesson, key)
    with lesson[0].begin() as conn:
        conn.execute(text("UPDATE assignments SET due_at=clock_timestamp()-interval '1 second'"))
    replay, repeated = accept(lesson, key)
    assert repeated and replay["mode"] == "FORMAL"
    assert {k: v for k, v in replay.items() if k != "request_id"} == {
        k: v for k, v in receipt.items() if k != "request_id"
    }
    with pytest.raises(Fault) as error:
        accept(lesson, str(uuid4()))
    assert error.value.code == "DEADLINE_PASSED"


def test_conflicting_key_and_disabled_membership_do_not_replay(lesson):
    key = str(uuid4())
    accept(lesson, key)
    with pytest.raises(Fault) as error:
        accept(lesson, key, code="print(2)")
    assert error.value.code == "IDEMPOTENCY_CONFLICT"
    with lesson[0].begin() as conn:
        conn.execute(text("UPDATE course_members SET status='DISABLED'"))
    with pytest.raises(Fault) as error:
        accept(lesson, key)
    assert error.value.status == 404


def test_interval_and_personal_capacity_are_transactional(lesson):
    accept(lesson, str(uuid4()))
    with pytest.raises(Fault) as error:
        accept(lesson, str(uuid4()))
    assert error.value.code == "STUDENT_INTERVAL"
    for _ in range(2):
        with lesson[0].begin() as conn:
            conn.execute(
                text(
                    "UPDATE admission_users SET last_accepted_at=clock_timestamp()-interval '6 seconds'"
                )
            )
        accept(lesson, str(uuid4()))
    with lesson[0].begin() as conn:
        conn.execute(
            text(
                "UPDATE admission_users SET last_accepted_at=clock_timestamp()-interval '6 seconds'"
            )
        )
    with pytest.raises(Fault) as error:
        accept(lesson, str(uuid4()))
    assert error.value.code == "STUDENT_PENDING_LIMIT"


def test_audit_failure_rolls_back_receipt_queue_and_capacity(lesson):
    class BrokenEffects(TransactionalEffects):
        def record(self, *args, **kwargs):
            super().record(*args, **kwargs)
            raise RuntimeError("synthetic audit failure")

    with pytest.raises(RuntimeError):
        accept(lesson, str(uuid4()), effects_type=BrokenEffects)
    with lesson[0].connect() as conn:
        assert conn.scalar(text("SELECT count(*) FROM submissions")) == 0
        assert conn.scalar(text("SELECT pending_count FROM capacity_control")) == 0
        assert conn.scalar(text("SELECT count(*) FROM admission_users")) == 0


@pytest.mark.parametrize(
    "column,value",
    [
        ("code", "convert_to('changed','UTF8')"),
        ("mode", "'PRACTICE'"),
        ("accepted_at", "clock_timestamp()+interval '1 hour'"),
    ],
)
def test_original_submission_identity_cannot_be_changed(lesson, column, value):
    from sqlalchemy.exc import IntegrityError

    accept(lesson, str(uuid4()))
    with pytest.raises(IntegrityError), lesson[0].begin() as conn:
        conn.execute(text("UPDATE submissions SET " + column + "=" + value))


def test_global_capacity_refusal_has_no_partial_receipt(lesson):
    with lesson[0].begin() as conn:
        conn.execute(text("UPDATE capacity_control SET pending_count=100"))
    with pytest.raises(Fault) as error:
        accept(lesson, str(uuid4()))
    assert error.value.code == "GLOBAL_CAPACITY"
    with lesson[0].connect() as conn:
        assert conn.scalar(text("SELECT count(*) FROM submissions")) == 0


def test_basis_pointer_cannot_reference_another_submission(lesson):
    from sqlalchemy.exc import IntegrityError

    first, _ = accept(lesson, str(uuid4()))
    with lesson[0].begin() as conn:
        conn.execute(
            text(
                "UPDATE admission_users SET last_accepted_at=clock_timestamp()-interval '6 seconds'"
            )
        )
    second, _ = accept(lesson, str(uuid4()))
    with pytest.raises(IntegrityError), lesson[0].begin() as conn:
        conn.execute(
            text(
                "UPDATE submissions SET active_basis_id=(SELECT active_basis_id FROM submissions WHERE submission_id=:other) WHERE submission_id=:id"
            ),
            {"id": first["submission_id"], "other": second["submission_id"]},
        )


@pytest.mark.parametrize("code,status", [("", 422), ("x" * 65537, 413)])
def test_invalid_code_is_rejected_before_durable_admission(lesson, code, status):
    with pytest.raises(Fault) as error:
        accept(lesson, str(uuid4()), code=code)
    assert error.value.status == status


def test_disabled_account_cannot_replay(lesson):
    key = str(uuid4())
    accept(lesson, key)
    with lesson[0].begin() as conn:
        conn.execute(
            text("UPDATE users SET status='DISABLED' WHERE user_id=:id"),
            {"id": lesson[1]["student"]},
        )
    with pytest.raises(Fault) as error:
        accept(lesson, key)
    assert error.value.status == 403


def test_clock_skew_stops_new_formal_but_allows_replay_and_practice(lesson, monkeypatch):
    from datetime import UTC, datetime, timedelta

    import app.modules.submissions.application as module

    key = str(uuid4())
    accept(lesson, key)

    class SkewedClock:
        @staticmethod
        def now(zone):
            return datetime.now(UTC) + timedelta(seconds=6)

    monkeypatch.setattr(module, "datetime", SkewedClock, raising=False)
    assert accept(lesson, key)[1]
    with pytest.raises(Fault) as error:
        accept(lesson, str(uuid4()))
    assert error.value.code == "CLOCK_UNHEALTHY"
    with lesson[0].begin() as conn:
        conn.execute(
            text(
                "UPDATE admission_users SET last_accepted_at=clock_timestamp()-interval '6 seconds'"
            )
        )
    assert accept(lesson, str(uuid4()), intent="PRACTICE")[0]["mode"] == "PRACTICE"
