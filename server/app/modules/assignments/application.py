from datetime import datetime
from uuid import uuid4

from app.modules.courses.application import Courses
from app.modules.identity.domain import Fault, require, revision, role, utc
from app.modules.identity.ports import Effects, Record, Repository
from app.modules.problems.domain import CONTENT_FIELDS

from .domain import assignment_state, submission_mode, validate_assignment
from .ports import AssignmentCoordinationPort


class Assignments:
    def __init__(
        self,
        repo: Repository,
        effects: Effects,
        coordination: AssignmentCoordinationPort | None = None,
    ):
        self.repo, self.effects, self.coordination = repo, effects, coordination
        self.courses = Courses(repo, effects)

    def access(
        self, actor: Record, aid: str, *, teacher=False, write=False
    ) -> tuple[Record, Record]:
        role(actor, ("TEACHER",) if teacher else ("TEACHER", "STUDENT"))
        assignment = self.repo.get("assignments", aid)
        require(assignment is not None, "NOT_FOUND", "作业不存在或无权访问。", 404)
        assert assignment
        course = self.courses.access(actor, assignment["course_id"], teacher=teacher, write=write)
        if write:
            assignment = self.repo.get("assignments", aid, lock=True)
            assert assignment
        require(
            actor["role"] == "TEACHER" or assignment["published_at"] is not None,
            "NOT_FOUND",
            "作业不存在或无权访问。",
            404,
        )
        return assignment, course

    def summary(self, assignment: Record, course: Record) -> Record:
        return {
            **{k: assignment[k] for k in ("assignment_id", "course_id", "title", "revision")},
            "open_at": utc(assignment["open_at"]),
            "due_at": utc(assignment["due_at"]),
            "state": assignment_state(
                assignment, self.repo.now(), archived=course["status"] == "ARCHIVED"
            ),
        }

    def visible(self, actor: Record, cid: str) -> list[Record]:
        course = self.courses.access(actor, cid)
        return [
            self.summary(a, course)
            for a in self.repo.rows("assignments", course_id=cid)
            if actor["role"] == "TEACHER" or a["published_at"] is not None
        ]

    def view(self, actor: Record, aid: str) -> Record:
        assignment, course = self.access(actor, aid)
        now = self.repo.now()
        visible_items = actor["role"] == "TEACHER" or now >= assignment["open_at"]
        items = []
        if visible_items:
            for item in self.repo.rows("assignment_items", assignment_id=aid):
                version = self.repo.get("problem_versions", item["effective_version_id"])
                assert version
                items.append(
                    dict(
                        problem_id=item["problem_id"], title=version["title"], points=item["points"]
                    )
                )
        status = (
            self.coordination.status(self.repo, assignment)
            if self.coordination
            else {
                "grade_state": "REJUDGING"
                if assignment["active_rejudge_batch_id"]
                else "PROVISIONAL",
                "fairness_notice": None,
            }
        )
        return {
            **self.summary(assignment, course),
            "server_time": utc(now),
            "items": items,
            "ai_policy": assignment["ai_policy"],
            "fairness_review": assignment["fairness_review"],
            **status,
        }

    def problem(self, actor: Record, aid: str, pid: str) -> Record:
        assignment, _ = self.access(actor, aid)
        require(
            actor["role"] == "TEACHER" or self.repo.now() >= assignment["open_at"],
            "NOT_FOUND",
            "题目尚未开放。",
            404,
        )
        item = self.repo.get("assignment_items", (aid, pid))
        require(item is not None, "NOT_FOUND", "作业中不存在该题目。", 404)
        assert item
        version = self.repo.get("problem_versions", item["effective_version_id"])
        assert version
        return {k: version[k] for k in ("problem_id", "version_id", *CONTENT_FIELDS)}

    def validate_items(self, actor: Record, cid: str, items: list[Record]) -> None:
        for item in items:
            problem = self.repo.get("problems", item["problem_id"])
            require(
                bool(problem and problem["owner_course_id"] == cid),
                "NOT_FOUND",
                "题目不属于当前课程。",
                404,
            )
            version = self.repo.get("problem_versions", item["version_id"])
            require(
                bool(version and version["problem_id"] == item["problem_id"]),
                "NOT_FOUND",
                "版本不属于当前题目。",
                404,
            )
            assert version
            require(
                version["published_at"] is not None
                and version["published_preflight_id"] is not None,
                "VERSION_NOT_PUBLISHED",
                "作业只能引用已通过预检并发布的版本。",
            )

    def store_items(self, aid: str, items: list[Record]) -> None:
        for old in self.repo.rows("assignment_items", assignment_id=aid):
            self.repo.remove("assignment_items", (aid, old["problem_id"]))
        for item in items:
            self.repo.add(
                "assignment_items",
                dict(
                    assignment_id=aid,
                    problem_id=item["problem_id"],
                    original_version_id=item["version_id"],
                    effective_version_id=item["version_id"],
                    points=item["points"],
                ),
            )

    def create(self, actor: Record, body: Record) -> Record:
        self.courses.access(actor, body["course_id"], teacher=True, write=True)
        data = {k: body[k] for k in ("course_id", "title", "ai_policy")}
        data.update(
            open_at=datetime.fromisoformat(body["open_at"]),
            due_at=datetime.fromisoformat(body["due_at"]),
        )
        validate_assignment(data, body["items"])
        self.validate_items(actor, body["course_id"], body["items"])
        aid = str(uuid4())
        self.repo.add(
            "assignments",
            dict(
                assignment_id=aid,
                **data,
                published_at=None,
                revision=1,
                grade_epoch=1,
                fairness_review="NONE",
                active_grade_version=None,
                active_rejudge_batch_id=None,
                created_at=self.repo.now(),
                updated_at=self.repo.now(),
            ),
        )
        self.store_items(aid, body["items"])
        self.effects.record(self.repo, actor["user_id"], "ASSIGNMENT_CREATED", aid)
        return dict(assignment_id=aid, revision=1)

    def update(self, actor: Record, aid: str, body: Record) -> Record:
        assignment, _ = self.access(actor, aid, teacher=True, write=True)
        revision(assignment, body["expected_revision"])
        require(
            assignment["published_at"] is None,
            "ASSIGNMENT_IMMUTABLE",
            "已发布作业的题目、分值和开放时间不可修改。",
        )
        require(
            body.get("course_id", assignment["course_id"]) == assignment["course_id"],
            "COURSE_IMMUTABLE",
            "作业不能转移到其他课程。",
        )
        items = body.get(
            "items",
            [
                dict(
                    problem_id=i["problem_id"],
                    version_id=i["original_version_id"],
                    points=i["points"],
                )
                for i in self.repo.rows("assignment_items", assignment_id=aid)
            ],
        )
        data = {k: body.get(k, assignment[k]) for k in ("title", "ai_policy")}
        data.update(
            {
                k: datetime.fromisoformat(body[k]) if k in body else assignment[k]
                for k in ("open_at", "due_at")
            }
        )
        validate_assignment(data, items)
        self.validate_items(actor, assignment["course_id"], items)
        self.store_items(aid, items)
        self.repo.change(
            "assignments",
            aid,
            **data,
            revision=assignment["revision"] + 1,
            updated_at=self.repo.now(),
        )
        self.effects.record(self.repo, actor["user_id"], "ASSIGNMENT_UPDATED", aid)
        return {"revision": assignment["revision"] + 1}

    def publish(self, actor: Record, aid: str, body: Record) -> Record:
        assignment, course = self.access(actor, aid, teacher=True, write=True)
        revision(assignment, body["expected_revision"])
        require(assignment["published_at"] is None, "ASSIGNMENT_IMMUTABLE", "作业已经发布。")
        items = [
            dict(
                problem_id=i["problem_id"], version_id=i["original_version_id"], points=i["points"]
            )
            for i in self.repo.rows("assignment_items", assignment_id=aid)
        ]
        validate_assignment(assignment, items)
        self.validate_items(actor, assignment["course_id"], items)
        updated = self.repo.change(
            "assignments",
            aid,
            published_at=self.repo.now(),
            revision=assignment["revision"] + 1,
            updated_at=self.repo.now(),
        )
        self.effects.record(
            self.repo,
            actor["user_id"],
            "ASSIGNMENT_PUBLISHED",
            aid,
            body["reason"],
            {"course_id": course["course_id"]},
        )
        return dict(state=assignment_state(updated, self.repo.now()), revision=updated["revision"])

    def controlled(self, actor: Record, aid: str, body: Record, action: str) -> Record:
        assignment, _ = self.access(actor, aid, teacher=True, write=True)
        revision(assignment, body["expected_revision"])
        require(
            assignment["published_at"] is not None,
            "ASSIGNMENT_DRAFT",
            "请使用草稿编辑修改未发布作业。",
        )
        if action == "DEADLINE_EXTENDED":
            require(
                assignment["active_rejudge_batch_id"] is None,
                "REJUDGE_ACTIVE",
                "活动重评期间不能延期。",
            )
        if self.coordination is None:
            raise Fault(503, "COORDINATION_UNAVAILABLE", "成绩与公平协调服务尚未接入。", retry=5)
        self.coordination.before_change(self.repo, assignment, action)
        now = self.repo.now()
        changes: Record = dict(revision=assignment["revision"] + 1, updated_at=now)
        if action == "DEADLINE_EXTENDED":
            due = datetime.fromisoformat(body["new_due_at"])
            require(
                due > assignment["due_at"] and due > now,
                "INVALID_DEADLINE",
                "新截止时间必须晚于原截止时间和当前时间。",
                422,
            )
            changes.update(
                due_at=due,
                grade_epoch=assignment["grade_epoch"] + (1 if now >= assignment["due_at"] else 0),
            )
            result = dict(
                old_due_at=utc(assignment["due_at"]),
                new_due_at=utc(due),
                revision=changes["revision"],
            )
        else:
            require(
                now < assignment["open_at"]
                or body["ai_policy"] == "DISABLED"
                or body["ai_policy"] == assignment["ai_policy"],
                "POLICY_RELAXATION_FORBIDDEN",
                "开放后只能收紧提示策略。",
            )
            changes["ai_policy"] = body["ai_policy"]
            result = {"revision": changes["revision"]}
        self.repo.change("assignments", aid, **changes)
        self.effects.record(self.repo, actor["user_id"], action, aid, body["reason"], result)
        return result

    def admission(self, actor: Record, aid: str, pid: str, language: str, intent: str) -> Record:
        """B calls inside shared guard/course/assignment locks before persisting receipt."""
        role(actor, ("STUDENT",))
        assignment, _ = self.access(actor, aid, write=True)
        now = self.repo.now()  # Database time AFTER lock, never transaction-start time.
        mode = submission_mode(assignment, now, intent)
        problem = self.problem(actor, aid, pid)
        require(
            language in {p["language_key"] for p in problem["profile"]["languages"]},
            "LANGUAGE_UNSUPPORTED",
            "此题不支持该语言。",
            422,
        )
        return dict(
            version_id=problem["version_id"],
            profile=problem["profile"],
            mode=mode,
            accepted_at=now,
            assignment_revision=assignment["revision"],
        )


def membership_changed(repo: Repository, course_id: str) -> None:
    """Controlled A write port for B's membership/account orchestration."""
    for value in repo.rows("assignments", course_id=course_id):
        if value["published_at"] is not None:
            repo.get("assignments", value["assignment_id"], lock=True)
            repo.change(
                "assignments",
                value["assignment_id"],
                grade_epoch=value["grade_epoch"] + 1,
                revision=value["revision"] + 1,
                updated_at=repo.now(),
            )
