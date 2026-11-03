from uuid import uuid4

from sqlalchemy import text
from test_preflight_storage import enqueue, finish_for_fixture, port
from test_submission_worker import queued as queued

from app.modules.problems.application import Problems
from app.shared.effects import TransactionalEffects
from app.shared.repository import SqlRepository


def replacement(engine, ids):
    with engine.begin() as conn:
        repo = SqlRepository(conn)
        effects = TransactionalEffects(repo, str(uuid4()))
        service = Problems(repo, effects)
        actor = repo.get("users", ids["teacher"])
        original = service.snapshot(ids["draft"])
        created = service.create_version(
            actor,
            dict(
                problem_id=ids["problem"],
                **{
                    k: original[k]
                    for k in ("title", "statement", "samples", "tags", "profile", "source_ref")
                },
            ),
        )
        vid = created["version_id"]
        revision = 1
        for order in (1, 2):
            revision = service.put_case(
                actor, vid, order, dict(input_text="1", answer_text="2", expected_revision=revision)
            )["revision"]
        for language in ("cpp17", "python3"):
            revision = service.put_reference(
                actor, vid, language, dict(code="public fixture", expected_revision=revision)
            )["revision"]
        snapshot = service.snapshot(vid)
    receipt = enqueue(engine, {**ids, "draft": vid}, snapshot)
    with engine.begin() as conn:
        finish_for_fixture(conn, receipt["preflight_id"])
        repo = SqlRepository(conn)
        Problems(repo, TransactionalEffects(repo, str(uuid4())), port(repo, snapshot)).publish(
            repo.get("users", ids["teacher"]),
            vid,
            dict(
                expected_revision=revision,
                preflight_id=receipt["preflight_id"],
                reason="replacement fixture",
            ),
        )
    return vid


def test_full_rejudge_keeps_old_grade_until_atomic_activation_and_can_lower_score(queued):
    from app.modules.grades.application import Grades
    from app.modules.rejudge.application import Rejudges
    from app.modules.submissions.worker_store import SubmissionStore

    engine, ids, _, receipt = queued
    store = SubmissionStore(engine)
    claim = store.claim()
    for order in (1, 2):
        store.begin_case(claim, order)
        store.record_case(claim, order, "AC", 1, None)
    target = replacement(engine, ids)
    with engine.begin() as conn:
        conn.execute(text("UPDATE assignments SET due_at=clock_timestamp()-interval '1 second'"))
        repo = SqlRepository(conn)
        effects = TransactionalEffects(repo, str(uuid4()))
        actor = repo.get("users", ids["teacher"])
        old = Grades(repo, effects).publish(
            actor, ids["assignment"], dict(expected_revision=1, reason="publish")
        )
        service = Rejudges(repo, effects)
        preview = service.preview(
            actor,
            ids["assignment"],
            dict(problem_id=ids["problem"], new_version_id=target, expected_revision=1),
        )
        batch = service.create(
            actor,
            ids["assignment"],
            dict(
                new_version_id=target,
                range_checksum=preview["range_checksum"],
                expected_revision=1,
                reason="fix test",
            ),
        )
    claim = store.claim()
    assert claim is not None
    store.begin_case(claim, 1)
    store.record_case(claim, 1, "WA", 1, None)
    with engine.begin() as conn:
        repo = SqlRepository(conn)
        effects = TransactionalEffects(repo, str(uuid4()))
        actor = repo.get("users", ids["teacher"])
        service = Rejudges(repo, effects)
        status = service.read(actor, batch["batch_id"])
        assert status["state"] == "READY"
        assert Grades(repo, effects).read(actor, ids["assignment"])["state"] == "REJUDGING"
        assert (
            Grades(repo, effects).snapshot(actor, old["grade_version"])["students"][0]["total"]
            == 100
        )
        service.activate(
            actor,
            batch["batch_id"],
            dict(
                expected_batch_revision=status["revision"],
                expected_assignment_revision=status["assignment_revision"],
                reason="activate",
            ),
        )
        current = Grades(repo, effects).read(actor, ids["assignment"])
        assert current["state"] == "PUBLISHED" and current["students"][0]["total"] == 0
        assert (
            Grades(repo, effects).snapshot(actor, old["grade_version"])["students"][0]["total"]
            == 100
        )


