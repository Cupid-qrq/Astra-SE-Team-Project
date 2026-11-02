from test_problems import attach_evidence, make_version


def test_practice_policy_requires_frozen_version_and_revision(env):
    teacher, cid, pid, vid, rev, _ = make_version(env)
    path = f"/api/v1/problems/{pid}/practice-policy"
    family = teacher.get(f"/api/v1/courses/{cid}/problems").json()["items"][0][
        "canonical_problem_id"
    ]
    body = dict(
        practice_released=True,
        canonical_problem_id=family,
        practice_version_id=vid,
        expected_revision=1,
        reason="教师开放本题作为课后练习",
    )
    assert teacher.patch(path, json=body).status_code == 409
    evidence = attach_evidence(env, vid)
    teacher = env.login("teacher_a")
    assert (
        teacher.post(
            f"/api/v1/problem-versions/{vid}/publish",
            json=dict(
                expected_revision=rev,
                preflight_id=evidence["preflight_id"],
                reason="全部语言样例和隐藏点均验证通过",
            ),
        ).status_code
        == 200
    )
    assert teacher.patch(path, json=body).json() == {"revision": 2}
    assert teacher.patch(path, json=body).status_code == 409
    body.update(practice_released=False, expected_revision=2)
    del body["practice_version_id"]
    assert teacher.patch(path, json=body).json() == {"revision": 3}
    item = teacher.get(f"/api/v1/courses/{cid}/problems").json()["items"][0]
    assert item["practice_version_id"] is None and not item["practice_released"]


def test_family_cannot_be_moved_out_of_or_into_an_active_assignment(env):
    from datetime import timedelta

    from test_assignments import make_assignment, publish

    teacher, cid, pid, _, aid, _ = make_assignment(env)
    other = teacher.post("/api/v1/problems", json={"course_id": cid}).json()
    family = next(
        row["canonical_problem_id"]
        for row in teacher.get(f"/api/v1/courses/{cid}/problems").json()["items"]
        if row["problem_id"] == pid
    )
    publish(teacher, aid)
    body = dict(practice_released=False, expected_revision=1, reason="教师修订并核对题目家族关联")
    for target, new_family in [(pid, other["canonical_problem_id"]), (other["problem_id"], family)]:
        url = f"/api/v1/problems/{target}/practice-policy"
        response = teacher.patch(url, json={**body, "canonical_problem_id": new_family})
        assert response.status_code == 409, response.text
    env.clock.advance(timedelta(hours=2))
    teacher = env.login("teacher_a")
    url = f"/api/v1/problems/{pid}/practice-policy"
    assert (
        teacher.patch(
            url, json={**body, "canonical_problem_id": other["canonical_problem_id"]}
        ).status_code
        == 200
    )


def test_public_practice_rechecks_same_family_membership_and_release(env):
    from datetime import timedelta

    from test_assignments import make_assignment, publish

    teacher, cid, pid, vid, aid, _ = make_assignment(env)
    family = teacher.get(f"/api/v1/courses/{cid}/problems").json()["items"][0][
        "canonical_problem_id"
    ]
    path = f"/api/v1/practice-problems/{pid}"
    student = env.login("student_a")
    assert student.get(path).status_code == 404
    policy = dict(
        expected_revision=1,
        practice_released=True,
        practice_version_id=vid,
        canonical_problem_id=family,
        reason="作为公开练习提供给当前课程学生",
    )
    assert teacher.patch(f"/api/v1/problems/{pid}/practice-policy", json=policy).status_code == 200
    assert student.get(path).json()["version_id"] == vid
    publish(teacher, aid)
    assert student.get(path).status_code == 404
    env.clock.advance(timedelta(hours=2))
    assert env.login("student_a").get(path).json()["samples"] == [{"input": "1 2", "output": "3"}]
    assert env.login("teacher_a").get(path).status_code == 403
