"""Allocate a new processing cycle under the shared policy/scheduler transaction."""

from uuid import uuid4

from sqlalchemy import func, select

from app.modules.identity.domain import require

from .models import attempts


def start_cycle(repo, submission, basis_id, kind, trigger, reason):
    capacity = repo.get("capacity_control", 1, lock=True)
    counter = repo.get("admission_users", submission["user_id"], lock=True)
    require(capacity["pending_count"] < 100, "GLOBAL_CAPACITY", "平台队列已满。", 503)
    require(counter["pending_count"] < 3, "STUDENT_PENDING_LIMIT", "该学生待处理提交已满。", 429)
    now = repo.now()
    cycle_id = str(uuid4())
    attempt_id = str(uuid4())
    generation = (
        repo.connection.scalar(
            select(func.max(attempts.c.generation)).where(
                attempts.c.submission_id == submission["submission_id"]
            )
        )
        + 1
    )
    repo.add(
        "processing_cycles",
        dict(
            cycle_id=cycle_id,
            basis_id=basis_id,
            submission_id=submission["submission_id"],
            started_at=now,
            finished_at=None,
            auto_retry_count=0,
            capacity_held=True,
            trigger=trigger,
            reason=reason,
        ),
    )
    repo.add(
        "attempts",
        dict(
            attempt_id=attempt_id,
            basis_id=basis_id,
            cycle_id=cycle_id,
            submission_id=submission["submission_id"],
            generation=generation,
            state="QUEUED",
            verdict=None,
            engine_meta={},
        ),
    )
    repo.add(
        "queue_jobs",
        dict(
            job_id=str(uuid4()),
            attempt_id=attempt_id,
            kind=kind,
            state="READY",
            ready_at=now,
            created_at=now,
            lease_epoch=0,
        ),
    )
    repo.change(
        "result_bases",
        basis_id,
        current_attempt_id=attempt_id,
        current_cycle_id=cycle_id,
        processing_state="QUEUED",
    )
    repo.change("capacity_control", 1, pending_count=capacity["pending_count"] + 1)
    repo.change(
        "admission_users", submission["user_id"], pending_count=counter["pending_count"] + 1
    )
    return dict(cycle_id=cycle_id, attempt_id=attempt_id)


def cancel_waiting(repo, basis_id):
    basis = repo.get("result_bases", basis_id)
    attempt = repo.get("attempts", basis["current_attempt_id"])
    if attempt["state"] == "FINISHED":
        return
    job = repo.rows("queue_jobs", attempt_id=attempt["attempt_id"])[0]
    if job["state"] == "LEASED":
        slot = repo.get("execution_slots", 1, lock=True)
        if slot["submission_job_id"] == job["job_id"]:
            repo.change("execution_slots", 1, state="QUARANTINED")
            repo.change("queue_jobs", job["job_id"], lease_until=repo.now())
        return
    cycle = repo.get("processing_cycles", attempt["cycle_id"])
    submission = repo.get("submissions", attempt["submission_id"])
    now = repo.now()
    repo.change(
        "attempts",
        attempt["attempt_id"],
        state="FINISHED",
        verdict="SE",
        reason_code="BATCH_CANCELLED",
        finished_at=now,
    )
    repo.change("queue_jobs", job["job_id"], state="DONE")
    repo.change("result_bases", basis_id, processing_state="FINISHED")
    if cycle["capacity_held"]:
        repo.change("processing_cycles", cycle["cycle_id"], capacity_held=False, finished_at=now)
        capacity = repo.get("capacity_control", 1, lock=True)
        counter = repo.get("admission_users", submission["user_id"], lock=True)
        repo.change("capacity_control", 1, pending_count=capacity["pending_count"] - 1)
        repo.change(
            "admission_users", submission["user_id"], pending_count=counter["pending_count"] - 1
        )
