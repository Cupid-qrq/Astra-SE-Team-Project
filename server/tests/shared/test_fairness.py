from datetime import timedelta
from uuid import uuid4

import pytest
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


@pytest.mark.parametrize("second_start_minutes,expected_extra", [(4, 0), (2, 0), (1, 10)])
def test_overlapping_or_adjacent_incidents_share_one_minimum_compensation(
    lesson, second_start_minutes, expected_extra
):
    from app.modules.operations.fairness import Fairness

    engine, ids = lesson
    with engine.begin() as conn:
        repo = SqlRepository(conn)
        service = Fairness(repo, TransactionalEffects(repo, str(uuid4())))
        admin = repo.required("users", ids["admin"])
        teacher = repo.required("users", ids["teacher"])
        now = repo.now()
        old_due = repo.required("assignments", ids["assignment"])["due_at"]
        for start, end in [
            (now - timedelta(minutes=4), now - timedelta(minutes=2)),
            (now - timedelta(minutes=second_start_minutes), now),
        ]:
            event = service.create(
                admin,
                dict(
                    started_at=utc(start),
                    assignment_ids=[ids["assignment"]],
                    reason_code="JUDGE_UNAVAILABLE",
                    reason="evidence",
                    evidence_refs=[],
                    evidence_incomplete=True,
                ),
            )
            service.recovery(
                admin,
                event["incident_id"],
                dict(recovered_at=utc(end), expected_revision=1, reason="restored"),
            )
            assignment = repo.required("assignments", ids["assignment"])
            service.decide(
                teacher,
                ids["assignment"],
                dict(
                    incident_id=event["incident_id"],
                    decision="EXTEND",
                    reason="compensation",
                    expected_revision=assignment["revision"],
                ),
            )
        assert repo.required("assignments", ids["assignment"])["due_at"] == old_due + timedelta(
            minutes=10 + expected_extra
        )
