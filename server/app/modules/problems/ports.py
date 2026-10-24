from typing import Protocol

from app.modules.identity.ports import Record, Repository


class PreflightPort(Protocol):
    """B implements transactional enqueue/read/evidence; never network under locks.

    Evidence includes version_id, content_digest, profile_hash, state, and a complete
    list of language_key/case_kind/case_order/state/verdict. B validates the actual
    installed profile; synthetic images/versions are only permitted in tests.
    """

    def enqueue(self, repo: Repository, actor: Record, version_id: str) -> Record: ...
    def read(self, repo: Repository, actor: Record, preflight_id: str) -> Record: ...
    def evidence(self, repo: Repository, preflight_id: str) -> Record | None: ...
