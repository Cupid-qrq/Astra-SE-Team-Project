"""Read course leaderboards from authoritative current results and grade snapshots."""

from uuid import UUID, uuid5

from sqlalchemy import text
from sqlalchemy.dialects.postgresql import insert

from app.modules.community.leaderboard_models import preferences
from app.modules.courses.application import Courses
from app.modules.identity.domain import require, role, utc
from app.shared.effects import TransactionalEffects
from app.shared.repository import SqlRepository


class Leaderboards:
    def __init__(self, repo: SqlRepository, effects: TransactionalEffects) -> None:
        self.repo, self.effects = repo, effects
        self.courses = Courses(repo, effects)

    def access(self, actor, course_id, *, write=False):
        self.repo.guard()
        user = self.repo.get("users", actor["user_id"])
        require(
            user is not None
            and user["status"] == "ACTIVE"
            and actor.get("status", "ACTIVE") == "ACTIVE",
            "FORBIDDEN",
            "账号不可用。",
            403,
        )
        self.courses.access(actor, course_id, write=write)

    def read(self, actor, course_id, kind):
        self.access(actor, course_id)
        require(kind in ("progress", "grades"), "VALIDATION_ERROR", "榜单类型无效。", 422)
        now = self.repo.now()
        params = {"course_id": course_id, "now": now}
        roster = (
            self.repo.connection.execute(
                text("""
            SELECT u.user_id, u.display_name, COALESCE(p.show_name, false) AS show_name
            FROM course_members m JOIN users u ON u.user_id=m.user_id
            LEFT JOIN leaderboard_preferences p ON p.course_id=m.course_id AND p.user_id=m.user_id
            WHERE m.course_id=:course_id AND m.status='ACTIVE'
              AND u.status='ACTIVE' AND u.role='STUDENT'
        """),
                params,
            )
            .mappings()
            .all()
        )
        if kind == "progress":
            eligible = """
                SELECT a.assignment_id FROM assignments a
                WHERE a.course_id=:course_id AND a.published_at IS NOT NULL AND a.open_at<=:now
            """
            query = f"""
                WITH eligible AS ({eligible})
                SELECT s.user_id, count(DISTINCT (s.assignment_id,s.problem_id)) AS value
                FROM submissions s JOIN eligible e ON e.assignment_id=s.assignment_id
                JOIN assignment_items i ON i.assignment_id=s.assignment_id AND i.problem_id=s.problem_id
                JOIN result_bases b ON b.basis_id=s.active_basis_id AND b.submission_id=s.submission_id
                JOIN attempts t ON t.attempt_id=b.current_attempt_id AND t.basis_id=b.basis_id
                  AND t.submission_id=s.submission_id AND t.cycle_id=b.current_cycle_id
                WHERE s.mode='FORMAL' AND b.target_version_id=i.effective_version_id
                  AND b.processing_state='FINISHED' AND t.state='FINISHED' AND t.verdict='AC'
                GROUP BY s.user_id
            """
        else:
            eligible = """
                SELECT a.assignment_id, v.grade_version FROM assignments a
                JOIN grade_versions v ON v.grade_version=a.active_grade_version
                  AND v.assignment_id=a.assignment_id AND v.grade_epoch=a.grade_epoch
                WHERE a.course_id=:course_id AND a.published_at IS NOT NULL AND a.open_at<=:now
                  AND a.active_rejudge_batch_id IS NULL AND a.fairness_review<>'PENDING'
                  AND v.state='PUBLISHED' AND v.published_at IS NOT NULL
            """
            query = f"""
                WITH eligible AS ({eligible})
                SELECT s.student_id AS user_id, sum(s.total) AS value
                FROM grade_students s JOIN eligible e ON e.grade_version=s.grade_version
                WHERE s.state='READY' GROUP BY s.student_id
            """
        included = self.repo.connection.execute(
            text(f"SELECT count(*) FROM ({eligible}) eligible"), params
        ).scalar_one()
        values = {
            str(row["user_id"]): int(row["value"])
            for row in self.repo.connection.execute(text(query), params).mappings()
        }
        rows = []
        own_preference = False
        for member in roster:
            member_id = str(member["user_id"])
            is_me = member_id == actor["user_id"]
            if is_me:
                own_preference = member["show_name"]
            # A course-scoped identifier is stable without disclosing the account UUID.
            entry_id = str(uuid5(UUID(course_id), "leaderboard:" + member_id))
            visible = actor["role"] == "TEACHER" or member["show_name"]
            rows.append(
                dict(
                    entry_id=entry_id,
                    rank=0,
                    display_name=member["display_name"] if visible else "匿名同学 " + entry_id[:8],
                    value=values.get(member_id, 0),
                    is_me=is_me,
                )
            )
        rows.sort(key=lambda row: (-row["value"], row["entry_id"]))
        previous = None
        rank = 0
        for position, row in enumerate(rows, 1):
            if row["value"] != previous:
                rank = position
            row["rank"] = rank
            previous = row["value"]
        return dict(
            course_id=course_id,
            kind=kind,
            updated_at=utc(now),
            included_assignments=included,
            show_name=own_preference,
            items=rows,
        )

    def preference(self, actor, course_id, body):
        role(actor, ("STUDENT",))
        self.access(actor, course_id, write=True)
        require(
            set(body) == {"show_name"} and type(body.get("show_name")) is bool,
            "VALIDATION_ERROR",
            "请提供姓名显示设置。",
            422,
        )
        self.repo.connection.execute(
            insert(preferences)
            .values(
                course_id=course_id,
                user_id=actor["user_id"],
                show_name=body["show_name"],
            )
            .on_conflict_do_update(
                index_elements=[preferences.c.course_id, preferences.c.user_id],
                set_={"show_name": body["show_name"]},
            )
        )
        self.effects.record(
            self.repo,
            actor["user_id"],
            "LEADERBOARD_PREFERENCE_UPDATED",
            course_id,
            summary={"show_name": body["show_name"]},
        )
        return {"show_name": body["show_name"]}
