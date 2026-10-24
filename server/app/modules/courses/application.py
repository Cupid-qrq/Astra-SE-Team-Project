from __future__ import annotations

from uuid import uuid4

from app.modules.identity.domain import require, revision, role
from app.modules.identity.ports import Effects, Record, Repository

COURSE_FIELDS = ("course_id", "title", "teacher_id", "status", "revision")


def public_course(course: Record) -> Record:
    return {key: course[key] for key in COURSE_FIELDS}


class Courses:
    def __init__(self, repo: Repository, effects: Effects):
        self.repo, self.effects = repo, effects

    def access(
        self, actor: Record, course_id: str, *, teacher: bool = False, write: bool = False
    ) -> Record:
        role(actor, ("TEACHER",) if teacher else ("TEACHER", "STUDENT"))
        course = self.repo.get("courses", course_id, lock=write)
        require(course is not None, "NOT_FOUND", "课程不存在或无权访问。", 404)
        assert course
        allowed = (
            course["teacher_id"] == actor["user_id"]
            if actor["role"] == "TEACHER"
            else any(
                m["status"] == "ACTIVE"
                for m in self.repo.rows(
                    "course_members", course_id=course_id, user_id=actor["user_id"]
                )
            )
        )
        require(allowed, "NOT_FOUND", "课程不存在或无权访问。", 404)
        require(not write or course["status"] == "ACTIVE", "COURSE_ARCHIVED", "归档课程不可修改。")
        return course

    def visible(self, actor: Record) -> list[Record]:
        role(actor, ("TEACHER", "STUDENT"))
        if actor["role"] == "TEACHER":
            rows = self.repo.rows("courses", teacher_id=actor["user_id"])
        else:
            ids = [
                m["course_id"]
                for m in self.repo.rows("course_members", user_id=actor["user_id"], status="ACTIVE")
            ]
            rows = self.repo.rows("courses", course_id=ids) if ids else []
        return [public_course(c) for c in rows]

    def create(self, actor: Record, body: Record) -> Record:
        role(actor, ("TEACHER",))
        now = self.repo.now()
        course = self.repo.add(
            "courses",
            dict(
                course_id=str(uuid4()),
                teacher_id=actor["user_id"],
                title=body["title"],
                status="ACTIVE",
                revision=1,
                archived_at=None,
                created_at=now,
                updated_at=now,
            ),
        )
        self.effects.record(self.repo, actor["user_id"], "COURSE_CREATED", course["course_id"])
        return {"course_id": course["course_id"], "revision": 1}

    def update(self, actor: Record, course_id: str, body: Record) -> Record:
        course = self.access(actor, course_id, teacher=True, write=True)
        revision(course, body["expected_revision"])
        result = self.repo.change(
            "courses",
            course_id,
            title=body["title"],
            revision=course["revision"] + 1,
            updated_at=self.repo.now(),
        )
        self.effects.record(self.repo, actor["user_id"], "COURSE_UPDATED", course_id)
        return public_course(result)

    def members(self, actor: Record, course_id: str) -> list[Record]:
        self.access(actor, course_id, teacher=True)
        return [
            dict(
                user_id=m["user_id"],
                display_name=(self.repo.get("users", m["user_id"]) or {})["display_name"],
                status=m["status"],
            )
            for m in self.repo.rows("course_members", course_id=course_id)
        ]

    def member(self, actor: Record, course_id: str, user_id: str, body: Record) -> Record:
        course = self.access(actor, course_id, teacher=True, write=True)
        revision(course, body["expected_revision"])
        user = self.repo.get("users", user_id)
        require(bool(user and user["role"] == "STUDENT"), "NOT_FOUND", "学生账号不存在。", 404)
        assert user
        require(
            body["status"] != "ACTIVE" or user["status"] == "ACTIVE",
            "USER_DISABLED",
            "停用账号不能加入课程。",
        )
        previous = self.repo.get("course_members", (course_id, user_id))
        if previous:
            self.repo.change("course_members", (course_id, user_id), status=body["status"])
        else:
            self.repo.add(
                "course_members",
                dict(
                    course_id=course_id,
                    user_id=user_id,
                    status=body["status"],
                    joined_at=self.repo.now(),
                ),
            )
        if previous is None or previous["status"] != body["status"]:
            self.effects.membership_changed(self.repo, course_id)
        self.repo.change(
            "courses", course_id, revision=course["revision"] + 1, updated_at=self.repo.now()
        )
        self.effects.record(
            self.repo,
            actor["user_id"],
            "MEMBER_UPDATED",
            course_id,
            summary={"user_id": user_id, "status": body["status"]},
        )
        return dict(user_id=user_id, status=body["status"], revision=course["revision"] + 1)
