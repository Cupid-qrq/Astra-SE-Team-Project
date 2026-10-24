from uuid import uuid4

import pytest
from app.modules.identity.domain import Fault
from app.modules.learning.application import Learning, seed_global_feedback
from app.modules.learning.domain import checksum, validate_body
from astra_a.app import create_app
from astra_a.storage import SqlRepository
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError


def seed(env):
    with env.engine.begin() as connection:
        repo = SqlRepository(connection, env.clock)
        return seed_global_feedback(repo, env.users["admin_a"])


def test_seeds_are_idempotent_and_frozen(env):
    first = seed(env)
    assert set(first) == {"CE", "WA", "TLE", "RE", "SE"}
    assert seed(env) == first
    with env.engine.begin() as connection:
        repo = SqlRepository(connection, env.clock)
        assert len(repo.rows("feedback_versions")) == 5
        service = Learning(repo, env.effects)
        for verdict, version_id in first.items():
            assert service.resolve(str(uuid4()), "python3", verdict) == version_id
        assert service.resolve(str(uuid4()), "python3", "AC") is None
        version = repo.get("feedback_versions", first["SE"])
        assert "平台" in version["explanation"]
    with pytest.raises(DBAPIError), env.engine.begin() as connection:
        connection.execute(
            text("UPDATE feedback_versions SET title=:t WHERE version_id=:v"),
            {"t": "篡改", "v": first["WA"]},
        )


def test_seed_requires_existing_active_admin_and_rolls_back(env):
    with pytest.raises(Fault), env.engine.begin() as connection:
        seed_global_feedback(SqlRepository(connection), env.users["teacher_a"])
    with env.engine.begin() as connection:
        assert SqlRepository(connection).rows("feedback_versions") == []


def add_version(repo, admin, scope, language, title="课程提示"):
    cid, vid = str(uuid4()), str(uuid4())
    body = dict(title=title, explanation="请检查边界。", checklist=["检查输入格式"])
    repo.add(
        "feedback_catalogs",
        dict(
            catalog_id=cid,
            scope_key=scope,
            verdict="WA",
            language_key=language,
            draft_payload=body,
            draft_revision=1,
            active_version_id=None,
        ),
    )
    repo.add(
        "feedback_versions",
        dict(
            version_id=vid,
            catalog_id=cid,
            version_no=1,
            **body,
            author_id=admin,
            published_at=repo.now(),
            checksum=checksum(body),
        ),
    )
    repo.change("feedback_catalogs", cid, active_version_id=vid)
    return cid, vid


def test_resolution_priority_and_historical_version(env):
    original = seed(env)["WA"]
    teacher = env.login("teacher_a")
    course = teacher.post("/api/v1/courses", json={"title": "帮助课程"}).json()["course_id"]
    with env.engine.begin() as connection:
        repo = SqlRepository(connection, env.clock)
        service = Learning(repo, env.effects)
        cid, common = add_version(repo, env.users["admin_a"], "COURSE:" + course, "ALL")
        _, specific = add_version(repo, env.users["admin_a"], "COURSE:" + course, "python3")
        assert service.resolve(course, "cpp17", "WA") == common
        assert service.resolve(course, "python3", "WA") == specific
        assert service.resolve(str(uuid4()), "python3", "WA") == original
        body = dict(title="更新后的课程说明", explanation="检查输出。", checklist=[])
        newer = str(uuid4())
        repo.add(
            "feedback_versions",
            dict(
                version_id=newer,
                catalog_id=cid,
                version_no=2,
                **body,
                author_id=env.users["admin_a"],
                published_at=repo.now(),
                checksum=checksum(body),
            ),
        )
        repo.change("feedback_catalogs", cid, active_version_id=newer)
        assert service.resolve(course, "cpp17", "WA") == newer
        assert repo.get("feedback_versions", common)["title"] == "课程提示"
    assert seed(env)["WA"] == original


@pytest.mark.parametrize(
    "body",
    [
        dict(title="标题", explanation="x" * 2001, checklist=[]),
        dict(title="标题", explanation="说明", checklist=["条目"] * 11),
        dict(title="标题", explanation="说明", checklist=[" "]),
        dict(title=" ", explanation="说明", checklist=[]),
        dict(title="标题", explanation="说明", checklist=["x" * 500] * 4),
    ],
)
def test_body_limits(body):
    with pytest.raises(Fault):
        validate_body(body)


def test_version_access_and_nonterminal_submission(env):
    ids = seed(env)
    teacher = env.login("teacher_a")
    course = teacher.post("/api/v1/courses", json={"title": "权限课程"}).json()["course_id"]
    with env.engine.begin() as connection:
        repo = SqlRepository(connection, env.clock)
        cid, vid = add_version(repo, env.users["admin_a"], "COURSE:" + course, "ALL")
        global_catalog = repo.get("feedback_versions", ids["WA"])["catalog_id"]
    path = f"/api/v1/feedback-catalogs/{cid}/versions/1"
    assert teacher.get(path).status_code == 200
    assert env.login("teacher_b").get(path).status_code == 404
    assert env.login("student_a").get(path).status_code == 404
    assert env.login("admin_a").get(path).status_code == 403
    assert env.client().get(path).status_code == 401
    assert teacher.get(path.replace("/1", "/abc")).status_code == 422
    assert (
        env.login("student_a")
        .get(f"/api/v1/feedback-catalogs/{global_catalog}/versions/1")
        .status_code
        == 200
    )
    assert teacher.get("/api/v1/submissions/" + str(uuid4()) + "/feedback").status_code == 503

    class Submissions:
        state = "QUEUED"

        def feedback(self, repo, actor, submission_id):
            return dict(
                user_id=env.users["student_a"],
                course_id=course,
                state=self.state,
                verdict="WA" if self.state == "FINISHED" else None,
                feedback_version_id=vid if self.state == "FINISHED" else None,
            )

    port = Submissions()
    env.app = create_app(
        env.engine,
        env.effects,
        secret=b"test-only-session-key-32-bytes-long",
        origin="https://testserver",
        clock=env.clock,
        feedback_submissions=port,
    )
    teacher = env.login("teacher_a")
    teacher.put(
        f"/api/v1/courses/{course}/members/{env.users['student_a']}",
        json={"status": "ACTIVE", "expected_revision": 1},
    )
    student = env.login("student_a")
    path = "/api/v1/submissions/" + str(uuid4()) + "/feedback"
    assert student.get(path).status_code == 409
    port.state = "FINISHED"
    assert student.get(path).json()["feedback_version_id"] == vid
    assert env.login("student_b").get(path).status_code == 404
    assert env.login("teacher_b").get(path).status_code == 404
    assert teacher.get(path).status_code == 200
    teacher.put(
        f"/api/v1/courses/{course}/members/{env.users['student_a']}",
        json={"status": "DISABLED", "expected_revision": 2},
    )
    assert student.get(path).status_code == 404
