"""Versioned fixed-help management; all effects share the caller's transaction."""

from uuid import uuid4

from app.modules.courses.application import Courses
from app.modules.identity.domain import require, role, utc
from app.modules.identity.ports import Effects, Record, Repository

from .domain import checksum, validate_body


def catalog_summary(row: Record) -> Record:
    course_id = row["scope_key"].removeprefix("COURSE:") if row["scope_key"] != "GLOBAL" else None
    return dict(
        catalog_id=row["catalog_id"],
        scope="COURSE" if course_id else "GLOBAL",
        course_id=course_id,
        title=row["draft_payload"]["title"],
        revision=row["draft_revision"],
    )


def version_summary(row: Record) -> Record:
    return {
        **{k: row[k] for k in ("version_id", "version_no", "title", "checksum")},
        "published_at": utc(row["published_at"]),
    }


class FeedbackManagement:
    def __init__(self, repo: Repository, effects: Effects):
        self.repo, self.effects, self.courses = repo, effects, Courses(repo, effects)

    def managed_catalog(self, actor: Record, catalog_id: str, *, write: bool = False) -> Record:
        role(actor, ("TEACHER", "ADMIN"))
        if write:
            self.repo.guard()
        row = self.repo.get("feedback_catalogs", catalog_id)
        require(row is not None, "NOT_FOUND", "帮助不存在或无权管理。", 404)
        assert row
        if row["scope_key"] == "GLOBAL":
            role(actor, ("ADMIN",))
        else:
            self.courses.access(
                actor, row["scope_key"].removeprefix("COURSE:"), teacher=True, write=write
            )
        if write:
            row = self.repo.get("feedback_catalogs", catalog_id, lock=True)
            assert row
        return row

    def catalogs(self, actor: Record, course_id: str | None = None) -> list[Record]:
        """Standalone host only; formal HTTP uses authorized SQL pagination."""
        role(actor, ("TEACHER", "ADMIN"))
        if actor["role"] == "ADMIN":
            require(course_id is None, "FORBIDDEN", "管理员只能维护全局帮助。", 403)
            rows = self.repo.rows("feedback_catalogs", scope_key="GLOBAL")
        else:
            if course_id:
                self.courses.access(actor, course_id, teacher=True)
                courses = [course_id]
            else:
                courses = [c["course_id"] for c in self.courses.visible(actor)]
            scopes = ["COURSE:" + cid for cid in courses]
            rows = self.repo.rows("feedback_catalogs", scope_key=scopes) if scopes else []
        return [catalog_summary(row) for row in rows]

    def create_catalog(self, actor: Record, body: Record) -> Record:
        role(actor, ("TEACHER", "ADMIN"))
        self.repo.guard()
        if body["scope"] == "GLOBAL":
            role(actor, ("ADMIN",))
            require(
                "course_id" not in body and body["language_key"] == "ALL",
                "VALIDATION_ERROR",
                "全局帮助使用通用语言且不绑定课程。",
                422,
            )
            scope = "GLOBAL"
        else:
            role(actor, ("TEACHER",))
            require(bool(body.get("course_id")), "VALIDATION_ERROR", "请选择所属课程。", 422)
            course = self.courses.access(actor, body["course_id"], teacher=True, write=True)
            scope = "COURSE:" + course["course_id"]
        validate_body(body["draft"])
        require(
            not self.repo.rows(
                "feedback_catalogs",
                scope_key=scope,
                verdict=body["verdict"],
                language_key=body["language_key"],
            ),
            "FEEDBACK_EXISTS",
            "该范围、判定和语言的帮助已存在，请编辑已有草稿。",
        )
        cid = str(uuid4())
        self.repo.add(
            "feedback_catalogs",
            dict(
                catalog_id=cid,
                scope_key=scope,
                verdict=body["verdict"],
                language_key=body["language_key"],
                draft_payload=body["draft"],
                draft_revision=1,
                active_version_id=None,
            ),
        )
        self.effects.record(self.repo, actor["user_id"], "FEEDBACK_CREATED", cid)
        return dict(catalog_id=cid, revision=1)

    def draft(self, actor: Record, catalog_id: str) -> Record:
        row = self.managed_catalog(actor, catalog_id)
        summary = catalog_summary(row)
        active = (
            self.repo.get("feedback_versions", row["active_version_id"])
            if row["active_version_id"]
            else None
        )
        course = self.repo.get("courses", summary["course_id"]) if summary["course_id"] else None
        return {
            **summary,
            **row["draft_payload"],
            "verdict": row["verdict"],
            "language_key": row["language_key"],
            "active_version_id": row["active_version_id"],
            "active_version_no": active["version_no"] if active else None,
            "course_status": course["status"] if course else None,
        }

    def save_draft(self, actor: Record, catalog_id: str, body: Record) -> Record:
        row = self.managed_catalog(actor, catalog_id, write=True)
        require(
            row["draft_revision"] == body["expected_revision"],
            "REVISION_CONFLICT",
            "内容已被修改，请重新载入后核对。",
        )
        payload = {key: body[key] for key in ("title", "explanation", "checklist")}
        validate_body(payload)
        revision = row["draft_revision"] + 1
        self.repo.change(
            "feedback_catalogs", catalog_id, draft_payload=payload, draft_revision=revision
        )
        self.effects.record(self.repo, actor["user_id"], "FEEDBACK_DRAFT_SAVED", catalog_id)
        return dict(revision=revision)

    def publish(self, actor: Record, catalog_id: str, body: Record) -> Record:
        row = self.managed_catalog(actor, catalog_id, write=True)
        require(
            row["draft_revision"] == body["expected_revision"],
            "REVISION_CONFLICT",
            "内容已被修改，请重新载入后核对。",
        )
        require(
            10 <= len(body["reason"].strip()) <= 500,
            "VALIDATION_ERROR",
            "发布理由需要10—500字。",
            422,
        )
        digest = checksum(row["draft_payload"])
        previous = (
            self.repo.get("feedback_versions", row["active_version_id"])
            if row["active_version_id"]
            else None
        )
        number = previous["version_no"] + 1 if previous else 1
        vid = str(uuid4())
        self.repo.add(
            "feedback_versions",
            dict(
                version_id=vid,
                catalog_id=catalog_id,
                version_no=number,
                **row["draft_payload"],
                author_id=actor["user_id"],
                published_at=self.repo.now(),
                checksum=digest,
            ),
        )
        self.repo.change(
            "feedback_catalogs",
            catalog_id,
            active_version_id=vid,
            draft_revision=row["draft_revision"] + 1,
        )
        self.effects.record(
            self.repo,
            actor["user_id"],
            "FEEDBACK_PUBLISHED",
            catalog_id,
            reason=body["reason"],
            summary=dict(version_id=vid, checksum=digest),
        )
        return dict(version_id=vid, checksum=digest)

    def history(self, actor: Record, catalog_id: str) -> list[Record]:
        """Standalone host only; formal HTTP uses authorized SQL pagination."""
        self.managed_catalog(actor, catalog_id)
        return [
            version_summary(row)
            for row in self.repo.rows("feedback_versions", catalog_id=catalog_id)
        ]
