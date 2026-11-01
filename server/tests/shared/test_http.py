from pathlib import Path
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from http_fixtures import profile
from sqlalchemy import text
from teaching_fixtures import SECRET, seed

from app.main import create_app
from app.shared.config import Settings
from app.shared.passwords import ArgonPasswords
from app.shared.repository import SqlRepository
from app.shared.uow import UnitOfWork


@pytest.fixture
def http_env(database):
    ids = seed(database, Path(__file__).parents[2] / "alembic.ini", profile=profile())
    passwords = ArgonPasswords()
    with UnitOfWork(database) as conn:
        repo = SqlRepository(conn)
        for key in ["teacher", "student", "admin"]:
            repo.change("users", ids[key], password_hash=passwords.hash("ExamplePassword123!"))
    settings = Settings(
        "postgresql+psycopg://unused/astra_test",
        SECRET,
        "https://testserver",
        "test-readiness-token-at-least-32bytes",
    )
    app = create_app(settings, engine=database)
    return database, ids, settings, app


def login(app, name="teacher"):
    client = TestClient(app, base_url="https://testserver", raise_server_exceptions=False)
    csrf = client.get("/api/v1/auth/session").json()["csrf_token"]
    client.headers.update({"Origin": "https://testserver", "X-CSRF-Token": csrf})
    result = client.post(
        "/api/v1/auth/login", json={"login_name": name, "password": "ExamplePassword123!"}
    )
    assert result.status_code == 200, result.text
    client.headers["X-CSRF-Token"] = client.get("/api/v1/auth/session").json()["csrf_token"]
    return client


def test_real_identity_courses_and_audit(http_env):
    engine, ids, _, app = http_env
    client = login(app)
    result = client.post("/api/v1/courses", json={"title": "HTTP course"})
    assert result.status_code == 201, result.text
    assert client.get("/api/v1/courses").status_code == 200
    with engine.connect() as conn:
        assert conn.scalar(text("SELECT count(*) FROM audit_events")) == 1
        assert conn.scalar(text("SELECT count(*) FROM outbox_events")) == 1
    student = login(app, "student")
    assert student.get("/api/v1/courses/" + result.json()["course_id"]).status_code == 404
    assert student.get("/api/v1/admin/users").status_code == 403


@pytest.mark.parametrize("body", [b"{broken", b'{"title":"x","title":"y"}', b"\xff"])
def test_malformed_json_is_safe_400(http_env, body):
    client = login(http_env[3])
    result = client.post(
        "/api/v1/courses", content=body, headers={"Content-Type": "application/json"}
    )
    assert result.status_code == 400, result.text
    assert result.json()["code"] == "INVALID_REQUEST"
    assert "broken" not in result.text and "title" not in result.text
    assert result.headers["Cache-Control"] == "no-store"
    assert result.json()["request_id"] == result.headers["X-Request-Id"]


def test_error_auth_csrf_and_request_id(http_env):
    client = TestClient(http_env[3], base_url="https://testserver")
    assert client.get("/api/v1/courses").status_code == 401
    csrf = client.get("/api/v1/auth/session").json()["csrf_token"]
    result = client.post(
        "/api/v1/auth/login",
        json={"login_name": "teacher", "password": "ExamplePassword123!"},
        headers={"X-CSRF-Token": csrf, "Origin": "https://evil.example"},
    )
    assert result.status_code == 403
    result = client.get("/api/v1/missing", headers={"X-Request-Id": "not-a-uuid"})
    assert result.status_code == 404
    uuid4().__class__(result.headers["X-Request-Id"])
    assert result.headers["X-Request-Id"] == result.json()["request_id"]
    cookie = client.cookies.get("astra_session")
    assert cookie
    response = client.get("/api/v1/auth/session")
    # A newly issued anonymous session has security flags on its Set-Cookie.
    fresh = TestClient(http_env[3], base_url="https://testserver").get("/api/v1/auth/session")
    value = fresh.headers["set-cookie"].lower()
    assert "secure" in value and "httponly" in value and "samesite=lax" in value
    assert response.json()["authenticated"] is False


def test_failed_login_ledger_commits_and_cooldown(http_env):
    engine, _, _, app = http_env
    client = TestClient(app, base_url="https://testserver")
    csrf = client.get("/api/v1/auth/session").json()["csrf_token"]
    client.headers.update({"Origin": "https://testserver", "X-CSRF-Token": csrf})
    for _ in range(5):
        assert (
            client.post(
                "/api/v1/auth/login",
                json={"login_name": "teacher", "password": "WrongPassword123!"},
            ).status_code
            == 401
        )
    result = client.post(
        "/api/v1/auth/login", json={"login_name": "teacher", "password": "WrongPassword123!"}
    )
    assert result.status_code == 429
    assert result.headers["Retry-After"]
    with engine.connect() as conn:
        assert conn.scalar(text("SELECT count(*) FROM login_attempts")) == 5


