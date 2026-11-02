import pytest
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError

BASE = "/api/v1/hint-templates"
DRAFT = dict(body="Analyse {verdict}.", allowed_placeholders=["verdict"], schema_version="v1")
PUBLISH = dict(expected_revision=1, reason="Reviewed for teaching use")


def test_template_freezes_saved_version_without_activating_or_exposing_it(env):
    teacher = env.login("teacher_a")
    course = teacher.post("/api/v1/courses", json={"title": "模板测试"}).json()["course_id"]
    body = dict(scope="COURSE", course_id=course, draft=DRAFT)
    created = teacher.post(BASE, json=body)
    assert created.status_code == 201, created.text
    tid = created.json()["template_id"]
    assert teacher.post(BASE, json=body).status_code == 409
    assert teacher.get(BASE, params={"course_id": course}).json()["items"][0]["template_id"] == tid
    path = f"{BASE}/{tid}"
    assert teacher.post(path + "/publish", json={**PUBLISH, "body": "injected"}).status_code == 422
    first = teacher.post(path + "/publish", json=PUBLISH)
    assert first.status_code == 200, first.text
    old = teacher.get(path + "/versions/1").json()
    assert old["body"] == DRAFT["body"] and old["checksum"] == first.json()["checksum"]
    assert teacher.post(path + "/publish", json=PUBLISH).status_code == 409
    assert teacher.put(
        path + "/draft", json={**DRAFT, "expected_revision": 2, "body": "new"}
    ).json() == {"revision": 3}
    assert (
        teacher.post(path + "/publish", json={**PUBLISH, "expected_revision": 3}).status_code == 200
    )
    assert teacher.get(path + "/versions/1").json() == old
    assert teacher.get(path + "/draft").json()["published_version_no"] == 2
    for name, status in [("student_a", 403), ("teacher_b", 404), ("admin_a", 403)]:
        other = env.login(name)
        for suffix in ["/draft", "/versions", "/versions/1"]:
            assert other.get(path + suffix).status_code == status
    with env.engine.begin() as conn:
        assert conn.scalar(text("SELECT active_version_id FROM template_catalogs")) is None
    with pytest.raises(DBAPIError), env.engine.begin() as conn:
        conn.execute(text("UPDATE template_versions SET body='changed'"))


def test_template_validation_and_rollback(env):
    admin = env.login("admin_a")
    body = dict(scope="GLOBAL", draft=DRAFT)
    for changes in [
        {"body": "界" * 2731},
        {"body": "{student_code}"},
        {"body": "{unknown}"},
        {"body": "{verdict.__class__}"},
        {"body": "{verdict!r}"},
        {"body": "{verdict"},
        {"allowed_placeholders": ["verdict", "verdict"]},
        {"schema_version": " "},
        {"body": "line\x00break"},
        {"schema_version": "v\x001"},
        {"body": " "},
    ]:
        assert admin.post(BASE, json={**body, "draft": {**DRAFT, **changes}}).status_code == 422
    created = admin.post(BASE, json={**body, "draft": {**DRAFT, "body": "x" * 8192}})
    assert created.status_code == 201, created.text
    path = BASE + "/" + created.json()["template_id"]
    assert env.login("teacher_a").get(path + "/draft").status_code == 403
    env.effects.fail = True
    assert admin.post(path + "/publish", json=PUBLISH).status_code == 503
    assert admin.get(path + "/versions").json()["items"] == []
    assert admin.get(path + "/draft").json()["revision"] == 1
