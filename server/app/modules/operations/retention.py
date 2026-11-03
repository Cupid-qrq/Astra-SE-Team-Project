import hashlib
import json
from datetime import timedelta
from uuid import uuid4

from sqlalchemy import select

from app.modules.courses.application import Courses
from app.modules.identity.domain import require, revision, utc
from app.modules.submissions.models import cycles, submissions
from app.shared.effects import TransactionalEffects
from app.shared.repository import SqlRepository


class Retention:
    def __init__(self, repo: SqlRepository, effects: TransactionalEffects):
        self.repo, self.effects = repo, effects
        self.courses = Courses(repo, effects)

    def access(self, actor, cid):
        if actor["role"] == "ADMIN":
            return self.repo.required("courses", cid, lock=True)
        return self.courses.access(actor, cid, teacher=True)

    def clear(self, cid):
        for assignment in self.repo.rows("assignments", course_id=cid):
            require(
                assignment["active_rejudge_batch_id"] is None
                and assignment["fairness_review"] != "PENDING",
                "NOT_READY",
                "请先处理重评与公平事项。",
            )
            held = self.repo.connection.execute(
                select(cycles.c.cycle_id)
                .join(submissions, submissions.c.submission_id == cycles.c.submission_id)
                .where(
                    submissions.c.assignment_id == assignment["assignment_id"],
                    cycles.c.capacity_held,
                )
                .limit(1)
            ).first()
            require(held is None, "NOT_READY", "仍有未终结评测任务。")
        for problem in self.repo.rows("problems", owner_course_id=cid):
            for version in self.repo.rows("problem_versions", problem_id=problem["problem_id"]):
                require(
                    not self.repo.rows(
                        "preflight_runs",
                        version_id=version["version_id"],
                        state=["QUEUED", "RUNNING"],
                    ),
                    "NOT_READY",
                    "仍有预检任务。",
                )
        require(
            not any(
                row["released_at"] is None for row in self.repo.rows("course_holds", course_id=cid)
            ),
            "RETENTION_HOLD",
            "课程存在申诉保留。",
        )
        require(
            not self.repo.rows("ai_hints", course_id=cid, status="PENDING"),
            "NOT_READY",
            "仍有提示任务。",
        )

    def digest(self, cid):
        course = self.repo.required("courses", cid)
        assignments = self.repo.rows("assignments", course_id=cid)
        submission_ids = [
            row["submission_id"]
            for assignment in assignments
            for row in self.repo.rows("submissions", assignment_id=assignment["assignment_id"])
        ]
        value = dict(
            course_id=cid,
            revision=course["revision"],
            assignments=sorted(row["assignment_id"] for row in assignments),
            submissions=sorted(submission_ids),
        )
        return hashlib.sha256(
            json.dumps(value, sort_keys=True, separators=(",", ":")).encode()
        ).hexdigest(), len(submission_ids)

    def archive(self, actor, cid, body):
        self.repo.guard()
        course = self.courses.access(actor, cid, teacher=True, write=True)
        revision(course, body["expected_revision"])
        self.clear(cid)
        self.repo.change(
            "courses",
            cid,
            status="ARCHIVED",
            archived_at=self.repo.now(),
            revision=course["revision"] + 1,
        )
        self.effects.record(
            self.repo, actor["user_id"], "COURSE_ARCHIVED", cid, reason=body["reason"]
        )
        return dict(status="ARCHIVED", revision=course["revision"] + 1)

    def preview(self, actor, body):
        require(actor["role"] == "ADMIN", "FORBIDDEN", "仅管理员创建清理计划。", 403)
        self.repo.guard()
        course = self.access(actor, body["course_id"])
        require(course["status"] == "ARCHIVED", "NOT_READY", "课程尚未归档。")
        digest, _ = self.digest(course["course_id"])
        pid = str(uuid4())
        self.repo.add(
            "retention_plans",
            dict(
                plan_id=pid,
                course_id=course["course_id"],
                object_digest=digest,
                state="PREVIEW",
                revision=1,
                created_at=self.repo.now(),
            ),
        )
        self.effects.record(
            self.repo,
            actor["user_id"],
            "RETENTION_PREVIEW",
            course["course_id"],
            reason=body["reason"],
        )
        return dict(plan_id=pid)

    def read(self, actor, pid):
        plan = self.repo.required("retention_plans", pid)
        course = self.access(actor, plan["course_id"])
        digest, count = self.digest(plan["course_id"])
        return dict(
            plan_id=pid,
            course_id=plan["course_id"],
            object_digest=digest,
            state=plan["state"],
            revision=plan["revision"],
            submission_count=count,
            eligible_at=utc(course["archived_at"] + timedelta(days=180))
            if course["archived_at"]
            else None,
            hold=any(
                row["released_at"] is None
                for row in self.repo.rows("course_holds", course_id=course["course_id"])
            ),
        )

    def confirm(self, actor, pid, body):
        self.repo.guard()
        plan = self.repo.required("retention_plans", pid, lock=True)
        self.courses.access(actor, plan["course_id"], teacher=True)
        revision(plan, body["expected_revision"])
        require(plan["state"] == "PREVIEW", "NOT_READY", "该计划不可重复确认。")
        digest, _ = self.digest(plan["course_id"])
        require(
            body["object_digest"] == digest == plan["object_digest"],
            "REVISION_CONFLICT",
            "清理范围变化，请重建预览。",
        )
        confirmation = str(uuid4())
        self.repo.add(
            "retention_confirmations",
            dict(
                confirmation_id=confirmation,
                plan_id=pid,
                teacher_id=actor["user_id"],
                object_digest=digest,
                reason=body["reason"],
                confirmed_at=self.repo.now(),
            ),
        )
        self.repo.change("retention_plans", pid, state="CONFIRMED", revision=plan["revision"] + 1)
        self.effects.record(
            self.repo,
            actor["user_id"],
            "RETENTION_CONFIRMED",
            plan["course_id"],
            reason=body["reason"],
        )
        return dict(confirmation_id=confirmation, revision=plan["revision"] + 1)

    def execute(self, actor, pid, body):
        require(actor["role"] == "ADMIN", "FORBIDDEN", "仅管理员执行清理。", 403)
        self.repo.guard()
        plan = self.repo.required("retention_plans", pid, lock=True)
        revision(plan, body["expected_revision"])
        course = self.access(actor, plan["course_id"])
        self.clear(course["course_id"])
        require(
            course["status"] == "ARCHIVED"
            and self.repo.now() >= course["archived_at"] + timedelta(days=180),
            "NOT_READY",
            "归档未满180天。",
        )
        confirmation = self.repo.required("retention_confirmations", body["confirmation_id"])
        digest, _ = self.digest(course["course_id"])
        require(
            plan["state"] == "CONFIRMED"
            and confirmation["plan_id"] == pid
            and confirmation["teacher_id"] == course["teacher_id"]
            and confirmation["object_digest"]
            == body["object_digest"]
            == digest
            == plan["object_digest"],
            "REVISION_CONFLICT",
            "确认与清理范围不一致。",
        )
        require(
            self.repo.get("course_cleanup", course["course_id"]) is None,
            "NOT_READY",
            "课程已清理。",
        )
        now = self.repo.now()
        self.repo.add(
            "course_cleanup",
            dict(
                course_id=course["course_id"],
                cleaned_at=now,
                purge_due_at=now + timedelta(days=30),
                purged_at=None,
                confirmed_by=confirmation["teacher_id"],
            ),
        )
        self.repo.change("retention_plans", pid, state="CLEANED", revision=plan["revision"] + 1)
        self.effects.record(
            self.repo,
            actor["user_id"],
            "RETENTION_EXECUTED",
            course["course_id"],
            reason=body["reason"],
        )
        return dict(state="CLEANED", revision=plan["revision"] + 1)

    def hold(self, actor, body):
        self.repo.guard()
        require(body["object_type"] == "course", "VALIDATION_ERROR", "仅支持课程保留。", 422)
        course = self.access(actor, body["object_id"])
        require(
            self.repo.get("course_cleanup", course["course_id"]) is None,
            "NOT_READY",
            "已清理课程不可新增保留。",
        )
        hid = str(uuid4())
        self.repo.add(
            "course_holds",
            dict(
                hold_id=hid,
                course_id=course["course_id"],
                reason=body["reason"],
                created_by=actor["user_id"],
                created_at=self.repo.now(),
                released_at=None,
            ),
        )
        self.effects.record(
            self.repo, actor["user_id"], "HOLD_CREATED", course["course_id"], reason=body["reason"]
        )
        return dict(hold_id=hid, revision=1)

    def close_hold(self, actor, hid, body):
        self.repo.guard()
        hold = self.repo.required("course_holds", hid, lock=True)
        self.access(actor, hold["course_id"])
        require(
            body["expected_revision"] == 1 and hold["released_at"] is None,
            "REVISION_CONFLICT",
            "保留记录已关闭。",
        )
        self.repo.change("course_holds", hid, released_at=self.repo.now())
        self.effects.record(
            self.repo, actor["user_id"], "HOLD_CLOSED", hold["course_id"], reason=body["reason"]
        )
        return dict(revision=2)
