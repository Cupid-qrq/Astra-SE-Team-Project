from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from uuid import uuid4

import pytest
from preflight_fixtures import catalog, draft
from sqlalchemy import text
from test_preflight_storage import enqueue

from app.adapters.course_executor import ExecutionResult
from app.shared.judge import ExecutionError


@pytest.fixture
def task(database):
    ids, snapshot = draft(database)
    receipt = enqueue(database, ids, snapshot)
    return database, ids, snapshot, receipt


def test_concurrent_claim_is_single_slot_and_frozen_material_is_private(task):
    from app.modules.judging.worker_store import WorkerStore

    engine, _, snapshot, _ = task
    store = WorkerStore(engine)
    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(lambda _: store.claim(), range(2)))
    active = [r for r in results if r]
    assert len(active) == 1 and active[0].epoch > 0
    assert "SECRET" not in repr(active[0])
    assert store.claim() is None


def test_round_executes_outside_transaction_all_points_then_publishes_evidence(task):
    from app.modules.judging.worker import PreflightWorker
    from app.modules.judging.worker_store import WorkerStore

    engine, _, snapshot, receipt = task
    calls = []

    class Executor:
        def __init__(self, image):
            self.image = image

        def execute(self, identity, language, code, stdin, timeout=40):
            with engine.connect() as conn:
                assert (
                    conn.scalar(text("SELECT state FROM execution_slots WHERE slot_id=1")) == "BUSY"
                )
                assert conn.scalar(text("SELECT current_execution FROM preflight_jobs")) == identity
            calls.append(identity)
            output = b"1" if stdin == b"1" else b"SECRET_ANSWER"
            return ExecutionResult("RUN", None, 0, output, 1, None)

        def cancel(self, identity):
            return True

    # Test profiles use different images; execution registry is supplied explicitly.
    worker = PreflightWorker(
        WorkerStore(engine),
        catalog(snapshot),
        {
            row["language_key"]: Executor(row["image_digest"])
            for row in snapshot["profile"]["languages"]
        },
    )
    assert worker.run_once()
    with engine.connect() as conn:
        assert conn.scalar(text("SELECT state FROM preflight_runs")) == "PASSED"
        assert conn.scalar(text("SELECT count(*) FROM preflight_cases WHERE verdict='AC'")) == 4
        assert conn.scalar(text("SELECT state FROM execution_slots WHERE slot_id=1")) == "FREE"
        assert conn.scalar(text("SELECT state FROM preflight_jobs")) == "DONE"
    assert len(set(calls)) == 4
    assert not worker.run_once()


@pytest.mark.parametrize("crash_round", range(20))
def test_expired_lease_recovery_fences_late_result_and_requires_cleanup(task, crash_round):
    from app.modules.judging.worker_store import WorkerStore

    engine, _, _, _ = task
    store = WorkerStore(engine)
    claim = store.claim()
    identity = store.begin_case(claim, ("cpp17", "SAMPLE", 1))
    with engine.begin() as conn:
        conn.execute(
            text("UPDATE preflight_jobs SET lease_until=clock_timestamp()-interval '1 second'")
        )
    recovery = store.recover_claim()
    assert recovery is not None and recovery.epoch > claim.epoch
    assert recovery.execution_id == identity
    assert not store.record_case(claim, ("cpp17", "SAMPLE", 1), "AC", 1, None)
    assert not store.finish_recovery(recovery, False)
    assert store.claim() is None
    assert store.finish_recovery(recovery, True)
    with engine.connect() as conn:
        assert conn.scalar(text("SELECT state FROM execution_slots WHERE slot_id=1")) == "FREE"
        assert conn.scalar(text("SELECT state FROM preflight_runs")) == "FAILED"
        assert conn.scalar(text("SELECT count(*) FROM preflight_cases WHERE verdict='SE'")) == 1


def test_deadline_and_global_assignment_protection_prevent_new_dispatch(task):
    from app.modules.judging.worker_store import WorkerStore

    engine, ids, _, _ = task
    with engine.begin() as conn:
        conn.execute(
            text(
                "UPDATE assignments SET due_at=clock_timestamp()+interval '5 minutes' WHERE assignment_id=:id"
            ),
            {"id": ids["assignment"]},
        )
    assert WorkerStore(engine).claim() is None


def test_unknown_execute_never_releases_slot_without_remote_fence(task):
    from app.modules.judging.worker import PreflightWorker
    from app.modules.judging.worker_store import WorkerStore

    engine, _, snapshot, _ = task

    class Executor:
        def __init__(self, image):
            self.image = image

        def execute(self, *args, **kwargs):
            raise ExecutionError("UNKNOWN")

        def cancel(self, identity):
            return False

    worker = PreflightWorker(
        WorkerStore(engine),
        catalog(snapshot),
        {
            row["language_key"]: Executor(row["image_digest"])
            for row in snapshot["profile"]["languages"]
        },
    )
    assert worker.run_once()
    with engine.connect() as conn:
        assert (
            conn.scalar(text("SELECT state FROM execution_slots WHERE slot_id=1")) == "QUARANTINED"
        )
        assert conn.scalar(text("SELECT current_execution FROM preflight_jobs")) is not None


