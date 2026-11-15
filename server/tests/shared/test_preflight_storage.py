import json
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from threading import Event
from time import sleep
from uuid import uuid4

import pytest
from alembic import command
from alembic.config import Config
from alembic.script import ScriptDirectory
from preflight_fixtures import catalog, draft
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError

from app.modules.identity.domain import Fault
from app.modules.judging.preflight import TransactionalPreflight
from app.modules.problems.application import Problems
from app.modules.problems.domain import verify_evidence
from app.shared.effects import TransactionalEffects
from app.shared.repository import SqlRepository
from app.shared.uow import UnitOfWork


@pytest.fixture
def lesson(database):
    ids, snapshot = draft(database)
    return database, ids, snapshot


def port(repo, snapshot):
    return TransactionalPreflight(repo, catalog(snapshot), TransactionalEffects(repo, str(uuid4())))


def enqueue(engine, ids, snapshot):
    with UnitOfWork(engine) as conn:
        repo = SqlRepository(conn)
        return port(repo, snapshot).enqueue(
            repo, {"user_id": ids["teacher"], "role": "TEACHER"}, ids["draft"]
        )


def finish_for_fixture(conn, pid):
    # Only a direct synthetic test fixture. There is no production completion writer.
    conn.execute(
        text("UPDATE preflight_cases SET state='FINISHED',verdict='AC' WHERE preflight_id=:id"),
        {"id": pid},
    )
    conn.execute(
        text(
            "UPDATE preflight_runs SET state='PASSED',started_at=created_at,finished_at=created_at WHERE preflight_id=:id"
        ),
        {"id": pid},
    )
    conn.execute(text("UPDATE preflight_jobs SET state='DONE' WHERE preflight_id=:id"), {"id": pid})


def test_preflight_migration_single_head_and_upgrade_preserves_a_rows(database):
    cfg = Config(str(Path(__file__).parents[2] / "alembic.ini"))
    assert ScriptDirectory.from_config(cfg).get_heads() == ["b019"]
    with database.begin() as conn:
        cfg.attributes["connection"] = conn
        command.upgrade(cfg, "b005")
        assert conn.scalar(text("SELECT count(*) FROM users")) == 0
        command.upgrade(cfg, "head")
        command.upgrade(cfg, "head")
        assert conn.scalar(text("SELECT version_num FROM alembic_version")) == "b019"
        for name in ("preflight_runs", "preflight_cases", "preflight_jobs"):
            assert conn.scalar(text("SELECT to_regclass(:name)"), {"name": name}) is not None


