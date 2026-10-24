from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from uuid import uuid4

import pytest
from app.modules.assignments.domain import assignment_state, submission_mode
from app.modules.identity.domain import Fault, utc
from sqlalchemy import text
from test_problems import attach_evidence, make_version


def make_assignment(env, *, ai_policy="DISABLED"):
    _, cid, pid, vid, rev, _ = make_version(env)
    evidence = attach_evidence(env, vid)
    teacher = env.login("teacher_a")
    assert (
        teacher.post(
            f"/api/v1/problem-versions/{vid}/publish",
            json={
                "expected_revision": rev,
                "preflight_id": evidence["preflight_id"],
                "reason": "测试作业所引用版本已通过全部预检",
            },
        ).status_code
        == 200
    )
    body = {
        "course_id": cid,
        "title": "第一周练习",
        "items": [{"problem_id": pid, "version_id": vid, "points": 100}],
        "open_at": utc(env.clock() + timedelta(hours=1)),
        "due_at": utc(env.clock() + timedelta(hours=2)),
        "ai_policy": ai_policy,
    }
    response = teacher.post("/api/v1/assignments", json=body)
    assert response.status_code == 201, response.text
    aid = response.json()["assignment_id"]
    assert (
        teacher.put(
            f"/api/v1/courses/{cid}/members/{env.users['student_a']}",
            json={"status": "ACTIVE", "expected_revision": 1},
        ).status_code
        == 200
    )
    return teacher, cid, pid, vid, aid, body


def publish(teacher, aid):
    response = teacher.post(
        f"/api/v1/assignments/{aid}/publish",
        json={"expected_revision": 1, "reason": "本次作业的题目分值和开放时间已经核对"},
    )
    assert response.status_code == 200, response.text


def test_draft_scheduled_open_closed_visibility_and_exact_boundaries(env):
    teacher, cid, pid, _, aid, _ = make_assignment(env)
    student = env.login("student_a")
    assert student.get(f"/api/v1/assignments/{aid}").status_code == 404
    assert student.get(f"/api/v1/courses/{cid}/assignments").json()["items"] == []
    publish(teacher, aid)
    view = student.get(f"/api/v1/assignments/{aid}").json()
    assert view["state"] == "SCHEDULED" and view["items"] == []
    assert student.get(f"/api/v1/assignments/{aid}/problems/{pid}").status_code == 404
    env.clock.advance(timedelta(hours=1))
    student = env.login("student_a")
    assert student.get(f"/api/v1/assignments/{aid}").json()["state"] == "OPEN"
    problem = student.get(f"/api/v1/assignments/{aid}/problems/{pid}")
    assert problem.status_code == 200, problem.text
    assert "test reference" not in problem.text and "5 8" not in problem.text
    assert problem.json()["samples"] == [{"input": "1 2", "output": "3"}]
    env.clock.advance(timedelta(hours=1))
    assert env.login("student_a").get(f"/api/v1/assignments/{aid}").json()["state"] == "CLOSED"


@pytest.mark.parametrize(
    "kind",
    ["points", "duplicate", "empty", "time", "foreign_version", "foreign_course", "draft_version"],
)
def test_invalid_assignment_items_and_times_rejected(env, kind):
    teacher, cid, pid, vid, _, body = make_assignment(env)
    if kind == "points":
        body["items"][0]["points"] = 99
    elif kind == "duplicate":
        body["items"] = [dict(body["items"][0], points=50)] * 2
    elif kind == "empty":
        body["items"] = []
    elif kind == "time":
        body["due_at"] = body["open_at"]
    elif kind == "foreign_version":
        body["items"][0]["version_id"] = str(uuid4())
    elif kind == "foreign_course":
        body["course_id"] = teacher.post("/api/v1/courses", json={"title": "其他课程"}).json()[
            "course_id"
        ]
    else:
        _, _, _, new_vid, _, _ = make_version(env, complete=False)
        body["items"][0]["version_id"] = new_vid
    assert teacher.post("/api/v1/assignments", json=body).status_code in (404, 409, 422)


@pytest.mark.parametrize("actor", ["student_b", "teacher_b", "admin_a"])
@pytest.mark.parametrize(
    "operation", ["get", "problem", "patch", "publish", "deadline", "ai-policy"]
)
def test_assignment_cross_object_authorization(env, actor, operation):
    teacher, _, pid, _, aid, _ = make_assignment(env)
    publish(teacher, aid)
    client = env.login(actor)
    url = f"/api/v1/assignments/{aid}"
    if operation == "get":
        response = client.get(url)
    elif operation == "problem":
        response = client.get(url + "/problems/" + pid)
    elif operation == "patch":
        response = client.patch(url, json={"expected_revision": 2, "title": "试图越权"})
    elif operation == "publish":
        response = client.post(
            url + "/publish",
            json={"expected_revision": 2, "reason": "跨对象权限测试禁止非法操作作业"},
        )
    elif operation == "deadline":
        response = client.patch(
            url + "/deadline",
            json={
                "expected_revision": 2,
                "new_due_at": utc(env.clock() + timedelta(days=1)),
                "reason": "跨对象权限测试禁止非法操作作业",
            },
        )
    else:
        response = client.patch(
            url + "/ai-policy",
            json={
                "expected_revision": 2,
                "ai_policy": "GUIDED",
                "reason": "跨对象权限测试禁止非法操作作业",
            },
        )
    assert response.status_code == (
        403
        if actor == "admin_a"
        or (actor.startswith("student") and operation not in ["get", "problem"])
        else 404
    )


