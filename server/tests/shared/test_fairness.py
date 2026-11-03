from datetime import timedelta
from uuid import uuid4

from test_submissions import lesson as lesson

from app.modules.identity.domain import utc
from app.shared.effects import TransactionalEffects
from app.shared.repository import SqlRepository


def test_recovered_incident_extends_whole_assignment_and_delivers_one_notification(lesson):
    from app.modules.operations.application import deliver
    from app.modules.operations.fairness import Fairness

    engine, ids = lesson
    with engine.begin() as conn:
        repo = SqlRepository(conn)
        service = Fairness(repo, TransactionalEffects(repo, str(uuid4())))
        now = repo.now()
        old_due = repo.get("assignments", ids["assignment"])["due_at"]
        event = service.create(
            repo.get("users", ids["admin"]),
            dict(
                started_at=utc(now - timedelta(minutes=2)),
                assignment_ids=[ids["assignment"]],
                reason_code="JUDGE_UNAVAILABLE",
                reason="恢复演练",
                evidence_refs=[],
                evidence_incomplete=True,
            ),
        )
        service.recovery(
            repo.get("users", ids["admin"]),
            event["incident_id"],
            dict(recovered_at=utc(now), expected_revision=1, reason="已恢复"),
        )
        result = service.decide(
            repo.get("users", ids["teacher"]),
            ids["assignment"],
            dict(
                incident_id=event["incident_id"],
                decision="EXTEND",
                reason="统一补偿",
                expected_revision=2,
            ),
        )
        assert result["new_due_at"] == utc(old_due + timedelta(minutes=10))
        assert result["fairness_review"] == "RESOLVED"
        deliver(repo)
        deliver(repo)
        assert len(repo.rows("notifications", user_id=ids["student"])) == 1
