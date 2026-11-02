from concurrent.futures import ThreadPoolExecutor

import pytest
from sqlalchemy import event, text
from test_http import http_env as http_env
from test_http import login

BASE = "/api/v1/hint-templates"
DRAFT = {"body": "Review {verdict}.", "allowed_placeholders": ["verdict"], "schema_version": "v1"}
PUBLISH = dict(expected_revision=1, reason="Reviewed for teaching use")


def create(client, course):
    result = client.post(BASE, json=dict(scope="COURSE", course_id=course, draft=DRAFT))
    assert result.status_code == 201, result.text
    return result.json()["template_id"]


def test_formal_template_pagination_is_bounded_and_scoped(http_env):
    engine, ids, _, app = http_env
    client = login(app)
    tid = create(client, ids["course"])
    other = client.post("/api/v1/courses", json={"title": "第二门课"}).json()["course_id"]
    second = create(client, other)
    statements = []

    def track(conn, cursor, statement, parameters, context, executemany):
        if "template_catalogs" in statement and "ORDER BY" in statement:
            statements.append(statement)

    event.listen(engine, "before_cursor_execute", track)
    try:
        page = client.get(BASE, params={"limit": 1}).json()
    finally:
        event.remove(engine, "before_cursor_execute", track)
    assert statements and all(
        "JOIN courses" in s and "LIMIT" in s and "teacher_id" in s for s in statements
    )
    following = client.get(BASE, params={"limit": 1, "cursor": page["next_cursor"]}).json()
    assert {p["items"][0]["template_id"] for p in [page, following]} == {tid, second}
    assert (
        client.get(BASE, params={"course_id": other, "cursor": page["next_cursor"]}).status_code
        == 422
    )
    assert login(app, "student").get(BASE).status_code == 403
    assert login(app, "admin").get(BASE).json()["items"] == []
    assert login(app, "admin").get(BASE + "/" + tid + "/draft").status_code == 403


def test_formal_concurrent_publication_and_archived_course(http_env):
    engine, ids, _, app = http_env
    client = login(app)
    tid = create(client, ids["course"])
    path = BASE + "/" + tid
    clients = [login(app), login(app)]
    with ThreadPoolExecutor(max_workers=2) as pool:
        statuses = list(
            pool.map(lambda c: c.post(path + "/publish", json=PUBLISH).status_code, clients)
        )
    assert sorted(statuses) == [200, 409]
    assert (
        client.post(path + "/publish", json={**PUBLISH, "expected_revision": 2}).status_code == 200
    )
    page = client.get(path + "/versions", params={"limit": 1}).json()
    following = client.get(
        path + "/versions", params={"limit": 1, "cursor": page["next_cursor"]}
    ).json()
    assert {p["items"][0]["version_no"] for p in [page, following]} == {1, 2}
    with engine.begin() as conn:
        assert (
            conn.scalar(
                text("SELECT count(*) FROM audit_events WHERE object_type='template_catalog'")
            )
            == 3
        )
        assert (
            conn.scalar(
                text("SELECT count(*) FROM outbox_events WHERE event_type='TEMPLATE_PUBLISHED'")
            )
            == 2
        )
        conn.execute(
            text("UPDATE courses SET status='ARCHIVED', archived_at=now() WHERE course_id=:cid"),
            {"cid": ids["course"]},
        )
    assert client.get(path + "/draft").json()["course_status"] == "ARCHIVED"
    assert client.put(path + "/draft", json={**DRAFT, "expected_revision": 3}).status_code == 409
    assert (
        client.post(path + "/publish", json={**PUBLISH, "expected_revision": 3}).status_code == 409
    )
    assert login(app, "student").get(path + "/versions/1").status_code == 403


@pytest.mark.parametrize("table", ["audit_events", "outbox_events"])
def test_formal_effect_failure_rolls_back_template_publication(http_env, table):
    engine, ids, _, app = http_env
    client = login(app)
    tid = create(client, ids["course"])
    with engine.begin() as conn:
        conn.exec_driver_sql(
            f"ALTER TABLE {table} ADD CONSTRAINT fail_future CHECK(false) NOT VALID"
        )
    assert client.post(f"{BASE}/{tid}/publish", json=PUBLISH).status_code == 503
    assert client.get(f"{BASE}/{tid}/draft").json()["revision"] == 1
    assert client.get(f"{BASE}/{tid}/versions").json()["items"] == []
