"""Browser cleanup must be scoped to exactly the schema owned by this run."""

import json
from pathlib import Path
from tempfile import TemporaryDirectory
from uuid import uuid4

import pytest
import web_harness
from sqlalchemy import text


@pytest.fixture
def browser_scope(database, monkeypatch):
    local = Path(__file__).resolve().parents[3] / ".local"
    local.mkdir(exist_ok=True)
    with TemporaryDirectory(prefix="b-browser-cleanup-", dir=local) as raw:
        target = Path(raw).resolve()
        assert target.parent == local.resolve()
        run = uuid4().hex
        monkeypatch.setenv("ASTRA_BROWSER_RUN", run)
        monkeypatch.setattr(web_harness, "SERVER", target / "server")
        url, schema, marker = web_harness.scope()
        marker.parent.mkdir(parents=True)
        marker.write_text(
            json.dumps({"schema": schema, "database": url.database}), encoding="utf-8"
        )
        with database.begin() as conn:
            conn.exec_driver_sql(f'CREATE SCHEMA "{schema}"')
        try:
            yield database, schema, marker
        finally:
            with database.begin() as conn:
                conn.exec_driver_sql(f'DROP SCHEMA IF EXISTS "{schema}" CASCADE')


def test_cleanup_is_idempotent_and_removes_owned_schema(browser_scope):
    engine, schema, marker = browser_scope
    web_harness.cleanup()
    web_harness.cleanup()
    with engine.connect() as conn:
        assert not conn.scalar(
            text("SELECT EXISTS(SELECT FROM pg_namespace WHERE nspname=:name)"), {"name": schema}
        )
    assert not marker.exists()


def test_cleanup_refuses_mismatched_marker(browser_scope):
    engine, schema, marker = browser_scope
    marker.write_text(
        json.dumps({"schema": "another_schema", "database": "wrong_test"}), encoding="utf-8"
    )
    with pytest.raises(RuntimeError, match="does not match"):
        web_harness.cleanup()
    with engine.connect() as conn:
        assert conn.scalar(
            text("SELECT EXISTS(SELECT FROM pg_namespace WHERE nspname=:name)"), {"name": schema}
        )
        assert conn.scalar(text("SELECT count(*) FROM entries")) == 0


def test_cleanup_rejects_untrusted_run_identifier(monkeypatch):
    monkeypatch.setenv("ASTRA_BROWSER_RUN", "../another_schema")
    with pytest.raises(RuntimeError, match="identifier"):
        web_harness.cleanup()
