import shutil
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

from sqlalchemy import select

from app.modules.identity.domain import require, revision, utc
from app.modules.submissions.models import attempts, bases, cycles, jobs, submissions
from app.modules.submissions.processing import start_cycle
from app.shared.effects import TransactionalEffects
from app.shared.repository import SqlRepository

from .models import notifications


class Operations:
    def __init__(self, repo: SqlRepository, effects: TransactionalEffects):
        self.repo, self.effects = repo, effects

    @staticmethod
    def admin(actor):
        require(actor["role"] == "ADMIN", "FORBIDDEN", "仅管理员可访问。", 403)

    def health(self, actor):
        self.admin(actor)
        slot = self.repo.required("execution_slots", 1)
        return dict(
            database="READY",
            server_time=utc(self.repo.now()),
            pending=self.repo.required("capacity_control", 1)["pending_count"],
            slot_state=slot["state"],
            disk_free_bytes=shutil.disk_usage(Path.cwd()).free,
            clock_skew_ms=round(abs((self.repo.now() - datetime.now(UTC)).total_seconds()) * 1000),
            budget=[
                dict(
                    scope=row["scope_key"],
                    limit=str(row["limit_amount"]),
                    settled=str(row["settled_amount"]),
                    reserved=str(row["reserved_amount"]),
                    uncertain=str(row["uncertain_amount"]),
                )
                for row in self.repo.rows("budget_accounts")
            ],
        )

    def queue(self, actor, pager):
        self.admin(actor)
        statement = select(
            jobs.c.job_id,
            jobs.c.kind,
            jobs.c.state,
            submissions.c.submission_id,
            submissions.c.revision,
            attempts.c.verdict,
            bases.c.batch_id,
        ).select_from(
            jobs.join(attempts, jobs.c.attempt_id == attempts.c.attempt_id)
            .join(submissions, submissions.c.submission_id == attempts.c.submission_id)
            .join(bases, bases.c.basis_id == attempts.c.basis_id)
        )
        if pager.after:
            statement = statement.where(jobs.c.job_id > pager.after)
        rows = self.repo.connection.execute(
            statement.order_by(jobs.c.job_id).limit(pager.limit + 1)
        ).mappings()
        return pager.finish([dict(row) for row in rows], "job_id")

    def retry(self, actor, sid, body):
        self.admin(actor)
        self.repo.guard()
        submission = self.repo.required("submissions", sid, lock=True)
        require(submission is not None, "NOT_FOUND", "提交不存在。", 404)
        revision(submission, body["expected_revision"])
        assignment = self.repo.required("assignments", submission["assignment_id"])
        require(
            self.repo.required("courses", assignment["course_id"])["status"] == "ACTIVE",
            "COURSE_ARCHIVED",
            "归档课程只读。",
        )
        basis = self.repo.required("result_bases", submission["active_basis_id"])
        attempt = self.repo.required("attempts", basis["current_attempt_id"])
        require(
            attempt["state"] == "FINISHED" and attempt["verdict"] == "SE",
            "NOT_READY",
            "只有当前平台故障结果可以人工重试。",
        )
        held = self.repo.connection.execute(
            select(cycles.c.cycle_id)
            .where(cycles.c.submission_id == sid, cycles.c.capacity_held)
            .limit(1)
        ).first()
        require(held is None, "NOT_READY", "该提交已有处理中周期。")
        result = start_cycle(
            self.repo, submission, basis["basis_id"], "NORMAL", "MANUAL", body["reason"]
        )
        self.repo.change("submissions", sid, revision=submission["revision"] + 1)
        if submission["mode"] == "FORMAL":
            self.repo.change(
                "assignments",
                assignment["assignment_id"],
                grade_epoch=assignment["grade_epoch"] + 1,
            )
        self.effects.record(
            self.repo, actor["user_id"], "SUBMISSION_RETRY", sid, reason=body["reason"]
        )
        return result

    def audit(self, actor, pager):
        self.admin(actor)
        rows = self.repo.page("audit_events", limit=pager.limit + 1, after=pager.after)
        return pager.finish(
            [{**row, "timestamp": utc(row["timestamp"])} for row in rows], "event_id"
        )

    def list_notifications(self, actor, pager):
        deliver(self.repo)
        statement = select(notifications).where(notifications.c.user_id == actor["user_id"])
        if pager.after:
            statement = statement.where(notifications.c.notification_id > pager.after)
        rows = self.repo.connection.execute(
            statement.order_by(notifications.c.notification_id).limit(pager.limit + 1)
        ).mappings()
        return pager.finish(
            [
                dict(
                    notification_id=row["notification_id"],
                    title=row["title"],
                    body=row["body"],
                    created_at=utc(row["created_at"]),
                    read_at=utc(row["read_at"]) if row["read_at"] else None,
                )
                for row in rows
            ],
            "notification_id",
        )

    def mark_read(self, actor, nid):
        self.repo.guard()
        row = self.repo.required("notifications", nid, lock=True)
        require(
            row is not None and row["user_id"] == actor["user_id"], "NOT_FOUND", "通知不存在。", 404
        )
        if row["read_at"] is None:
            self.repo.change("notifications", nid, read_at=self.repo.now())
        return dict(read=True)


