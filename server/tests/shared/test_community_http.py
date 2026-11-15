from uuid import uuid4

from fastapi.testclient import TestClient
from test_http import http_env as http_env
from test_http import login


def test_community_contract_csrf_projection_and_course_scope(http_env):
    _, ids, _, app = http_env
    anonymous = TestClient(app, base_url="https://testserver")
    board = f"/api/v1/courses/{ids['course']}/leaderboard?kind=progress"
    assert anonymous.get(board).status_code == 401
    student = login(app, "student")
    result = student.get(board)
    assert result.status_code == 200, result.text
    value = result.json()
    assert value["included_assignments"] == 1
    assert value["items"][0]["is_me"] is True
    assert value["items"][0]["display_name"].startswith("匿名同学")
    assert "student_id" not in value["items"][0]
    preference = f"/api/v1/courses/{ids['course']}/leaderboard-preference"
    assert (
        student.patch(
            preference, json={"show_name": True}, headers={"X-CSRF-Token": "wrong"}
        ).status_code
        == 403
    )
    assert student.patch(preference, json={"show_name": True}).json() == {"show_name": True}
    assert student.get(board).json()["items"][0]["display_name"] == "student"
    assert student.get(f"/api/v1/courses/{uuid4()}/leaderboard?kind=progress").status_code == 404
    assert login(app, "admin").get(board).status_code == 403


def test_discussion_roundtrip_lock_hidden_and_unknown_field(http_env):
    _, ids, _, app = http_env
    student, teacher = login(app, "student"), login(app, "teacher")
    path = f"/api/v1/courses/{ids['course']}/problems/{ids['problem']}/discussions"
    payload = {
        "version_id": ids["version"],
        "title": "边界输入应该如何考虑？",
        "body": "我已经检查了零值输入，还有哪些边界值得检查？",
    }
    assert student.post(path, json=dict(payload, author_id=ids["teacher"])).status_code == 422
    response = student.post(path, json=payload)
    assert response.status_code == 201, response.text
    thread = response.json()
    assert thread["author_name"] == "student" and thread["is_mine"]
    tid = thread["thread_id"]
    assert student.post(path, json=payload).status_code == 429
    listed = student.get(path, params={"version_id": ids["version"]})
    assert listed.status_code == 200, listed.text
    assert len(listed.json()["items"]) == 1
    response = teacher.post(
        f"/api/v1/discussions/{tid}/replies", json={"body": "可以分别检查相等、负数和边界大小。"}
    )
    assert response.status_code == 201, response.text
    current = teacher.get(f"/api/v1/discussions/{tid}").json()["thread"]
    locked = teacher.patch(
        f"/api/v1/discussions/{tid}",
        json={
            "expected_revision": current["revision"],
            "locked": True,
            "reason": "课堂问题已集中解答，暂时关闭新增回复",
        },
    )
    assert locked.status_code == 200, locked.text
    assert student.post(
        f"/api/v1/discussions/{tid}/replies", json={"body": "补充一个问题"}
    ).status_code in (409, 429)
    hidden = teacher.patch(
        f"/api/v1/discussions/{tid}",
        json={
            "expected_revision": locked.json()["revision"],
            "hidden": True,
            "reason": "讨论内容需要进一步核对，暂时隐藏处理",
        },
    )
    assert hidden.status_code == 200, hidden.text
    visible = student.get(f"/api/v1/discussions/{tid}")
    assert visible.status_code == 200, visible.text
    assert visible.json()["thread"]["body"] == ""
    assert visible.json()["thread"]["title"] == "已隐藏的讨论"
    assert login(app, "admin").get(f"/api/v1/discussions/{tid}").status_code == 403


def test_pinned_thread_is_first_and_signed_cursor_preserves_order(http_env):
    _, ids, _, app = http_env
    student, teacher = login(app, "student"), login(app, "teacher")
    path = f"/api/v1/courses/{ids['course']}/problems/{ids['problem']}/discussions"
    first = student.post(
        path,
        json={"version_id": ids["version"], "title": "边界情况", "body": "相等的输入该如何考虑？"},
    ).json()
    second = teacher.post(
        path,
        json={
            "version_id": ids["version"],
            "title": "输入格式",
            "body": "先核对输入数量和空白分隔。",
        },
    ).json()
    pinned = teacher.patch(
        "/api/v1/discussions/" + first["thread_id"],
        json={
            "expected_revision": first["revision"],
            "pinned": True,
            "reason": "将常见边界问题置顶，方便本课程学生查阅",
        },
    )
    assert pinned.status_code == 200, pinned.text
    page = student.get(path, params={"version_id": ids["version"], "limit": 1}).json()
    assert page["items"][0]["thread_id"] == first["thread_id"]
    assert page["next_cursor"]
    following = student.get(
        path, params={"version_id": ids["version"], "limit": 1, "cursor": page["next_cursor"]}
    )
    assert following.status_code == 200, following.text
    assert following.json()["items"][0]["thread_id"] == second["thread_id"]
