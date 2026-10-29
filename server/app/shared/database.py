"""PostgreSQL connection factory. This function never creates business schema."""

from sqlalchemy import create_engine
from sqlalchemy.engine import Engine, make_url
from sqlalchemy.exc import ArgumentError


def create_database_engine(database_url: str) -> Engine:
    """Build a bounded pool; connection errors propagate to the caller."""
    try:
        url = make_url(database_url)
    except ArgumentError:
        raise ValueError("Expected a postgresql+psycopg database URL.") from None
    if url.drivername != "postgresql+psycopg" or not url.database:
        raise ValueError("Expected a postgresql+psycopg database URL.")
    return create_engine(
        url,
        isolation_level="READ COMMITTED",
        pool_pre_ping=True,
        pool_size=5,
        max_overflow=5,
        pool_timeout=5,
        hide_parameters=True,
        echo=False,
        connect_args={"connect_timeout": 5, "options": "-c timezone=UTC"},
    )
