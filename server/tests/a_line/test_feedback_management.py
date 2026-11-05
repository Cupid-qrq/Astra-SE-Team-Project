"""Real HTTP/PostgreSQL management; no accepted submission or model is invented."""

from concurrent.futures import ThreadPoolExecutor
from uuid import uuid4

import pytest
from astra_a.storage import SqlRepository
from sqlalchemy import text

from app.modules.identity.domain import Fault
from app.modules.learning.application import Learning

BASE = "/api/v1/feedback-catalogs"
BODY = dict(
    title="检查边界", explanation="检查**空输入**和重复值。", checklist=["手工计算小规模样例。"]
)
REASON = "核对课程教学内容后发布帮助版本"


def course_and_catalog(env, *, language="ALL", verdict="WA"):
    teacher = env.login("teacher_a")
    course = teacher.post("/api/v1/courses", json={"title": "固定帮助维护"}).json()["course_id"]
    created = teacher.post(
        BASE,
        json=dict(
            scope="COURSE", course_id=course, language_key=language, verdict=verdict, draft=BODY
        ),
    )
    assert created.status_code == 201, created.text
    return teacher, course, created.json()["catalog_id"]


def test_publish_only_saved_draft_and_keep_old_versions(env):
    teacher, course, cid = course_and_catalog(env)
    draft = teacher.get(f"{BASE}/{cid}/draft").json()
    assert draft["revision"] == 1 and draft["active_version_id"] is None
    assert draft["verdict"] == "WA" and draft["language_key"] == "ALL"
    first = teacher.post(f"{BASE}/{cid}/publish", json=dict(expected_revision=1, reason=REASON))
    assert first.status_code == 200, first.text
    original = teacher.get(f"{BASE}/{cid}/versions/1").json()
    assert original["title"] == BODY["title"]
    assert original["feedback_version_id"] == first.json()["version_id"]
    assert teacher.get(f"{BASE}/{cid}/draft").json()["revision"] == 2
    stale = teacher.post(f"{BASE}/{cid}/publish", json=dict(expected_revision=1, reason=REASON))
    assert stale.status_code == 409 and stale.json()["code"] == "REVISION_CONFLICT"
    update = teacher.put(
        f"{BASE}/{cid}/draft", json={**BODY, "title": "第二版", "expected_revision": 2}
    )
    assert update.json() == {"revision": 3}
    assert teacher.get(f"{BASE}/{cid}/versions/1").json() == original
    with env.engine.begin() as conn:
        assert (
            Learning(SqlRepository(conn), env.effects).resolve(course, "python3", "WA")
            == first.json()["version_id"]
        )
    second = teacher.post(f"{BASE}/{cid}/publish", json=dict(expected_revision=3, reason=REASON))
    assert second.status_code == 200 and second.json()["version_id"] != first.json()["version_id"]
    assert teacher.get(f"{BASE}/{cid}/versions/1").json() == original
    assert teacher.get(f"{BASE}/{cid}/versions/2").json()["title"] == "第二版"
    draft = teacher.get(f"{BASE}/{cid}/draft").json()
    assert draft["active_version_no"] == 2 and draft["revision"] == 4
    page = teacher.get(f"{BASE}/{cid}/versions?limit=1").json()
    assert len(page["items"]) == 1 and page["next_cursor"]
    other = teacher.get(
        f"{BASE}/{cid}/versions", params={"limit": 1, "cursor": page["next_cursor"]}
    ).json()
    assert {page["items"][0]["version_no"], other["items"][0]["version_no"]} == {1, 2}


@pytest.mark.parametrize("name,status", [("student_a", 403), ("teacher_b", 404), ("admin_a", 403)])
def test_course_management_permissions(env, name, status):
    _, course, cid = course_and_catalog(env)
    client = env.login(name)
    assert client.get(f"{BASE}/{cid}/draft").status_code == status
    assert client.get(f"{BASE}/{cid}/versions").status_code == status
    assert (
        client.put(f"{BASE}/{cid}/draft", json={**BODY, "expected_revision": 1}).status_code
        == status
    )
    assert (
        client.post(
            f"{BASE}/{cid}/publish", json=dict(expected_revision=1, reason=REASON)
        ).status_code
        == status
    )
    assert client.get(BASE, params={"course_id": course}).status_code == status


def test_global_scope_is_admin_only_and_general_language(env):
    admin, teacher = env.login("admin_a"), env.login("teacher_a")
    body = dict(scope="GLOBAL", language_key="ALL", verdict="CE", draft=BODY)
    assert teacher.post(BASE, json=body).status_code == 403
    assert admin.post(BASE, json={**body, "language_key": "python3"}).status_code == 422
    assert admin.post(BASE, json={**body, "course_id": str(uuid4())}).status_code == 422
    created = admin.post(BASE, json=body)
    assert created.status_code == 201, created.text
    cid = created.json()["catalog_id"]
    assert teacher.get(f"{BASE}/{cid}/draft").status_code == 403
    assert teacher.get(f"{BASE}/{cid}/versions").status_code == 403
    assert admin.post(BASE, json=body).status_code == 409
    assert (
        admin.post(
            f"{BASE}/{cid}/publish", json=dict(expected_revision=1, reason=REASON)
        ).status_code
        == 200
    )
    assert env.login("student_a").get(f"{BASE}/{cid}/versions/1").status_code == 200


