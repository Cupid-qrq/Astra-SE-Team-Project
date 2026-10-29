"""Read wall-clock time from the caller's database transaction."""

from datetime import UTC, datetime

from sqlalchemy import text
from sqlalchemy.engine import Connection


class DatabaseClock:
    def __init__(self, connection: Connection) -> None:
        self._connection = connection

    def now(self) -> datetime:
        value = self._connection.scalar(
            text("SELECT date_trunc('milliseconds', clock_timestamp())")
        )
        if not isinstance(value, datetime) or value.tzinfo is None:
            raise RuntimeError("Database clock returned an invalid timestamp.")
        return value.astimezone(UTC)
