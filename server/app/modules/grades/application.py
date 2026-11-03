"""Compute effective formal grades and publish one immutable assignment snapshot."""

import csv
import io
from uuid import uuid4

from sqlalchemy import select

from app.modules.assignments.application import Assignments
from app.modules.identity.domain import require, revision, utc
from app.modules.submissions.models import attempts, bases, submissions
from app.shared.effects import TransactionalEffects
from app.shared.repository import SqlRepository


class Grades:
    def __init__(self, repo: SqlRepository, effects: TransactionalEffects):
        self.repo, self.effects = repo, effects
        self.assignments = Assignments(repo, effects)

    def calculate(self, assignment):
        members = self.repo.rows(
            "course_members", course_id=assignment["course_id"], status="ACTIVE"
        )
        members = [
            member
            for member in members
            if (self.repo.get("users", member["user_id"]) or {}).get("status") == "ACTIVE"
        ]
        problems = self.repo.rows("assignment_items", assignment_id=assignment["assignment_id"])
        results = (
            self.repo.connection.execute(
                select(
                    submissions.c.user_id,
                    submissions.c.problem_id,
                    bases.c.target_version_id,
                    bases.c.processing_state,
                    attempts.c.attempt_id,
                    attempts.c.verdict,
                )
                .select_from(
                    submissions.join(bases, bases.c.basis_id == submissions.c.active_basis_id).join(
                        attempts, attempts.c.attempt_id == bases.c.current_attempt_id
                    )
                )
                .where(
                    submissions.c.assignment_id == assignment["assignment_id"],
                    submissions.c.mode == "FORMAL",
                )
                .order_by(submissions.c.accepted_at, submissions.c.submission_id)
            )
            .mappings()
            .all()
        )
        students = []
        for member in members:
            pending = False
            items = []
            for problem in problems:
                current = [
                    r
                    for r in results
                    if r["user_id"] == member["user_id"]
                    and r["problem_id"] == problem["problem_id"]
                    and r["target_version_id"] == problem["effective_version_id"]
                ]
                pending = pending or any(
                    r["processing_state"] != "FINISHED" or r["verdict"] == "SE" for r in current
                )
                passed = next(
                    (
                        r
                        for r in current
                        if r["processing_state"] == "FINISHED" and r["verdict"] == "AC"
                    ),
                    None,
                )
                items.append(
                    dict(
                        problem_id=problem["problem_id"],
                        points=problem["points"],
                        score=problem["points"] if passed else 0,
                        target_version_id=problem["effective_version_id"],
                        source_attempt_id=passed["attempt_id"] if passed else None,
                    )
                )
            students.append(
                dict(
                    student_id=member["user_id"],
                    total=sum(item["score"] for item in items),
                    state="PENDING" if pending else "READY",
                    items=items,
                )
            )
        return students

    def read(self, actor, assignment_id):
        self.repo.guard()
        assignment, _ = self.assignments.access(actor, assignment_id)
        if assignment["active_grade_version"]:
            snapshot = self.repo.get("grade_versions", assignment["active_grade_version"])
            if (
                snapshot
                and snapshot["grade_epoch"] == assignment["grade_epoch"]
                and assignment["fairness_review"] != "PENDING"
            ):
                return self.snapshot(actor, snapshot["grade_version"])
        students = self.calculate(assignment)
        if actor["role"] == "STUDENT":
            students = [row for row in students if row["student_id"] == actor["user_id"]]
        return dict(
            assignment_id=assignment_id,
            grade_version=None,
            assignment_revision=assignment["revision"],
            grade_epoch=assignment["grade_epoch"],
            state="REJUDGING" if assignment["active_rejudge_batch_id"] else "PROVISIONAL",
            published_at=None,
            students=students,
        )

    def snapshot(self, actor, version_id):
        snapshot = self.repo.get("grade_versions", version_id)
        require(snapshot is not None, "NOT_FOUND", "成绩版本不存在。", 404)
        assert snapshot is not None
        self.assignments.access(actor, snapshot["assignment_id"])
        students = self.repo.rows("grade_students", grade_version=version_id)
        if actor["role"] == "STUDENT":
            students = [row for row in students if row["student_id"] == actor["user_id"]]
        rows = []
        for row in students:
            items = self.repo.rows(
                "grade_items", grade_version=version_id, student_id=row["student_id"]
            )
            rows.append(
                dict(
                    student_id=row["student_id"],
                    total=row["total"],
                    state=row["state"],
                    items=[
                        {k: v for k, v in item.items() if k not in ("grade_version", "student_id")}
                        for item in items
                    ],
                )
            )
        return dict(
            assignment_id=snapshot["assignment_id"],
            grade_version=version_id,
            assignment_revision=snapshot["assignment_revision"],
            grade_epoch=snapshot["grade_epoch"],
            state=snapshot["state"],
            published_at=utc(snapshot["published_at"]) if snapshot["published_at"] else None,
            students=rows,
        )

    def publish(self, actor, assignment_id, body):
        self.repo.guard()
        assignment, _ = self.assignments.access(actor, assignment_id, teacher=True, write=True)
        revision(assignment, body["expected_revision"])
        require(
            assignment["published_at"] is not None,
            "ASSIGNMENT_DRAFT",
            "作业发布并截止后才可发布成绩。",
        )
        require(bool(body.get("reason", "").strip()), "VALIDATION_ERROR", "请填写发布理由。", 422)
        require(self.repo.now() >= assignment["due_at"], "NOT_READY", "作业截止后才可发布成绩。")
        require(
            assignment["fairness_review"] != "PENDING",
            "UNRESOLVED_FAIRNESS",
            "请先完成公平事项裁决。",
        )
        require(
            assignment["active_rejudge_batch_id"] is None, "ACTIVE_REJUDGE", "请先完成或取消重评。"
        )
        students = self.calculate(assignment)
        require(
            all(row["state"] == "READY" for row in students),
            "NOT_READY",
            "仍有处理中或平台故障结果。",
        )
        if assignment["active_grade_version"]:
            old = self.repo.get("grade_versions", assignment["active_grade_version"])
            if old and old["grade_epoch"] == assignment["grade_epoch"]:
                return dict(
                    grade_version=old["grade_version"], published_at=utc(old["published_at"])
                )
        snapshot = self.freeze(assignment, students, published=True)
        self.repo.change(
            "assignments", assignment_id, active_grade_version=snapshot["grade_version"]
        )
        self.effects.record(
            self.repo,
            actor["user_id"],
            "GRADE_PUBLISHED",
            assignment_id,
            reason=body["reason"],
            summary={"grade_version": snapshot["grade_version"]},
        )
        return dict(
            grade_version=snapshot["grade_version"], published_at=utc(snapshot["published_at"])
        )

    def freeze(self, assignment, students, *, published):
        now = self.repo.now()
        version_id = str(uuid4())
        snapshot = self.repo.add(
            "grade_versions",
            dict(
                grade_version=version_id,
                assignment_id=assignment["assignment_id"],
                assignment_revision=assignment["revision"],
                grade_epoch=assignment["grade_epoch"],
                state="PUBLISHED" if published else "PROVISIONAL",
                published_at=now if published else None,
                created_at=now,
            ),
        )
        for student in students:
            self.repo.add(
                "grade_students",
                dict(
                    grade_version=version_id,
                    student_id=student["student_id"],
                    total=student["total"],
                    state=student["state"],
                ),
            )
            for item in student["items"]:
                self.repo.add(
                    "grade_items",
                    dict(grade_version=version_id, student_id=student["student_id"], **item),
                )
        return snapshot

    def export(self, actor, assignment_id, version_id):
        self.assignments.access(actor, assignment_id, teacher=True)
        snapshot = self.snapshot(actor, version_id)
        require(
            snapshot["assignment_id"] == assignment_id, "NOT_FOUND", "成绩版本不属于该作业。", 404
        )
        stream = io.StringIO(newline="")
        writer = csv.writer(stream)
        writer.writerow(["学生编号", "题目编号", "题分", "得分", "总分", "状态", "成绩版本"])

        def safe(value):
            value = str(value)
            return (
                "'" + value
                if value.lstrip().startswith(("=", "+", "-", "@", "\t", "\r"))
                else value
            )

        for student in snapshot["students"]:
            for item in student["items"]:
                writer.writerow(
                    [
                        safe(student["student_id"]),
                        safe(item["problem_id"]),
                        item["points"],
                        item["score"],
                        student["total"],
                        student["state"],
                        version_id,
                    ]
                )
        return "\ufeff" + stream.getvalue()


class GradeCoordination:
    def before_change(self, repo, assignment, action):
        if action == "DEADLINE_EXTENDED":
            require(
                assignment["active_rejudge_batch_id"] is None,
                "ACTIVE_REJUDGE",
                "请先取消未激活重评。",
            )

    def status(self, repo, assignment):
        state = "REJUDGING" if assignment["active_rejudge_batch_id"] else "PROVISIONAL"
        if state != "REJUDGING" and assignment["active_grade_version"]:
            snapshot = repo.get("grade_versions", assignment["active_grade_version"])
            if (
                snapshot
                and snapshot["grade_epoch"] == assignment["grade_epoch"]
                and assignment["fairness_review"] != "PENDING"
            ):
                state = snapshot["state"]
        links = repo.rows("incident_assignments", assignment_id=assignment["assignment_id"])
        notices = [
            "故障事件 " + row["incident_id"] + " 待教师裁决。"
            if row["decision"] == "PENDING"
            else "故障事件已裁决，"
            + ("全班统一延期。" if row["decision"] == "EXTEND" else "确认无影响。")
            for row in links
        ]
        return dict(grade_state=state, fairness_notice=" ".join(notices) if notices else None)
