"""Manage frozen template publications. Activation requires separate deployment evidence."""

import re
from uuid import uuid4

from app.modules.identity.domain import byte_limit, require, role, utc
from app.modules.identity.ports import Record
from app.modules.problems.domain import canonical_hash

from .feedback import ScopedManagement

PLACEHOLDERS = frozenset(
    (
        "public_problem",
        "public_samples",
        "student_code",
        "sanitized_diagnostic",
        "verdict",
        "question",
    )
)
TOKEN = re.compile(r"\{([a-z_]+)\}")
FIELDS = ("body", "allowed_placeholders", "schema_version")


def validate_template(draft: Record) -> None:
    body = draft["body"]
    allowed = draft["allowed_placeholders"]
    byte_limit(body, 8192, "模板正文")
    byte_limit(draft["schema_version"], 160, "结构版本")
    require(
        bool(body.strip())
        and "\x00" not in body
        and "\x00" not in draft["schema_version"]
        and bool(draft["schema_version"].strip()),
        "VALIDATION_ERROR",
        "模板正文不能为空且不超过 8 KiB，必须指定结构版本。",
        422,
    )
    plain = TOKEN.sub("", body)
    require(
        len(set(allowed)) == len(allowed)
        and set(allowed) <= PLACEHOLDERS
        and "{" not in plain
        and "}" not in plain
        and set(TOKEN.findall(body)) <= set(allowed),
        "VALIDATION_ERROR",
        "仅支持已声明的 {name} 占位符。",
        422,
    )


def template_summary(row: Record) -> Record:
    scope = row["scope_key"]
    return dict(
        template_id=row["template_id"],
        scope="GLOBAL" if scope == "GLOBAL" else "COURSE",
        course_id=None if scope == "GLOBAL" else scope.removeprefix("COURSE:"),
        revision=row["draft_revision"],
    )


def template_version_summary(row: Record) -> Record:
    return {
        **{key: row[key] for key in ("version_id", "version_no", "checksum")},
        "published_at": utc(row["published_at"]),
    }


class TemplateManagement(ScopedManagement):
    def catalogs(self, actor: Record, course_id: str | None) -> list[Record]:
        return [
            template_summary(row) for row in self.scoped_rows("template_catalogs", actor, course_id)
        ]

    def create_catalog(self, actor: Record, body: Record) -> Record:
        role(actor, ("TEACHER", "ADMIN"))
        self.repo.guard()
        if body["scope"] == "GLOBAL":
            role(actor, ("ADMIN",))
            require("course_id" not in body, "VALIDATION_ERROR", "全局模板不绑定课程。", 422)
            scope = "GLOBAL"
        else:
            role(actor, ("TEACHER",))
            require(bool(body.get("course_id")), "VALIDATION_ERROR", "请选择所属课程。", 422)
            course = self.courses.access(actor, body["course_id"], teacher=True, write=True)
            scope = "COURSE:" + course["course_id"]
        validate_template(body["draft"])
        require(
            not self.repo.rows("template_catalogs", scope_key=scope),
            "TEMPLATE_EXISTS",
            "此范围已有模板，请编辑已有草稿。",
        )
        tid = str(uuid4())
        self.repo.add(
            "template_catalogs",
            dict(template_id=tid, scope_key=scope, draft_payload=body["draft"], draft_revision=1),
        )
        self.effects.record(self.repo, actor["user_id"], "TEMPLATE_CREATED", tid)
        return dict(template_id=tid, revision=1)

    def draft(self, actor: Record, tid: str) -> Record:
        row = self.managed("template_catalogs", actor, tid)
        summary = template_summary(row)
        course = self.repo.get("courses", summary["course_id"]) if summary["course_id"] else None
        published = (
            self.repo.get("template_versions", row["published_version_id"])
            if row["published_version_id"]
            else None
        )
        return {
            **summary,
            **row["draft_payload"],
            "course_status": course["status"] if course else None,
            "published_version_id": row["published_version_id"],
            "published_version_no": published["version_no"] if published else None,
        }

    def for_revision(self, actor: Record, tid: str, revision: int) -> Record:
        row = self.managed("template_catalogs", actor, tid, write=True)
        require(
            row["draft_revision"] == revision,
            "REVISION_CONFLICT",
            "内容已被修改，请重新载入后核对。",
        )
        return row

    def save_draft(self, actor: Record, tid: str, body: Record) -> Record:
        row = self.for_revision(actor, tid, body["expected_revision"])
        payload = {k: body[k] for k in FIELDS}
        validate_template(payload)
        revision = row["draft_revision"] + 1
        self.repo.change("template_catalogs", tid, draft_payload=payload, draft_revision=revision)
        self.effects.record(self.repo, actor["user_id"], "TEMPLATE_DRAFT_SAVED", tid)
        return dict(revision=revision)

    def publish(self, actor: Record, tid: str, body: Record) -> Record:
        row = self.for_revision(actor, tid, body["expected_revision"])
        byte_limit(body["reason"], 2000, "发布理由")
        require(
            "\x00" not in body["reason"] and 10 <= len(body["reason"].strip()) <= 500,
            "VALIDATION_ERROR",
            "发布理由需要10—500字。",
            422,
        )
        payload = row["draft_payload"]
        validate_template(payload)
        digest = canonical_hash(payload)
        previous = (
            self.repo.get("template_versions", row["published_version_id"])
            if row["published_version_id"]
            else None
        )
        vid = str(uuid4())
        self.repo.add(
            "template_versions",
            dict(
                version_id=vid,
                template_id=tid,
                version_no=previous["version_no"] + 1 if previous else 1,
                **payload,
                author_id=actor["user_id"],
                published_at=self.repo.now(),
                checksum=digest,
            ),
        )
        self.repo.change(
            "template_catalogs",
            tid,
            published_version_id=vid,
            draft_revision=row["draft_revision"] + 1,
        )
        result = dict(version_id=vid, checksum=digest)
        self.effects.record(
            self.repo,
            actor["user_id"],
            "TEMPLATE_PUBLISHED",
            tid,
            reason=body["reason"],
            summary=result,
        )
        return result

    def history(self, actor: Record, tid: str) -> list[Record]:
        self.managed("template_catalogs", actor, tid)
        return [
            template_version_summary(row)
            for row in self.repo.rows("template_versions", template_id=tid)
        ]

    def version(self, actor: Record, tid: str, number: str) -> Record:
        self.managed("template_catalogs", actor, tid)
        require(
            number.isascii()
            and number.isdigit()
            and len(number) <= 10
            and 0 < int(number) <= 2147483647,
            "VALIDATION_ERROR",
            "版本号必须为正整数。",
            422,
        )
        rows = self.repo.rows("template_versions", template_id=tid, version_no=int(number))
        require(bool(rows), "NOT_FOUND", "模板版本不存在。", 404)
        return {**template_version_summary(rows[0]), **{key: rows[0][key] for key in FIELDS}}
