import pytest
from sqlalchemy import text
from sqlalchemy.exc import OperationalError

from app.shared.database import create_database_engine


@pytest.mark.parametrize("url", ["", "sqlite://", "postgresql://localhost/x", "garbage"])
def test_rejects_invalid_database_urls_without_echoing_them(url):
    with pytest.raises(ValueError) as failure:
        create_database_engine(url)
    assert str(failure.value) == "Expected a postgresql+psycopg database URL."


def test_rejects_missing_database_name():
    with pytest.raises(ValueError):
        create_database_engine("postgresql+psycopg://localhost")


def test_connection_failure_is_not_silently_accepted():
    engine = create_database_engine("postgresql+psycopg://127.0.0.1:1/astra_test")
    try:
        with pytest.raises(OperationalError):
            with engine.connect():
                pass
    finally:
        engine.dispose()


def test_factory_enforces_utc_and_read_committed(database):
    engine = create_database_engine(database.url)
    try:
        with engine.connect() as connection:
            assert connection.scalar(text("SHOW TIME ZONE")) == "UTC"
            assert connection.get_isolation_level() == "READ COMMITTED"
    finally:
        engine.dispose()
