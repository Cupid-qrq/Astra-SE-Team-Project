from copy import deepcopy
from uuid import uuid4

import pytest
from app.modules.problems.application import Problems
from app.modules.problems.domain import content_digest, profile_digest
from astra_a.app import create_app
from astra_a.storage import SqlRepository


def profile():
    return {
        "profile_id": str(uuid4()),
        "languages": [
            {
                "language_key": "cpp17",
                "version": "test-cpp17",
                "image_digest": "sha256:" + "a" * 64,
                "cpu_time_ms": 2000,
                "wall_time_ms": 5000,
            },
            {
                "language_key": "python3",
                "version": "test-python3",
                "image_digest": "sha256:" + "b" * 64,
                "cpu_time_ms": 4000,
                "wall_time_ms": 10000,
            },
        ],
        "memory_bytes": 268435456,
        "output_bytes": 1048576,
        "comparison": "ASCII_TOKENS",
        "directory_bytes": 33554432,
        "run_entities": 1,
        "compile_timeout_ms": 20000,
        "compile_memory_bytes": 536870912,
        "compile_entities": 30,
    }


def make_version(env, *, complete=True):
    teacher = env.login("teacher_a")
    cid = teacher.post("/api/v1/courses", json={"title": "版本测试课程"}).json()["course_id"]
    problem = teacher.post("/api/v1/problems", json={"course_id": cid})
    assert problem.status_code == 201, problem.text
    pid = problem.json()["problem_id"]
    body = {
        "problem_id": pid,
        "title": "两数之和",
        "statement": "计算两数之和。",
        "samples": [{"input": "1 2", "output": "3"}],
        "tags": ["基础"],
        "profile": profile(),
        "source_ref": "自编",
    }
    response = teacher.post("/api/v1/problem-versions", json=body)
    assert response.status_code == 201, response.text
    vid = response.json()["version_id"]
    revision = 1
    if complete:
        response = teacher.put(
            f"/api/v1/problem-versions/{vid}/testcases/1",
            json={"input_text": "5 8\n", "answer_text": "13\n", "expected_revision": revision},
        )
        assert response.status_code == 200, response.text
        revision += 1
        for lang in ["cpp17", "python3"]:
            response = teacher.put(
                f"/api/v1/problem-versions/{vid}/references/{lang}",
                json={"code": "test reference only, never executed", "expected_revision": revision},
            )
            assert response.status_code == 200, response.text
            revision += 1
    return teacher, cid, pid, vid, revision, body


class SyntheticPreflight:
    """Test-only evidence. Never wired by standalone application startup."""

    def __init__(self, evidence):
        self.value = evidence

    def evidence(self, repo, preflight_id):
        return self.value if self.value["preflight_id"] == preflight_id else None


def attach_evidence(env, vid):
    with env.engine.begin() as connection:
        repo = SqlRepository(connection, env.clock)
        snapshot = Problems(repo, env.effects).snapshot(vid)
    evidence = {
        "preflight_id": str(uuid4()),
        "version_id": vid,
        "content_digest": content_digest(snapshot),
        "profile_hash": profile_digest(snapshot["profile"]),
        "state": "PASSED",
        "cases": [
            {
                "language_key": lang,
                "case_kind": kind,
                "case_order": 1,
                "state": "FINISHED",
                "verdict": "AC",
            }
            for lang in ["cpp17", "python3"]
            for kind in ["SAMPLE", "HIDDEN"]
        ],
    }
    env.preflight = SyntheticPreflight(evidence)
    env.app = create_app(
        env.engine,
        env.effects,
        secret=b"test-only-session-key-32-bytes-long",
        origin="https://testserver",
        clock=env.clock,
        preflight=env.preflight,
        assignment_guard=env.coordination,
    )
    return evidence


def test_version_paired_bytes_digest_and_immutable_publication(env):
    _, cid, pid, vid, rev, body = make_version(env)
    evidence = attach_evidence(env, vid)
    teacher = env.login("teacher_a")
    pub = teacher.post(
        f"/api/v1/problem-versions/{vid}/publish",
        json={
            "expected_revision": rev,
            "preflight_id": evidence["preflight_id"],
            "reason": "全部语言样例和隐藏点均验证通过",
        },
    )
    assert pub.status_code == 200, pub.text
    assert pub.json()["checksum"] == evidence["content_digest"]
    assert (
        teacher.patch(
            f"/api/v1/problem-versions/{vid}",
            json={"title": "禁止改写", "expected_revision": rev + 1},
        ).status_code
        == 409
    )
    assert (
        teacher.request(
            "DELETE",
            f"/api/v1/problem-versions/{vid}",
            json={"expected_revision": rev + 1, "reason": "不能删除已经发布的历史题目版本"},
        ).status_code
        == 409
    )
    copy = teacher.post("/api/v1/problem-versions", json={**body, "base_version_id": vid})
    assert copy.status_code == 201, copy.text
    new_id = copy.json()["version_id"]
    assert (
        teacher.get(f"/api/v1/problem-versions/{new_id}/testcases").json()["items"][0]["input_text"]
        == "5 8\n"
    )
    assert len(teacher.get(f"/api/v1/problems/{pid}/versions").json()["items"]) == 2


