"""Durable admission shares A's authorization and the caller's transaction."""

import hashlib
import json
from datetime import timedelta
from uuid import UUID, uuid4

from sqlalchemy import select

from app.modules.assignments.application import Assignments
from app.modules.identity.domain import Fault, require, utc
from app.modules.identity.ports import Record
from app.shared.effects import TransactionalEffects
from app.shared.repository import SqlRepository

from .models import submissions


class Submissions:
    def __init__(self, repo: SqlRepository, effects: TransactionalEffects):
        self.repo, self.effects = repo, effects
        self.assignments = Assignments(repo, effects)

    def accept(self, actor: Record, body: Record, key: str, intent: str, request_id: str):
        self.repo.guard()
        user = self.repo.get("users", actor.get("user_id"))
        require(
            user is not None and user["status"] == "ACTIVE" and user["role"] == "STUDENT",
            "FORBIDDEN",
            "当前账号不能提交。",
            403,
        )
        assert user is not None
        body, key, code, digest = self._validate(body, key, intent)
        existing = (
            self.repo.connection.execute(
                select(submissions).where(
                    submissions.c.user_id == user["user_id"], submissions.c.idempotency_key == key
                )
            )
            .mappings()
            .first()
        )
        if existing is not None:
            self.assignments.access(user, existing["assignment_id"])
            require(
                existing["request_digest"] == digest,
                "IDEMPOTENCY_CONFLICT",
                "该请求编号已用于不同提交。",
            )
            return dict(existing["original_receipt"], request_id=request_id), True
        admission = self.assignments.admission(
            user, body["assignment_id"], body["problem_id"], body["language_key"], intent
        )
        now = admission["accepted_at"]
        capacity = self.repo.get("capacity_control", 1, lock=True)
        assert capacity is not None
        require(
            capacity["pending_count"] < 100, "GLOBAL_CAPACITY", "平台队列已满，请稍后重试。", 503
        )
        counter = self.repo.get("admission_users", user["user_id"], lock=True)
        if counter is None:
            counter = self.repo.add(
                "admission_users",
                dict(user_id=user["user_id"], last_accepted_at=None, pending_count=0),
            )
        require(
            counter["pending_count"] < 3, "STUDENT_PENDING_LIMIT", "已有三个提交正在处理。", 429
        )
        require(
            counter["last_accepted_at"] is None
            or now >= counter["last_accepted_at"] + timedelta(seconds=5),
            "STUDENT_INTERVAL",
            "提交间隔至少五秒。",
            429,
        )
        sid, basis, cycle, attempt, job = (str(uuid4()) for _ in range(5))
        receipt = dict(
            submission_id=sid, accepted_at=utc(now), mode=admission["mode"], state="QUEUED"
        )
        self.repo.add(
            "submissions",
            dict(
                submission_id=sid,
                user_id=user["user_id"],
                assignment_id=body["assignment_id"],
                problem_id=body["problem_id"],
                version_id=admission["version_id"],
                language_key=body["language_key"],
                code=code,
                code_sha256=hashlib.sha256(code).hexdigest(),
                intent=intent,
                mode=admission["mode"],
                accepted_at=now,
                idempotency_key=key,
                request_digest=digest,
                original_receipt=receipt,
                active_basis_id=basis,
                revision=1,
            ),
        )
        self.repo.add(
            "result_bases",
            dict(
                basis_id=basis,
                submission_id=sid,
                batch_id=None,
                target_version_id=admission["version_id"],
                current_attempt_id=attempt,
                current_cycle_id=cycle,
                processing_state="QUEUED",
            ),
        )
        self.repo.add(
            "processing_cycles",
            dict(
                cycle_id=cycle,
                basis_id=basis,
                submission_id=sid,
                started_at=now,
                finished_at=None,
                auto_retry_count=0,
                capacity_held=True,
                trigger="INITIAL",
                reason=None,
            ),
        )
        self.repo.add(
            "attempts",
            dict(
                attempt_id=attempt,
                submission_id=sid,
                basis_id=basis,
                cycle_id=cycle,
                generation=1,
                state="QUEUED",
                verdict=None,
                reason_code=None,
                started_at=None,
                finished_at=None,
                time_ms=None,
                memory_bytes=None,
                engine_meta={},
                feedback_version_id=None,
            ),
        )
        self.repo.add(
            "queue_jobs",
            dict(
                job_id=job,
                attempt_id=attempt,
                kind="NORMAL",
                state="READY",
                ready_at=now,
                created_at=now,
                lease_until=None,
                deadline=None,
                lease_epoch=0,
                worker_id=None,
                current_execution=None,
            ),
        )
        self.repo.change(
            "admission_users",
            user["user_id"],
            last_accepted_at=now,
            pending_count=counter["pending_count"] + 1,
        )
        self.repo.change("capacity_control", 1, pending_count=capacity["pending_count"] + 1)
        self.effects.record(self.repo, user["user_id"], "SUBMISSION_ACCEPTED", sid)
        return dict(receipt, request_id=request_id), False

    @staticmethod
    def _validate(body, key, intent):
        require(
            set(body) == {"assignment_id", "problem_id", "language_key", "code"},
            "VALIDATION_ERROR",
            "提交字段不正确。",
            422,
        )
        require(intent in ("FORMAL", "PRACTICE"), "VALIDATION_ERROR", "请选择提交意图。", 422)
        require(isinstance(body["code"], str), "VALIDATION_ERROR", "代码必须是文本。", 422)
        try:
            key = str(UUID(key))
            body = dict(
                body,
                assignment_id=str(UUID(body["assignment_id"])),
                problem_id=str(UUID(body["problem_id"])),
            )
            code = body["code"].encode("utf-8")
        except (ValueError, TypeError, AttributeError, UnicodeEncodeError):
            raise Fault(422, "VALIDATION_ERROR", "提交编号或文本无效。") from None
        require(bool(code), "VALIDATION_ERROR", "代码不能为空。", 422)
        require(len(code) <= 65536, "CODE_TOO_LARGE", "代码不能超过64KiB。", 413)
        digest = hashlib.sha256(
            json.dumps(
                dict(body, intent=intent), sort_keys=True, ensure_ascii=False, separators=(",", ":")
            ).encode()
        ).hexdigest()
        return body, key, code, digest
