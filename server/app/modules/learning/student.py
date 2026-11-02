"""Authorized PostgreSQL projections for review items and practice recommendations."""

from typing import Any, Protocol

from sqlalchemy import String, and_, case, func, select, tuple_
from sqlalchemy.engine import Connection
from sqlalchemy.sql import Select

from app.modules.assignments.models import assignments, items
from app.modules.courses.application import Courses
from app.modules.courses.models import course_members as members
from app.modules.courses.models import courses
from app.modules.identity.domain import Fault, require, role, utc
from app.modules.identity.ports import Effects, Record, Repository
from app.modules.problems.domain import CONTENT_FIELDS
from app.modules.problems.models import families, problems, versions

from .hint_tables import hints


class LearningResults(Protocol):
    """B supplies a read-only SELECT over authorized terminal submission outcomes.

    Columns: user_id, submission_id, assignment_id, problem_id, version_id,
    accepted_at, context (FORMAL/PRACTICE), verdict, effective (bool).
    Include historical student errors and mark only currently effective AC rows.
    Do not project code, tests, diagnostics, scores or unrelated student data.
    A joins the query to current membership, assignment and published version.
    """

    def projection(self, repo: Repository, actor: Record) -> Select[Any]: ...


class StudentLearning:
    def __init__(
        self,
        connection: Connection,
        repo: Repository,
        effects: Effects,
        results: LearningResults | None,
    ):
        self.connection, self.repo, self.results = connection, repo, results
        self.courses = Courses(repo, effects)

    def hint_history(self, actor: Record, pager: Any) -> Record:
        role(actor, ("STUDENT",))
        statement = select(hints.c.hint_id, hints.c.created_at).where(
            hints.c.user_id == actor["user_id"]
        )
        if pager.after is not None:
            previous = self.connection.execute(
                statement.where(hints.c.hint_id == pager.after)
            ).first()
            require(previous is not None, "VALIDATION_ERROR", "游标已失效。", 422)
            assert previous is not None
            statement = statement.where(
                tuple_(hints.c.created_at, hints.c.hint_id)
                < (previous.created_at, previous.hint_id)
            )
        rows = self.connection.execute(
            statement.order_by(hints.c.created_at.desc(), hints.c.hint_id.desc()).limit(
                pager.limit + 1
            )
        ).mappings()
        page = [dict(hint_id=row["hint_id"], created_at=utc(row["created_at"])) for row in rows]
        return dict(pager.finish(page, "hint_id"))

    def wrong_items(
        self, actor: Record, course: str | None, context: str | None = None
    ) -> Select[Any]:
        role(actor, ("STUDENT",))
        if course:
            self.courses.access(actor, course)
        if self.results is None:
            raise Fault(503, "INTEGRATION_UNAVAILABLE", "提交结果查询尚未接入。", retry=5)
        source = self.results.projection(self.repo, actor).subquery()
        r = source.c
        key = [r.problem_id, r.context]
        wrong = r.verdict.in_(["CE", "WA", "TLE", "RE"])
        solved = func.bool_or(and_(r.verdict == "AC", r.effective.is_(True))).over(partition_by=key)
        rank = func.row_number().over(
            partition_by=key,
            order_by=[
                case((wrong, 0), else_=1),
                r.accepted_at.desc(),
                r.submission_id.desc(),
                r.verdict,
            ],
        )
        statement = (
            select(
                r.submission_id.cast(String).label("submission_id"),
                assignments.c.assignment_id,
                problems.c.problem_id,
                versions.c.title,
                versions.c.tags,
                r.verdict,
                r.context,
                r.accepted_at,
                solved.label("solved"),
                rank.label("rank"),
            )
            .select_from(source)
            .join(assignments, assignments.c.assignment_id == r.assignment_id)
            .join(
                members,
                and_(
                    members.c.course_id == assignments.c.course_id, members.c.user_id == r.user_id
                ),
            )
            .join(
                items,
                and_(items.c.assignment_id == r.assignment_id, items.c.problem_id == r.problem_id),
            )
            .join(
                problems,
                and_(
                    problems.c.problem_id == r.problem_id,
                    problems.c.owner_course_id == assignments.c.course_id,
                ),
            )
            .join(
                versions,
                and_(versions.c.version_id == r.version_id, versions.c.problem_id == r.problem_id),
            )
            .where(
                members.c.user_id == actor["user_id"],
                members.c.status == "ACTIVE",
                assignments.c.published_at.is_not(None),
                assignments.c.open_at <= self.repo.now(),
                versions.c.published_at.is_not(None),
                r.context.in_(["FORMAL", "PRACTICE"]),
            )
        )
        if course:
            statement = statement.where(assignments.c.course_id == course)
        if context:
            statement = statement.where(r.context == context)
        ranked = statement.subquery()
        return select(ranked).where(
            ranked.c.rank == 1,
            ranked.c.solved.is_not(True),
            ranked.c.verdict.in_(["CE", "WA", "TLE", "RE"]),
        )

    def review(self, actor: Record, query: Record, pager: Any) -> Record:
        require(
            query.get("context") in ("FORMAL", "PRACTICE"),
            "VALIDATION_ERROR",
            "请选择正式或练习。",
            422,
        )
        rows = self.wrong_items(actor, query.get("course_id"), query["context"]).subquery()
        statement = select(
            *(
                rows.c[k]
                for k in (
                    "submission_id",
                    "assignment_id",
                    "problem_id",
                    "title",
                    "verdict",
                    "context",
                    "accepted_at",
                )
            )
        )
        key = rows.c.submission_id
        if pager.after is not None:
            require(
                self.connection.execute(statement.where(key == pager.after).limit(1)).first()
                is not None,
                "VALIDATION_ERROR",
                "游标已失效。",
                422,
            )
            statement = statement.where(key > pager.after)
        page = [
            {**row, "accepted_at": utc(row["accepted_at"])}
            for row in self.connection.execute(
                statement.order_by(key).limit(pager.limit + 1)
            ).mappings()
        ]
        return dict(pager.finish(page, "submission_id"))

    def practice_candidates(self, actor: Record, course: str | None = None) -> Select[Any]:
        role(actor, ("STUDENT",))
        related = problems.alias("related_problem")
        active_members = members.alias("active_members")

        unavailable = (
            select(1)
            .select_from(related)
            .join(items, items.c.problem_id == related.c.problem_id)
            .join(assignments, assignments.c.assignment_id == items.c.assignment_id)
            .join(courses, courses.c.course_id == assignments.c.course_id)
            .join(active_members, active_members.c.course_id == courses.c.course_id)
            .where(
                related.c.canonical_problem_id == problems.c.canonical_problem_id,
                active_members.c.user_id == actor["user_id"],
                active_members.c.status == "ACTIVE",
                courses.c.status != "ARCHIVED",
                assignments.c.published_at.is_not(None),
                assignments.c.due_at > self.repo.now(),
            )
            .exists()
        )
        candidates = (
            select(versions)
            .select_from(problems)
            .join(families, families.c.canonical_problem_id == problems.c.canonical_problem_id)
            .join(
                versions,
                and_(
                    versions.c.version_id == problems.c.practice_version_id,
                    versions.c.problem_id == problems.c.problem_id,
                ),
            )
            .join(members, members.c.course_id == problems.c.owner_course_id)
            .where(
                members.c.user_id == actor["user_id"],
                members.c.status == "ACTIVE",
                versions.c.published_at.is_not(None),
                problems.c.practice_released.is_(True),
                ~unavailable,
            )
        )
        if course:
            candidates = candidates.where(problems.c.owner_course_id == course)
        return candidates

    def public_practice(self, actor: Record, pid: str) -> Record:
        self.repo.guard()
        statement = self.practice_candidates(actor).where(problems.c.problem_id == pid)
        row = self.connection.execute(statement).mappings().first()
        require(row is not None, "NOT_FOUND", "该练习当前不可用。", 404)
        assert row is not None
        return {k: row[k] for k in ("problem_id", "version_id", *CONTENT_FIELDS)}

    def recommendations(self, actor: Record, course: str | None) -> Record:
        wrong = self.wrong_items(actor, course).subquery()
        weak = (
            select(func.jsonb_array_elements_text(wrong.c.tags).label("tag")).distinct().subquery()
        )
        eligible = self.practice_candidates(actor, course).subquery()
        fields = [
            eligible.c.problem_id,
            eligible.c.version_id.label("practice_version_id"),
            eligible.c.title,
        ]
        statement = (
            select(
                *fields,
                func.array_agg(weak.c.tag).filter(weak.c.tag.is_not(None)).label("tags"),
            )
            .select_from(eligible)
            .outerjoin(weak, eligible.c.tags.bool_op("?")(weak.c.tag))
            .group_by(*fields)
            .order_by(func.count(weak.c.tag).desc(), eligible.c.problem_id)
            .limit(5)
        )
        return {
            "items": [
                {**row, "tags": sorted(row["tags"] or [])}
                for row in self.connection.execute(statement).mappings()
            ]
        }
