"""Real PostgreSQL HTTP acceptance; only test fixtures may synthesize completion."""

from dataclasses import replace
from uuid import uuid4

import pytest
from preflight_fixtures import draft
from sqlalchemy import text
from test_http import login

from app.main import create_app
from app.shared.config import Settings
from app.shared.passwords import ArgonPasswords
from app.shared.repository import SqlRepository
from app.shared.uow import UnitOfWork


@pytest.fixture
def environment(database):
    ids, snapshot = draft(database)
    hashed = ArgonPasswords().hash("ExamplePassword123!")
    with UnitOfWork(database) as conn:
        repo = SqlRepository(conn)
        for name in ("teacher", "student", "admin"):
            repo.change("users", ids[name], password_hash=hashed)
        teacher = repo.get("users", ids["teacher"])
        repo.add(
            "users",
            {
                **teacher,
                "user_id": str(uuid4()),
                "login_name": "teacher_b",
                "display_name": "teacher_b",
            },
        )
    config = Settings(
        "postgresql+psycopg://unused/astra_test",
        b"test-session-secret-at-least-32-bytes",
        "https://testserver",
        "test-readiness-token-at-least-32-bytes",
        profiles=(snapshot["profile"],),
    )
    app = create_app(config, engine=database)
    return database, ids, snapshot, config, app


def request_preflight(client, ids, snapshot, **patch):
    return client.post(
        "/api/v1/problem-versions/" + ids["draft"] + "/preflight",
        json={"expected_revision": snapshot["revision"], **patch},
    )


def accepted(environment):
    engine, ids, snapshot, _, app = environment
    teacher = login(app)
    response = request_preflight(teacher, ids, snapshot)
    assert response.status_code == 202, response.text
    return teacher, response.json()


def test_http_enqueues_deduplicates_and_reads_only_public_case_status(environment):
    engine, ids, snapshot, _, _ = environment
    teacher, receipt = accepted(environment)
    second = request_preflight(teacher, ids, snapshot)
    assert second.status_code == 202 and second.json() == receipt
    assert set(receipt) == {"preflight_id", "state", "content_digest"}
    response = teacher.get(
        "/api/v1/preflights/" + receipt["preflight_id"], headers={"X-Astra-Background": "1"}
    )
    assert response.status_code == 200, response.text
    value = response.json()
    assert value["version_id"] == ids["draft"] and value["state"] == "QUEUED"
    assert len(value["cases"]) == 4
    assert not any(
        secret in response.text
        for secret in ("SECRET", "frozen_blob", "engine_meta", "reference_programs")
    )
    with engine.connect() as conn:
        assert conn.scalar(text("SELECT count(*) FROM preflight_runs")) == 1
        assert conn.scalar(text("SELECT count(*) FROM preflight_jobs")) == 1
        assert (
            conn.scalar(text("SELECT count(*) FROM audit_events WHERE action='PREFLIGHT_QUEUED'"))
            == 1
        )
    refreshed = login(environment[-1])
    assert refreshed.get("/api/v1/preflights/" + receipt["preflight_id"]).json() == value


@pytest.mark.parametrize("name,status", [("student", 403), ("admin", 403), ("teacher_b", 404)])
def test_preflight_owner_role_and_course_apply_to_post_and_get(environment, name, status):
    _, ids, snapshot, _, app = environment
    _, receipt = accepted(environment)
    stranger = login(app, name)
    assert request_preflight(stranger, ids, snapshot).status_code == status
    assert stranger.get("/api/v1/preflights/" + receipt["preflight_id"]).status_code == status


def test_expected_revision_is_checked_before_any_enqueue(environment):
    engine, ids, snapshot, _, app = environment
    teacher = login(app)
    response = request_preflight(teacher, ids, snapshot, expected_revision=snapshot["revision"] - 1)
    assert response.status_code == 409, response.text
    with engine.connect() as conn:
        assert conn.scalar(text("SELECT count(*) FROM preflight_runs")) == 0
    assert request_preflight(teacher, ids, snapshot, actor_id=ids["admin"]).status_code == 422