def test_started_worker_lease_blocks_destructive_migration_rollback(task):
    from pathlib import Path

    from alembic import command
    from alembic.config import Config

    from app.modules.judging.worker_store import WorkerStore

    engine, _, _, _ = task
    assert WorkerStore(engine).claim()
    config = Config(str(Path(__file__).parents[2] / "alembic.ini"))
    with pytest.raises(RuntimeError, match="lease"), engine.begin() as conn:
        config.attributes["connection"] = conn
        command.downgrade(config, "b009")


def test_expired_round_cannot_renew_or_complete_and_recovers_to_failure(task):
    from app.modules.judging.worker_store import WorkerStore

    engine, _, _, _ = task
    store = WorkerStore(engine)
    claim = store.claim()
    with engine.begin() as conn:
        conn.execute(
            text("UPDATE preflight_jobs SET deadline=clock_timestamp()-interval '1 second'")
        )
    assert not store.heartbeat(claim)
    assert store.begin_case(claim, ("cpp17", "SAMPLE", 1)) is None
    recovery = store.recover_claim()
    assert recovery and store.finish_recovery(recovery, True)
    with engine.connect() as conn:
        assert conn.scalar(text("SELECT state FROM preflight_runs")) == "FAILED"


def test_worker_failure_cannot_forge_terminal_without_all_points(task):
    from app.modules.judging.worker_store import WorkerStore

    engine, _, _, _ = task
    store = WorkerStore(engine)
    claim = store.claim()
    assert not store.complete(claim)
    assert not store.record_case(
        replace(claim, epoch=claim.epoch + 1), ("cpp17", "SAMPLE", 1), "AC", 0, None
    )
    assert not store.finish_recovery(replace(claim, owner=str(uuid4())), True)


def test_recovery_cancels_before_freeing_physical_slot(task):
    from app.modules.judging.worker import PreflightWorker
    from app.modules.judging.worker_store import WorkerStore

    engine, _, snapshot, _ = task
    store = WorkerStore(engine)
    claim = store.claim()
    identity = store.begin_case(claim, ("cpp17", "SAMPLE", 1))
    store.quarantine(claim)
    calls = []

    class Executor:
        def cancel(self, execution_id):
            with engine.connect() as conn:
                assert (
                    conn.scalar(text("SELECT state FROM execution_slots WHERE slot_id=1"))
                    == "QUARANTINED"
                )
            assert execution_id == identity
            calls.append(execution_id)
            return True

    worker = PreflightWorker(store, catalog(snapshot), {"cpp17": Executor(), "python3": Executor()})
    assert worker.recover_once() and len(calls) == 2
    assert not store.record_case(claim, ("cpp17", "SAMPLE", 1), "AC", 0, None)
    with engine.connect() as conn:
        assert conn.scalar(text("SELECT state FROM execution_slots WHERE slot_id=1")) == "FREE"


@pytest.mark.parametrize("diagnosis", ["CE", "WA", "TLE", "RE", "SE"])
def test_first_non_ac_atomically_stops_later_points_and_releases_clean_slot(task, diagnosis):
    from app.modules.judging.worker import PreflightWorker
    from app.modules.judging.worker_store import WorkerStore

    engine, _, snapshot, _ = task
    calls = []

    class Executor:
        def __init__(self, image):
            self.image = image

        def execute(self, identity, language, code, stdin, timeout=40):
            calls.append(identity)
            return ExecutionResult(
                "COMPILE" if diagnosis == "CE" else "RUN",
                None if diagnosis == "WA" else diagnosis,
                0 if diagnosis == "WA" else 1,
                b"wrong public output",
                1,
                None,
            )

        def cancel(self, identity):
            return True

    worker = PreflightWorker(
        WorkerStore(engine),
        catalog(snapshot),
        {
            row["language_key"]: Executor(row["image_digest"])
            for row in snapshot["profile"]["languages"]
        },
    )
    assert worker.run_once()
    assert len(calls) == 1
    with engine.connect() as conn:
        assert conn.scalar(text("SELECT count(*) FROM preflight_cases WHERE state='FINISHED'")) == 1
        assert conn.scalar(text("SELECT count(*) FROM preflight_cases WHERE state='SKIPPED'")) == 3
        assert conn.scalar(text("SELECT state FROM preflight_runs")) == "FAILED"
        assert conn.scalar(text("SELECT state FROM preflight_jobs")) == "DONE"
        assert conn.scalar(text("SELECT state FROM execution_slots WHERE slot_id=1")) == "FREE"


def test_controller_configuration_cannot_change_while_old_slot_is_owned(task):
    from app.modules.judging.worker_store import WorkerStore

    engine, _, _, _ = task
    store = WorkerStore(engine)
    store.bind_executor("a" * 64)
    store.bind_executor("a" * 64)
    claim = store.claim()
    with pytest.raises(ValueError, match="EXECUTOR_BINDING"):
        store.bind_executor("b" * 64)
    store.quarantine(claim)
    with pytest.raises(ValueError, match="EXECUTOR_BINDING"):
        store.bind_executor("b" * 64)
    recovery = store.recover_claim()
    assert store.finish_recovery(recovery, True)
    store.bind_executor("b" * 64)
