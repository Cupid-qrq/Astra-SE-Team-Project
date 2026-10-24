from typing import Protocol

from app.modules.identity.ports import Record, Repository


class AssignmentCoordinationPort(Protocol):
    """B binds grades/fairness to the SAME UoW. No network calls in these methods."""

    def before_change(self, repo: Repository, assignment: Record, action: str) -> None: ...
    def status(self, repo: Repository, assignment: Record) -> Record: ...
