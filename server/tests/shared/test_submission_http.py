# ruff: noqa: F811
from uuid import uuid4

from test_http import http_env as environment  # noqa: F401
from test_http import login


def test_http_admission_replay_detail_and_authorized_history(environment):
    _, ids, _, app = environment
    client = login(app, "student")
    body = dict(
        assignment_id=ids["assignment"],
        problem_id=ids["problem"],
        language_key="python3",
        code="print(1)",
    )
    headers = {"Idempotency-Key": str(uuid4()), "X-Submission-Intent": "FORMAL"}
    first = client.post("/api/v1/submissions", json=body, headers=headers)
    assert first.status_code == 202, first.text
    second = client.post("/api/v1/submissions", json=body, headers=headers)
    assert second.status_code == 202 and second.headers["Idempotent-Replay"] == "true"
    sid = first.json()["submission_id"]
    detail = client.get("/api/v1/submissions/" + sid)
    assert detail.status_code == 200, detail.text
    assert detail.json()["code"] == "print(1)" and detail.json()["state"] == "QUEUED"
    assert detail.json()["case_results"] == [] and detail.json()["verdict"] is None
    history = client.get("/api/v1/submissions", params={"assignment_id": ids["assignment"]})
    assert history.status_code == 200, history.text
    assert history.json()["items"][0]["submission_id"] == sid
    rounds = client.get("/api/v1/submissions/" + sid + "/attempts")
    assert rounds.status_code == 200 and rounds.json()["items"][0]["generation"] == 1
    teacher = login(app, "teacher")
    assert teacher.get("/api/v1/submissions/" + sid).status_code == 200
    admin = login(app, "admin")
    assert admin.get("/api/v1/submissions/" + sid).status_code == 403
    for value in (detail.text, history.text, rounds.text):
        assert all(
            secret not in value
            for secret in ["engine_meta", "request_digest", "stdout", "answer_blob"]
        )


def test_http_requires_unique_submission_headers(environment):
    _, ids, _, app = environment
    client = login(app, "student")
    body = dict(
        assignment_id=ids["assignment"],
        problem_id=ids["problem"],
        language_key="python3",
        code="print(1)",
    )
    assert client.post("/api/v1/submissions", json=body).status_code == 422
    response = client.post(
        "/api/v1/submissions",
        json=body,
        headers=[
            ("Idempotency-Key", str(uuid4())),
            ("Idempotency-Key", str(uuid4())),
            ("X-Submission-Intent", "FORMAL"),
        ],
    )
    assert response.status_code == 400


def test_submission_preserves_utf8_bytes_including_nul(environment):
    _, ids, _, app = environment
    client = login(app, "student")
    response = client.post(
        "/api/v1/submissions",
        json=dict(
            assignment_id=ids["assignment"],
            problem_id=ids["problem"],
            language_key="python3",
            code="print(1)\x00",
        ),
        headers={"Idempotency-Key": str(uuid4()), "X-Submission-Intent": "FORMAL"},
    )
    assert response.status_code == 202, response.text
    assert (
        client.get("/api/v1/submissions/" + response.json()["submission_id"]).json()["code"]
        == "print(1)\x00"
    )
