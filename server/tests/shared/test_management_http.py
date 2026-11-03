from datetime import UTC, datetime, timedelta
from uuid import uuid4

from test_http import http_env as http_env
from test_http import login


def test_management_http_emergency_scope_runtime_and_fairness(http_env):
    _, ids, _, app = http_env
    admin = login(app, "admin")
    teacher = login(app, "teacher")
    student = login(app, "student")
    assert admin.get("/api/v1/admin/health").status_code == 200
    assert student.get("/api/v1/admin/health").status_code == 403
    receipt = student.post(
        "/api/v1/submissions",
        json=dict(
            assignment_id=ids["assignment"],
            problem_id=ids["problem"],
            language_key="python3",
            code="print(1)",
        ),
        headers={"Idempotency-Key": str(uuid4()), "X-Submission-Intent": "FORMAL"},
    )
    assert receipt.status_code == 202, receipt.text
    incident = admin.post(
        "/api/v1/admin/incidents",
        json=dict(
            started_at=(datetime.now(UTC) - timedelta(seconds=2)).isoformat(),
            assignment_ids=[ids["assignment"]],
            reason_code="JUDGE_UNAVAILABLE",
            reason="故障演练",
            evidence_refs=[],
            evidence_incomplete=True,
        ),
    )
    assert incident.status_code == 201, incident.text
    iid = incident.json()["incident_id"]
    grant = admin.post(
        "/api/v1/admin/emergency-access",
        json=dict(
            incident_id=iid,
            scope={"course_id": ids["course"]},
            expires_at=(datetime.now(UTC) + timedelta(minutes=10)).isoformat(),
            reason="授权排查",
        ),
    )
    assert grant.status_code == 201, grant.text
    gid = grant.json()["grant_id"]
    sid = receipt.json()["submission_id"]
    assert admin.get("/api/v1/submissions/" + sid).status_code == 403
    response = admin.get(
        "/api/v1/admin/emergency-access/" + gid + "/submission", params={"submission_id": sid}
    )
    assert response.status_code == 200 and response.json()["code"] == "print(1)"
    assert (
        admin.post(
            "/api/v1/admin/emergency-access/" + gid + "/revoke", json={"reason": "排查结束"}
        ).status_code
        == 204
    )
    assert (
        admin.get(
            "/api/v1/admin/emergency-access/" + gid + "/submission", params={"submission_id": sid}
        ).status_code
        == 403
    )
    recovered = admin.patch(
        "/api/v1/admin/incidents/" + iid + "/recovery",
        json=dict(
            recovered_at=admin.get("/api/v1/admin/health").json()["server_time"], expected_revision=1, reason="恢复完成"
        ),
    )
    assert recovered.status_code == 200, recovered.text
    decided = teacher.post(
        "/api/v1/assignments/" + ids["assignment"] + "/fairness-decisions",
        json=dict(incident_id=iid, decision="EXTEND", expected_revision=2, reason="统一补偿"),
    )
    assert decided.status_code == 200, decided.text
    assert student.get("/api/v1/notifications").status_code == 200
    config = admin.get("/api/v1/admin/runtime-config").json()
    paused = admin.patch(
        "/api/v1/admin/runtime-config",
        json=dict(
            expected_revision=config["revision"],
            submission_enabled=False,
            judge_enabled=True,
            reason="暂停演练",
        ),
    )
    assert paused.status_code == 200, paused.text
    rejected = student.post(
        "/api/v1/submissions",
        json=dict(
            assignment_id=ids["assignment"],
            problem_id=ids["problem"],
            language_key="python3",
            code="print(2)",
        ),
        headers={"Idempotency-Key": str(uuid4()), "X-Submission-Intent": "FORMAL"},
    )
    assert rejected.status_code == 503 and rejected.json()["code"] == "JUDGE_UNAVAILABLE"
