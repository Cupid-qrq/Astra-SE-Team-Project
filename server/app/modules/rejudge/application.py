"""Freeze all formal submissions, execute separate bases, then activate atomically."""

import hashlib
from uuid import uuid4

from sqlalchemy import select

from app.modules.assignments.application import Assignments
from app.modules.grades.application import Grades
from app.modules.identity.domain import require, revision
from app.modules.submissions.models import bases, submissions
from app.modules.submissions.processing import start_cycle
from app.shared.effects import TransactionalEffects
from app.shared.repository import SqlRepository

from .models import batches, members


def checksum(ids):
    return hashlib.sha256("\n".join(sorted(ids)).encode()).hexdigest()


class Rejudges:
    def __init__(self, repo: SqlRepository, effects: TransactionalEffects):
        self.repo, self.effects = repo, effects
        self.assignments = Assignments(repo, effects)

    def _range(self, assignment_id, problem_id):
        return (
            self.repo.connection.execute(
                select(submissions)
                .where(
                    submissions.c.assignment_id == assignment_id,
                    submissions.c.problem_id == problem_id,
                    submissions.c.mode == "FORMAL",
                )
                .order_by(submissions.c.submission_id)
            )
            .mappings()
            .all()
        )

    def preview(self, actor, assignment_id, body):
        self.repo.guard()
        assignment, _ = self.assignments.access(actor, assignment_id, teacher=True, write=True)
        revision(assignment, body["expected_revision"])
        require(self.repo.now() >= assignment["due_at"], "NOT_READY", "作业截止后才可重评。")
        require(
            assignment["fairness_review"] != "PENDING", "UNRESOLVED_FAIRNESS", "请先裁决公平事项。"
        )
        require(assignment["active_rejudge_batch_id"] is None, "ACTIVE_REJUDGE", "已有未激活重评。")
        target = self.repo.required("problem_versions", body["new_version_id"])
        require(
            target is not None
            and target["published_at"] is not None
            and target["published_preflight_id"] is not None,
            "NOT_FOUND",
            "目标版本尚未发布。",
            404,
        )
        assert target is not None
        require(
            target["problem_id"] == body["problem_id"], "NOT_FOUND", "目标版本不属于该题。", 404
        )
        item = self.repo.required("assignment_items", (assignment_id, body["problem_id"]))
        require(item is not None, "NOT_FOUND", "该题不属于作业。", 404)
        # Every original formal result must be terminal before creating a batch.
        original_pending = self.repo.connection.execute(
            select(bases.c.basis_id)
            .join(submissions, submissions.c.submission_id == bases.c.submission_id)
            .where(
                submissions.c.assignment_id == assignment_id,
                submissions.c.mode == "FORMAL",
                bases.c.batch_id.is_(None),
                bases.c.processing_state != "FINISHED",
            )
            .limit(1)
        ).first()
        require(original_pending is None, "NOT_READY", "原始正式提交尚未全部终结。")
        rows = self._range(assignment_id, body["problem_id"])
        languages = sorted({row["language_key"] for row in rows})
        supported = {row["language_key"] for row in target["profile"]["languages"]}
        require(
            set(languages) <= supported, "REJUDGE_LANGUAGE_MISMATCH", "目标版本缺少历史提交语言。"
        )
        return dict(
            affected_count=len(rows),
            range_checksum=checksum([r["submission_id"] for r in rows]),
            languages=languages,
            old_version_id=item["effective_version_id"],
            new_version_id=target["version_id"],
        )

    def create(self, actor, assignment_id, body):
        target = self.repo.required("problem_versions", body["new_version_id"])
        require(target is not None, "NOT_FOUND", "版本不存在。", 404)
        preview = self.preview(actor, assignment_id, dict(body, problem_id=target["problem_id"]))
        require(
            preview["range_checksum"] == body["range_checksum"],
            "REVISION_CONFLICT",
            "影响范围已变化，请重新预览。",
        )
        require(bool(body["reason"].strip()), "VALIDATION_ERROR", "请填写理由。", 422)
        assignment = self.repo.required("assignments", assignment_id)
        batch_id = str(uuid4())
        self.repo.add(
            "rejudge_batches",
            dict(
                batch_id=batch_id,
                assignment_id=assignment_id,
                problem_id=target["problem_id"],
                new_version_id=target["version_id"],
                assignment_revision=assignment["revision"] + 1,
                revision=1,
                state="QUEUED",
                reason=body["reason"],
                range_checksum=preview["range_checksum"],
                affected_count=preview["affected_count"],
                created_at=self.repo.now(),
            ),
        )
        for row in self._range(assignment_id, target["problem_id"]):
            self.repo.add(
                "rejudge_members",
                dict(
                    batch_id=batch_id,
                    submission_id=row["submission_id"],
                    basis_id=None,
                    state="WAITING",
                ),
            )
        self.repo.change(
            "assignments",
            assignment_id,
            active_rejudge_batch_id=batch_id,
            revision=assignment["revision"] + 1,
        )
        self.effects.record(
            self.repo, actor["user_id"], "REJUDGE_CREATED", batch_id, reason=body["reason"]
        )
        return dict(batch_id=batch_id, affected_count=preview["affected_count"], state="QUEUED")

    def _access(self, actor, batch_id):
        self.repo.guard()
        batch = self.repo.required("rejudge_batches", batch_id, lock=True)
        require(batch is not None, "NOT_FOUND", "重评批次不存在。", 404)
        assert batch is not None
        assignment, _ = self.assignments.access(actor, batch["assignment_id"], teacher=True)
        return batch, assignment

    def read(self, actor, batch_id):
        batch, assignment = self._access(actor, batch_id)
        rows = self.repo.rows("rejudge_members", batch_id=batch_id)
        finished = 0
        failed = 0
        for row in rows:
            basis = self.repo.required("result_bases", row["basis_id"]) if row["basis_id"] else None
            if basis and basis["processing_state"] == "FINISHED" and row["state"] != "WAITING":
                finished += 1
                failed += (
                    self.repo.required("attempts", basis["current_attempt_id"])["verdict"] == "SE"
                )
        if batch["state"] not in ("ACTIVE", "CANCELLED"):
            state = (
                ("FAILED" if failed else "READY")
                if finished == len(rows)
                else "RUNNING"
                if any(row["basis_id"] for row in rows)
                else "QUEUED"
            )
            if state != batch["state"]:
                batch = self.repo.change(
                    "rejudge_batches", batch_id, state=state, revision=batch["revision"] + 1
                )
        differences = []
        if batch["state"] == "READY":
            for student in Grades(self.repo, self.effects).calculate(assignment):
                old_item = next(
                    item for item in student["items"] if item["problem_id"] == batch["problem_id"]
                )
                new_score = 0
                for member in rows:
                    submission = self.repo.required("submissions", member["submission_id"])
                    if submission["user_id"] == student["student_id"] and member["basis_id"]:
                        basis = self.repo.required("result_bases", member["basis_id"])
                        attempt = self.repo.required("attempts", basis["current_attempt_id"])
                        if attempt["verdict"] == "AC":
                            new_score = old_item["points"]
                after = student["total"] - old_item["score"] + new_score
                differences.append(
                    dict(
                        student_id=student["student_id"],
                        before=student["total"],
                        after=after,
                        delta=after - student["total"],
                    )
                )
        return dict(
            differences=differences,
            batch_id=batch_id,
            assignment_id=batch["assignment_id"],
            problem_id=batch["problem_id"],
            new_version_id=batch["new_version_id"],
            state=batch["state"],
            affected_count=len(rows),
            finished_count=finished,
            failed_count=failed,
            revision=batch["revision"],
            assignment_revision=assignment["revision"],
            range_checksum=batch["range_checksum"],
        )

    def activate(self, actor, batch_id, body):
        status = self.read(actor, batch_id)
        require(
            status["revision"] == body["expected_batch_revision"],
            "REVISION_CONFLICT",
            "批次已变化。",
        )
        require(status["state"] == "READY", "NOT_READY", "全部成员非平台故障终结后才能激活。")
        batch, assignment = self._access(actor, batch_id)
        revision(assignment, body["expected_assignment_revision"])
        require(
            self.repo.now() >= assignment["due_at"] and assignment["fairness_review"] != "PENDING",
            "UNRESOLVED_FAIRNESS",
            "请核对截止与公平事项。",
        )
        rows = self._range(batch["assignment_id"], batch["problem_id"])
        require(
            checksum([r["submission_id"] for r in rows]) == batch["range_checksum"],
            "REVISION_CONFLICT",
            "重评范围已变化。",
        )
        published = bool(
            assignment["active_grade_version"]
            and self.repo.required("grade_versions", assignment["active_grade_version"])["state"]
            == "PUBLISHED"
        )
        for member in self.repo.rows("rejudge_members", batch_id=batch_id):
            submission = self.repo.required("submissions", member["submission_id"])
            self.repo.change(
                "submissions",
                member["submission_id"],
                active_basis_id=member["basis_id"],
                revision=submission["revision"] + 1,
            )
        self.repo.change(
            "assignment_items",
            (batch["assignment_id"], batch["problem_id"]),
            effective_version_id=batch["new_version_id"],
        )
        assignment = self.repo.change(
            "assignments",
            assignment["assignment_id"],
            active_rejudge_batch_id=None,
            revision=assignment["revision"] + 1,
            grade_epoch=assignment["grade_epoch"] + 1,
        )
        grades = Grades(self.repo, self.effects)
        snapshot = grades.freeze(assignment, grades.calculate(assignment), published=published)
        self.repo.change(
            "assignments",
            assignment["assignment_id"],
            active_grade_version=snapshot["grade_version"],
        )
        self.repo.change(
            "rejudge_batches", batch_id, state="ACTIVE", revision=batch["revision"] + 1
        )
        self.effects.record(
            self.repo, actor["user_id"], "REJUDGE_ACTIVATED", batch_id, reason=body["reason"]
        )
        return dict(
            grade_version=snapshot["grade_version"], assignment_revision=assignment["revision"]
        )

    def cancel(self, actor, batch_id, body):
        from app.modules.submissions.processing import cancel_waiting

        batch, assignment = self._access(actor, batch_id)
        revision(batch, body["expected_revision"])
        require(batch["state"] not in ("ACTIVE", "CANCELLED"), "NOT_READY", "批次已结束。")
        self.repo.change(
            "rejudge_batches", batch_id, state="CANCELLED", revision=batch["revision"] + 1
        )
        for member in self.repo.rows("rejudge_members", batch_id=batch_id):
            if member["basis_id"]:
                cancel_waiting(self.repo, member["basis_id"])
        self.repo.change(
            "assignments",
            assignment["assignment_id"],
            active_rejudge_batch_id=None,
            revision=assignment["revision"] + 1,
        )
        self.effects.record(
            self.repo, actor["user_id"], "REJUDGE_CANCELLED", batch_id, reason=body["reason"]
        )
        return dict(state="CANCELLED", revision=batch["revision"] + 1)

    def retry(self, actor, batch_id, body):
        require(actor["role"] == "ADMIN", "FORBIDDEN", "仅管理员可重试故障批次。", 403)
        self.repo.guard()
        batch = self.repo.required("rejudge_batches", batch_id, lock=True)
        require(batch is not None and batch["state"] == "FAILED", "NOT_READY", "只能重试失败批次。")
        revision(batch, body["expected_revision"])
        count = 0
        for member in self.repo.rows("rejudge_members", batch_id=batch_id):
            if not member["basis_id"]:
                continue
            basis = self.repo.required("result_bases", member["basis_id"])
            attempt = self.repo.required("attempts", basis["current_attempt_id"])
            if attempt["state"] == "FINISHED" and attempt["verdict"] == "SE":
                self.repo.change(
                    "rejudge_members", (batch_id, member["submission_id"]), state="WAITING"
                )
                count += 1
        self.repo.change(
            "rejudge_batches", batch_id, state="RUNNING", revision=batch["revision"] + 1
        )
        self.effects.record(
            self.repo, actor["user_id"], "REJUDGE_RETRY", batch_id, reason=body["reason"]
        )
        return dict(retried_count=count, revision=batch["revision"] + 1)

    @staticmethod
    def dispatch_one(repo):
        active = repo.connection.execute(
            select(members)
            .join(batches, batches.c.batch_id == members.c.batch_id)
            .where(members.c.state == "WAITING", batches.c.state.in_(["QUEUED", "RUNNING"]))
            .order_by(batches.c.created_at, members.c.submission_id)
        ).mappings()
        for member in active:
            capacity = repo.get("capacity_control", 1, lock=True)
            if capacity["pending_count"] >= 100:
                return
            submission = repo.get("submissions", member["submission_id"])
            counter = repo.get("admission_users", submission["user_id"], lock=True)
            if counter["pending_count"] >= 3:
                continue
            batch = repo.get("rejudge_batches", member["batch_id"])
            basis_id = member["basis_id"]
            if basis_id is None:
                basis_id = str(uuid4())
                repo.add(
                    "result_bases",
                    dict(
                        basis_id=basis_id,
                        submission_id=submission["submission_id"],
                        batch_id=batch["batch_id"],
                        target_version_id=batch["new_version_id"],
                        current_attempt_id=None,
                        current_cycle_id=None,
                        processing_state="QUEUED",
                    ),
                )
            start_cycle(
                repo,
                submission,
                basis_id,
                "REJUDGE",
                "MANUAL" if member["basis_id"] else "REJUDGE",
                batch["reason"],
            )
            repo.change(
                "rejudge_members",
                (batch["batch_id"], submission["submission_id"]),
                basis_id=basis_id,
                state="RUNNING",
            )
            return
