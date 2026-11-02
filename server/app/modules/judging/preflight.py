"""A-compatible transactional preflight port. No HTTP, network, completion or execution."""

import json
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError

from app.adapters.judge_profiles import ProfileCatalog
from app.modules.identity.domain import Fault
from app.modules.identity.ports import Effects, Record, Repository
from app.modules.judging.domain import freeze_snapshot
from app.modules.judging.models import cases, runs
from app.modules.problems.application import Problems
from app.shared.judge import ExecutionError, uuid_value
from app.shared.repository import SqlRepository


def _uuid(value: str) -> str:
    try:
        return uuid_value(value)
    except ExecutionError:
        pass
    raise Fault(404, "NOT_FOUND", "预检记录不存在或无权访问。")


class TransactionalPreflight:
    def __init__(self, repo: SqlRepository, catalog: ProfileCatalog, effects: Effects) -> None:
        self.repo, self.catalog, self.effects = repo, catalog, effects

    def _check(self, repo: Repository) -> None:
        if repo is not self.repo or not self.repo.connection.in_transaction():
            raise RuntimeError("Preflight requires the same repository and active transaction.")

    def _actor(self, actor: Record) -> Record:
        user = self.repo.get("users", _uuid(actor.get("user_id", "")))
        if user is None or user["status"] != "ACTIVE" or user["role"] != "TEACHER":
            raise Fault(403, "FORBIDDEN", "当前账号无权访问预检任务。")
        return user

    def _public_run(self, pid: str) -> Record | None:
        columns = [
            runs.c.preflight_id,
            runs.c.version_id,
            runs.c.content_digest,
            runs.c.profile_hash,
            runs.c.state,
        ]
        row = (
            self.repo.connection.execute(select(*columns).where(runs.c.preflight_id == pid))
            .mappings()
            .first()
        )
        return dict(row) if row is not None else None

    def _cases(self, pid: str) -> list[Record]:
        columns = [
            cases.c.language_key,
            cases.c.case_kind,
            cases.c.case_order,
            cases.c.state,
            cases.c.verdict,
        ]
        query = (
            select(*columns)
            .where(cases.c.preflight_id == pid)
            .order_by(cases.c.language_key, cases.c.case_kind, cases.c.case_order)
        )
        return [dict(row) for row in self.repo.connection.execute(query).mappings()]

    def enqueue(self, repo: Repository, actor: Record, version_id: str) -> Record:
        self._check(repo)
        try:
            self.repo.guard()
            teacher = self._actor(actor)
            vid = _uuid(version_id)
            problems = Problems(self.repo, self.effects)
            problems.version(teacher, vid, write=True)
            self.repo.get("problem_versions", vid, lock=True)
            plan = freeze_snapshot(problems.snapshot(vid), self.catalog)
            query = select(runs.c.preflight_id, runs.c.state, runs.c.content_digest).where(
                runs.c.version_id == vid,
                runs.c.content_digest == plan.content_digest,
                runs.c.profile_hash == plan.profile_hash,
                runs.c.state.in_(["QUEUED", "RUNNING"]),
            )
            existing = self.repo.connection.execute(query).mappings().first()
            if existing is not None:
                return dict(existing)
            pid, now = str(uuid4()), self.repo.now()
            self.repo.add(
                "preflight_runs",
                dict(
                    preflight_id=pid,
                    version_id=vid,
                    version_revision=plan.version_revision,
                    content_digest=plan.content_digest,
                    profile_hash=plan.profile_hash,
                    frozen_blob=plan.blob,
                    state="QUEUED",
                    created_by=teacher["user_id"],
                    created_at=now,
                    started_at=None,
                    finished_at=None,
                ),
            )
            for language, kind, order in plan.cases:
                self.repo.add(
                    "preflight_cases",
                    dict(
                        preflight_id=pid,
                        language_key=language,
                        case_kind=kind,
                        case_order=order,
                        state="QUEUED",
                        verdict=None,
                        engine_meta={},
                    ),
                )
            self.repo.add(
                "preflight_jobs",
                dict(job_id=str(uuid4()), preflight_id=pid, state="READY", ready_at=now),
            )
            self.effects.record(
                self.repo,
                teacher["user_id"],
                "PREFLIGHT_QUEUED",
                pid,
                summary={
                    "version_id": vid,
                    "content_digest": plan.content_digest,
                    "profile_hash": plan.profile_hash,
                },
            )
            return dict(preflight_id=pid, state="QUEUED", content_digest=plan.content_digest)
        except SQLAlchemyError:
            pass
        raise Fault(
            503, "PREFLIGHT_STORAGE_UNAVAILABLE", "预检任务暂时不可用，请稍后重试。", retry=5
        )

    def read(self, repo: Repository, actor: Record, preflight_id: str) -> Record:
        self._check(repo)
        try:
            self.repo.guard()
            teacher = self._actor(actor)
            pid = _uuid(preflight_id)
            value = self._public_run(pid)
            if value is None:
                raise Fault(404, "NOT_FOUND", "预检记录不存在或无权访问。")
            Problems(self.repo, self.effects).version(teacher, value["version_id"])
            return {**value, "cases": self._cases(pid)}
        except SQLAlchemyError:
            pass
        raise Fault(
            503, "PREFLIGHT_STORAGE_UNAVAILABLE", "预检任务暂时不可用，请稍后重试。", retry=5
        )

    def evidence(self, repo: Repository, preflight_id: str) -> Record | None:
        self._check(repo)
        try:
            self.repo.guard()
            pid = _uuid(preflight_id)
            value = self._public_run(pid)
            if value is None or value["state"] != "PASSED":
                return None
            rows = self._cases(pid)
            blob = self.repo.connection.execute(
                select(runs.c.frozen_blob).where(runs.c.preflight_id == pid)
            ).scalar_one()
            try:
                plan = freeze_snapshot(json.loads(bytes(blob)), self.catalog)
            except (Fault, ValueError, TypeError):
                return None
            actual = {(r["language_key"], r["case_kind"], r["case_order"]) for r in rows}
            if (
                plan.version_id != value["version_id"]
                or plan.content_digest != value["content_digest"]
                or plan.profile_hash != value["profile_hash"]
                or actual != set(plan.cases)
                or len(rows) != len(plan.cases)
                or not all(r["state"] == "FINISHED" and r["verdict"] == "AC" for r in rows)
            ):
                return None
            return {**value, "cases": rows}
        except SQLAlchemyError:
            pass
        raise Fault(
            503, "PREFLIGHT_STORAGE_UNAVAILABLE", "预检任务暂时不可用，请稍后重试。", retry=5
        )
