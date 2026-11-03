"""Preflight orchestration: commit leases before calling a private executor."""

import json
import threading
from collections.abc import Mapping
from typing import Protocol

from app.adapters.course_executor import ExecutionResult
from app.adapters.judge_profiles import ProfileCatalog, SnapshotCatalog
from app.modules.judging.domain import freeze_snapshot
from app.modules.judging.worker_store import Claim, WorkerStore
from app.shared.judge import ExecutionError


class Executor(Protocol):
    image: str

    def execute(
        self, identity: str, language: str, code: bytes, stdin: bytes, timeout: float = 40
    ) -> ExecutionResult: ...
    def cancel(self, identity: str) -> bool: ...


def tokens(value: bytes) -> list[bytes]:
    # bytes.split() recognizes exactly ASCII whitespace; Unicode space stays data.
    return value.replace(b"\r\n", b"\n").split()


class PreflightWorker:
    def __init__(
        self,
        store: WorkerStore,
        catalog: ProfileCatalog | SnapshotCatalog,
        executors: Mapping[str, Executor],
    ):
        self.store, self.catalog, self.executors = store, catalog, executors

    def recover_once(self) -> bool:
        claim = self.store.recover_claim()
        if claim is None:
            return False
        cleaned = claim.execution_id is None
        if claim.execution_id is not None:
            # A single controller owns the physical slot. Every configured controller
            # must fence the identity before the global database slot is reusable.
            cleaned = all(
                executor.cancel(claim.execution_id) for executor in self.executors.values()
            )
        self.store.finish_recovery(claim, cleaned)
        return True

    def run_once(self) -> bool:
        claim = self.store.claim()
        if claim is None:
            return False
        stop = threading.Event()
        lost = threading.Event()

        def renew() -> None:
            while not stop.wait(5):
                try:
                    if not self.store.heartbeat(claim):
                        lost.set()
                        return
                except Exception:
                    lost.set()
                    return

        heartbeat = threading.Thread(target=renew, daemon=True)
        heartbeat.start()
        try:
            self._run(claim, lost)
        except (Exception, KeyboardInterrupt):
            self.store.quarantine(claim)
        finally:
            stop.set()
            heartbeat.join(timeout=6)
        return True

    def _run(self, claim: Claim, lost: threading.Event) -> None:
        snapshot = json.loads(claim.blob)
        plan = freeze_snapshot(snapshot, self.catalog)
        references = {
            row["language_key"]: row["code"].encode("utf-8") for row in snapshot["references"]
        }
        images = {
            row["language_key"]: row["image_digest"] for row in snapshot["profile"]["languages"]
        }
        for language, kind, order in plan.cases:
            if lost.is_set():
                raise ExecutionError("WORKER_LEASE_LOST")
            executor = self.executors[language]
            if executor.image != images[language]:
                raise ExecutionError("WORKER_IMAGE_MISMATCH")
            point = snapshot["samples" if kind == "SAMPLE" else "testcases"][order - 1]
            stdin = point["input" if kind == "SAMPLE" else "input_text"].encode("utf-8")
            answer = point["output" if kind == "SAMPLE" else "answer_text"].encode("utf-8")
            key = (language, kind, order)
            identity = self.store.begin_case(claim, key)
            if identity is None:
                raise ExecutionError("WORKER_LEASE_LOST")
            # No connection/transaction spans execute/cancel.
            remaining = self.store.remaining(claim)
            if remaining <= 0:
                raise ExecutionError("WORKER_DEADLINE_EXCEEDED")
            result = executor.execute(
                identity, language, references[language], stdin, timeout=remaining
            )
            if lost.is_set():
                raise ExecutionError("WORKER_LEASE_LOST")
            verdict = result.diagnosis or (
                "AC" if tokens(result.stdout) == tokens(answer) else "WA"
            )
            if not self.store.record_case(claim, key, verdict, result.cpu_ms, result.memory_bytes):
                raise ExecutionError("WORKER_LEASE_LOST")
            if verdict != "AC":
                return
        if not self.store.complete(claim):
            raise ExecutionError("WORKER_COMPLETION_REJECTED")