def batch_after_initial_failure(queued):
    from app.modules.identity.domain import utc
    from app.modules.operations.fairness import Fairness
    from app.modules.rejudge.application import Rejudges
    from app.modules.submissions.worker_store import SubmissionStore

    engine, ids, _, _ = queued
    store = SubmissionStore(engine)
    for _ in range(2):
        claim = store.claim()
        store.begin_case(claim, 1)
        store.record_case(claim, 1, "SE", None, None)
    target = replacement(engine, ids)
    with engine.begin() as conn:
        repo = SqlRepository(conn)
        effects = TransactionalEffects(repo, str(uuid4()))
        fairness = Fairness(repo, effects)
        incident = repo.rows("fairness_incidents")[0]
        fairness.recovery(
            repo.required("users", ids["admin"]),
            incident["incident_id"],
            dict(
                recovered_at=utc(repo.now()),
                expected_revision=incident["revision"],
                reason="restored",
            ),
        )
        assignment = repo.required("assignments", ids["assignment"])
        fairness.decide(
            repo.required("users", ids["teacher"]),
            ids["assignment"],
            dict(
                incident_id=incident["incident_id"],
                decision="NO_IMPACT",
                reason="checked",
                expected_revision=assignment["revision"],
            ),
        )
        conn.execute(text("UPDATE assignments SET due_at=clock_timestamp()-interval '1 second'"))
        assignment = repo.required("assignments", ids["assignment"])
        service = Rejudges(repo, effects)
        actor = repo.required("users", ids["teacher"])
        preview = service.preview(
            actor,
            ids["assignment"],
            dict(
                problem_id=ids["problem"],
                new_version_id=target,
                expected_revision=assignment["revision"],
            ),
        )
        batch = service.create(
            actor,
            ids["assignment"],
            dict(
                new_version_id=target,
                expected_revision=assignment["revision"],
                range_checksum=preview["range_checksum"],
                reason="rejudge",
            ),
        )
    return batch


def test_rejudge_dispatch_waits_for_existing_manual_cycle(queued):
    from app.modules.operations.application import Operations
    from app.modules.submissions.worker_store import SubmissionStore

    engine, ids, _, receipt = queued
    batch_after_initial_failure(queued)
    with engine.begin() as conn:
        repo = SqlRepository(conn)
        service = Operations(repo, TransactionalEffects(repo, str(uuid4())))
        submission = repo.required("submissions", receipt["submission_id"])
        service.retry(
            repo.required("users", ids["admin"]),
            submission["submission_id"],
            dict(expected_revision=submission["revision"], reason="manual retry"),
        )
    assert SubmissionStore(engine).claim() is not None


def test_active_rejudge_allows_no_impact_decision_after_recovery(queued):
    from app.modules.identity.domain import utc
    from app.modules.operations.fairness import Fairness
    from app.modules.submissions.worker_store import SubmissionStore

    engine, ids, _, _ = queued
    batch_after_initial_failure(queued)
    store = SubmissionStore(engine)
    for _ in range(2):
        claim = store.claim()
        store.begin_case(claim, 1)
        store.record_case(claim, 1, "SE", None, None)
    with engine.begin() as conn:
        repo = SqlRepository(conn)
        service = Fairness(repo, TransactionalEffects(repo, str(uuid4())))
        incident = repo.rows("fairness_incidents", recovered_at=None)[0]
        admin = repo.required("users", ids["admin"])
        teacher = repo.required("users", ids["teacher"])
        service.recovery(
            admin,
            incident["incident_id"],
            dict(
                expected_revision=incident["revision"],
                recovered_at=utc(repo.now()),
                reason="restored",
            ),
        )
        assignment = repo.required("assignments", ids["assignment"])
        assert (
            service.decide(
                teacher,
                ids["assignment"],
                dict(
                    expected_revision=assignment["revision"],
                    incident_id=incident["incident_id"],
                    decision="NO_IMPACT",
                    reason="no submission opportunity affected",
                ),
            )["fairness_review"]
            == "RESOLVED"
        )