@pytest.mark.parametrize(
    "mutation",
    ["digest", "profile", "version", "language", "case", "verdict", "state", "duplicate"],
)
def test_reject_stale_or_incomplete_preflight(env, mutation):
    _, _, _, vid, rev, _ = make_version(env)
    evidence = attach_evidence(env, vid)
    if mutation == "digest":
        evidence["content_digest"] = "0" * 64
    elif mutation == "profile":
        evidence["profile_hash"] = "0" * 64
    elif mutation == "version":
        evidence["version_id"] = str(uuid4())
    elif mutation == "language":
        evidence["cases"] = evidence["cases"][:2]
    elif mutation == "case":
        evidence["cases"][0]["case_order"] = 2
    elif mutation == "verdict":
        evidence["cases"][0]["verdict"] = "WA"
    elif mutation == "state":
        evidence["state"] = "RUNNING"
    else:
        evidence["cases"].append(deepcopy(evidence["cases"][0]))
    teacher = env.login("teacher_a")
    response = teacher.post(
        f"/api/v1/problem-versions/{vid}/publish",
        json={
            "expected_revision": rev,
            "preflight_id": evidence["preflight_id"],
            "reason": "验证不匹配预检不能作为发布证据",
        },
    )
    assert response.status_code == 409, response.text
    assert teacher.get(f"/api/v1/problem-versions/{vid}").json()["published_at"] is None


def test_missing_preflight_fails_closed_and_edit_invalidates_evidence(env):
    teacher, _, _, vid, rev, _ = make_version(env)
    body = {
        "expected_revision": rev,
        "preflight_id": str(uuid4()),
        "reason": "预检服务尚未接入时应明确阻止发布",
    }
    assert teacher.post(f"/api/v1/problem-versions/{vid}/publish", json=body).status_code == 503
    evidence = attach_evidence(env, vid)
    teacher = env.login("teacher_a")
    assert (
        teacher.patch(
            f"/api/v1/problem-versions/{vid}",
            json={"title": "改变题目摘要", "expected_revision": rev},
        ).status_code
        == 200
    )
    assert (
        teacher.post(
            f"/api/v1/problem-versions/{vid}/publish",
            json={**body, "expected_revision": rev + 1, "preflight_id": evidence["preflight_id"]},
        ).status_code
        == 409
    )


@pytest.mark.parametrize("actor", ["student_a", "teacher_b", "admin_a"])
@pytest.mark.parametrize("suffix", ["", "/testcases", "/references"])
def test_hidden_material_never_crosses_authorization(env, actor, suffix):
    _, _, _, vid, _, _ = make_version(env)
    response = env.login(actor).get(f"/api/v1/problem-versions/{vid}" + suffix)
    assert response.status_code == (404 if actor == "teacher_b" else 403)
    assert "test reference" not in response.text and "5 8" not in response.text


def test_utf8_limits_missing_pair_zip_blank_reference_and_gap(env):
    teacher, _, _, vid, rev, _ = make_version(env, complete=False)
    base = f"/api/v1/problem-versions/{vid}"
    assert (
        teacher.patch(base, json={"statement": "汉" * 12000, "expected_revision": rev}).status_code
        == 422
    )
    assert (
        teacher.put(
            base + "/testcases/1", json={"input_text": "only input", "expected_revision": rev}
        ).status_code
        == 422
    )
    assert (
        teacher.put(
            base + "/testcases/1",
            json={"input_text": "汉" * 22000, "answer_text": "", "expected_revision": rev},
        ).status_code
        == 422
    )
    assert (
        teacher.put(
            base + "/testcases/1",
            json={"input_text": "PK\u0003\u0004zip", "answer_text": "", "expected_revision": rev},
        ).status_code
        == 422
    )
    assert (
        teacher.put(
            base + "/references/python3", json={"code": " \n ", "expected_revision": rev}
        ).status_code
        == 422
    )
    assert (
        teacher.put(
            base + "/testcases/2",
            json={"input_text": "", "answer_text": "", "expected_revision": rev},
        ).status_code
        == 200
    )
    assert (
        teacher.post(
            base + "/publish",
            json={
                "expected_revision": rev + 1,
                "preflight_id": str(uuid4()),
                "reason": "配对测试顺序不连续时不得进行发布",
            },
        ).status_code
        == 409
    )
