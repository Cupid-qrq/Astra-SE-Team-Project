"""Student execution uses the same heartbeat and physical recovery as preflight."""

import threading
from collections.abc import Mapping

from app.adapters.judge_profiles import SnapshotCatalog
from app.modules.judging.worker import Executor, tokens
from app.shared.judge import ExecutionError

from .worker_store import SubmissionStore


class SubmissionWorker:
    def __init__(
        self, store: SubmissionStore, catalog: SnapshotCatalog, executors: Mapping[str, Executor]
    ) -> None:
        self.store, self.catalog, self.executors = store, catalog, executors

    def recover_once(self) -> bool:
        claim = self.store.recover_claim()
        if claim is None:
            return False
        cleaned = claim.execution_id is None
        if claim.execution_id is not None:
            cleaned = all(
                executor.cancel(claim.execution_id) for executor in self.executors.values()
            )
        self.store.finish_recovery(claim, cleaned)
        return True

    def run_once(self) -> bool:
        claim = self.store.claim()
        if claim is None:
            return False
        stop, lost = threading.Event(), threading.Event()

        def renew():
            while not stop.wait(5):
                try:
                    if self.store.heartbeat(claim):
                        continue
                except Exception:
                    pass
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

    def _run(self, claim, lost):
        self.catalog.bind(claim.profile)
        language = claim.submission["language_key"]
        executor = self.executors[language]
        image = next(
            row["image_digest"]
            for row in claim.profile["languages"]
            if row["language_key"] == language
        )
        if executor.image != image or not claim.cases:
            raise ExecutionError("WORKER_PROFILE_INVALID")
        for case in claim.cases:
            if lost.is_set():
                raise ExecutionError("WORKER_LEASE_LOST")
            identity = self.store.begin_case(claim, case["order"])
            if identity is None:
                raise ExecutionError("WORKER_LEASE_LOST")
            remaining = self.store.remaining(claim)
            if remaining <= 0:
                raise ExecutionError("WORKER_DEADLINE_EXCEEDED")
            result = executor.execute(
                identity,
                language,
                claim.submission["code"],
                bytes(case["input_blob"]),
                timeout=remaining,
            )
            if lost.is_set():
                raise ExecutionError("WORKER_LEASE_LOST")
            verdict = result.diagnosis or (
                "AC" if tokens(result.stdout) == tokens(bytes(case["answer_blob"])) else "WA"
            )
            if not self.store.record_case(
                claim, case["order"], verdict, result.cpu_ms, result.memory_bytes
            ):
                raise ExecutionError("WORKER_LEASE_LOST")
            if verdict != "AC":
                return
