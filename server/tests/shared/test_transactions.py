from datetime import UTC, timedelta

import pytest
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError

from app.shared.clock import DatabaseClock
from app.shared.uow import UnitOfWork


def rows(engine):
    with engine.connect() as connection:
        return connection.execute(text("SELECT id FROM entries ORDER BY id")).scalars().all()


def insert(connection, key, value):
    connection.execute(
        text("INSERT INTO entries(id,value) VALUES (:key,:value)"),
        {"key": key, "value": value},
    )


def test_commits_both_steps_only_on_success(database):
    with UnitOfWork(database) as connection:
        insert(connection, 1, 10)
        insert(connection, 2, 20)
        assert rows(database) == []
    assert rows(database) == [1, 2]
    assert connection.closed


def test_caller_exception_rolls_back_every_step(database):
    with pytest.raises(ValueError, match="caller"):
        with UnitOfWork(database) as connection:
            insert(connection, 1, 10)
            insert(connection, 2, 20)
            raise ValueError("caller")
    assert rows(database) == []
    assert connection.closed


def test_constraint_failure_releases_connection(database):
    with pytest.raises(IntegrityError):
        with UnitOfWork(database) as connection:
            insert(connection, 1, 10)
            insert(connection, 1, 20)
    assert rows(database) == []
    assert connection.closed
    with UnitOfWork(database) as recovered:
        insert(recovered, 3, 30)
    assert rows(database) == [3]


def test_deferred_commit_failure_rolls_back_and_pool_recovers(database):
    for _ in range(4):
        with pytest.raises(IntegrityError):
            with UnitOfWork(database) as connection:
                insert(connection, 1, 10)
                insert(connection, 2, 10)
        assert connection.closed
        assert rows(database) == []
    with UnitOfWork(database) as connection:
        insert(connection, 3, 30)
    assert rows(database) == [3]


def test_keyboard_interrupt_also_rolls_back(database):
    with pytest.raises(KeyboardInterrupt):
        with UnitOfWork(database) as connection:
            insert(connection, 1, 10)
            raise KeyboardInterrupt
    assert connection.closed
    assert rows(database) == []


def test_database_clock_advances_inside_same_transaction(database):
    with UnitOfWork(database) as connection:
        clock = DatabaseClock(connection)
        started = connection.scalar(text("SELECT transaction_timestamp()"))
        first = clock.now()
        connection.execute(text("SELECT pg_sleep(0.03)"))
        second = clock.now()
        assert connection.scalar(text("SELECT transaction_timestamp()")) == started
        assert second - first >= timedelta(milliseconds=20)
        assert first.tzinfo is UTC and second.tzinfo is UTC
        assert first.microsecond % 1000 == second.microsecond % 1000 == 0


def test_uow_cannot_be_nested_or_reused(database):
    uow = UnitOfWork(database)
    with uow as connection:
        insert(connection, 1, 10)
        with pytest.raises(RuntimeError):
            with uow:
                pass
    with pytest.raises(RuntimeError):
        with uow:
            pass
    assert rows(database) == [1]
