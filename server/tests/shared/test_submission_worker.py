from uuid import uuid4

import pytest
from sqlalchemy import text
from test_submissions import accept

from app.adapters.course_executor import ExecutionResult
from app.adapters.judge_profiles import SnapshotCatalog
from app.shared.judge import ExecutionError
from app.shared.repository import SqlRepository


@pytest.fixture
def queued(database):
    from preflight_fixtures import draft
    from test_preflight_storage import enqueue, finish_for_fixture, port

    from app.modules.problems.application import Problems
    from app.shared.effects import TransactionalEffects

    ids, snapshot = draft(database)
    runtime = snapshot["profile"]
    with database.begin() as conn:
        repo = SqlRepository(conn)
        service = Problems(repo, TransactionalEffects(repo, str(uuid4())))
        teacher = repo.get("users", ids["teacher"])
        service.put_case(
            teacher,
            ids["draft"],
            1,
            dict(input_text="1", answer_text="1", expected_revision=snapshot["revision"]),
        )
        snapshot = service.snapshot(ids["draft"])
        service.put_case(
            teacher,
            ids["draft"],
            2,
            dict(input_text="1", answer_text="1", expected_revision=snapshot["revision"]),
        )
        snapshot = service.snapshot(ids["draft"])
    receipt = enqueue(database, ids, snapshot)
    with database.begin() as conn:
        finish_for_fixture(conn, receipt["preflight_id"])
        repo = SqlRepository(conn)
        service = Problems(repo, TransactionalEffects(repo, str(uuid4())), port(repo, snapshot))
        service.publish(
            repo.get("users", ids["teacher"]),
            ids["draft"],
            dict(
                expected_revision=snapshot["revision"],
                preflight_id=receipt["preflight_id"],
                reason="synthetic worker fixture",
            ),
        )
        repo.change(
            "assignment_items",
            (ids["assignment"], ids["problem"]),
            effective_version_id=ids["draft"],
        )
    from app.modules.learning.application import seed_global_feedback

    with database.begin() as conn:
        seed_global_feedback(SqlRepository(conn), ids["admin"])
    receipt, _ = accept((database, ids), str(uuid4()))
    return database, ids, runtime, receipt


@pytest.mark.parametrize("verdict", ["AC", "WA", "CE", "RE", "TLE"])
def test_student_worker_terminalizes_and_releases_capacity_once(queued, verdict):
    from app.modules.submissions.worker import SubmissionWorker
    from app.modules.submissions.worker_store import SubmissionStore

    engine, _, runtime, receipt = queued
    calls = []

    class Executor:
        image = runtime["languages"][1]["image_digest"]

        def execute(self, identity, language, code, stdin, timeout=40):
            with engine.connect() as conn:
                assert conn.scalar(text("SELECT state FROM execution_slots")) == "BUSY"
            calls.append(identity)
            return ExecutionResult(
                "RUN",
                None if verdict in ("AC", "WA") else verdict,
                0,
                b"1" if verdict == "AC" else b"2",
                1,
                None,
            )

        def cancel(self, identity):
            return True

    worker = SubmissionWorker(
        SubmissionStore(engine), SnapshotCatalog((runtime,)), {"python3": Executor()}
    )
    assert worker.run_once()
    assert not worker.run_once()
    assert len(calls) == (2 if verdict == "AC" else 1)
    with engine.connect() as conn:
        assert conn.scalar(text("SELECT verdict FROM attempts")) == verdict
        assert conn.scalar(text("SELECT pending_count FROM capacity_control")) == 0
        assert conn.scalar(text("SELECT pending_count FROM admission_users")) == 0
        assert conn.scalar(text("SELECT state FROM execution_slots")) == "FREE"
        assert conn.scalar(text("SELECT count(*) FROM case_results")) == 2


def test_infrastructure_failure_retries_once_without_resetting_cycle(queued):
    from app.modules.submissions.worker import SubmissionWorker
    from app.modules.submissions.worker_store import SubmissionStore

    engine, _, runtime, _ = queued

    class Executor:
        image = runtime["languages"][1]["image_digest"]

        def execute(self, *args, **kwargs):
            raise ExecutionError("UNKNOWN")

        def cancel(self, identity):
            return True

    worker = SubmissionWorker(
        SubmissionStore(engine), SnapshotCatalog((runtime,)), {"python3": Executor()}
    )
    assert worker.run_once() and worker.recover_once()
    with engine.connect() as conn:
        assert conn.scalar(text("SELECT auto_retry_count FROM processing_cycles")) == 1
        assert conn.scalar(text("SELECT pending_count FROM capacity_control")) == 1
        assert conn.scalar(text("SELECT count(*) FROM processing_cycles")) == 1
    assert worker.run_once() and worker.recover_once()
    with engine.connect() as conn:
        assert conn.scalar(text("SELECT count(*) FROM attempts")) == 2
        assert conn.scalar(text("SELECT count(*) FROM attempts WHERE verdict='SE'")) == 2
        assert conn.scalar(text("SELECT pending_count FROM capacity_control")) == 0