def test_background_does_not_renew_and_disable_revokes(http_env):
    engine, ids, _, app = http_env
    client = login(app, "student")
    with engine.connect() as conn:
        old = conn.scalar(
            text(
                "SELECT last_seen_at FROM sessions WHERE user_id=:uid AND revoked_at IS NULL ORDER BY created_at DESC LIMIT 1"
            ),
            {"uid": ids["student"]},
        )
    assert client.get("/api/v1/courses", headers={"X-Astra-Background": "1"}).status_code == 200
    with engine.connect() as conn:
        assert (
            conn.scalar(
                text("SELECT max(last_seen_at) FROM sessions WHERE user_id=:uid"),
                {"uid": ids["student"]},
            )
            == old
        )
    admin = login(app, "admin")
    result = admin.patch(
        "/api/v1/admin/users/" + ids["student"],
        json={
            "status": "DISABLED",
            "expected_revision": 1,
            "reason": "Testing disable account via formal HTTP",
        },
    )
    assert result.status_code == 200, result.text
    assert client.get("/api/v1/courses").status_code == 401


def test_internal_readiness_and_public_liveness(http_env):
    _, _, settings, app = http_env
    client = TestClient(app, base_url="https://testserver")
    assert client.get("/health/live").status_code == 200
    assert client.get("/health/ready").status_code == 403
    assert (
        client.get(
            "/health/ready", headers={"X-Readiness-Token": settings.readiness_token}
        ).status_code
        == 200
    )


def test_input_limits_queries_and_transaction_rollback(http_env):
    engine, _, _, app = http_env
    client = login(app)
    assert client.post("/api/v1/courses", content=b"x" * (512 * 1024 + 1)).status_code == 413
    assert client.get("/api/v1/courses?limit=0").status_code == 422
    assert client.get("/api/v1/courses?unknown=x").status_code == 422
    assert client.get("/api/v1/courses?limit=1&limit=2").status_code == 422
    with engine.begin() as conn:
        conn.exec_driver_sql(
            "ALTER TABLE outbox_events ADD CONSTRAINT inject_failure CHECK (false)"
        )
    result = client.post("/api/v1/courses", json={"title": "must rollback"})
    assert result.status_code == 409, result.text
    with engine.connect() as conn:
        assert conn.scalar(text("SELECT count(*) FROM courses WHERE title='must rollback'")) == 0
        assert conn.scalar(text("SELECT count(*) FROM audit_events")) == 0


def test_settings_reject_unsafe_config_without_secret_echo():
    with pytest.raises(ValueError):
        Settings("sqlite://", SECRET, "https://testserver", "x" * 32)
    with pytest.raises(ValueError):
        Settings("postgresql+psycopg://unused/astra_test", SECRET, "http://testserver", "x" * 32)
    assert SECRET.decode() not in repr(
        Settings("postgresql+psycopg://unused/astra_test", SECRET, "https://testserver", "x" * 32)
    )


def test_keyset_pages_are_bounded_and_scoped(http_env, monkeypatch):
    _, _, _, app = http_env
    client = login(app)
    for i in range(3):
        assert client.post("/api/v1/courses", json={"title": f"page {i}"}).status_code == 201
    original = SqlRepository.rows

    def no_full_courses(self, table, **filters):
        assert table != "courses", "Public list must not load every course"
        return original(self, table, **filters)

    monkeypatch.setattr(SqlRepository, "rows", no_full_courses)
    first = client.get("/api/v1/courses?limit=1").json()
    assert len(first["items"]) == 1 and first["next_cursor"]
    cursor = first["next_cursor"]
    second = client.get("/api/v1/courses", params={"limit": 1, "cursor": cursor})
    assert second.status_code == 200, second.text
    assert second.json()["items"][0]["course_id"] != first["items"][0]["course_id"]
    assert (
        client.get("/api/v1/courses", params={"cursor": cursor, "status": "ACTIVE"}).status_code
        == 422
    )
    assert (
        login(app, "student").get("/api/v1/courses", params={"cursor": cursor}).status_code == 422
    )
    assert client.get("/api/v1/courses", params={"cursor": cursor + "x"}).status_code == 422


def test_response_contract_failure_rolls_back(http_env, monkeypatch):
    from app.modules.courses.application import Courses

    engine, _, _, app = http_env
    original = Courses.create

    def invalid(self, actor, body):
        original(self, actor, body)
        return {"course_id": "invalid-id", "revision": 1}

    monkeypatch.setattr(Courses, "create", invalid)
    result = login(app).post("/api/v1/courses", json={"title": "response rollback"})
    assert result.status_code == 500, result.text
    assert result.json()["code"] == "RESPONSE_CONTRACT_ERROR"
    with engine.connect() as conn:
        assert (
            conn.scalar(text("SELECT count(*) FROM courses WHERE title='response rollback'")) == 0
        )
        assert conn.scalar(text("SELECT count(*) FROM audit_events")) == 0


