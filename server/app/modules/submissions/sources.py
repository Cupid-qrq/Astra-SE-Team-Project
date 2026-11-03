"""Allowlisted B projections consumed by A's feedback, hint and learning services."""

from typing import Any
from uuid import uuid4

from sqlalchemy import and_, select
from sqlalchemy.sql import Select

from app.modules.assignments.models import assignments, items
from app.modules.courses.models import course_members, courses
from app.modules.identity.domain import Fault
from app.modules.identity.ports import Record, Repository
from app.modules.learning.policy_rules import HintSource
from app.shared.effects import TransactionalEffects
from app.shared.repository import SqlRepository

from .application import Submissions
from .models import attempts, bases, submissions


class SubmissionSources:
    @staticmethod
    def _detail(repo: Repository, actor: Record, submission_id: str) -> Record:
        if not isinstance(repo, SqlRepository):
            raise TypeError("Submission sources require the shared transactional repository")
        return Submissions(repo, TransactionalEffects(repo, str(uuid4()))).detail(
            actor, submission_id
        )

    def feedback(self, repo: Repository, actor: Record, submission_id: str) -> Record | None:
        detail = self._detail(repo, actor, submission_id)
        submission = repo.get("submissions", submission_id)
        assignment = repo.get("assignments", detail["assignment_id"])
        assert submission is not None and assignment is not None
        return dict(
            user_id=submission["user_id"],
            course_id=assignment["course_id"],
            state=detail["state"],
            verdict=detail["verdict"],
            feedback_version_id=detail["feedback_version_id"],
        )

    def hint_source(
        self, repo: Repository, student_id: str, submission_id: str
    ) -> HintSource | None:
        student = repo.get("users", student_id)
        if student is None or student["role"] != "STUDENT" or student["status"] != "ACTIVE":
            return None
        try:
            detail = self._detail(repo, student, submission_id)
        except Fault:
            return None
        assignment = repo.get("assignments", detail["assignment_id"])
        assert assignment is not None
        return HintSource(
            submission_id,
            student_id,
            assignment["course_id"],
            detail["problem_id"],
            detail["state"],
            detail["verdict"] or "",
            detail["feedback_version_id"],
        )

    def hint_context(self, repo: Repository, source: HintSource) -> Record:
        current = self.hint_source(repo, source.student_id, source.submission_id)
        if current is None or current != source:
            raise Fault(404, "NOT_FOUND", "提交不存在或无权访问。")
        detail = self._detail(
            repo, {"user_id": source.student_id, "role": "STUDENT"}, source.submission_id
        )
        version = repo.get("problem_versions", detail["effective_version_id"])
        assert version is not None
        return dict(
            public_problem=version["statement"],
            public_samples=version["samples"],
            student_code=detail["code"],
            language_key=detail["language_key"],
            sanitized_diagnostic="",
            verdict=detail["verdict"],
        )

    def projection(self, repo: Repository, actor: Record) -> Select[Any]:
        effective = and_(
            submissions.c.active_basis_id == bases.c.basis_id,
            bases.c.current_attempt_id == attempts.c.attempt_id,
            items.c.effective_version_id == bases.c.target_version_id,
        )
        return (
            select(
                submissions.c.user_id,
                submissions.c.submission_id,
                submissions.c.assignment_id,
                submissions.c.problem_id,
                bases.c.target_version_id.label("version_id"),
                submissions.c.accepted_at,
                submissions.c.mode.label("context"),
                attempts.c.verdict,
                effective.label("effective"),
            )
            .select_from(
                submissions.join(bases, bases.c.submission_id == submissions.c.submission_id)
                .join(attempts, attempts.c.basis_id == bases.c.basis_id)
                .join(assignments, assignments.c.assignment_id == submissions.c.assignment_id)
                .join(courses, courses.c.course_id == assignments.c.course_id)
                .join(
                    course_members,
                    and_(
                        course_members.c.course_id == courses.c.course_id,
                        course_members.c.user_id == submissions.c.user_id,
                    ),
                )
                .join(
                    items,
                    and_(
                        items.c.assignment_id == submissions.c.assignment_id,
                        items.c.problem_id == submissions.c.problem_id,
                    ),
                )
            )
            .where(
                submissions.c.user_id == actor["user_id"],
                course_members.c.status == "ACTIVE",
                attempts.c.state == "FINISHED",
            )
        )


def build_sources(engine: Any) -> SubmissionSources:
    """Trusted factory for the separately enabled A model Worker."""
    return SubmissionSources()