def test_late_result_and_unconfirmed_cleanup_cannot_free_slot(queued):
    from app.modules.submissions.worker_store import SubmissionStore

    engine, *_ = queued
    store = SubmissionStore(engine)
    claim = store.claim()
    identity = store.begin_case(claim, 1)
    with engine.begin() as conn:
        conn.execute(
            text("UPDATE queue_jobs SET lease_until=clock_timestamp()-interval '1 second'")
        )
    recovery = store.recover_claim()
    assert recovery.execution_id == identity and recovery.epoch > claim.epoch
    assert not store.record_case(claim, 1, "AC", 1, None)
    assert not store.finish_recovery(recovery, False)
    assert store.claim() is None
    assert store.finish_recovery(recovery, True)


def test_expired_total_budget_finishes_without_execution_or_retry(queued):
    from app.modules.submissions.worker_store import SubmissionStore

    engine, _, _, _ = queued
    with engine.begin() as conn:
        conn.execute(
            text("UPDATE processing_cycles SET started_at=clock_timestamp()-interval '16 minutes'")
        )
    assert SubmissionStore(engine).claim() is None
    with engine.connect() as conn:
        assert conn.scalar(text("SELECT verdict FROM attempts")) == "SE"
        assert conn.scalar(text("SELECT reason_code FROM attempts")) == "CYCLE_TIMEOUT"
        assert conn.scalar(text("SELECT pending_count FROM capacity_control")) == 0


def test_preflight_cannot_claim_while_student_task_waits(queued):
    from app.modules.judging.worker_store import WorkerStore
    from app.modules.submissions.worker_store import SubmissionStore

    engine, *_ = queued
    assert WorkerStore(engine).claim() is None
    claim = SubmissionStore(engine).claim()
    assert claim is not None
    assert WorkerStore(engine).recover_claim() is None


def test_a_learning_source_projects_only_authorized_public_material(queued):
    from app.modules.learning.policy_rules import HintSource
    from app.modules.submissions.sources import SubmissionSources
    from app.modules.submissions.worker_store import SubmissionStore

    engine, ids, _, receipt = queued
    store = SubmissionStore(engine)
    claim = store.claim()
    store.begin_case(claim, 1)
    assert store.record_case(claim, 1, "WA", 1, None)
    with engine.begin() as conn:
        repo = SqlRepository(conn)
        sources = SubmissionSources()
        source = sources.hint_source(repo, ids["student"], receipt["submission_id"])
        assert isinstance(source, HintSource) and source.verdict == "WA"
        submission = repo.get("submissions", receipt["submission_id"])
        basis = repo.get("result_bases", submission["active_basis_id"])
        assert source.result_basis_id == submission["active_basis_id"]
        assert source.attempt_id == basis["current_attempt_id"]
        assert source.effective_version_id == basis["target_version_id"]

        context = sources.hint_context(repo, source)
        assert set(context) == {
            "public_problem",
            "public_samples",
            "student_code",
            "language_key",
            "sanitized_diagnostic",
            "verdict",
        }
        assert "SECRET" not in str(context)
        assert sources.hint_source(repo, ids["teacher"], receipt["submission_id"]) is None
        rows = (
            conn.execute(sources.projection(repo, {"user_id": ids["student"], "role": "STUDENT"}))
            .mappings()
            .all()
        )
        assert len(rows) == 1 and "code" not in rows[0]


def test_expired_waiting_cycle_releases_capacity_while_other_slot_is_quarantined(queued):
    from app.modules.submissions.worker_store import SubmissionStore

    engine, ids, _, _ = queued
    store = SubmissionStore(engine)
    claim = store.claim()
    store.begin_case(claim, 1)
    store.quarantine(claim)
    with engine.begin() as conn:
        conn.execute(
            text(
                "UPDATE admission_users SET last_accepted_at=clock_timestamp()-interval '6 seconds'"
            )
        )
    receipt, _ = accept((engine, ids), str(uuid4()))
    with engine.begin() as conn:
        conn.execute(
            text(
                "UPDATE processing_cycles SET started_at=clock_timestamp()-interval '16 minutes' WHERE submission_id=:sid"
            ),
            {"sid": receipt["submission_id"]},
        )
    assert store.claim() is None
    with engine.connect() as conn:
        assert (
            conn.scalar(
                text("SELECT verdict FROM attempts WHERE submission_id=:sid"),
                {"sid": receipt["submission_id"]},
            )
            == "SE"
        )
        assert conn.scalar(text("SELECT pending_count FROM capacity_control")) == 1
        assert conn.scalar(text("SELECT state FROM execution_slots")) == "QUARANTINED"
