from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta

import pytest
from sqlalchemy import select


def test_cookie_rotation_csrf_origin_and_password_hash(env):
    client = env.client()
    before = client.get("/api/v1/auth/session")
    assert before.status_code == 200
    assert "HttpOnly" in before.headers["set-cookie"]
    assert "Secure" in before.headers["set-cookie"]
    assert "SameSite=lax" in before.headers["set-cookie"]
    cookie = client.cookies.get("astra_session")
    body = {"login_name": "teacher_a", "password": env.password}
    assert client.post("/api/v1/auth/login", json=body).status_code == 403
    client.headers.update(
        {"Origin": "https://testserver", "X-CSRF-Token": before.json()["csrf_token"]}
    )
    assert client.post("/api/v1/auth/login", json=body).status_code == 200
    assert client.cookies.get("astra_session") != cookie
    assert client.post("/api/v1/courses", json={"title": "课程"}).status_code == 403
    data = client.get("/api/v1/auth/session").json()
    client.headers["X-CSRF-Token"] = data["csrf_token"]
    assert client.post("/api/v1/courses", json={"title": "课程"}).status_code == 201
    with env.engine.begin() as conn:
        row = conn.execute(select(env.tables["users"])).mappings().first()
        assert "$argon2id$v=19$m=19456,t=2,p=1$" in row["password_hash"]
        sessions = conn.execute(select(env.tables["sessions"])).mappings().all()
        assert all(
            s["token_hash"] != cookie and s["csrf_hash"] != data["csrf_token"] for s in sessions
        )


@pytest.mark.parametrize("elapsed", [timedelta(minutes=15), timedelta(hours=8)])
def test_session_expires_at_boundary(env, elapsed):
    client = env.login("teacher_a")
    env.clock.advance(elapsed)
    assert client.get("/api/v1/courses").status_code == 401


def test_failed_login_window_cooldown_and_unknown_user(env):
    client = env.client()
    csrf = client.get("/api/v1/auth/session").json()["csrf_token"]
    client.headers.update({"Origin": "https://testserver", "X-CSRF-Token": csrf})
    for _ in range(5):
        response = client.post(
            "/api/v1/auth/login", json={"login_name": "teacher_a", "password": "wrong_password_123"}
        )
        assert response.status_code == 401
    assert (
        client.post(
            "/api/v1/auth/login", json={"login_name": "teacher_a", "password": env.password}
        ).status_code
        == 429
    )
    env.clock.advance(timedelta(minutes=10))
    assert (
        client.post(
            "/api/v1/auth/login", json={"login_name": "teacher_a", "password": env.password}
        ).status_code
        == 200
    )


def test_reset_revoke_force_password_and_no_echo(env):
    student = env.login("student_a")
    admin = env.login("admin_a")
    user_id = env.users["student_a"]
    new_password = "ChangedPassword456!"
    reset = admin.post(
        f"/api/v1/admin/users/{user_id}/reset-password",
        json={
            "one_time_password": new_password,
            "expected_revision": 1,
            "reason": "课程测试需要重新设置账号密码",
        },
    )
    assert reset.status_code == 204
    assert student.get("/api/v1/courses").status_code == 401
    student = env.login("student_a", new_password)
    assert student.get("/api/v1/courses").status_code == 403
    changed = student.post(
        "/api/v1/auth/password",
        json={
            "current_password": new_password,
            "new_password": "FinalPassword789!",
        },
    )
    assert changed.status_code == 204
    assert student.get("/api/v1/courses").status_code == 401
    response = admin.get("/api/v1/admin/users")
    assert "password_hash" not in response.text
    assert new_password not in response.text


def test_course_revision_membership_and_parallel_writes(env):
    teacher = env.login("teacher_a")
    course = teacher.post("/api/v1/courses", json={"title": "程序设计"}).json()
    cid = course["course_id"]
    student = env.login("student_a")
    assert student.get(f"/api/v1/courses/{cid}").status_code == 404
    joined = teacher.put(
        f"/api/v1/courses/{cid}/members/{env.users['student_a']}",
        json={"status": "ACTIVE", "expected_revision": 1},
    )
    assert joined.status_code == 200
    assert student.get(f"/api/v1/courses/{cid}").status_code == 200

    def update(title):
        c = env.login("teacher_a")
        return c.patch(
            f"/api/v1/courses/{cid}", json={"title": title, "expected_revision": 2}
        ).status_code

    with ThreadPoolExecutor(2) as pool:
        assert sorted(pool.map(update, ["课程甲", "课程乙"])) == [200, 409]
    assert (
        teacher.put(
            f"/api/v1/courses/{cid}/members/{env.users['student_a']}",
            json={"status": "DISABLED", "expected_revision": 3},
        ).status_code
        == 200
    )
    assert student.get(f"/api/v1/courses/{cid}").status_code == 404
    assert teacher.get(f"/api/v1/courses/{cid}/members").json()["items"][0]["status"] == "DISABLED"


@pytest.mark.parametrize("actor", ["teacher_b", "student_a", "student_b", "admin_a", None])
@pytest.mark.parametrize(
    "operation", ["get", "patch", "members", "put_member", "problems", "assignments"]
)
def test_cross_object_authorization_30_cases(env, actor, operation):
    owner = env.login("teacher_a")
    cid = owner.post("/api/v1/courses", json={"title": "不可见课程"}).json()["course_id"]
    client = env.login(actor) if actor else env.client()
    url = f"/api/v1/courses/{cid}"
    if operation == "get":
        response = client.get(url)
    elif operation == "patch":
        response = client.patch(url, json={"title": "改名", "expected_revision": 1})
    elif operation == "put_member":
        response = client.put(
            url + "/members/" + env.users["student_a"],
            json={"status": "ACTIVE", "expected_revision": 1},
        )
    else:
        response = client.get(url + "/" + operation)
    expected = (
        401
        if actor is None
        else (
            403
            if actor == "admin_a"
            or (
                actor.startswith("student")
                and operation in ["patch", "members", "put_member", "problems"]
            )
            else 404
        )
    )
    assert response.status_code == expected
    assert response.json()["request_id"] == response.headers["X-Request-Id"]
    assert response.headers["Cache-Control"] == "no-store"


def test_reject_unknown_fields_cursor_and_sensitive_audit_rollback(env):
    teacher = env.login("teacher_a")
    assert (
        teacher.post(
            "/api/v1/courses", json={"title": "x", "teacher_id": env.users["teacher_b"]}
        ).status_code
        == 422
    )
    assert teacher.get("/api/v1/courses?cursor=bogus").status_code == 422
    assert teacher.get("/api/v1/courses?limit=101").status_code == 422
    env.effects.fail = True
    response = teacher.post("/api/v1/courses", json={"title": "审计失败"})
    assert response.status_code == 503
    env.effects.fail = False
    assert teacher.get("/api/v1/courses").json()["items"] == []


def test_disable_user_revokes_and_cannot_self_disable(env):
    admin = env.login("admin_a")
    student = env.login("student_a")
    assert (
        admin.patch(
            f"/api/v1/admin/users/{env.users['admin_a']}",
            json={
                "status": "DISABLED",
                "expected_revision": 1,
                "reason": "测试管理员不能停用自己账号",
            },
        ).status_code
        == 409
    )
    assert (
        admin.patch(
            f"/api/v1/admin/users/{env.users['student_a']}",
            json={
                "status": "DISABLED",
                "expected_revision": 1,
                "reason": "测试停用账号并撤销全部会话",
            },
        ).status_code
        == 200
    )
    assert student.get("/api/v1/courses").status_code == 401
