from datetime import datetime, timedelta, timezone
from unittest.mock import patch

from app.modules.identity.domain import utc
from astra_a.contracts import SPEC
from sqlalchemy.exc import OperationalError
from test_assignments import make_assignment
from test_problems import make_version


def test_connect_failure_returns_safe_error_envelope(env):
    client = env.client()
    with patch.object(
        env.engine,
        "connect",
        side_effect=OperationalError("secret sql", {}, Exception("private-host")),
    ):
        result = client.get("/api/v1/auth/session")
    assert result.status_code == 503
    assert result.json()["code"] == "DATABASE_UNAVAILABLE"
    assert "private-host" not in result.text and "secret sql" not in result.text
    assert result.headers["cache-control"] == "no-store"


def test_runtime_openapi_serves_implemented_canonical_schemas(env):
    document = env.client().get("/openapi.json").json()
    assert document["paths"]["/auth/login"]["post"] == SPEC["paths"]["/auth/login"]["post"]
    expected = {
        (path, method.upper()) for path, methods in document["paths"].items() for method in methods
    }
    actual = {
        (route.path.removeprefix("/api/v1"), method)
        for route in env.app.routes
        if route.path.startswith("/api/v1")
        for method in route.methods
    }
    assert expected == actual
    assert "/ai-hints" not in document["paths"]


def test_utc_serialization_normalizes_offset():
    assert (
        utc(datetime(2026, 10, 25, 8, tzinfo=timezone(timedelta(hours=8))))
        == "2026-10-25T00:00:00.000Z"
    )


def test_contract_list_filters_are_validated_and_applied(env):
    teacher, cid, _, _, _, body = make_assignment(env)
    rows = teacher.get(f"/api/v1/courses/{cid}/assignments?state=DRAFT")
    assert rows.status_code == 200, rows.text
    assert len(rows.json()["items"]) == 1
    assert teacher.get(f"/api/v1/courses/{cid}/assignments?state=CLOSED").json()["items"] == []
    assert teacher.get(f"/api/v1/courses/{cid}/assignments?state=BAD").status_code == 422
    assert teacher.get(f"/api/v1/courses/{cid}/members?status=DISABLED").json()["items"] == []
    admin = env.login("admin_a")
    users = admin.get("/api/v1/admin/users?role=STUDENT&login_name=student_a").json()["items"]
    assert [u["login_name"] for u in users] == ["student_a"]
    assert admin.get("/api/v1/admin/users?role=TEACHER&role=STUDENT").status_code == 422


def test_problem_list_filters_match_the_same_version(env):
    teacher, cid, _, _, _, _ = make_version(env, complete=False)
    rows = teacher.get(f"/api/v1/courses/{cid}/problems?status=DRAFT")
    assert rows.status_code == 200, rows.text
    assert len(rows.json()["items"]) == 1
    assert teacher.get(f"/api/v1/courses/{cid}/problems?status=PUBLISHED").json()["items"] == []
    assert teacher.get(f"/api/v1/courses/{cid}/problems?tag=nonexistent").json()["items"] == []
