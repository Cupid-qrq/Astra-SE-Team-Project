from datetime import timedelta
from uuid import uuid4

import pytest
from test_submissions import lesson as lesson

from app.modules.identity.domain import Fault
from app.shared.effects import TransactionalEffects
from app.shared.repository import SqlRepository


def test_retention_requires_age_confirmation_and_no_hold_then_hides_course(lesson):
    from app.modules.courses.application import Courses
    from app.modules.operations.retention import Retention

    engine, ids = lesson
    with engine.begin() as conn:
        repo = SqlRepository(conn)
        effects = TransactionalEffects(repo, str(uuid4()))
        service = Retention(repo, effects)
        teacher = repo.required("users", ids["teacher"])
        admin = repo.required("users", ids["admin"])
        service.archive(teacher, ids["course"], dict(expected_revision=1, reason="course finished"))
        pid = service.preview(admin, dict(course_id=ids["course"], reason="cleanup"))["plan_id"]
        view = service.read(teacher, pid)
        confirmation = service.confirm(
            teacher,
            pid,
            dict(expected_revision=1, object_digest=view["object_digest"], reason="confirmed"),
        )
        body = dict(
            expected_revision=2,
            object_digest=view["object_digest"],
            confirmation_id=confirmation["confirmation_id"],
            reason="execute",
        )
        with pytest.raises(Fault):
            service.execute(admin, pid, body)
        repo.change("courses", ids["course"], archived_at=repo.now() - timedelta(days=181))
        hold = service.hold(
            teacher, dict(object_type="course", object_id=ids["course"], reason="appeal")
        )
        with pytest.raises(Fault) as error:
            service.execute(admin, pid, body)
        assert error.value.code == "RETENTION_HOLD"
        service.close_hold(teacher, hold["hold_id"], dict(expected_revision=1, reason="resolved"))
        assert service.execute(admin, pid, body)["state"] == "CLEANED"
        with pytest.raises(Fault) as error:
            Courses(repo, effects).access(teacher, ids["course"])
        assert error.value.status == 404