def test_draft_validation_duplicate_and_archived_course(env):
    teacher, course, cid = course_and_catalog(env)
    body = dict(scope="COURSE", course_id=course, language_key="ALL", verdict="WA", draft=BODY)
    assert teacher.post(BASE, json=body).status_code == 409
    assert (
        teacher.post(BASE, json={k: v for k, v in body.items() if k != "course_id"}).status_code
        == 422
    )
    assert (
        teacher.put(f"{BASE}/{cid}/draft", json={**BODY, "expected_revision": 9}).status_code == 409
    )
    for bad in [
        {**BODY, "title": " "},
        {**BODY, "explanation": "x" * 2000},
        {**BODY, "checklist": ["x"] * 11},
    ]:
        assert (
            teacher.put(f"{BASE}/{cid}/draft", json={**bad, "expected_revision": 1}).status_code
            == 422
        )
    assert (
        teacher.post(
            f"{BASE}/{cid}/publish", json=dict(expected_revision=1, reason=" " * 10)
        ).status_code
        == 422
    )
    assert (
        teacher.post(
            f"{BASE}/{cid}/publish", json=dict(expected_revision=1, reason=REASON, title="夹带正文")
        ).status_code
        == 422
    )
    with env.engine.begin() as conn:
        SqlRepository(conn).change("courses", course, status="ARCHIVED", archived_at=env.clock())
    assert teacher.get(f"{BASE}/{cid}/draft").json()["course_status"] == "ARCHIVED"
    assert teacher.get(BASE, params={"course_id": course}).status_code == 200
    assert (
        teacher.put(f"{BASE}/{cid}/draft", json={**BODY, "expected_revision": 1}).status_code == 409
    )
    assert (
        teacher.post(
            f"{BASE}/{cid}/publish", json=dict(expected_revision=1, reason=REASON)
        ).status_code
        == 409
    )


def test_audit_failure_rolls_back_creation_draft_and_publish(env):
    teacher, course, cid = course_and_catalog(env)
    env.effects.fail = True
    assert (
        teacher.post(
            BASE,
            json=dict(
                scope="COURSE", course_id=course, language_key="ALL", verdict="RE", draft=BODY
            ),
        ).status_code
        == 503
    )
    assert (
        teacher.put(
            f"{BASE}/{cid}/draft", json={**BODY, "title": "不能留下", "expected_revision": 1}
        ).status_code
        == 503
    )
    assert (
        teacher.post(
            f"{BASE}/{cid}/publish", json=dict(expected_revision=1, reason=REASON)
        ).status_code
        == 503
    )
    with env.engine.begin() as conn:
        repo = SqlRepository(conn)
        assert len(repo.rows("feedback_catalogs")) == 1
        assert repo.rows("feedback_versions") == []
        row = repo.get("feedback_catalogs", cid)
        assert row["draft_revision"] == 1 and row["active_version_id"] is None
        assert row["draft_payload"]["title"] == BODY["title"]


def test_simultaneous_publication_uses_one_revision_once(env):
    _, _, cid = course_and_catalog(env)

    def publish():
        try:
            with env.engine.begin() as conn:
                repo = SqlRepository(conn, env.clock)
                actor = repo.get("users", env.users["teacher_a"])
                Learning(repo, env.effects).publish(
                    actor, cid, dict(expected_revision=1, reason=REASON)
                )
            return 200
        except Fault as error:
            return error.status

    with ThreadPoolExecutor(max_workers=2) as pool:
        assert sorted(pool.map(lambda _: publish(), range(2))) == [200, 409]
    with env.engine.begin() as conn:
        assert conn.execute(text("SELECT count(*) FROM feedback_versions")).scalar_one() == 1


def test_catalog_list_is_scoped_and_cursor_cannot_cross_course(env):
    teacher, course, cid = course_and_catalog(env)
    teacher.post(
        BASE,
        json=dict(
            scope="COURSE", course_id=course, language_key="python3", verdict="WA", draft=BODY
        ),
    )
    other = teacher.post("/api/v1/courses", json={"title": "另一个课程"}).json()["course_id"]
    teacher.post(
        BASE,
        json=dict(scope="COURSE", course_id=other, language_key="ALL", verdict="RE", draft=BODY),
    )
    page = teacher.get(BASE, params={"course_id": course, "limit": 1}).json()
    assert len(page["items"]) == 1 and page["next_cursor"]
    assert (
        teacher.get(BASE, params={"course_id": other, "cursor": page["next_cursor"]}).status_code
        == 422
    )
    items = teacher.get(BASE).json()["items"]
    assert len(items) == 3 and cid in {item["catalog_id"] for item in items}
    assert env.login("teacher_b").get(BASE).json()["items"] == []
    assert env.login("student_a").get(BASE).status_code == 403