def test_database_failure_is_safe_retryable_503(http_env, monkeypatch):
    from sqlalchemy.exc import OperationalError

    client = login(http_env[3])

    def unavailable(self):
        raise OperationalError(
            "sensitive SQL", {"password": "never echo"}, RuntimeError("private/path")
        )

    monkeypatch.setattr(SqlRepository, "guard", unavailable)
    result = client.get("/api/v1/courses")
    assert result.status_code == 503
    assert result.headers["Retry-After"] == "2"
    assert (
        "sensitive" not in result.text
        and "private" not in result.text
        and "password" not in result.text
    )


def test_missing_configuration_fails_startup(monkeypatch):
    for key in (
        "ASTRA_DATABASE_URL",
        "ASTRA_SESSION_SECRET",
        "ASTRA_ORIGIN",
        "ASTRA_READINESS_TOKEN",
    ):
        monkeypatch.delenv(key, raising=False)
    with pytest.raises(ValueError, match="configuration"):
        create_app()


def test_members_and_unavailable_coordination(http_env):
    _, ids, _, app = http_env
    teacher = login(app)
    student = login(app, "student")
    path = "/api/v1/courses/" + ids["course"]
    result = teacher.put(
        path + "/members/" + ids["student"], json={"status": "DISABLED", "expected_revision": 1}
    )
    assert result.status_code == 200, result.text
    assert student.get(path).status_code == 404
    rows = teacher.get(path + "/members?status=DISABLED").json()["items"]
    assert rows == [{"user_id": ids["student"], "display_name": "student", "status": "DISABLED"}]
    assert (
        teacher.put(
            path + "/members/" + ids["student"], json={"status": "ACTIVE", "expected_revision": 2}
        ).status_code
        == 200
    )
    assert student.get(path).status_code == 200
    assert len(student.get(path + "/assignments?state=OPEN").json()["items"]) == 1
    revision = teacher.get("/api/v1/assignments/" + ids["assignment"]).json()["revision"]
    result = teacher.patch(
        "/api/v1/assignments/" + ids["assignment"] + "/deadline",
        json={
            "expected_revision": revision,
            "new_due_at": "2031-01-01T00:00:00.000Z",
            "reason": "Unavailable coordination must never fabricate success",
        },
    )
    assert result.status_code == 503, result.text
    assert teacher.get("/api/v1/assignments/" + ids["assignment"]).json()["revision"] == revision


def test_problem_without_versions_has_safe_title(http_env):
    _, ids, _, app = http_env
    teacher = login(app)
    result = teacher.post("/api/v1/problems", json={"course_id": ids["course"]})
    assert result.status_code == 201, result.text
    pid = result.json()["problem_id"]
    result = teacher.get("/api/v1/courses/" + ids["course"] + "/problems?status=DRAFT")
    assert result.status_code == 200, result.text
    assert result.json()["items"][0]["problem_id"] == pid
    assert result.json()["items"][0]["title"] == "未命名题目"


@pytest.mark.parametrize("raw", [b'{"title":"\\ud800"}', b'{"title":NaN}', b'{"title":Infinity}'])
def test_non_unicode_and_non_finite_json_is_400(http_env, raw):
    result = login(http_env[3]).post(
        "/api/v1/courses", content=raw, headers={"Content-Type": "application/json"}
    )
    assert result.status_code == 400, result.text


def test_duplicate_security_headers_are_rejected(http_env):
    client = login(http_env[3])
    result = client.get(
        "/api/v1/courses", headers=[("X-Astra-Background", "1"), ("X-Astra-Background", "0")]
    )
    assert result.status_code == 400, result.text


def test_readiness_detects_wrong_migration(http_env):
    engine, _, settings, app = http_env
    with engine.begin() as conn:
        conn.exec_driver_sql("UPDATE alembic_version SET version_num='b004'")
    result = TestClient(app, base_url="https://testserver").get(
        "/health/ready", headers={"X-Readiness-Token": settings.readiness_token}
    )
    assert result.status_code == 503, result.text
    assert result.json()["retryable"] is True
    assert "b004" not in result.text


def test_student_public_problem_uses_full_schema_without_hidden_material(http_env):
    _, ids, _, app = http_env
    response = login(app, "student").get(
        "/api/v1/assignments/" + ids["assignment"] + "/problems/" + ids["problem"]
    )
    assert response.status_code == 200, response.text
    assert response.json()["profile"]["comparison"] == "ASCII_TOKENS"
    assert (
        not {"input_text", "answer_text", "code", "references", "testcases"}
        & response.json().keys()
    )


def test_unparseable_database_url_is_configuration_error():
    with pytest.raises(ValueError, match="configuration"):
        Settings("not a database URL", SECRET, "https://testserver", "x" * 32)
