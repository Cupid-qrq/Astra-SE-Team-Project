"""Discussion authorization and mutations share the caller-owned transaction."""

from datetime import timedelta
from uuid import UUID, uuid4

from app.modules.courses.application import Courses
from app.modules.identity.domain import require, revision, utc
from app.modules.learning.student import StudentLearning
from app.shared.effects import TransactionalEffects
from app.shared.repository import SqlRepository

from . import discussion_models  # noqa: F401


def text(value, maximum):
    require(isinstance(value, str), "VALIDATION_ERROR", "内容必须是文本。", 422)
    value = value.strip()
    require(
        1 <= len(value) <= maximum and not any(ord(c) < 32 and c not in "\n\r\t" for c in value),
        "VALIDATION_ERROR",
        "内容为空、过长或含控制字符。",
        422,
    )
    try:
        value.encode("utf-8")
    except UnicodeEncodeError:
        require(False, "VALIDATION_ERROR", "文本编码无效。", 422)
    return value


def fields(body, required, optional=()):
    require(
        isinstance(body, dict)
        and set(required) <= body.keys()
        and body.keys() <= set(required) | set(optional),
        "VALIDATION_ERROR",
        "请求字段不完整或包含未知字段。",
        422,
    )


class Discussions:
    def __init__(self, repo: SqlRepository, effects: TransactionalEffects) -> None:
        self.repo, self.effects = repo, effects
        self.courses = Courses(repo, effects)

    def _actor(self, actor):
        user = self.repo.get("users", actor.get("user_id"))
        require(
            user is not None and user["status"] == "ACTIVE", "FORBIDDEN", "当前账号不可访问。", 403
        )
        return user

    def _access(self, actor, cid, pid, vid, *, write=False):
        actor = self._actor(actor)
        self.courses.access(actor, cid, write=write)
        problem = self.repo.get("problems", pid)
        version = self.repo.get("problem_versions", vid)
        require(
            bool(
                problem
                and problem["owner_course_id"] == cid
                and version
                and version["problem_id"] == pid
                and version["published_at"]
            ),
            "NOT_FOUND",
            "题目版本不存在或不可访问。",
            404,
        )
        if actor["role"] == "STUDENT":
            now = self.repo.now()
            allowed = False
            for item in self.repo.rows(
                "assignment_items", problem_id=pid, effective_version_id=vid
            ):
                assignment = self.repo.get("assignments", item["assignment_id"])
                if (
                    assignment
                    and assignment["course_id"] == cid
                    and assignment["published_at"]
                    and assignment["open_at"] <= now
                ):
                    allowed = True
                    break
            if not allowed:
                query = StudentLearning(
                    self.repo.connection, self.repo, self.effects, None
                ).practice_candidates(actor, cid)
                allowed = any(
                    row["version_id"] == vid
                    for row in self.repo.connection.execute(query).mappings()
                )
            require(allowed, "NOT_FOUND", "题目版本尚未开放或不可访问。", 404)
        return actor

    def _thread(self, actor, tid, *, write=False):
        thread = self.repo.get("discussion_threads", tid, lock=write)
        require(thread is not None, "NOT_FOUND", "讨论不存在或不可访问。", 404)
        assert thread is not None
        actor = self._access(
            actor, thread["course_id"], thread["problem_id"], thread["version_id"], write=write
        )
        return actor, thread

    def _reply_view(self, actor, row):
        author = self.repo.required("users", row["author_id"])
        return dict(
            reply_id=row["reply_id"],
            thread_id=row["thread_id"],
            body=row["body"] if not row["hidden"] or actor["role"] == "TEACHER" else "",
            author_name=author["display_name"],
            is_mine=actor["user_id"] == row["author_id"],
            hidden=row["hidden"],
            revision=row["revision"],
            created_at=utc(row["created_at"]),
        )

    def _view(self, actor, row):
        author = self.repo.required("users", row["author_id"])
        visible = not row["hidden"] or actor["role"] == "TEACHER"
        return dict(
            **{
                k: row[k]
                for k in (
                    "thread_id",
                    "course_id",
                    "problem_id",
                    "version_id",
                    "resolved",
                    "locked",
                    "pinned",
                    "hidden",
                    "revision",
                )
            },
            title=row["title"] if visible else "已隐藏的讨论",
            body=row["body"] if visible else "",
            author_name=author["display_name"],
            is_mine=actor["user_id"] == row["author_id"],
            can_moderate=actor["role"] == "TEACHER",
            reply_count=len(self.repo.rows("discussion_replies", thread_id=row["thread_id"]))
            if visible
            else 0,
            created_at=utc(row["created_at"]),
            updated_at=utc(row["updated_at"]),
        )

    def list(self, actor, course_id, problem_id, version_id):
        actor = self._access(actor, course_id, problem_id, version_id)
        return [
            self._view(actor, row)
            for row in self.repo.rows(
                "discussion_threads",
                course_id=course_id,
                problem_id=problem_id,
                version_id=version_id,
            )
        ]

    def _rate(self, actor, cid):
        # All writers hold policy_guard before checking the combined post/reply history.
        now = self.repo.now()
        entries = [
            (r["created_at"], r["course_id"])
            for r in self.repo.rows("discussion_threads", author_id=actor["user_id"])
        ]
        for row in self.repo.rows("discussion_replies", author_id=actor["user_id"]):
            thread = self.repo.required("discussion_threads", row["thread_id"])
            entries.append((row["created_at"], thread["course_id"]))
        require(
            all(now >= at + timedelta(seconds=10) for at, _ in entries),
            "DISCUSSION_INTERVAL",
            "发帖或回复间隔至少10秒。",
            429,
        )
        require(
            sum(1 for at, course in entries if course == cid and at > now - timedelta(hours=1))
            < 30,
            "DISCUSSION_HOURLY_LIMIT",
            "每课程每小时最多30条。",
            429,
        )
        return now

    def create(self, actor, course_id, problem_id, body):
        fields(body, ("version_id", "title", "body"))
        title, content = text(body["title"], 120), text(body["body"], 4000)
        try:
            vid = str(UUID(body["version_id"]))
        except (ValueError, TypeError, AttributeError):
            require(False, "VALIDATION_ERROR", "版本编号无效。", 422)
        self.repo.guard()
        actor = self._access(actor, course_id, problem_id, vid, write=True)
        now = self._rate(actor, course_id)
        row = self.repo.add(
            "discussion_threads",
            dict(
                thread_id=str(uuid4()),
                course_id=course_id,
                problem_id=problem_id,
                version_id=vid,
                author_id=actor["user_id"],
                title=title,
                body=content,
                resolved=False,
                locked=False,
                pinned=False,
                hidden=False,
                revision=1,
                created_at=now,
                updated_at=now,
            ),
        )
        self.effects.record(self.repo, actor["user_id"], "DISCUSSION_CREATED", row["thread_id"])
        return self._view(actor, row)

    def read(self, actor, id):
        actor, row = self._thread(actor, id)
        replies = (
            self.repo.rows("discussion_replies", thread_id=id)
            if not row["hidden"] or actor["role"] == "TEACHER"
            else []
        )
        return dict(
            thread=self._view(actor, row), replies=[self._reply_view(actor, r) for r in replies]
        )

    def reply(self, actor, id, body):
        fields(body, ("body",))
        content = text(body["body"], 4000)
        self.repo.guard()
        actor, thread = self._thread(actor, id, write=True)
        require(
            not thread["locked"] and not thread["hidden"], "DISCUSSION_LOCKED", "讨论已锁定或隐藏。"
        )
        now = self._rate(actor, thread["course_id"])
        row = self.repo.add(
            "discussion_replies",
            dict(
                reply_id=str(uuid4()),
                thread_id=id,
                author_id=actor["user_id"],
                body=content,
                hidden=False,
                revision=1,
                created_at=now,
            ),
        )
        self.repo.change("discussion_threads", id, updated_at=now)
        self.effects.record(self.repo, actor["user_id"], "DISCUSSION_REPLIED", row["reply_id"])
        return self._reply_view(actor, row)

    def _changes(self, body, allowed):
        fields(body, ("expected_revision", "reason"), allowed)
        changes = {k: body[k] for k in allowed if k in body}
        require(
            bool(changes) and all(type(v) is bool for v in changes.values()),
            "VALIDATION_ERROR",
            "至少指定一个布尔状态。",
            422,
        )
        require(
            type(body["expected_revision"]) is int and body["expected_revision"] > 0,
            "VALIDATION_ERROR",
            "版本号无效。",
            422,
        )
        reason = text(body["reason"], 500)
        require(len(reason) >= 10, "VALIDATION_ERROR", "理由至少10字。", 422)
        return changes, reason

    def update(self, actor, id, body):
        changes, reason = self._changes(body, ("resolved", "locked", "pinned", "hidden"))
        self.repo.guard()
        actor, thread = self._thread(actor, id, write=True)
        revision(thread, body["expected_revision"])
        teacher = actor["role"] == "TEACHER"
        require(
            teacher or actor["user_id"] == thread["author_id"],
            "FORBIDDEN",
            "仅作者或教师可以管理讨论。",
            403,
        )
        require(
            teacher or not set(changes) & {"locked", "pinned"},
            "FORBIDDEN",
            "仅教师可以锁定或置顶。",
            403,
        )
        require(
            teacher or changes.get("hidden") is not False,
            "FORBIDDEN",
            "仅教师可以恢复隐藏内容。",
            403,
        )
        row = self.repo.change(
            "discussion_threads",
            id,
            **changes,
            revision=thread["revision"] + 1,
            updated_at=self.repo.now(),
        )
        self.effects.record(
            self.repo, actor["user_id"], "DISCUSSION_UPDATED", id, reason=reason, summary=changes
        )
        return self._view(actor, row)

    def update_reply(self, actor, id, body):
        changes, reason = self._changes(body, ("hidden",))
        self.repo.guard()
        row = self.repo.get("discussion_replies", id, lock=True)
        require(row is not None, "NOT_FOUND", "回复不存在或不可访问。", 404)
        assert row is not None
        actor, _ = self._thread(actor, row["thread_id"], write=True)
        revision(row, body["expected_revision"])
        require(
            actor["role"] == "TEACHER" or actor["user_id"] == row["author_id"],
            "FORBIDDEN",
            "仅作者或教师可以管理回复。",
            403,
        )
        require(
            actor["role"] == "TEACHER" or changes.get("hidden") is not False,
            "FORBIDDEN",
            "仅教师可以恢复隐藏内容。",
            403,
        )
        updated = self.repo.change(
            "discussion_replies", id, **changes, revision=row["revision"] + 1
        )
        self.effects.record(
            self.repo,
            actor["user_id"],
            "DISCUSSION_REPLY_UPDATED",
            id,
            reason=reason,
            summary=changes,
        )
        return self._reply_view(actor, updated)