def test_enqueue_read_dedup_and_private_snapshot_are_transactional(lesson):
    engine, ids, snapshot = lesson
    first = enqueue(engine, ids, snapshot)
    second = enqueue(engine, ids, snapshot)
    assert first == second and first["state"] == "QUEUED"
    with UnitOfWork(engine) as conn:
        repo = SqlRepository(conn)
        service = port(repo, snapshot)
        value = service.read(repo, {"user_id": ids["teacher"]}, first["preflight_id"])
        assert len(value["cases"]) == 4 and "SECRET" not in json.dumps(value)
        assert service.evidence(repo, first["preflight_id"]) is None
        run = repo.get("preflight_runs", first["preflight_id"])
        assert (
            json.loads(bytes(run["frozen_blob"]))["testcases"][0]["input_text"]
            == "SECRET_INPUT\x00"
        )
        assert run["created_at"] == run["created_at"].replace(
            microsecond=(run["created_at"].microsecond // 1000) * 1000
        )
        assert len(repo.rows("preflight_runs")) == len(repo.rows("preflight_jobs")) == 1
        assert len(repo.rows("audit_events", action="PREFLIGHT_QUEUED")) == 1
        assert "SECRET" not in str(repo.rows("outbox_events"))


def test_edits_create_new_snapshot_and_old_evidence_cannot_publish(lesson):
    engine, ids, snapshot = lesson
    old = enqueue(engine, ids, snapshot)
    with UnitOfWork(engine) as conn:
        repo = SqlRepository(conn)
        repo.guard()
        effects = TransactionalEffects(repo, str(uuid4()))
        service = Problems(repo, effects)
        service.update(
            {"user_id": ids["teacher"], "role": "TEACHER"},
            ids["draft"],
            {"expected_revision": snapshot["revision"], "title": "changed"},
        )
        current = service.snapshot(ids["draft"])
    new = enqueue(engine, ids, snapshot)
    assert (
        old["preflight_id"] != new["preflight_id"]
        and old["content_digest"] != new["content_digest"]
    )
    with UnitOfWork(engine) as conn:
        finish_for_fixture(conn, old["preflight_id"])
        repo = SqlRepository(conn)
        evidence = port(repo, snapshot).evidence(repo, old["preflight_id"])
        assert evidence is not None and "SECRET" not in str(evidence)
        verify_evidence(snapshot, evidence)
        with pytest.raises(Fault, match="失效"):
            verify_evidence(current, evidence)


@pytest.mark.parametrize(
    "who", ["student", "forged_student", "foreign_teacher", "disabled_teacher"]
)
def test_permissions_reload_database_identity_before_status(lesson, who):
    engine, ids, snapshot = lesson
    receipt = enqueue(engine, ids, snapshot)
    with UnitOfWork(engine) as conn:
        repo = SqlRepository(conn)
        if who == "foreign_teacher":
            actor_id = str(uuid4())
            base = repo.get("users", ids["teacher"])
            repo.add("users", {**base, "user_id": actor_id, "login_name": "foreign"})
        else:
            actor_id = ids["student"] if "student" in who else ids["teacher"]
        if who == "disabled_teacher":
            repo.change("users", actor_id, status="DISABLED")
    with pytest.raises(Fault) as error:
        with UnitOfWork(engine) as conn:
            repo = SqlRepository(conn)
            port(repo, snapshot).read(
                repo,
                {"user_id": actor_id, "role": "STUDENT" if who == "student" else "TEACHER"},
                receipt["preflight_id"],
            )
    assert error.value.status in (403, 404)


@pytest.mark.parametrize(
    "table", ["preflight_cases", "preflight_jobs", "audit_events", "outbox_events"]
)
def test_write_failure_rolls_back_all_facts_and_has_safe_error_chain(lesson, table):
    engine, ids, snapshot = lesson
    with engine.begin() as conn:
        conn.exec_driver_sql(
            "CREATE FUNCTION fail_preflight() RETURNS trigger LANGUAGE plpgsql AS $$ BEGIN RAISE EXCEPTION 'SECRET_DATABASE_SENTINEL'; END $$"
        )
        conn.exec_driver_sql(
            f"CREATE TRIGGER fail_preflight BEFORE INSERT ON {table} FOR EACH ROW EXECUTE FUNCTION fail_preflight()"
        )
    with pytest.raises(Fault) as error:
        enqueue(engine, ids, snapshot)
    assert error.value.status == 503 and "SECRET" not in str(error.value)
    assert error.value.__context__ is None and error.value.__cause__ is None
    with engine.connect() as conn:
        for name in ("preflight_runs", "preflight_cases", "preflight_jobs"):
            assert conn.scalar(text(f"SELECT count(*) FROM {name}")) == 0
        assert (
            conn.scalar(text("SELECT count(*) FROM audit_events WHERE action='PREFLIGHT_QUEUED'"))
            == 0
        )


def test_concurrent_enqueue_reuses_one_committed_active_job(lesson):
    engine, ids, snapshot = lesson
    held, release, second_started = Event(), Event(), Event()

    def worker(first):
        with UnitOfWork(engine) as conn:
            repo = SqlRepository(conn)
            if not first:
                second_started.set()
            result = port(repo, snapshot).enqueue(repo, {"user_id": ids["teacher"]}, ids["draft"])
            if first:
                held.set()
                if not release.wait(8):
                    raise RuntimeError("fixture timeout")
            return result

    with ThreadPoolExecutor(max_workers=2) as pool:
        first = pool.submit(worker, True)
        assert held.wait(8)
        second = pool.submit(worker, False)
        try:
            assert second_started.wait(8)
            sleep(0.15)
            assert not second.done()
        finally:
            release.set()
        assert first.result(8) == second.result(8)
    with engine.connect() as conn:
        assert conn.scalar(text("SELECT count(*) FROM preflight_jobs")) == 1


def test_frozen_binding_terminal_history_and_version_reference_are_protected(lesson):
    engine, ids, snapshot = lesson
    pid = enqueue(engine, ids, snapshot)["preflight_id"]
    for change in ("content_digest='" + "f" * 64 + "'", "frozen_blob=decode('00','hex')"):
        with pytest.raises(IntegrityError):
            with engine.begin() as conn:
                conn.execute(
                    text("UPDATE preflight_runs SET " + change + " WHERE preflight_id=:id"),
                    {"id": pid},
                )
    with engine.begin() as conn:
        finish_for_fixture(conn, pid)
    with pytest.raises(IntegrityError):
        with engine.begin() as conn:
            conn.execute(
                text("UPDATE preflight_runs SET state='FAILED' WHERE preflight_id=:id"), {"id": pid}
            )
    with pytest.raises(IntegrityError):
        with engine.begin() as conn:
            conn.execute(
                text("DELETE FROM problem_versions WHERE version_id=:id"), {"id": ids["draft"]}
            )


def test_incomplete_passed_record_and_foreign_repository_cannot_supply_evidence(lesson):
    engine, ids, snapshot = lesson
    pid = enqueue(engine, ids, snapshot)["preflight_id"]
    with engine.begin() as conn:
        conn.execute(
            text(
                "UPDATE preflight_runs SET state='PASSED',started_at=created_at,finished_at=created_at WHERE preflight_id=:id"
            ),
            {"id": pid},
        )
    with UnitOfWork(engine) as first, UnitOfWork(engine) as second:
        repo = SqlRepository(first)
        service = port(repo, snapshot)
        assert service.evidence(repo, pid) is None
        with pytest.raises(RuntimeError, match="same repository"):
            service.evidence(SqlRepository(second), pid)


@pytest.mark.parametrize("method", ["enqueue", "read", "evidence"])
def test_policy_lock_failure_is_sanitized(method, lesson, monkeypatch):
    from sqlalchemy.exc import SQLAlchemyError

    engine, ids, snapshot = lesson
    with pytest.raises(Fault) as error:
        with UnitOfWork(engine) as conn:
            repo = SqlRepository(conn)
            service = port(repo, snapshot)

            def fail():
                raise SQLAlchemyError("SECRET_LOCK_DETAIL")

            monkeypatch.setattr(repo, "guard", fail)
            if method == "enqueue":
                service.enqueue(repo, {"user_id": ids["teacher"]}, ids["draft"])
            elif method == "read":
                service.read(repo, {"user_id": ids["teacher"]}, str(uuid4()))
            else:
                service.evidence(repo, str(uuid4()))
    assert error.value.status == 503
    assert error.value.__context__ is None and "SECRET" not in str(error.value)


@pytest.mark.parametrize("state", ["QUEUED", "PASSED"])
@pytest.mark.parametrize("extra", ["language", "sample", "hidden"])
def test_frozen_case_set_rejects_late_insert_without_changing_history(database, state, extra):
    ids, snapshot = draft(database, one_language=extra == "language")
    pid = enqueue(database, ids, snapshot)["preflight_id"]
    if state == "PASSED":
        with database.begin() as conn:
            finish_for_fixture(conn, pid)
    with UnitOfWork(database) as conn:
        repo = SqlRepository(conn)
        service = port(repo, snapshot)
        before = service.read(repo, {"user_id": ids["teacher"]}, pid)
        evidence_before = service.evidence(repo, pid)
    language = "python3" if extra == "language" else "cpp17"
    kind = "SAMPLE" if extra == "sample" else "HIDDEN"
    order = 1 if extra == "language" else 2
    with pytest.raises(IntegrityError):
        with database.begin() as conn:
            conn.execute(
                text(
                    "INSERT INTO preflight_cases(preflight_id,language_key,case_kind,case_order,state,verdict,engine_meta) VALUES(:id,:lang,:kind,:ord,'QUEUED',NULL,'{}')"
                ),
                {"id": pid, "lang": language, "kind": kind, "ord": order},
            )
    with UnitOfWork(database) as conn:
        repo = SqlRepository(conn)
        service = port(repo, snapshot)
        assert service.read(repo, {"user_id": ids["teacher"]}, pid) == before
        assert service.evidence(repo, pid) == evidence_before


def test_frozen_manifest_cannot_be_rebound(lesson):
    engine, ids, snapshot = lesson
    pid = enqueue(engine, ids, snapshot)["preflight_id"]
    with pytest.raises(IntegrityError):
        with engine.begin() as conn:
            conn.execute(
                text(
                    "UPDATE preflight_runs SET case_manifest=jsonb_set(case_manifest,'{0,case_order}','2') WHERE preflight_id=:id"
                ),
                {"id": pid},
            )
