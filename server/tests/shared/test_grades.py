from uuid import uuid4

import pytest
from sqlalchemy import text
from test_submission_worker import queued as queued

from app.modules.identity.domain import Fault
from app.shared.effects import TransactionalEffects
from app.shared.repository import SqlRepository


def test_grade_publish_requires_finished_results_and_freezes_same_snapshot(queued):
    from app.modules.grades.application import Grades
    from app.modules.submissions.worker_store import SubmissionStore

    engine, ids, _, _ = queued

    def service(conn):
        repo = SqlRepository(conn)
        return repo, Grades(repo, TransactionalEffects(repo, str(uuid4())))

    with engine.begin() as conn:
        repo, grades = service(conn)
        actor = repo.get("users", ids["teacher"])
        assert grades.read(actor, ids["assignment"])["students"][0]["state"] == "PENDING"
        with pytest.raises(Fault):
            grades.publish(actor, ids["assignment"], dict(expected_revision=1, reason="test"))
    store = SubmissionStore(engine)
    claim = store.claim()
    for order in (1, 2):
        store.begin_case(claim, order)
        assert store.record_case(claim, order, "AC", 1, None)
    with engine.begin() as conn:
        conn.execute(text("UPDATE assignments SET due_at=clock_timestamp()-interval '1 second'"))
        repo, grades = service(conn)
        actor = repo.get("users", ids["teacher"])
        published = grades.publish(
            actor, ids["assignment"], dict(expected_revision=1, reason="核对完成")
        )
        view = grades.read(repo.get("users", ids["student"]), ids["assignment"])
        assert view["state"] == "PUBLISHED" and view["students"][0]["total"] == 100
        assert view["grade_version"] == published["grade_version"]
        assert len(view["students"]) == 1
        csv = grades.export(actor, ids["assignment"], published["grade_version"])
        assert "100" in csv and published["grade_version"] in csv
        repo.change("assignments", ids["assignment"], grade_epoch=view["grade_epoch"] + 1)
        assert grades.read(actor, ids["assignment"])["state"] == "PROVISIONAL"
        assert grades.snapshot(actor, published["grade_version"])["students"][0]["total"] == 100
        with pytest.raises(Fault):
            grades.read(repo.get("users", ids["admin"]), ids["assignment"])
