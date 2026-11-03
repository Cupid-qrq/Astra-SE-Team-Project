"""Transactional hint service. The HTTP application supplies no source/model by default."""

from dataclasses import dataclass, field, replace
from datetime import timedelta, timezone
from decimal import Decimal
from typing import Protocol
from uuid import uuid4

from app.modules.identity.domain import Fault, require, role, utc
from app.modules.identity.ports import Record, Repository
from app.modules.problems.domain import canonical_hash

from .domain import public_version
from .hint_store import HintLedger
from .model_worker import Candidate, FrozenModel, prepare_context
from .policy_rules import HintPolicy, HintSource, HintSources


class Sources(HintSources, Protocol):
    def hint_context(self, repo: Repository, source: HintSource) -> Record:
        """Fetch public samples, owner code and sanitized diagnostics after current authorization."""
        ...


@dataclass(frozen=True)
class Permit:
    hint_id: str
    lease_epoch: int
    model: FrozenModel
    context: Record = field(repr=False)


class HintService:
    def __init__(
        self,
        repo: Repository,
        sources: Sources | None = None,
        configuration: str | None = None,
        project_budget_cny: Decimal | None = None,
    ):
        self.repo, self.sources, self.configuration = repo, sources, configuration
        self.project_budget_cny = project_budget_cny
        self.policy, self.ledger = HintPolicy(repo, sources), HintLedger(repo)

    def _hint(self, hid: str) -> Record:
        hint = self.repo.get("ai_hints", hid)
        require(hint is not None, "NOT_FOUND", "提示不存在或无权访问。", 404)
        assert hint
        return hint

    def _config(self) -> Record:
        model = self.repo.get("model_configs", self.configuration) if self.configuration else None
        if not model or not model["enabled"]:
            raise Fault(503, "MODEL_DISABLED", "尚未启用经过验证的模型配置。")
        if self.project_budget_cny is not None:
            account = self.repo.get("budget_accounts", "PROJECT", lock=True)
            if (
                account is None
                or account["limit_amount"] > self.project_budget_cny
                or account["settled_amount"]
                + account["reserved_amount"]
                + account["uncertain_amount"]
                > account["limit_amount"]
            ):
                raise Fault(503, "MODEL_DISABLED", "模型部署预算尚未完成核对。")
        return model

    def create(self, actor: Record, body: Record) -> tuple[int, Record]:
        role(actor, ("STUDENT",))
        self.repo.guard()
        uid, sid = actor["user_id"], body["submission_id"]
        consent, question = body["data_sharing_consent"], body.get("question", "")
        digest = canonical_hash([sid, question, consent])
        existing = self.repo.rows("ai_hints", user_id=uid, request_key=body["request_key"])
        if existing:
            hint = existing[0]
            require(
                hint["request_digest"] == digest, "IDEMPOTENCY_CONFLICT", "同一请求键的内容不同。"
            )
            view = self.read(actor, hint["hint_id"])
            if view["status"] == "PENDING":
                return 202, dict(hint_id=hint["hint_id"], status="PENDING")
            return 200, view
        auth = self.policy.authorize(uid, sid, consent=consent)
        model = self._config()
        cid = auth.source.course_id
        template = None
        for scope in ("COURSE:" + cid, "GLOBAL"):
            catalogs = self.repo.rows("template_catalogs", scope_key=scope)
            if catalogs and catalogs[0]["active_version_id"]:
                template = catalogs[0]["active_version_id"]
                break
        require(template is not None, "TEMPLATE_UNAVAILABLE", "尚未启用提示模板。", 503)
        fixed = (
            self.repo.get("feedback_versions", auth.source.feedback_version_id)
            if auth.source.feedback_version_id
            else None
        )
        catalog = self.repo.get("feedback_catalogs", fixed["catalog_id"]) if fixed else None
        require(
            bool(
                catalog
                and catalog["verdict"] == auth.source.verdict
                and catalog["scope_key"] in ("GLOBAL", "COURSE:" + cid)
            ),
            "FEEDBACK_UNAVAILABLE",
            "缺少原提交的固定帮助。",
            503,
        )
        self.expire()
        require(
            not self.repo.rows("ai_hints", user_id=uid, status="PENDING"),
            "HINT_IN_PROGRESS",
            "已有提示正在处理。",
            429,
        )
        require(
            len(self.repo.rows("hint_jobs", state="WAITING")) < 10,
            "HINT_QUEUE_FULL",
            "提示队列已满。",
            503,
        )
        now = auth.authorized_at
        hid = str(uuid4())
        hint = self.repo.add(
            "ai_hints",
            dict(
                hint_id=hid,
                user_id=uid,
                course_id=cid,
                submission_id=sid,
                request_key=body["request_key"],
                request_digest=digest,
                question=question,
                accepted_date=now.astimezone(timezone(timedelta(hours=8))).date(),
                status="PENDING",
                reason_code=None,
                template_version_id=template,
                model_config_id=model["config_id"],
                feedback_version_id=auth.source.feedback_version_id,
                accepted_policy_digest=auth.policy_digest,
                consented_at=now,
                created_at=now,
            ),
        )
        upper = (
            model["input_price"] * model["max_input_tokens"]
            + model["output_price"] * model["max_output_tokens"]
        ) / Decimal(1_000_000)
        self.ledger.reserve(hint, upper)
        self.repo.add(
            "hint_jobs",
            dict(
                hint_id=hid,
                state="WAITING",
                queued_at=now,
                deadline_at=now + timedelta(seconds=10),
                lease_epoch=0,
            ),
        )
        return 202, dict(hint_id=hid, status="PENDING")

    def read(self, actor: Record, hid: str) -> Record:
        self.repo.guard()
        hint = self._hint(hid)
        if hint["status"] == "PENDING":
            # Authorize before persisting timeout recovery from an ordinary GET/replay.
            self.policy.can_read_sections(
                actor["user_id"],
                hint["user_id"],
                hint["submission_id"],
                course_id=hint["course_id"],
                consent=hint["consented_at"] is not None,
            )
            self.expire(hid)
            hint = self._hint(hid)
        model = self.repo.get("model_configs", hint["model_config_id"])
        fixed = self.repo.get("feedback_versions", hint["feedback_version_id"])
        assert model and fixed
        return self.policy.read_projection(
            actor["user_id"],
            hint | dict(model_version=model["version_label"], created_at=utc(hint["created_at"])),
            public_version(fixed),
        )

    def rate(self, actor: Record, hid: str, body: Record) -> Record:
        role(actor, ("STUDENT",))
        view = self.read(actor, hid)
        require(view["status"] == "READY", "HINT_NOT_READY", "仅可评价当前可见的已完成提示。")
        values = dict(
            rating=body["rating"], comment=body.get("comment", ""), updated_at=self.repo.now()
        )
        if self.repo.get("hint_feedback", hid):
            self.repo.change("hint_feedback", hid, **values)
        else:
            self.repo.add("hint_feedback", dict(hint_id=hid, user_id=actor["user_id"], **values))
        return dict(rating=body["rating"])

    def _close(self, hint: Record, status: str, candidate: Candidate) -> None:
        hid = hint["hint_id"]
        self.ledger.settle(
            hint, candidate.billing, candidate.actual_cost_cny, ready=status == "READY"
        )
        self.repo.change(
            "ai_hints",
            hid,
            status=status,
            sections=candidate.sections if status == "READY" else None,
            reason_code=candidate.reason_code,
            usage=candidate.usage,
            provider_request_id=candidate.provider_request_id,
        )
        self.repo.change("hint_jobs", hid, state="DONE")

    def expire(self, hid: str | None = None) -> None:
        self.repo.guard()
        now = self.repo.now()
        filters: Record = dict(state=["WAITING", "RUNNING"])
        if hid is not None:
            filters["hint_id"] = hid
        for job in self.repo.rows("hint_jobs", **filters):
            if job["deadline_at"] <= now:
                running = job["state"] == "RUNNING"
                self._close(
                    self._hint(job["hint_id"]),
                    "FAILED",
                    Candidate(
                        None,
                        "MODEL_TIMEOUT" if running else "QUEUE_TIMEOUT",
                        "UNCERTAIN" if running else "RELEASED",
                        None,
                    ),
                )

    def dispatch(self, hid: str | None = None) -> Permit | None:
        self.repo.guard()
        self.expire()
        waiting = self.repo.rows("hint_jobs", state="WAITING")
        if hid is not None:
            waiting = [j for j in waiting if j["hint_id"] == hid]
        if not waiting or len(self.repo.rows("hint_jobs", state="RUNNING")) >= 2:
            return None
        job = min(waiting, key=lambda j: (j["queued_at"], j["hint_id"]))
        hid = job["hint_id"]
        hint = self._hint(hid)
        try:
            auth = self.policy.authorize(
                hint["user_id"],
                hint["submission_id"],
                consent=hint["consented_at"] is not None,
                phase="dispatch",
            )
            require(
                auth.source.course_id == hint["course_id"],
                "HINT_POLICY_BLOCKED",
                "来源课程已失效。",
                403,
            )
            require(
                self._config()["config_id"] == hint["model_config_id"],
                "MODEL_DISABLED",
                "已暂停旧模型派发。",
                503,
            )
            assert self.sources
            data = self.sources.hint_context(self.repo, auth.source)
            require(
                data.get("verdict") == auth.source.verdict,
                "SOURCE_CHANGED",
                "来源判定不一致。",
                409,
            )
            context = prepare_context(data, question=hint["question"])
            # Reading and validating code can span an automatic assignment opening.
            latest = self.policy.authorize(
                hint["user_id"],
                hint["submission_id"],
                consent=hint["consented_at"] is not None,
                phase="dispatch",
            )
            require(latest.source == auth.source, "SOURCE_CHANGED", "来源已发生变化。", 409)
            auth = latest
        except Fault as exc:
            self._close(
                hint,
                "FAILED" if exc.status == 503 else "BLOCKED",
                Candidate(None, exc.code, "RELEASED", None),
            )
            return None
        except ValueError:
            self._close(hint, "FAILED", Candidate(None, "INVALID_MODEL_CONTEXT", "RELEASED", None))
            return None
        now = self.repo.now()
        if now >= job["deadline_at"]:
            self._close(hint, "FAILED", Candidate(None, "QUEUE_TIMEOUT", "RELEASED", None))
            return None
        config = self._config()
        frozen = FrozenModel(
            config["version_label"],
            hint["template_version_id"],
            config["max_input_tokens"],
            config["max_output_tokens"],
            provider_model_id=config["model_id"],
            config_id=config["config_id"],
            input_price_ceiling=config["input_price"],
            output_price=config["output_price"],
        )
        epoch = job["lease_epoch"] + 1
        self.repo.change(
            "hint_jobs",
            hid,
            state="RUNNING",
            lease_epoch=epoch,
            started_at=now,
            deadline_at=now + timedelta(seconds=20),
        )
        self.repo.change(
            "ai_hints",
            hid,
            authorized_at=auth.authorized_at,
            dispatch_policy_digest=auth.policy_digest,
        )
        return Permit(hid, epoch, frozen, context)

    def finish(self, hid: str, epoch: int, candidate: Candidate) -> bool:
        self.repo.guard()
        job = self.repo.get("hint_jobs", hid, lock=True)
        if not job or job["lease_epoch"] != epoch:
            return False
        if job["state"] == "DONE":
            if candidate.billing != "SETTLED" or candidate.actual_cost_cny is None:
                return False
            if not self.reconcile(hid, candidate.actual_cost_cny):
                return False
            self.repo.change(
                "ai_hints",
                hid,
                usage=candidate.usage,
                provider_request_id=candidate.provider_request_id,
            )
            return True
        if job["state"] != "RUNNING":
            return False
        hint = self._hint(hid)
        status = "FAILED"
        if self.repo.now() >= job["deadline_at"]:
            candidate = replace(candidate, sections=None, reason_code="MODEL_TIMEOUT")
        elif candidate.sections is not None:
            try:
                auth = self.policy.authorize(
                    hint["user_id"],
                    hint["submission_id"],
                    consent=hint["consented_at"] is not None,
                    phase="ready",
                )
                require(
                    auth.source.course_id == hint["course_id"],
                    "HINT_POLICY_BLOCKED",
                    "来源课程已失效。",
                    403,
                )
                status = "READY"
            except Fault as exc:
                status = "FAILED" if exc.status == 503 else "BLOCKED"
                candidate = replace(candidate, sections=None, reason_code=exc.code)
        self._close(hint, status, candidate)
        return True

    def reconcile(self, hid: str, actual: Decimal) -> bool:
        self.repo.guard()
        reservation = self.repo.get("budget_reservations", hid, lock=True)
        if not reservation or reservation["state"] != "UNCERTAIN":
            return False
        return self.ledger.settle(self._hint(hid), "SETTLED", actual)