def test_publication_freezes_content_and_concurrent_revision(env):
    teacher, _, _, _, aid, _ = make_assignment(env)

    def update(title):
        return (
            env.login("teacher_a")
            .patch(f"/api/v1/assignments/{aid}", json={"expected_revision": 1, "title": title})
            .status_code
        )

    with ThreadPoolExecutor(2) as pool:
        assert sorted(pool.map(update, ["练习甲", "练习乙"])) == [200, 409]
    assert (
        teacher.post(
            f"/api/v1/assignments/{aid}/publish",
            json={"expected_revision": 2, "reason": "确认并发修改后的作业内容后发布"},
        ).status_code
        == 200
    )
    assert (
        teacher.patch(
            f"/api/v1/assignments/{aid}", json={"expected_revision": 3, "title": "不能修改"}
        ).status_code
        == 409
    )


def test_deadline_policy_epoch_rejudge_and_audit_atomicity(env):
    teacher, cid, _, _, aid, _ = make_assignment(env, ai_policy="GUIDED")
    publish(teacher, aid)
    env.clock.advance(timedelta(hours=2))
    teacher = env.login("teacher_a")
    payload = {
        "expected_revision": 2,
        "new_due_at": utc(env.clock() + timedelta(hours=1)),
        "reason": "课程统一延期并重新开放正式提交机会",
    }
    with env.engine.begin() as conn:
        conn.execute(
            text("UPDATE assignments SET active_rejudge_batch_id=:batch WHERE assignment_id=:aid"),
            {"aid": aid, "batch": str(uuid4())},
        )
    assert teacher.patch(f"/api/v1/assignments/{aid}/deadline", json=payload).status_code == 409
    with env.engine.begin() as conn:
        conn.execute(
            text("UPDATE assignments SET active_rejudge_batch_id=NULL WHERE assignment_id=:aid"),
            {"aid": aid},
        )
        before = conn.scalar(
            text("SELECT grade_epoch FROM assignments WHERE assignment_id=:aid"), {"aid": aid}
        )
    env.effects.fail = True
    assert teacher.patch(f"/api/v1/assignments/{aid}/deadline", json=payload).status_code == 503
    env.effects.fail = False
    assert teacher.patch(f"/api/v1/assignments/{aid}/deadline", json=payload).status_code == 200
    assert (
        teacher.patch(
            f"/api/v1/assignments/{aid}/ai-policy",
            json={
                "expected_revision": 3,
                "ai_policy": "DISABLED",
                "reason": "开放后收紧作业提示策略确保公平",
            },
        ).status_code
        == 200
    )
    assert (
        teacher.patch(
            f"/api/v1/assignments/{aid}/ai-policy",
            json={
                "expected_revision": 4,
                "ai_policy": "GUIDED",
                "reason": "开放后不允许重新放宽提示策略",
            },
        ).status_code
        == 409
    )
    with env.engine.begin() as conn:
        assert (
            conn.scalar(
                text("SELECT grade_epoch FROM assignments WHERE assignment_id=:aid"), {"aid": aid}
            )
            == before + 1
        )
    assert (
        teacher.put(
            f"/api/v1/courses/{cid}/members/{env.users['student_a']}",
            json={"status": "DISABLED", "expected_revision": 2},
        ).status_code
        == 200
    )
    with env.engine.begin() as conn:
        assert (
            conn.scalar(
                text("SELECT grade_epoch FROM assignments WHERE assignment_id=:aid"), {"aid": aid}
            )
            == before + 2
        )


def test_submission_mode_uses_server_time_and_never_silently_downgrades(env):
    now = env.clock()
    assignment = {"published_at": now, "open_at": now, "due_at": now + timedelta(hours=1)}
    assert submission_mode(assignment, now, "FORMAL") == "FORMAL"
    assert submission_mode(assignment, now, "PRACTICE") == "PRACTICE"
    assert submission_mode(assignment, now + timedelta(hours=1), "PRACTICE") == "PRACTICE"
    with pytest.raises(Fault, match="正式"):
        submission_mode(assignment, now + timedelta(hours=1), "FORMAL")
    with pytest.raises(Fault):
        submission_mode(assignment, now - timedelta(milliseconds=1), "PRACTICE")
    assert assignment_state(assignment, now + timedelta(hours=1), archived=True) == "ARCHIVED"