def deliver(repo):
    repo.guard()
    events = repo.page("outbox_events", limit=100, state="READY")
    titles = {
        "GRADE_PUBLISHED": "成绩已发布",
        "ASSIGNMENT_PUBLISHED": "作业已发布",
        "DEADLINE_EXTENDED": "作业已统一延期",
        "REJUDGE_ACTIVATED": "重评成绩已更新",
        "FAIRNESS_DECIDED": "公平事项已裁决",
        "INCIDENT_DETECTED": "平台事件等待裁决",
        "INCIDENT_CREATED": "平台事件已登记",
        "SUBMISSION_FINISHED": "评测结果已更新",
    }
    for event in events:
        title = titles.get(event["event_type"])
        recipients = set()
        aid = None
        if title:
            object_id = event["payload"]["object_id"]
            if event["event_type"].startswith("SUBMISSION"):
                submission = repo.get("submissions", object_id)
                if submission:
                    recipients.add(submission["user_id"])
                    aid = submission["assignment_id"]
            else:
                if event["event_type"].startswith("INCIDENT"):
                    for link in repo.rows("incident_assignments", incident_id=object_id):
                        affected = repo.get("assignments", link["assignment_id"])
                        if affected:
                            recipients.add(repo.get("courses", affected["course_id"])["teacher_id"])
                    aid = None
                elif event["event_type"].startswith("REJUDGE"):
                    batch = repo.get("rejudge_batches", object_id)
                    aid = batch["assignment_id"] if batch else None
                else:
                    aid = object_id
                assignment = repo.get("assignments", aid) if aid else None
                if assignment:
                    course = repo.get("courses", assignment["course_id"])
                    recipients.add(course["teacher_id"])
                    recipients.update(
                        row["user_id"]
                        for row in repo.rows(
                            "course_members", course_id=course["course_id"], status="ACTIVE"
                        )
                    )
            for uid in sorted(recipients):
                key = event["event_key"] + ":" + uid
                if not repo.rows("notifications", event_key=key):
                    repo.add(
                        "notifications",
                        dict(
                            notification_id=str(uuid4()),
                            user_id=uid,
                            event_key=key,
                            title=title,
                            body=("平台事件 " + object_id + " 等待处理，请进入重评与公平处理。")
                            if event["event_type"].startswith("INCIDENT")
                            else "作业 " + str(aid) + " 有更新，请从课程进入查看。",
                            created_at=repo.now(),
                            read_at=None,
                        ),
                    )
        repo.change("outbox_events", event["event_id"], state="SENT", tries=event["tries"] + 1)
