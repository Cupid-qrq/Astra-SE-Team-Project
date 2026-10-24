"""PostgreSQL adapter for A validation only. The caller owns the transaction."""

from collections.abc import Callable
from datetime import datetime
from typing import Any

import app.modules.assignments.models  # noqa: F401
import app.modules.courses.models  # noqa: F401
import app.modules.learning.models  # noqa: F401
import app.modules.problems.models  # noqa: F401
from app.modules.identity.models import metadata
from app.modules.identity.ports import Record
from sqlalchemy import select, text
from sqlalchemy.engine import Connection


class SqlRepository:
    def __init__(self, connection: Connection, clock: Callable[[], datetime] | None = None):
        self.connection, self.clock = connection, clock

    def where(self, table: str, key: Any):
        entity = metadata.tables[table]
        keys = key if isinstance(key, tuple) else (key,)
        if len(keys) != len(entity.primary_key.columns):
            raise ValueError("Wrong primary key arity")
        return [column == value for column, value in zip(entity.primary_key.columns, keys)]

    def get(self, table: str, key: Any, *, lock: bool = False) -> Record | None:
        query = select(metadata.tables[table]).where(*self.where(table, key))
        if lock:
            query = query.with_for_update()
        row = self.connection.execute(query).mappings().first()
        return dict(row) if row else None

    def rows(self, table: str, **filters: Any) -> list[Record]:
        entity = metadata.tables[table]
        clauses = [
            entity.c[k].in_(v) if isinstance(v, list) else entity.c[k] == v
            for k, v in filters.items()
        ]
        query = select(entity).where(*clauses).order_by(*entity.primary_key.columns)
        return [dict(row) for row in self.connection.execute(query).mappings()]

    def add(self, table: str, data: Record) -> Record:
        entity = metadata.tables[table]
        return dict(
            self.connection.execute(entity.insert().values(**data).returning(entity))
            .mappings()
            .one()
        )

    def change(self, table: str, key: Any, **values: Any) -> Record:
        entity = metadata.tables[table]
        return dict(
            self.connection.execute(
                entity.update().where(*self.where(table, key)).values(**values).returning(entity)
            )
            .mappings()
            .one()
        )

    def remove(self, table: str, key: Any) -> None:
        self.connection.execute(metadata.tables[table].delete().where(*self.where(table, key)))

    def now(self) -> datetime:
        if self.clock:
            return self.clock()
        return self.connection.scalar(text("SELECT date_trunc('milliseconds', clock_timestamp())"))

    def guard(self) -> None:
        # Standalone adapter for B's shared policy_guard; same key for every A mutation.
        self.connection.execute(text("SELECT pg_advisory_xact_lock(1463899218)"))
