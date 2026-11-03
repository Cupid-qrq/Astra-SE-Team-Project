"""Short database transactions for preflight leases. Never calls the executor."""

import hashlib
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any
from uuid import uuid4

from sqlalchemy import select, text
from sqlalchemy.engine import Engine

from app.modules.judging.models import cases, jobs, scheduler, slots
from app.shared.effects import TransactionalEffects
from app.shared.repository import SqlRepository
from app.shared.uow import UnitOfWork


@dataclass(frozen=True)
class Claim:
    job_id: str
    preflight_id: str
    epoch: int
    owner: str
    deadline: datetime
    blob: bytes = field(repr=False)
    execution_id: str | None = None


class WorkerStore:
    def __init__(self, engine: Engine):
        self.engine = engine

    @staticmethod
    def _lock(repo: SqlRepository) -> dict[str, Any]:
        repo.guard()
        repo.connection.execute(
            select(scheduler).where(scheduler.c.control_id == 1).with_for_update()
        ).one()
        return dict(
            repo.connection.execute(select(slots).where(slots.c.slot_id == 1).with_for_update())
            .mappings()
            .one()
        )

    @staticmethod
    def _claim(job: dict[str, Any], run: dict[str, Any]) -> Claim:
        return Claim(
            job["job_id"],
            job["preflight_id"],
            job["lease_epoch"],
            job["claimed_by"],
            job["deadline"],
            bytes(run["frozen_blob"]),
            job["current_execution"],
        )

    def bind_executor(self, fingerprint: str) -> None:
        from app.shared.judge import sha_value

        sha_value(fingerprint)
        with UnitOfWork(self.engine) as conn:
            repo = SqlRepository(conn)
            slot = self._lock(repo)
            previous = conn.scalar(
                select(scheduler.c.executor_binding).where(scheduler.c.control_id == 1)
            )
            if previous != fingerprint:
                if slot["state"] != "FREE":
                    raise ValueError("EXECUTOR_BINDING_BUSY")
                conn.execute(
                    scheduler.update()
                    .where(scheduler.c.control_id == 1)
                    .values(executor_binding=fingerprint)
                )

    def claim(self) -> Claim | None:
        with UnitOfWork(self.engine) as conn:
            repo = SqlRepository(conn)
            slot = self._lock(repo)
            now = repo.now()
            if slot["state"] != "FREE":
                return None
            protected = conn.scalar(
                text(
                    "SELECT EXISTS(SELECT 1 FROM assignments a JOIN courses c ON c.course_id=a.course_id WHERE a.published_at IS NOT NULL AND c.status='ACTIVE' AND a.due_at>:now AND a.due_at<=:until)"
                ),
                {"now": now, "until": now + timedelta(minutes=10)},
            )
            if protected:
                return None
            row = (
                conn.execute(
                    select(jobs)
                    .where(
                        jobs.c.state == "READY", jobs.c.claimed_by.is_(None), jobs.c.ready_at <= now
                    )
                    .order_by(jobs.c.ready_at, jobs.c.job_id)
                    .limit(1)
                    .with_for_update()
                )
                .mappings()
                .first()
            )
            if row is None:
                return None
            job = dict(row)
            run = repo.get("preflight_runs", job["preflight_id"], lock=True)
            assert run is not None
            if run["state"] != "QUEUED":
                raise RuntimeError("Invalid preflight queue state")
            epoch = slot["lease_epoch"] + 1
            job = repo.change(
                "preflight_jobs",
                job["job_id"],
                lease_epoch=epoch,
                claimed_by=str(uuid4()),
                lease_until=now + timedelta(seconds=15),
                deadline=now + timedelta(seconds=360),
            )
            repo.change("execution_slots", 1, state="BUSY", job_id=job["job_id"], lease_epoch=epoch)
            repo.change("preflight_runs", job["preflight_id"], state="RUNNING", started_at=now)
            return self._claim(job, run)

    def _owned(
        self, repo: SqlRepository, claim: Claim, *, live: bool = True
    ) -> dict[str, Any] | None:
        slot = self._lock(repo)
        if slot["job_id"] != claim.job_id or slot["lease_epoch"] != claim.epoch:
            return None
        job = repo.get("preflight_jobs", claim.job_id, lock=True)
        if (
            job is None
            or job["state"] == "DONE"
            or job["claimed_by"] != claim.owner
            or job["lease_epoch"] != claim.epoch
        ):
            return None
        if live and (job["lease_until"] <= repo.now() or job["deadline"] <= repo.now()):
            return None
        return job

    def remaining(self, claim: Claim) -> float:
        with UnitOfWork(self.engine) as conn:
            repo = SqlRepository(conn)
            if self._owned(repo, claim) is None:
                return 0
            return max(0.0, min(40.0, (claim.deadline - repo.now()).total_seconds()))

    def heartbeat(self, claim: Claim) -> bool:
        with UnitOfWork(self.engine) as conn:
            repo = SqlRepository(conn)
            if self._owned(repo, claim) is None:
                return False
            repo.change(
                "preflight_jobs", claim.job_id, lease_until=repo.now() + timedelta(seconds=15)
            )
            return True

    def begin_case(self, claim: Claim, key: tuple[str, str, int]) -> str | None:
        with UnitOfWork(self.engine) as conn:
            repo = SqlRepository(conn)
            job = self._owned(repo, claim)
            if job is None:
                return None
            if job["current_execution"] is not None:
                raise RuntimeError("Previous execution not closed")
            row = repo.get("preflight_cases", (claim.preflight_id, *key), lock=True)
            if row is None or row["state"] != "QUEUED":
                raise RuntimeError("Invalid case state")
            identity = hashlib.sha256(
                f"{claim.job_id}:{claim.epoch}:{key[0]}:{key[1]}:{key[2]}".encode()
            ).hexdigest()
            repo.change("preflight_cases", (claim.preflight_id, *key), state="RUNNING")
            repo.change("preflight_jobs", claim.job_id, current_execution=identity)
            return identity

    def record_case(
        self,
        claim: Claim,
        key: tuple[str, str, int],
        verdict: str,
        cpu_ms: int | None,
        memory_bytes: int | None,
    ) -> bool:
        with UnitOfWork(self.engine) as conn:
            repo = SqlRepository(conn)
            job = self._owned(repo, claim)
            if job is None:
                return False
            expected = hashlib.sha256(
                f"{claim.job_id}:{claim.epoch}:{key[0]}:{key[1]}:{key[2]}".encode()
            ).hexdigest()
            if job["current_execution"] != expected:
                return False
            row = repo.get("preflight_cases", (claim.preflight_id, *key), lock=True)
            if row is None or row["state"] != "RUNNING":
                return False
            repo.change(
                "preflight_cases",
                (claim.preflight_id, *key),
                state="FINISHED",
                verdict=verdict,
                engine_meta={"cpu_ms": cpu_ms, "memory_bytes": memory_bytes},
            )
            repo.change("preflight_jobs", claim.job_id, current_execution=None)
            if verdict != "AC":
                conn.execute(
                    cases.update()
                    .where(cases.c.preflight_id == claim.preflight_id, cases.c.state == "QUEUED")
                    .values(state="SKIPPED")
                )
                self._finish(repo, claim, False)
            return True

    def complete(self, claim: Claim) -> bool:
        with UnitOfWork(self.engine) as conn:
            repo = SqlRepository(conn)
            job = self._owned(repo, claim)
            if job is None or job["current_execution"] is not None:
                return False
            rows = repo.rows("preflight_cases", preflight_id=claim.preflight_id)
            if not rows or any(row["state"] != "FINISHED" for row in rows):
                return False
            self._finish(repo, claim, all(row["verdict"] == "AC" for row in rows))
            return True

    @staticmethod
    def _finish(repo: SqlRepository, claim: Claim, passed: bool) -> None:
        repo.change(
            "preflight_runs",
            claim.preflight_id,
            state="PASSED" if passed else "FAILED",
            finished_at=repo.now(),
        )
        repo.change(
            "preflight_jobs", claim.job_id, state="DONE", lease_until=None, current_execution=None
        )
        repo.change("execution_slots", 1, state="FREE", job_id=None)
        TransactionalEffects(repo, str(uuid4())).record(
            repo, None, "PREFLIGHT_FINISHED", claim.preflight_id, summary={"passed": passed}
        )

    def quarantine(self, claim: Claim) -> bool:
        with UnitOfWork(self.engine) as conn:
            repo = SqlRepository(conn)
            if self._owned(repo, claim, live=False) is None:
                return False
            repo.change("execution_slots", 1, state="QUARANTINED")
            repo.change("preflight_jobs", claim.job_id, lease_until=repo.now())
            return True

    def recover_claim(self) -> Claim | None:
        with UnitOfWork(self.engine) as conn:
            repo = SqlRepository(conn)
            slot = self._lock(repo)
            now = repo.now()
            if slot["state"] == "FREE":
                return None
            job = repo.get("preflight_jobs", slot["job_id"], lock=True)
            assert job is not None
            if job["lease_until"] > now and job["deadline"] > now:
                return None
            epoch = slot["lease_epoch"] + 1
            job = repo.change(
                "preflight_jobs",
                job["job_id"],
                lease_epoch=epoch,
                claimed_by=str(uuid4()),
                lease_until=now + timedelta(seconds=15),
            )
            repo.change("execution_slots", 1, state="QUARANTINED", lease_epoch=epoch)
            run = repo.get("preflight_runs", job["preflight_id"])
            assert run is not None
            return self._claim(job, run)

    def finish_recovery(self, claim: Claim, cleaned: bool) -> bool:
        with UnitOfWork(self.engine) as conn:
            repo = SqlRepository(conn)
            job = self._owned(repo, claim, live=False)
            if job is None or not cleaned:
                return False
            for row in repo.rows("preflight_cases", preflight_id=claim.preflight_id):
                key = (claim.preflight_id, row["language_key"], row["case_kind"], row["case_order"])
                if row["state"] == "RUNNING":
                    repo.change(
                        "preflight_cases",
                        key,
                        state="FINISHED",
                        verdict="SE",
                        engine_meta={"failure_code": "WORKER_RECOVERY"},
                    )
                elif row["state"] == "QUEUED":
                    repo.change("preflight_cases", key, state="SKIPPED")
            self._finish(repo, claim, False)
            return True
