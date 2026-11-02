"""One caller-owned transaction shared by all participating application services."""

from contextlib import AbstractContextManager
from types import TracebackType

from sqlalchemy.engine import Connection, Engine


class UnitOfWork:
    """Single-use transaction scope; participants must not commit or roll back.

    SQLAlchemy owns commit/rollback/connection cleanup, including exceptions during
    commit and BaseException exits. A failed commit is never automatically retried.
    """

    def __init__(self, engine: Engine) -> None:
        self._engine = engine
        self._used = False
        self._scope: AbstractContextManager[Connection] | None = None

    def __enter__(self) -> Connection:
        if self._used:
            raise RuntimeError("A UnitOfWork cannot be nested or reused.")
        self._used = True
        self._scope = self._engine.begin()
        return self._scope.__enter__()

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: TracebackType | None,
    ) -> bool | None:
        if self._scope is None:
            raise RuntimeError("UnitOfWork has not been entered.")
        return self._scope.__exit__(exc_type, exc_value, traceback)
