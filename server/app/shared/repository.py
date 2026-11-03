"""A-compatible transactional repository; public lists use explicit keyset pages."""

from datetime import datetime
from typing import Any

from sqlalchemy import Table, select
from sqlalchemy.engine import Connection
from sqlalchemy.sql.elements import ColumnElement

from app.modules.identity.ports import Record
from app.shared.clock import DatabaseClock
from app.shared.metadata import metadata


class SqlRepository:
    def __init__(self, connection: Connection) -> None:
        if not connection.in_transaction():
            raise RuntimeError("Repository requires a caller-owned transaction.")
        self.connection = connection

    def _where(self, table: Table, key: Any) -> list[ColumnElement[bool]]:
        keys = key if isinstance(key, tuple) else (key,)
        columns = list(table.primary_key.columns)
        if len(keys) != len(columns):
            raise ValueError("Wrong primary key arity.")
        return [column == value for column, value in zip(columns, keys, strict=True)]

    def get(self, table: str, key: Any, *, lock: bool = False) -> Record | None:
        entity = metadata.tables[table]
        query = select(entity).where(*self._where(entity, key))
        if lock:
            query = query.with_for_update()
        row = self.connection.execute(query).mappings().first()
        return dict(row) if row is not None else None

    def course_is_cleaned(self, course_id: str) -> bool:
        return self.get("course_cleanup", course_id) is not None

    def required(self, table: str, key: Any, *, lock: bool = False) -> Record:
        from app.modules.identity.domain import Fault

        row = self.get(table, key, lock=lock)
        if row is None:
            raise Fault(404, "NOT_FOUND", "记录不存在或无权访问。")
        return row

    def rows(self, table: str, **filters: Any) -> list[Record]:
        # Complete internal collections retain A's semantics; never silently truncate.
        entity = metadata.tables[table]
        query = (
            select(entity)
            .where(
                *[
                    entity.c[k].in_(v) if isinstance(v, list) else entity.c[k] == v
                    for k, v in filters.items()
                ]
            )
            .order_by(*entity.primary_key.columns)
        )
        return [dict(row) for row in self.connection.execute(query).mappings()]

    def page(
        self, table: str, *, limit: int = 20, after: str | None = None, **filters: Any
    ) -> list[Record]:
        entity = metadata.tables[table]
        columns = list(entity.primary_key.columns)
        if not 1 <= limit <= 100 or len(columns) != 1:
            raise ValueError("Page requires a single primary key and limit 1..100.")
        query = select(entity).where(*[entity.c[k] == v for k, v in filters.items()])
        if after is not None:
            query = query.where(columns[0] > after)
        query = query.order_by(columns[0]).limit(limit)
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
                entity.update().where(*self._where(entity, key)).values(**values).returning(entity)
            )
            .mappings()
            .one()
        )

    def remove(self, table: str, key: Any) -> None:
        entity = metadata.tables[table]
        self.connection.execute(entity.delete().where(*self._where(entity, key)))

    def now(self) -> datetime:
        return DatabaseClock(self.connection).now()

    def guard(self) -> None:
        guard = metadata.tables["policy_guard"]
        if (
            self.connection.execute(
                select(guard.c.guard_id).where(guard.c.guard_id == 1).with_for_update()
            ).first()
            is None
        ):
            raise RuntimeError("Policy guard is missing; run formal migrations.")
