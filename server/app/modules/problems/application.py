from __future__ import annotations

from hashlib import sha256
from uuid import uuid4

from app.modules.courses.application import Courses
from app.modules.identity.domain import Fault, require, revision, role, utc
from app.modules.identity.ports import Effects, Record, Repository

from .domain import (
    CONTENT_FIELDS,
    content_digest,
    publishable,
    validate_content,
    validate_text,
    verify_evidence,
)
from .ports import PreflightPort


class Problems:
    def __init__(self, repo: Repository, effects: Effects, preflight: PreflightPort | None = None):
        self.repo, self.effects, self.preflight = repo, effects, preflight
        self.courses = Courses(repo, effects)

    def problem(self, actor: Record, pid: str, *, write=False) -> Record:
        role(actor, ("TEACHER",))
        problem = self.repo.get("problems", pid)
        require(problem is not None, "NOT_FOUND", "题目不存在或无权访问。", 404)
        assert problem
        self.courses.access(actor, problem["owner_course_id"], teacher=True, write=write)
        return problem

    def version(self, actor: Record, vid: str, *, write=False) -> Record:
        role(actor, ("TEACHER",))
        version = self.repo.get("problem_versions", vid)
        require(version is not None, "NOT_FOUND", "版本不存在或无权访问。", 404)
        assert version
        self.problem(actor, version["problem_id"], write=write)
        if write:
            require(
                version["published_at"] is None,
                "VERSION_IMMUTABLE",
                "已发布版本不可修改，请复制新版本。",
            )
        return version

    def view(self, version: Record) -> Record:
        return {
            **{
                k: version[k]
                for k in ("version_id", "problem_id", *CONTENT_FIELDS, "revision", "checksum")
            },
            "published_at": utc(version["published_at"]) if version["published_at"] else None,
        }

    def visible(self, actor: Record, cid: str) -> list[Record]:
        self.courses.access(actor, cid, teacher=True)
        result = []
        for p in self.repo.rows("problems", owner_course_id=cid):
            versions = sorted(
                self.repo.rows("problem_versions", problem_id=p["problem_id"]),
                key=lambda v: v["version_no"],
            )
            result.append(
                {
                    **{
                        k: p[k]
                        for k in (
                            "problem_id",
                            "canonical_problem_id",
                            "owner_course_id",
                            "practice_released",
                            "practice_version_id",
                            "revision",
                        )
                    },
                    "title": versions[-1]["title"] if versions else "未命名题目",
                    "status": "PUBLISHED" if any(v["published_at"] for v in versions) else "DRAFT",
                }
            )
        return result

    def version_list(self, actor: Record, pid: str) -> list[Record]:
        self.problem(actor, pid)
        return [self.view(v) for v in self.repo.rows("problem_versions", problem_id=pid)]

    def create(self, actor: Record, body: Record) -> Record:
        self.courses.access(actor, body["course_id"], teacher=True, write=True)
        family_id = body.get("canonical_problem_id")
        if family_id:
            family = self.repo.get("problem_families", family_id)
            require(
                bool(family and family["owner_teacher_id"] == actor["user_id"]),
                "NOT_FOUND",
                "题目家族不存在或无权使用。",
                404,
            )
        else:
            family_id = str(uuid4())
            self.repo.add(
                "problem_families",
                dict(
                    canonical_problem_id=family_id,
                    owner_teacher_id=actor["user_id"],
                    label="新题目",
                ),
            )
        pid = str(uuid4())
        self.repo.add(
            "problems",
            dict(
                problem_id=pid,
                canonical_problem_id=family_id,
                owner_course_id=body["course_id"],
                practice_released=False,
                practice_version_id=None,
                revision=1,
                created_at=self.repo.now(),
                updated_at=self.repo.now(),
            ),
        )
        self.effects.record(self.repo, actor["user_id"], "PROBLEM_CREATED", pid)
        return dict(problem_id=pid, canonical_problem_id=family_id)

    def create_version(self, actor: Record, body: Record) -> Record:
        self.problem(actor, body["problem_id"], write=True)
        validate_content(body)
        base_id = body.get("base_version_id")
        if base_id:
            base = self.version(actor, base_id)
            require(
                base["problem_id"] == body["problem_id"],
                "VERSION_MISMATCH",
                "基础版本不属于当前题目。",
            )
        versions = self.repo.rows("problem_versions", problem_id=body["problem_id"])
        vid = str(uuid4())
        self.repo.add(
            "problem_versions",
            dict(
                version_id=vid,
                problem_id=body["problem_id"],
                version_no=max((v["version_no"] for v in versions), default=0) + 1,
                **{k: body[k] for k in CONTENT_FIELDS},
                checksum=None,
                published_at=None,
                published_preflight_id=None,
                revision=1,
                created_at=self.repo.now(),
                updated_at=self.repo.now(),
            ),
        )
        if base_id:
            for table, key in [
                ("testcases", "testcase_id"),
                ("reference_programs", "reference_id"),
            ]:
                for row in self.repo.rows(table, version_id=base_id):
                    self.repo.add(table, {**row, key: str(uuid4()), "version_id": vid})
        self.effects.record(self.repo, actor["user_id"], "VERSION_CREATED", vid)
        return dict(version_id=vid, revision=1)

    def update(self, actor: Record, vid: str, body: Record) -> Record:
        version = self.version(actor, vid, write=True)
        revision(version, body["expected_revision"])
        content: Record = {k: body.get(k, version[k]) for k in CONTENT_FIELDS}
        validate_content(content)
        allowed = {p["language_key"] for p in content["profile"]["languages"]}
        for ref in self.repo.rows("reference_programs", version_id=vid):
            if ref["language_key"] not in allowed:
                self.repo.remove("reference_programs", ref["reference_id"])
        self.repo.change(
            "problem_versions",
            vid,
            **content,
            revision=version["revision"] + 1,
            updated_at=self.repo.now(),
        )
        self.effects.record(self.repo, actor["user_id"], "VERSION_UPDATED", vid)
        return {"revision": version["revision"] + 1}

    def delete(self, actor: Record, vid: str, body: Record) -> None:
        version = self.version(actor, vid, write=True)
        revision(version, body["expected_revision"])
        for table, key in [("testcases", "testcase_id"), ("reference_programs", "reference_id")]:
            for row in self.repo.rows(table, version_id=vid):
                self.repo.remove(table, row[key])
        self.repo.remove("problem_versions", vid)
        self.effects.record(self.repo, actor["user_id"], "VERSION_DELETED", vid, body["reason"])

    def cases(self, vid: str) -> list[Record]:
        return [
            dict(
                testcase_id=c["testcase_id"],
                order=c["order"],
                input_text=bytes(c["input_blob"]).decode("utf-8"),
                answer_text=bytes(c["answer_blob"]).decode("utf-8"),
                input_sha256=c["input_sha256"],
                answer_sha256=c["answer_sha256"],
            )
            for c in sorted(self.repo.rows("testcases", version_id=vid), key=lambda c: c["order"])
        ]

    def references(self, vid: str) -> list[Record]:
        return [
            dict(
                reference_id=r["reference_id"],
                language_key=r["language_key"],
                code=bytes(r["code"]).decode("utf-8"),
                checksum=r["code_sha256"],
            )
            for r in sorted(
                self.repo.rows("reference_programs", version_id=vid),
                key=lambda r: r["language_key"],
            )
        ]

    def put_case(
        self, actor: Record, vid: str, order: int, body: Record, *, delete=False
    ) -> Record | None:
        require(1 <= order <= 10, "VALIDATION_ERROR", "测试编号应为1—10。", 422)
        version = self.version(actor, vid, write=True)
        revision(version, body["expected_revision"])
        old = self.repo.rows("testcases", version_id=vid, order=order)
        if delete:
            require(bool(old), "NOT_FOUND", "测试点不存在。", 404)
            self.repo.remove("testcases", old[0]["testcase_id"])
            result = None
        else:
            input_blob, answer_blob = (
                validate_text(body["input_text"], "测试输入"),
                validate_text(body["answer_text"], "测试答案"),
            )
            data = dict(
                input_blob=input_blob,
                answer_blob=answer_blob,
                input_sha256=sha256(input_blob).hexdigest(),
                answer_sha256=sha256(answer_blob).hexdigest(),
            )
            tid = old[0]["testcase_id"] if old else str(uuid4())
            if old:
                self.repo.change("testcases", tid, **data)
            else:
                self.repo.add(
                    "testcases", dict(testcase_id=tid, version_id=vid, order=order, **data)
                )
            result = dict(
                testcase_id=tid,
                input_sha256=data["input_sha256"],
                answer_sha256=data["answer_sha256"],
                revision=version["revision"] + 1,
            )
        self.repo.change(
            "problem_versions", vid, revision=version["revision"] + 1, updated_at=self.repo.now()
        )
        self.effects.record(
            self.repo,
            actor["user_id"],
            "TESTCASE_DELETED" if delete else "TESTCASE_UPDATED",
            vid,
            body.get("reason", ""),
        )
        return result

    def put_reference(self, actor: Record, vid: str, language: str, body: Record) -> Record:
        version = self.version(actor, vid, write=True)
        revision(version, body["expected_revision"])
        require(
            language in {p["language_key"] for p in version["profile"]["languages"]},
            "VALIDATION_ERROR",
            "语言不在当前运行环境中。",
            422,
        )
        code = validate_text(body["code"], "参考程序")
        require(bool(body["code"].strip()), "VALIDATION_ERROR", "参考程序不能为空白。", 422)
        old = self.repo.rows("reference_programs", version_id=vid, language_key=language)
        rid, checksum = old[0]["reference_id"] if old else str(uuid4()), sha256(code).hexdigest()
        if old:
            self.repo.change("reference_programs", rid, code=code, code_sha256=checksum)
        else:
            self.repo.add(
                "reference_programs",
                dict(
                    reference_id=rid,
                    version_id=vid,
                    language_key=language,
                    code=code,
                    code_sha256=checksum,
                ),
            )
        self.repo.change(
            "problem_versions", vid, revision=version["revision"] + 1, updated_at=self.repo.now()
        )
        self.effects.record(self.repo, actor["user_id"], "REFERENCE_UPDATED", vid)
        return dict(reference_id=rid, checksum=checksum, revision=version["revision"] + 1)

    def snapshot(self, vid: str) -> Record:
        version = self.repo.get("problem_versions", vid)
        require(version is not None, "NOT_FOUND", "版本不存在。", 404)
        assert version
        return {
            **version,
            "testcases": [
                {k: c[k] for k in ("order", "input_text", "answer_text")} for c in self.cases(vid)
            ],
            "references": [
                {k: r[k] for k in ("language_key", "code")} for r in self.references(vid)
            ],
        }

    def publish(self, actor: Record, vid: str, body: Record) -> Record:
        version = self.version(actor, vid, write=True)
        revision(version, body["expected_revision"])
        snapshot = self.snapshot(vid)
        publishable(snapshot)
        if self.preflight is None:
            raise Fault(503, "PREFLIGHT_UNAVAILABLE", "预检服务尚未接入，暂时不能发布。", retry=5)
        verify_evidence(snapshot, self.preflight.evidence(self.repo, body["preflight_id"]))
        checksum, now = content_digest(snapshot), self.repo.now()
        self.repo.change(
            "problem_versions",
            vid,
            checksum=checksum,
            published_at=now,
            published_preflight_id=body["preflight_id"],
            revision=version["revision"] + 1,
            updated_at=now,
        )
        self.effects.record(
            self.repo,
            actor["user_id"],
            "VERSION_PUBLISHED",
            vid,
            body["reason"],
            {"checksum": checksum, "preflight_id": body["preflight_id"]},
        )
        return dict(published_at=utc(now), checksum=checksum)
