"""BR-13. Run each check inside the phase's own caller-owned transaction."""

from dataclasses import dataclass
from datetime import datetime
from typing import Literal, Protocol

from app.modules.assignments.domain import assignment_state
from app.modules.identity.domain import Fault, require
from app.modules.identity.ports import Record, Repository
from app.modules.problems.domain import canonical_hash


@dataclass(frozen=True)
class HintSource:
    submission_id: str
    student_id: str
    course_id: str
    problem_id: str
    state: str
    verdict: str
    feedback_version_id: str | None = None
    result_basis_id: str | None = None
    attempt_id: str | None = None
    effective_version_id: str | None = None


def source_snapshot(source: HintSource) -> Record:
    """Only immutable provenance and public result identifiers; never code or diagnostics."""
    return {
        name: getattr(source, name)
        for name in (
            "submission_id",
            "student_id",
            "course_id",
            "problem_id",
            "state",
            "verdict",
            "feedback_version_id",
            "result_basis_id",
            "attempt_id",
            "effective_version_id",
        )
    }


def require_same_source(hint: Record, source: HintSource) -> None:
    require(
        bool(hint.get("source_snapshot")) and hint["source_snapshot"] == source_snapshot(source),
        "SOURCE_CHANGED",
        "提示来源已变化，请重新请求。",
        409,
    )


class HintSources(Protocol):
    def hint_source(
        self, repo: Repository, student_id: str, submission_id: str
    ) -> HintSource | None:
        """B revalidates assignment and submission visibility in this transaction."""
        ...


@dataclass(frozen=True)
class Authorization:
    source: HintSource
    authorized_at: datetime
    policy_digest: str


class HintPolicy:
    def __init__(self, repo: Repository, sources: HintSources | None):
        self.repo, self.sources = repo, sources

    def authorize(
        self,
        student_id: str,
        submission_id: str,
        *,
        consent: bool,
        phase: Literal["accept", "dispatch", "ready", "read"] = "accept",
    ) -> Authorization:
        self.repo.guard()
        if self.sources is None:
            raise Fault(503, "INTEGRATION_UNAVAILABLE", "提交授权查询尚未接入。", retry=5)
        require(consent is True, "CONSENT_REQUIRED", "需要本人确认代码外发。", 403)
        student = self.repo.get("users", student_id)
        source = self.sources.hint_source(self.repo, student_id, submission_id)
        require(
            bool(
                student
                and student["status"] == "ACTIVE"
                and student["role"] == "STUDENT"
                and source
                and source.student_id == student_id
                and source.submission_id == submission_id
            ),
            "NOT_FOUND",
            "提交不存在或无权访问。",
            404,
        )
        assert source
        require(
            all((source.result_basis_id, source.attempt_id, source.effective_version_id)),
            "SOURCE_UNVERIFIABLE",
            "提交来源身份不完整。",
            503,
        )
        memberships = self.repo.rows("course_members", user_id=student_id, status="ACTIVE")
        ids = [m["course_id"] for m in memberships]
        require(source.course_id in ids, "NOT_FOUND", "提交不存在或无权访问。", 404)
        active = [c["course_id"] for c in self.repo.rows("courses", course_id=ids, status="ACTIVE")]
        require(phase == "read" or source.course_id in active, "COURSE_ARCHIVED", "归档课程只读。")
        require(
            source.state == "FINISHED" and source.verdict in ("CE", "WA", "TLE", "RE"),
            "HINT_NOT_APPLICABLE",
            "该提交不能请求模型提示。",
        )
        problem = self.repo.get("problems", source.problem_id)
        require(problem is not None, "NOT_FOUND", "来源题目不可访问。", 404)
        assert problem
        family = problem["canonical_problem_id"]
        related = self.repo.rows("problems", canonical_problem_id=family)
        items = self.repo.rows("assignment_items", problem_id=[p["problem_id"] for p in related])
        assignments = self.repo.rows(
            "assignments", assignment_id=[i["assignment_id"] for i in items], course_id=active
        )
        now = self.repo.now()
        opened = [a for a in assignments if assignment_state(a, now) == "OPEN"]
        require(
            all(a["ai_policy"] == "GUIDED" for a in opened),
            "HINT_POLICY_BLOCKED",
            "当前开放作业限制了同族题目的提示。",
            403,
        )
        digest = canonical_hash(
            dict(
                family=family,
                student=student_id,
                course=source.course_id,
                submission=submission_id,
                courses=sorted(active),
                open_assignments=sorted(
                    (a["assignment_id"], a["revision"], a["ai_policy"]) for a in opened
                ),
            )
        )
        return Authorization(source, now, digest)

    def can_read_sections(
        self, viewer_id: str, student_id: str, submission_id: str, *, course_id: str, consent: bool
    ) -> bool:
        """Pass frozen owner/course from the hint, never query parameters. False means BLOCKED."""
        self.repo.guard()
        viewer = self.repo.get("users", viewer_id)
        course = self.repo.get("courses", course_id)
        member = self.repo.rows(
            "course_members", course_id=course_id, user_id=viewer_id, status="ACTIVE"
        )
        require(
            bool(
                viewer
                and course
                and viewer["status"] == "ACTIVE"
                and (
                    (viewer_id == student_id and viewer["role"] == "STUDENT" and member)
                    or (viewer["role"] == "TEACHER" and course["teacher_id"] == viewer_id)
                )
            ),
            "NOT_FOUND",
            "提示不存在或无权访问。",
            404,
        )
        try:
            return (
                self.authorize(
                    student_id, submission_id, consent=consent, phase="read"
                ).source.course_id
                == course_id
            )
        except Fault as exc:
            if exc.status not in (403, 404, 409):
                raise
            return False

    def read_projection(self, viewer_id: str, hint: Record, fallback: Record | None) -> Record:
        """The store supplies the frozen source and its already-public fixed-help version."""
        allowed = self.can_read_sections(
            viewer_id,
            hint["user_id"],
            hint["submission_id"],
            course_id=hint["course_id"],
            consent=hint["consented_at"] is not None,
        )
        current = (
            self.sources.hint_source(self.repo, hint["user_id"], hint["submission_id"])
            if self.sources
            else None
        )
        same_source = bool(
            current
            and hint.get("source_snapshot")
            and hint["source_snapshot"] == source_snapshot(current)
        )
        result = {
            k: hint[k]
            for k in (
                "hint_id",
                "submission_id",
                "status",
                "reason_code",
                "model_version",
                "template_version_id",
                "created_at",
            )
        }
        if not allowed:
            result.update(status="BLOCKED", reason_code="HINT_POLICY_BLOCKED")
        if not same_source:
            result.update(status="BLOCKED", reason_code="SOURCE_CHANGED")
        result["sections"] = hint["sections"] if result["status"] == "READY" else None
        result["fallback_feedback"] = (
            {k: fallback[k] for k in ("feedback_version_id", "title", "explanation", "checklist")}
            if fallback and same_source and result["status"] in ("FAILED", "BLOCKED")
            else None
        )
        return result
