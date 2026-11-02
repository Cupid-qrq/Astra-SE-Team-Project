"""Audit and outbox append in the same caller-owned transaction as A business writes."""

import hashlib
import json
from uuid import UUID, uuid4

from app.modules.assignments.application import membership_changed
from app.modules.identity.ports import Record, Repository


class TransactionalEffects:
    def __init__(self, repo: Repository, request_id: str) -> None:
        self.repo = repo
        self.request_id = str(UUID(request_id))

    def _check(self, repo: Repository) -> None:
        if repo is not self.repo:
            raise RuntimeError("Effects and business writes must share the same repository.")

    def record(
        self,
        repo: Repository,
        actor: str | None,
        action: str,
        object_id: str,
        reason: str = "",
        summary: Record | None = None,
    ) -> None:
        self._check(repo)
        digest = hashlib.sha256(
            json.dumps(
                summary or {}, sort_keys=True, ensure_ascii=False, separators=(",", ":")
            ).encode()
        ).hexdigest()
        event_id, now = str(uuid4()), repo.now()
        # Only identifiers and a digest leave the audit append; never copy arbitrary summary fields.
        repo.add(
            "audit_events",
            dict(
                event_id=event_id,
                actor_id=actor,
                actor_kind="USER" if actor else "SYSTEM",
                action=action,
                object_type={
                    "MEMBER": "course",
                    "COURSE": "course",
                    "USER": "user",
                    "PASSWORD": "user",
                    "VERSION": "problem_version",
                    "TESTCASE": "problem_version",
                    "REFERENCE": "problem_version",
                    "PROBLEM": "problem",
                    "ASSIGNMENT": "assignment",
                    "DEADLINE": "assignment",
                    "POLICY": "assignment",
                    "FEEDBACK": "feedback_catalog",
                    "TEMPLATE": "template_catalog",
                }[action.split("_", 1)[0]],
                object_id=object_id,
                before_after_digest=digest,
                reason=reason,
                timestamp=now,
                request_id=self.request_id,
            ),
        )
        repo.add(
            "outbox_events",
            dict(
                event_id=event_id,
                event_key=event_id,
                event_type=action,
                payload={"object_id": object_id, "summary_digest": digest},
                state="READY",
                tries=0,
                next_at=now,
                created_at=now,
            ),
        )

    def membership_changed(self, repo: Repository, course_id: str) -> None:
        self._check(repo)
        membership_changed(repo, course_id)

    def account_disabled(self, repo: Repository, user_id: str) -> None:
        self._check(repo)
        courses = sorted(
            {r["course_id"] for r in repo.rows("course_members", user_id=user_id, status="ACTIVE")}
        )
        for course_id in courses:
            repo.get("courses", course_id, lock=True)
        for course_id in courses:
            self.membership_changed(repo, course_id)
