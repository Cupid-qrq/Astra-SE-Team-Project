import hashlib
import json
from datetime import datetime, timedelta
from uuid import uuid4

from sqlalchemy import select

from app.modules.identity.domain import require, utc
from app.shared.effects import TransactionalEffects
from app.shared.repository import SqlRepository

from .models import runtime


def current_config(repo: SqlRepository) -> dict:
    row = (
        repo.connection.execute(select(runtime).order_by(runtime.c.revision.desc()).limit(1))
        .mappings()
        .first()
    )
    return (
        dict(payload=dict(submission_enabled=True, judge_enabled=True), revision=0)
        if row is None
        else dict(row)
    )


class Controls:
    def __init__(self, repo: SqlRepository, effects: TransactionalEffects):
        self.repo, self.effects = repo, effects

    def config(self, actor):
        require(actor["role"] == "ADMIN", "FORBIDDEN", "仅管理员可读取配置。", 403)
        value = current_config(self.repo)
        return dict(revision=value["revision"], **value["payload"])

    def update(self, actor, body):
        require(actor["role"] == "ADMIN", "FORBIDDEN", "仅管理员可变更配置。", 403)
        self.repo.guard()
        old = current_config(self.repo)
        require(old["revision"] == body["expected_revision"], "REVISION_CONFLICT", "配置已变化。")
        payload = {key: body[key] for key in ("submission_enabled", "judge_enabled")}
        checksum = hashlib.sha256(json.dumps(payload, sort_keys=True).encode()).hexdigest()
        vid = str(uuid4())
        self.repo.add(
            "runtime_config_versions",
            dict(
                config_version=vid,
                payload=payload,
                checksum=checksum,
                created_by=actor["user_id"],
                reason=body["reason"],
                created_at=self.repo.now(),
                revision=old["revision"] + 1,
            ),
        )
        self.effects.record(
            self.repo, actor["user_id"], "CONFIG_UPDATED", vid, reason=body["reason"]
        )
        return dict(revision=old["revision"] + 1, **payload)

    def grant(self, actor, body):
        require(actor["role"] == "ADMIN", "FORBIDDEN", "仅管理员可创建应急授权。", 403)
        self.repo.guard()
        incident = self.repo.required("fairness_incidents", body["incident_id"])
        course_id = body["scope"]["course_id"]
        aids = self.repo.rows("incident_assignments", incident_id=incident["incident_id"])
        require(
            any(
                self.repo.required("assignments", row["assignment_id"])["course_id"] == course_id
                for row in aids
            ),
            "FORBIDDEN",
            "授权范围必须属于事件影响课程。",
            403,
        )
        expires = datetime.fromisoformat(body["expires_at"].replace("Z", "+00:00"))
        now = self.repo.now()
        require(
            now < expires <= now + timedelta(hours=1),
            "VALIDATION_ERROR",
            "应急授权最多一小时。",
            422,
        )
        gid = str(uuid4())
        self.repo.add(
            "emergency_grants",
            dict(
                grant_id=gid,
                admin_id=actor["user_id"],
                incident_id=body["incident_id"],
                scope={"course_id": course_id},
                expires_at=expires,
                revoked_at=None,
                reason=body["reason"],
            ),
        )
        self.effects.record(
            self.repo, actor["user_id"], "EMERGENCY_GRANTED", gid, reason=body["reason"]
        )
        return dict(grant_id=gid, expires_at=utc(expires))

    def revoke(self, actor, gid, body):
        require(actor["role"] == "ADMIN", "FORBIDDEN", "仅管理员可撤销应急授权。", 403)
        self.repo.guard()
        grant = self.repo.required("emergency_grants", gid, lock=True)
        require(grant["admin_id"] == actor["user_id"], "FORBIDDEN", "只能撤销本人授权。", 403)
        if grant["revoked_at"] is None:
            self.repo.change("emergency_grants", gid, revoked_at=self.repo.now())
        self.effects.record(
            self.repo, actor["user_id"], "EMERGENCY_REVOKED", gid, reason=body["reason"]
        )
        return None

    def read_submission(self, actor, gid, sid):
        require(actor["role"] == "ADMIN", "FORBIDDEN", "仅管理员可使用应急授权。", 403)
        self.repo.guard()
        grant = self.repo.required("emergency_grants", gid)
        require(
            grant["admin_id"] == actor["user_id"]
            and grant["revoked_at"] is None
            and grant["expires_at"] > self.repo.now(),
            "FORBIDDEN",
            "应急授权已失效。",
            403,
        )
        submission = self.repo.required("submissions", sid)
        assignment = self.repo.required("assignments", submission["assignment_id"])
        require(
            assignment["course_id"] == grant["scope"]["course_id"]
            and not self.repo.course_is_cleaned(assignment["course_id"]),
            "NOT_FOUND",
            "提交不在授权范围内。",
            404,
        )
        self.effects.record(
            self.repo,
            actor["user_id"],
            "EMERGENCY_READ",
            sid,
            reason=grant["reason"],
            summary={"grant_id": gid},
        )
        return dict(
            submission_id=sid,
            code=submission["code"].decode("utf-8"),
            language_key=submission["language_key"],
            accepted_at=utc(submission["accepted_at"]),
        )