def test_missing_profile_configuration_rejects_enqueue_but_keeps_history_readable(environment):
    engine, ids, snapshot, config, _ = environment
    _, receipt = accepted(environment)
    disabled = create_app(replace(config, profiles=()), engine=engine)
    teacher = login(disabled)
    response = request_preflight(teacher, ids, snapshot)
    assert response.status_code == 503, response.text
    assert teacher.get("/api/v1/preflights/" + receipt["preflight_id"]).status_code == 200


@pytest.mark.parametrize("target", ["archived", "disabled"])
def test_archived_course_or_disabled_teacher_cannot_enqueue(environment, target):
    engine, ids, snapshot, _, app = environment
    teacher = login(app)
    with engine.begin() as conn:
        if target == "archived":
            conn.execute(
                text("UPDATE courses SET status='ARCHIVED',archived_at=now() WHERE course_id=:id"),
                {"id": ids["course"]},
            )
        else:
            conn.execute(
                text("UPDATE users SET status='DISABLED' WHERE user_id=:id"), {"id": ids["teacher"]}
            )
    response = request_preflight(teacher, ids, snapshot)
    assert response.status_code in (401, 403, 409), response.text
    with engine.connect() as conn:
        assert conn.scalar(text("SELECT count(*) FROM preflight_runs")) == 0


def test_outbox_failure_rolls_back_entire_http_acceptance(environment):
    engine, ids, snapshot, _, app = environment
    teacher = login(app)
    with engine.begin() as conn:
        conn.exec_driver_sql(
            "CREATE FUNCTION fail_preflight_outbox() RETURNS trigger LANGUAGE plpgsql AS $$ BEGIN RAISE EXCEPTION 'PRIVATE_FAILURE'; END $$"
        )
        conn.exec_driver_sql(
            "CREATE TRIGGER fail_preflight_outbox BEFORE INSERT ON outbox_events FOR EACH ROW EXECUTE FUNCTION fail_preflight_outbox()"
        )
    response = request_preflight(teacher, ids, snapshot)
    assert response.status_code == 503, response.text
    assert "PRIVATE" not in response.text and "SECRET" not in response.text
    with engine.connect() as conn:
        for table in ("preflight_runs", "preflight_cases", "preflight_jobs"):
            assert conn.scalar(text("SELECT count(*) FROM " + table)) == 0
        assert (
            conn.scalar(text("SELECT count(*) FROM audit_events WHERE action='PREFLIGHT_QUEUED'"))
            == 0
        )


def test_background_status_poll_does_not_extend_idle_session(environment):
    engine, ids, _, _, _ = environment
    teacher, receipt = accepted(environment)
    with engine.begin() as conn:
        conn.execute(
            text("UPDATE sessions SET last_seen_at=now()-interval '5 minutes' WHERE user_id=:id"),
            {"id": ids["teacher"]},
        )
        before = conn.scalar(
            text("SELECT last_seen_at FROM sessions WHERE user_id=:id"), {"id": ids["teacher"]}
        )
    response = teacher.get(
        "/api/v1/preflights/" + receipt["preflight_id"], headers={"X-Astra-Background": "1"}
    )
    assert response.status_code == 200
    with engine.connect() as conn:
        assert (
            conn.scalar(
                text("SELECT last_seen_at FROM sessions WHERE user_id=:id"), {"id": ids["teacher"]}
            )
            == before
        )


def test_failed_preflight_summary_is_derived_only_from_safe_case_verdict(environment):
    engine, _, _, _, _ = environment
    teacher, receipt = accepted(environment)
    with engine.begin() as conn:
        conn.execute(
            text("UPDATE preflight_cases SET state='FINISHED',verdict='WA' WHERE preflight_id=:id"),
            {"id": receipt["preflight_id"]},
        )
        conn.execute(
            text(
                "UPDATE preflight_runs SET state='FAILED',started_at=created_at,finished_at=created_at WHERE preflight_id=:id"
            ),
            {"id": receipt["preflight_id"]},
        )
    result = teacher.get("/api/v1/preflights/" + receipt["preflight_id"])
    assert result.status_code == 200, result.text
    assert "WA" in result.json()["summary"]
    assert "SECRET" not in result.text
