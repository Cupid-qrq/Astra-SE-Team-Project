from datetime import timedelta

from sqlalchemy import select
from test_assignments import make_assignment, publish


def test_background_session_and_assignment_polls_do_not_extend_idle_session(env):
    teacher, _, _, _, aid, _ = make_assignment(env)
    publish(teacher, aid)
    student = env.login("student_a")
    for _ in range(14):
        env.clock.advance(timedelta(minutes=1))
        assert student.get("/api/v1/auth/session").json()["authenticated"]
        assert (
            student.get(
                f"/api/v1/assignments/{aid}", headers={"X-Astra-Background": "1"}
            ).status_code
            == 200
        )
    env.clock.advance(timedelta(minutes=1))
    assert not student.get("/api/v1/auth/session").json()["authenticated"]
    assert student.get(f"/api/v1/assignments/{aid}").status_code == 401


def test_user_navigation_still_renews_idle_window(env):
    teacher = env.login("teacher_a")
    env.clock.advance(timedelta(minutes=14))
    assert teacher.get("/api/v1/courses").status_code == 200
    env.clock.advance(timedelta(minutes=2))
    assert teacher.get("/api/v1/auth/session").json()["authenticated"]


def test_cooldown_lasts_ten_minutes_after_fifth_failure(env):
    client = env.client()
    client.headers.update(
        {
            "Origin": "https://testserver",
            "X-CSRF-Token": client.get("/api/v1/auth/session").json()["csrf_token"],
        }
    )
    for minute in [0, 1, 2, 3, 8]:
        env.clock.value = env.clock.value.replace(minute=minute)
        assert (
            client.post(
                "/api/v1/auth/login",
                json={"login_name": "teacher_a", "password": "WrongPassword123!"},
            ).status_code
            == 401
        )
    env.clock.advance(timedelta(minutes=3))
    assert (
        client.post(
            "/api/v1/auth/login", json={"login_name": "teacher_a", "password": env.password}
        ).status_code
        == 429
    )
    env.clock.advance(timedelta(minutes=7))
    client.headers["X-CSRF-Token"] = client.get("/api/v1/auth/session").json()["csrf_token"]
    assert (
        client.post(
            "/api/v1/auth/login", json={"login_name": "teacher_a", "password": env.password}
        ).status_code
        == 200
    )


def test_absolute_expiry_despite_recent_activity(env):
    client = env.login("teacher_a")
    env.clock.advance(timedelta(hours=8))
    with env.engine.begin() as connection:
        connection.execute(env.tables["sessions"].update().values(last_seen_at=env.clock()))
    assert client.get("/api/v1/courses").status_code == 401


def test_origin_duplicate_json_and_unknown_query_rejected(env):
    client = env.login("teacher_a")
    client.headers["Origin"] = "https://attacker.example"
    assert client.post("/api/v1/courses", json={"title": "不能创建"}).status_code == 403
    client.headers["Origin"] = "https://testserver"
    assert (
        client.post(
            "/api/v1/courses",
            content=b'{"title":"first","title":"second"}',
            headers={"Content-Type": "application/json"},
        ).status_code
        == 422
    )
    cid = client.post("/api/v1/courses", json={"title": "正常课程"}).json()["course_id"]
    assert client.get(f"/api/v1/courses/{cid}?unexpected=1").status_code == 422


def test_admin_create_force_change_unique_salts_and_atomic_reset(env):
    admin = env.login("admin_a")
    created = admin.post(
        "/api/v1/admin/users",
        json={
            "login_name": "student_new",
            "display_name": "新同学",
            "role": "STUDENT",
            "initial_password": env.password,
            "reason": "为新学期课程创建学生测试账号",
        },
    )
    assert created.status_code == 201
    assert created.json()["must_change_password"] is True
    with env.engine.begin() as connection:
        hashes = connection.execute(select(env.tables["users"].c.password_hash)).scalars().all()
        assert len(set(hashes)) == len(hashes)
    env.effects.fail = True
    assert (
        admin.post(
            f"/api/v1/admin/users/{created.json()['user_id']}/reset-password",
            json={
                "one_time_password": "DifferentPassword123!",
                "expected_revision": 1,
                "reason": "验证审计失败时密码不能发生变更",
            },
        ).status_code
        == 503
    )
    env.effects.fail = False
    assert env.login("student_new").get("/api/v1/auth/session").json()["user"]["revision"] == 1
