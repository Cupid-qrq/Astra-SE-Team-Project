import os
from uuid import uuid4

import pytest
from sqlalchemy import create_engine
from sqlalchemy.engine import make_url


@pytest.fixture
def database():
    raw = os.environ.get("ASTRA_TEST_DATABASE_URL")
    if not raw:
        pytest.fail("ASTRA_TEST_DATABASE_URL is required; database tests never skip.")
    try:
        url = make_url(raw)
    except Exception:
        pytest.fail("Invalid test database configuration.", pytrace=False)
    if url.drivername != "postgresql+psycopg" or not (url.database or "").endswith("_test"):
        pytest.fail("Use a dedicated postgresql+psycopg database ending in _test.")
    schema = "b_shared_" + uuid4().hex
    root = create_engine(url, hide_parameters=True)
    engine = None
    created = False
    try:
        with root.begin() as connection:
            connection.exec_driver_sql(f'CREATE SCHEMA "{schema}"')
        created = True
        engine = create_engine(
            url,
            hide_parameters=True,
            pool_size=2,
            max_overflow=0,
            connect_args={"options": f"-csearch_path={schema} -ctimezone=Asia/Shanghai"},
        )
        with engine.begin() as connection:
            connection.exec_driver_sql(
                "CREATE TABLE entries (id integer PRIMARY KEY, value integer NOT NULL, "
                "UNIQUE(value) DEFERRABLE INITIALLY DEFERRED)"
            )
        yield engine
    finally:
        if engine is not None:
            engine.dispose()
        try:
            if created:
                with root.begin() as connection:
                    connection.exec_driver_sql(f'DROP SCHEMA "{schema}" CASCADE')
        finally:
            root.dispose()
