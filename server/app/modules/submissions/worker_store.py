"""Student queue leases and result transactions share the physical preflight slot."""

import hashlib
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from uuid import uuid4

from sqlalchemy import select, text
from sqlalchemy.engine import Engine

from app.modules.judging.worker_store import WorkerStore
from app.modules.learning.application import Learning
from app.shared.effects import TransactionalEffects
from app.shared.repository import SqlRepository
from app.shared.uow import UnitOfWork

from .models import attempts, cycles, jobs


@dataclass(frozen=True)
class Claim:
    job_id: str
    attempt_id: str
    epoch: int
    owner: str
    deadline: datetime
    submission: dict = field(repr=False)
    profile: dict = field(repr=False)
    cases: tuple = field(repr=False)
    execution_id: str | None = None


class SubmissionStore:
    def __init__(self, engine: Engine) -> None:
        self.engine = engine

    @staticmethod
    def _claim(repo, job):
        attempt = repo.get("attempts", job["attempt_id"])
        submission = repo.get("submissions", attempt["submission_id"])
        basis = repo.get("result_bases", attempt["basis_id"])
        version = repo.get("problem_versions", basis["target_version_id"])
        cases = tuple(
            sorted(
                repo.rows("testcases", version_id=version["version_id"]),
                key=lambda row: row["order"],
            )
        )
        return Claim(
            job["job_id"],
            job["attempt_id"],
            job["lease_epoch"],
            job["worker_id"],
            job["deadline"],
            submission,
            version["profile"],
            cases,
            job["current_execution"],
        )

    def claim(self):
        with UnitOfWork(self.engine) as conn:
            repo = SqlRepository(conn)
            slot = WorkerStore._lock(repo)
            self._expire_waiting(repo)
            from app.modules.operations.controls import current_config

            if not current_config(repo)["payload"]["judge_enabled"]:
                return None
            if slot["state"] != "FREE":
                return None
            now = repo.now()
            from app.modules.rejudge.application import Rejudges

            Rejudges.dispatch_one(repo)
            now = repo.now()
            control = repo.required("scheduler_control", 1)
            normal = (
                conn.execute(
                    select(jobs.c.job_id)
                    .where(jobs.c.state == "READY", jobs.c.kind == "NORMAL", jobs.c.ready_at <= now)
                    .limit(1)
                ).first()
                is not None
            )
            rejudge = (
                conn.execute(
                    select(jobs.c.job_id)
                    .where(
                        jobs.c.state == "READY", jobs.c.kind == "REJUDGE", jobs.c.ready_at <= now
                    )
                    .limit(1)
                ).first()
                is not None
            )
            protected = conn.scalar(
                text(
                    "SELECT EXISTS(SELECT 1 FROM assignments a JOIN courses c ON c.course_id=a.course_id WHERE a.published_at IS NOT NULL AND c.status='ACTIVE' AND a.due_at>:now AND a.due_at<=:until)"
                ),
                {"now": now, "until": now + timedelta(minutes=10)},
            )
            mode = (
                "PROTECTED"
                if protected
                else "BOTH"
                if normal and rejudge
                else "NORMAL"
                if normal
                else "REJUDGE"
                if rejudge
                else "EMPTY"
            )
            cursor = (
                control["cursor"]
                if mode == "BOTH" and control["previous_queue_mode"] == "BOTH"
                else 0
            )
            kind = "NORMAL" if normal and (mode != "BOTH" or cursor < 4) else "REJUDGE"
            repo.change(
                "scheduler_control",
                1,
                cursor=(cursor + 1) % 5 if mode == "BOTH" else 0,
                previous_queue_mode=mode,
            )
            if (protected and not normal) or mode == "EMPTY":
                return None
            row = (
                conn.execute(
                    select(jobs)
                    .where(jobs.c.state == "READY", jobs.c.ready_at <= now, jobs.c.kind == kind)
                    .order_by(jobs.c.ready_at, jobs.c.created_at, jobs.c.job_id)
                    .limit(1)
                    .with_for_update()
                )
                .mappings()
                .first()
            )
            if row is None:
                return None
            job = dict(row)
            attempt = repo.get("attempts", job["attempt_id"])
            assert attempt is not None
            cycle = repo.get("processing_cycles", attempt["cycle_id"])
            assert cycle is not None
            epoch = slot["lease_epoch"] + 1
            job = repo.change(
                "queue_jobs",
                job["job_id"],
                state="LEASED",
                lease_epoch=epoch,
                worker_id=str(uuid4()),
                lease_until=now + timedelta(seconds=15),
                deadline=min(
                    now + timedelta(seconds=360), cycle["started_at"] + timedelta(minutes=15)
                ),
            )
            repo.change(
                "execution_slots",
                1,
                state="BUSY",
                submission_job_id=job["job_id"],
                lease_epoch=epoch,
            )
            repo.change("attempts", attempt["attempt_id"], state="RUNNING", started_at=now)
            repo.change("result_bases", attempt["basis_id"], processing_state="RUNNING")
            claim = self._claim(repo, job)
            if job["deadline"] <= now:
                self._finish(repo, claim, "SE", "CYCLE_TIMEOUT")
                return None
            return claim

    def _owned(self, repo, claim, live=True):
        slot = WorkerStore._lock(repo)
        if slot["submission_job_id"] != claim.job_id or slot["lease_epoch"] != claim.epoch:
            return None
        job = repo.get("queue_jobs", claim.job_id, lock=True)
        if (
            job is None
            or job["state"] != "LEASED"
            or job["worker_id"] != claim.owner
            or job["lease_epoch"] != claim.epoch
        ):
            return None
        if live and (job["lease_until"] <= repo.now() or job["deadline"] <= repo.now()):
            return None
        return job

    def heartbeat(self, claim):
        with UnitOfWork(self.engine) as conn:
            repo = SqlRepository(conn)
            if self._owned(repo, claim) is None:
                return False
            repo.change("queue_jobs", claim.job_id, lease_until=repo.now() + timedelta(seconds=15))
            return True

    def remaining(self, claim):
        with UnitOfWork(self.engine) as conn:
            repo = SqlRepository(conn)
            if self._owned(repo, claim) is None:
                return 0.0
            return max(0.0, min(40.0, (claim.deadline - repo.now()).total_seconds()))

    @staticmethod
    def _identity(claim, order):
        return hashlib.sha256(
            f"submission:{claim.job_id}:{claim.epoch}:{order}".encode()
        ).hexdigest()

    def begin_case(self, claim, order):
        with UnitOfWork(self.engine) as conn:
            repo = SqlRepository(conn)
            job = self._owned(repo, claim)
            if job is None:
                return None
            rows = repo.rows("case_results", attempt_id=claim.attempt_id)
            if (
                job["current_execution"] is not None
                or order != len(rows) + 1
                or not any(point["order"] == order for point in claim.cases)
            ):
                raise RuntimeError("Invalid execution order")
            identity = self._identity(claim, order)
            repo.change("queue_jobs", claim.job_id, current_execution=identity)
            return identity

    def record_case(self, claim, order, verdict, cpu_ms, memory_bytes):
        with UnitOfWork(self.engine) as conn:
            repo = SqlRepository(conn)
            job = self._owned(repo, claim)
            if job is None or job["current_execution"] != self._identity(claim, order):
                return False
            case = next(point for point in claim.cases if point["order"] == order)
            repo.add(
                "case_results",
                dict(
                    attempt_id=claim.attempt_id,
                    order=order,
                    testcase_id=case["testcase_id"],
                    verdict=verdict,
                    cpu_ms=cpu_ms,
                    memory_bytes=memory_bytes,
                    engine_meta={},
                ),
            )
            repo.change("queue_jobs", claim.job_id, current_execution=None)
            if verdict != "AC" or order == len(claim.cases):
                self._finish(repo, claim, verdict)
            return True

    def _expire_waiting(self, repo):
        now = repo.now()
        rows = (
            repo.connection.execute(
                select(jobs, cycles.c.started_at.label("cycle_started"))
                .join(attempts, attempts.c.attempt_id == jobs.c.attempt_id)
                .join(cycles, cycles.c.cycle_id == attempts.c.cycle_id)
                .where(
                    jobs.c.state == "READY",
                    cycles.c.capacity_held,
                    cycles.c.started_at <= now - timedelta(minutes=15),
                )
            )
            .mappings()
            .all()
        )
        for row in rows:
            job = dict(row)
            job["deadline"] = job["cycle_started"] + timedelta(minutes=15)
            claim = self._claim(repo, job)
            self._finish(repo, claim, "SE", "CYCLE_TIMEOUT", release_slot=False)

    def _finish(self, repo, claim, verdict, reason=None, *, release_slot=True):
        attempt = repo.get("attempts", claim.attempt_id)
        cycle = repo.get("processing_cycles", attempt["cycle_id"])
        basis = repo.get("result_bases", attempt["basis_id"])
        batch = repo.get("rejudge_batches", basis["batch_id"]) if basis["batch_id"] else None
        now = repo.now()
        rows = repo.rows("case_results", attempt_id=claim.attempt_id)
        completed = {r["order"] for r in rows}
        for case in claim.cases:
            if case["order"] not in completed:
                repo.add(
                    "case_results",
                    dict(
                        attempt_id=claim.attempt_id,
                        order=case["order"],
                        testcase_id=case["testcase_id"],
                        verdict="SKIPPED",
                        cpu_ms=None,
                        memory_bytes=None,
                        engine_meta={},
                    ),
                )
        effects = TransactionalEffects(repo, str(uuid4()))
        assignment = repo.get("assignments", claim.submission["assignment_id"], lock=True)
        feedback = Learning(repo, effects).resolve(
            assignment["course_id"], claim.submission["language_key"], verdict
        )
        cpu = [r["cpu_ms"] for r in rows]
        memory = [r["memory_bytes"] for r in rows]
        repo.change(
            "attempts",
            claim.attempt_id,
            state="FINISHED",
            verdict=verdict,
            reason_code=reason,
            time_ms=sum(cpu) if cpu and all(v is not None for v in cpu) else None,
            memory_bytes=max(memory) if memory and all(v is not None for v in memory) else None,
            finished_at=now,
            feedback_version_id=feedback,
        )
        repo.change(
            "queue_jobs", claim.job_id, state="DONE", current_execution=None, lease_until=None
        )
        if release_slot:
            repo.change("execution_slots", 1, state="FREE", submission_job_id=None)
        if (
            verdict == "SE"
            and (batch is None or batch["state"] != "CANCELLED")
            and cycle["auto_retry_count"] == 0
            and now < cycle["started_at"] + timedelta(minutes=15)
        ):
            next_attempt = str(uuid4())
            repo.change("processing_cycles", cycle["cycle_id"], auto_retry_count=1)
            repo.add(
                "attempts",
                dict(
                    attempt_id=next_attempt,
                    submission_id=attempt["submission_id"],
                    basis_id=attempt["basis_id"],
                    cycle_id=cycle["cycle_id"],
                    generation=attempt["generation"] + 1,
                    state="RETRY_WAIT",
                    verdict=None,
                    reason_code=None,
                    started_at=None,
                    finished_at=None,
                    time_ms=None,
                    memory_bytes=None,
                    engine_meta={},
                    feedback_version_id=None,
                ),
            )
            repo.add(
                "queue_jobs",
                dict(
                    job_id=str(uuid4()),
                    attempt_id=next_attempt,
                    kind="REJUDGE" if basis["batch_id"] else "NORMAL",
                    state="READY",
                    ready_at=now,
                    created_at=now,
                    lease_epoch=0,
                ),
            )
            repo.change(
                "result_bases",
                attempt["basis_id"],
                current_attempt_id=next_attempt,
                processing_state="RETRY_WAIT",
            )
        else:
            repo.change(
                "processing_cycles", cycle["cycle_id"], capacity_held=False, finished_at=now
            )
            repo.change("result_bases", attempt["basis_id"], processing_state="FINISHED")
            if verdict == "SE" and (batch is None or batch["state"] != "CANCELLED"):
                from app.modules.operations.fairness import note_platform_failure

                note_platform_failure(
                    repo, assignment["assignment_id"], "JUDGE_UNAVAILABLE", str(uuid4())
                )
            capacity = repo.get("capacity_control", 1, lock=True)
            counter = repo.get("admission_users", claim.submission["user_id"], lock=True)
            repo.change("capacity_control", 1, pending_count=capacity["pending_count"] - 1)
            repo.change(
                "admission_users",
                claim.submission["user_id"],
                pending_count=counter["pending_count"] - 1,
            )
        submission = repo.get("submissions", claim.submission["submission_id"])
        repo.change("submissions", submission["submission_id"], revision=submission["revision"] + 1)
        if submission["mode"] == "FORMAL" and submission["active_basis_id"] == attempt["basis_id"]:
            repo.change(
                "assignments",
                assignment["assignment_id"],
                grade_epoch=assignment["grade_epoch"] + 1,
            )
        effects.record(
            repo,
            None,
            "SUBMISSION_FINISHED",
            submission["submission_id"],
            summary={"verdict": verdict},
        )

    def quarantine(self, claim):
        with UnitOfWork(self.engine) as conn:
            repo = SqlRepository(conn)
            if self._owned(repo, claim, live=False) is None:
                return False
            repo.change("execution_slots", 1, state="QUARANTINED")
            repo.change("queue_jobs", claim.job_id, lease_until=repo.now())
            return True

    def recover_claim(self):
        with UnitOfWork(self.engine) as conn:
            repo = SqlRepository(conn)
            slot = WorkerStore._lock(repo)
            if slot["state"] == "FREE" or slot["submission_job_id"] is None:
                return None
            job = repo.get("queue_jobs", slot["submission_job_id"], lock=True)
            assert job is not None
            now = repo.now()
            if job["lease_until"] > now and job["deadline"] > now:
                return None
            epoch = slot["lease_epoch"] + 1
            job = repo.change(
                "queue_jobs",
                job["job_id"],
                worker_id=str(uuid4()),
                lease_epoch=epoch,
                lease_until=now + timedelta(seconds=15),
            )
            repo.change("execution_slots", 1, state="QUARANTINED", lease_epoch=epoch)
            return self._claim(repo, job)

    def finish_recovery(self, claim, cleaned):
        with UnitOfWork(self.engine) as conn:
            repo = SqlRepository(conn)
            if self._owned(repo, claim, live=False) is None or not cleaned:
                return False
            self._finish(repo, claim, "SE", "WORKER_RECOVERY")
            return True
