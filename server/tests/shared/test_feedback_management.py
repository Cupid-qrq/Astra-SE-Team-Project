from concurrent.futures import ThreadPoolExecutor
from uuid import uuid4

import pytest
from sqlalchemy import event, text
from test_http import http_env as http_env
from test_http import login

from app.shared.repository import SqlRepository
from app.shared.uow import UnitOfWork

BASE = "/api/v1/feedback-catalogs"
BODY = {"title": "检查边界", "explanation": "检查输入与输出。", "checklist": ["手工核算。"]}
REASON = "核对课程教学内容后发布帮助版本"


def create(client, course, *, verdict="WA", language="ALL"):
    result = client.post(
        BASE,
        json=dict(
            scope="COURSE", course_id=course, verdict=verdict, language_key=language, draft=BODY
        ),
    )
    assert result.status_code == 201, result.text
    return result.json()["catalog_id"]


def test_formal_help_uses_real_uow_effects_and_frozen_history(http_env):
    engine, ids, _, app = http_env
    client = login(app)
    cid = create(client, ids["course"])
    first = client.post(f"{BASE}/{cid}/publish", json=dict(expected_revision=1, reason=REASON))
    assert first.status_code == 200, first.text
    old = client.get(f"{BASE}/{cid}/versions/1").json()
    saved = client.put(
        f"{BASE}/{cid}/draft", json={**BODY, "title": "更新后", "expected_revision": 2}
    )
    assert saved.json() == {"revision": 3}
    assert (
        client.post(
            f"{BASE}/{cid}/publish", json=dict(expected_revision=3, reason=REASON)
        ).status_code
        == 200
    )
    assert client.get(f"{BASE}/{cid}/versions/1").json() == old
    assert client.get(f"{BASE}/{cid}/versions/2").json()["title"] == "更新后"
    assert client.get(f"{BASE}/{cid}/draft").json()["active_version_no"] == 2
    with UnitOfWork(engine) as conn:
        events = SqlRepository(conn).rows("audit_events", object_id=cid)
        assert [e["action"] for e in sorted(events, key=lambda e: e["timestamp"])] == [
            "FEEDBACK_CREATED",
            "FEEDBACK_PUBLISHED",
            "FEEDBACK_DRAFT_SAVED",
            "FEEDBACK_PUBLISHED",
        ]
        assert all(e["object_type"] == "feedback_catalog" for e in events)
        assert (
            conn.scalar(
                text("SELECT count(*) FROM outbox_events WHERE event_type LIKE 'FEEDBACK_%'")
            )
            == 4
        )


def test_formal_lists_filter_in_sql_and_bind_cursors(http_env):
    engine, ids, _, app = http_env
    client = login(app)
    cid = create(client, ids["course"])
    create(client, ids["course"], verdict="RE")
    other = client.post("/api/v1/courses", json={"title": "另一课程"}).json()["course_id"]
    create(client, other)
    statements = []

    def track(conn, cursor, statement, parameters, context, executemany):
        if (
            statement.lstrip().startswith("SELECT")
            and "feedback_catalogs" in statement
            and "ORDER BY" in statement
        ):
            statements.append(statement)

    event.listen(engine, "before_cursor_execute", track)
    try:
        page = client.get(BASE, params={"course_id": ids["course"], "limit": 1})
    finally:
        event.remove(engine, "before_cursor_execute", track)
    assert page.status_code == 200, page.text
    assert statements and all(
        "LIMIT" in s and "JOIN courses" in s and "teacher_id" in s for s in statements
    )
    value = page.json()
    assert len(value["items"]) == 1 and value["next_cursor"]
    assert (
        client.get(BASE, params={"course_id": other, "cursor": value["next_cursor"]}).status_code
        == 422
    )
    assert login(app, "student").get(BASE).status_code == 403
    assert login(app, "student").get(f"{BASE}/{cid}/draft").status_code == 403
    assert login(app, "admin").get(BASE).json()["items"] == []
    assert login(app, "admin").get(f"{BASE}/{cid}/draft").status_code == 403
    assert client.get(f"{BASE}/{cid}/versions").json()["items"] == []


@pytest.mark.parametrize("table", ["audit_events", "outbox_events"])
def test_formal_publish_failure_rolls_back_revision_and_active_pointer(http_env, table):
    engine, ids, _, app = http_env
    client = login(app)
    cid = create(client, ids["course"])
    with UnitOfWork(engine) as conn:
        conn.exec_driver_sql(
            "CREATE FUNCTION reject_help_effect() RETURNS trigger LANGUAGE plpgsql AS $$ BEGIN RAISE EXCEPTION 'synthetic effect failure'; END $$"
        )
        conn.exec_driver_sql(
            f"CREATE TRIGGER reject_help_effect BEFORE INSERT ON {table} FOR EACH ROW EXECUTE FUNCTION reject_help_effect()"
        )
    result = client.post(f"{BASE}/{cid}/publish", json=dict(expected_revision=1, reason=REASON))
    assert result.status_code == 503, result.text
    with UnitOfWork(engine) as conn:
        repo = SqlRepository(conn)
        assert repo.rows("feedback_versions", catalog_id=cid) == []
        assert repo.get("feedback_catalogs", cid)["draft_revision"] == 1
        assert repo.get("feedback_catalogs", cid)["active_version_id"] is None


def test_formal_same_revision_can_publish_only_once(http_env):
    engine, ids, _, app = http_env
    client = login(app)
    cid = create(client, ids["course"])
    clients = [login(app), login(app)]
    with ThreadPoolExecutor(max_workers=2) as pool:
        statuses = list(
            pool.map(
                lambda c: (
                    c.post(
                        f"{BASE}/{cid}/publish", json=dict(expected_revision=1, reason=REASON)
                    ).status_code
                ),
                clients,
            )
        )
    assert sorted(statuses) == [200, 409]
    with UnitOfWork(engine) as conn:
        assert len(SqlRepository(conn).rows("feedback_versions", catalog_id=cid)) == 1


def test_formal_global_and_storage_validation(http_env):
    _, _, _, app = http_env
    admin = login(app, "admin")
    body = dict(scope="GLOBAL", language_key="ALL", verdict="SE", draft=BODY)
    assert (
        admin.post(
            BASE, json={**body, "draft": {**BODY, "explanation": "hidden\x00text"}}
        ).status_code
        == 422
    )
    cid = admin.post(BASE, json=body).json()["catalog_id"]
    assert (
        admin.post(
            f"{BASE}/{cid}/publish", json=dict(expected_revision=1, reason=REASON)
        ).status_code
        == 200
    )
    assert login(app, "student").get(f"{BASE}/{cid}/versions/1").json()["title"] == BODY["title"]
    assert login(app).get(f"{BASE}/{cid}/draft").status_code == 403
    assert admin.get(BASE, params={"course_id": str(uuid4())}).status_code == 403
