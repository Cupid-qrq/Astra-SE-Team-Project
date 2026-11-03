"""Publication/reference boundaries. Completion is synthetic test data only."""

from copy import deepcopy
from uuid import uuid4

import pytest
from sqlalchemy import event, text
from sqlalchemy.exc import IntegrityError
from test_http import login
from test_preflight_http import accepted
from test_preflight_http import environment as environment
from test_preflight_storage import finish_for_fixture

from app.modules.courses.application import Courses
from app.modules.problems.application import Problems
from app.shared.effects import TransactionalEffects
from app.shared.repository import SqlRepository
from app.shared.uow import UnitOfWork


def publish(teacher, ids, snapshot, pid):
    return teacher.post(
        "/api/v1/problem-versions/" + ids["draft"] + "/publish",
        json={
            "expected_revision": snapshot["revision"],
            "preflight_id": pid,
            "reason": "核对全部测试与参考程序后发布此版本",
        },
    )


def test_only_matching_completed_evidence_can_publish(environment):
    engine, ids, snapshot, _, _ = environment
    teacher, receipt = accepted(environment)
    pid = receipt["preflight_id"]
    assert publish(teacher, ids, snapshot, pid).status_code == 409
    with engine.begin() as conn:
        finish_for_fixture(conn, pid)
    result = publish(teacher, ids, snapshot, pid)
    assert result.status_code == 200, result.text
    with engine.connect() as conn:
        assert (
            conn.scalar(
                text(
                    "SELECT published_preflight_id::text FROM problem_versions WHERE version_id=:id"
                ),
                {"id": ids["draft"]},
            )
            == pid
        )


def test_content_edit_invalidates_completed_evidence(environment):
    engine, ids, snapshot, _, _ = environment
    teacher, receipt = accepted(environment)
    with engine.begin() as conn:
        finish_for_fixture(conn, receipt["preflight_id"])
    changed = teacher.put(
        "/api/v1/problem-versions/" + ids["draft"] + "/references/cpp17",
        json={"expected_revision": snapshot["revision"], "code": "changed synthetic reference"},
    )
    assert changed.status_code == 200, changed.text
    assert (
        publish(
            teacher,
            ids,
            dict(snapshot, revision=changed.json()["revision"]),
            receipt["preflight_id"],
        ).status_code
        == 409
    )


def test_draft_delete_after_preflight_is_safe_conflict_with_all_materials_retained(environment):
    engine, ids, snapshot, _, _ = environment
    teacher, receipt = accepted(environment)
    response = teacher.request(
        "DELETE",
        "/api/v1/problem-versions/" + ids["draft"],
        json={
            "expected_revision": snapshot["revision"],
            "reason": "核对删除理由但该草稿已有预检历史记录",
        },
    )
    assert response.status_code == 409, response.text
    assert response.json()["code"] == "VERSION_IN_USE"
    with engine.connect() as conn:
        assert (
            conn.scalar(
                text("SELECT count(*) FROM testcases WHERE version_id=:id"), {"id": ids["draft"]}
            )
            == 1
        )
        assert (
            conn.scalar(
                text("SELECT count(*) FROM reference_programs WHERE version_id=:id"),
                {"id": ids["draft"]},
            )
            == 2
        )
        assert (
            conn.scalar(
                text("SELECT count(*) FROM preflight_runs WHERE preflight_id=:id"),
                {"id": receipt["preflight_id"]},
            )
            == 1
        )


@pytest.mark.parametrize("kind", ["missing", "other_version"])
def test_database_rejects_missing_or_cross_version_publication_reference(environment, kind):
    engine, ids, _, _, _ = environment
    _, receipt = accepted(environment)
    target = ids["version"] if kind == "other_version" else ids["draft"]
    # For a published immutable row, test the FK on INSERT of a new draft clone instead.
    with engine.connect() as conn:
        original = dict(
            conn.execute(
                text("SELECT * FROM problem_versions WHERE version_id=:id"), {"id": target}
            )
            .mappings()
            .one()
        )
    original.update(
        version_id=str(uuid4()),
        version_no=50,
        checksum=None,
        published_at=None,
        published_preflight_id=receipt["preflight_id"] if kind == "other_version" else str(uuid4()),
    )
    with pytest.raises(IntegrityError), UnitOfWork(engine) as conn:
        SqlRepository(conn).add("problem_versions", original)


def test_unauthorized_evidence_is_rejected_before_reading_frozen_material(environment):
    engine, ids, snapshot, _, app = environment
    _, receipt = accepted(environment)
    with UnitOfWork(engine) as conn:
        finish_for_fixture(conn, receipt["preflight_id"])
        repo = SqlRepository(conn)
        repo.guard()
        actor = repo.rows("users", login_name="teacher_b")[0]
        effects = TransactionalEffects(repo, str(uuid4()))
        cid = Courses(repo, effects).create(actor, {"title": "other teacher course"})["course_id"]
        service = Problems(repo, effects)
        pid = service.create(actor, {"course_id": cid})["problem_id"]
        value = {
            k: deepcopy(snapshot[k])
            for k in ("title", "statement", "samples", "tags", "profile", "source_ref")
        }
        vid = service.create_version(actor, {**value, "problem_id": pid})["version_id"]
        revision = service.put_case(
            actor, vid, 1, {"input_text": "1", "answer_text": "1", "expected_revision": 1}
        )["revision"]
        for language in ("cpp17", "python3"):
            revision = service.put_reference(
                actor, vid, language, {"code": "synthetic", "expected_revision": revision}
            )["revision"]
    teacher_b = login(app, "teacher_b")
    private_reads = []

    def observe(conn, cursor, statement, parameters, context, executemany):
        if (
            statement.lstrip().upper().startswith("SELECT")
            and "preflight_runs.frozen_blob" in statement
        ):
            private_reads.append(True)

    event.listen(engine, "before_cursor_execute", observe)
    try:
        response = publish(
            teacher_b, {"draft": vid}, {"revision": revision}, receipt["preflight_id"]
        )
    finally:
        event.remove(engine, "before_cursor_execute", observe)
    assert response.status_code == 404, response.text
    assert not private_reads


@pytest.mark.parametrize("kind", ["missing", "failed", "partial"])
def test_incomplete_failed_or_missing_evidence_never_publishes(environment, kind):
    engine, ids, snapshot, _, _ = environment
    teacher, receipt = accepted(environment)
    pid = receipt["preflight_id"]
    if kind == "missing":
        pid = str(uuid4())
    else:
        with engine.begin() as conn:
            if kind == "failed":
                conn.execute(
                    text(
                        "UPDATE preflight_cases SET state='FINISHED',verdict='WA' WHERE preflight_id=:id"
                    ),
                    {"id": pid},
                )
            else:
                conn.execute(
                    text(
                        "UPDATE preflight_cases SET state='FINISHED',verdict='AC' WHERE preflight_id=:id AND case_kind='SAMPLE'"
                    ),
                    {"id": pid},
                )
            conn.execute(
                text(
                    "UPDATE preflight_runs SET state=:state,started_at=created_at,finished_at=created_at WHERE preflight_id=:id"
                ),
                {"id": pid, "state": "FAILED" if kind == "failed" else "PASSED"},
            )
    assert publish(teacher, ids, snapshot, pid).status_code == (404 if kind == "missing" else 409)
    with engine.connect() as conn:
        assert (
            conn.scalar(
                text("SELECT published_at FROM problem_versions WHERE version_id=:id"),
                {"id": ids["draft"]},
            )
            is None
        )


def test_publication_audit_failure_rolls_back_published_version(environment):
    engine, ids, snapshot, _, _ = environment
    teacher, receipt = accepted(environment)
    with engine.begin() as conn:
        finish_for_fixture(conn, receipt["preflight_id"])
        conn.exec_driver_sql(
            "CREATE FUNCTION reject_publication_audit() RETURNS trigger LANGUAGE plpgsql AS $$ BEGIN IF NEW.action='VERSION_PUBLISHED' THEN RAISE EXCEPTION 'PRIVATE_PUBLICATION'; END IF; RETURN NEW; END $$"
        )
        conn.exec_driver_sql(
            "CREATE TRIGGER reject_publication_audit BEFORE INSERT ON audit_events FOR EACH ROW EXECUTE FUNCTION reject_publication_audit()"
        )
    result = publish(teacher, ids, snapshot, receipt["preflight_id"])
    assert result.status_code == 503 and "PRIVATE" not in result.text
    with engine.connect() as conn:
        value = (
            conn.execute(
                text(
                    "SELECT published_at,checksum,revision FROM problem_versions WHERE version_id=:id"
                ),
                {"id": ids["draft"]},
            )
            .mappings()
            .one()
        )
        assert (
            value["published_at"] is None
            and value["checksum"] is None
            and value["revision"] == snapshot["revision"]
        )


def test_b009_upgrade_preserves_preflight_history_and_has_reversible_constraints(environment):
    from pathlib import Path

    from alembic import command
    from alembic.config import Config

    engine, ids, _, _, _ = environment
    _, receipt = accepted(environment)
    cfg = Config(str(Path(__file__).parents[2] / "alembic.ini"))
    with engine.connect() as conn:
        before = bytes(
            conn.scalar(
                text("SELECT frozen_blob FROM preflight_runs WHERE preflight_id=:id"),
                {"id": receipt["preflight_id"]},
            )
        )
    with engine.begin() as conn:
        cfg.attributes["connection"] = conn
        command.downgrade(cfg, "b008")
        assert conn.scalar(text("SELECT version_num FROM alembic_version")) == "b008"
    with engine.begin() as conn:
        cfg.attributes["connection"] = conn
        command.upgrade(cfg, "head")
        assert conn.scalar(text("SELECT version_num FROM alembic_version")) == "b017"
        assert (
            bytes(
                conn.scalar(
                    text("SELECT frozen_blob FROM preflight_runs WHERE preflight_id=:id"),
                    {"id": receipt["preflight_id"]},
                )
            )
            == before
        )
        assert (
            conn.scalar(
                text("SELECT count(*) FROM preflight_cases WHERE preflight_id=:id"),
                {"id": receipt["preflight_id"]},
            )
            == 4
        )


def test_b009_invalid_legacy_reference_blocks_upgrade_without_rewriting_history(environment):
    from pathlib import Path

    from alembic import command
    from alembic.config import Config

    engine, ids, _, _, _ = environment
    cfg = Config(str(Path(__file__).parents[2] / "alembic.ini"))
    with engine.begin() as conn:
        cfg.attributes["connection"] = conn
        command.downgrade(cfg, "b008")
        row = dict(
            conn.execute(
                text("SELECT * FROM problem_versions WHERE version_id=:id"), {"id": ids["draft"]}
            )
            .mappings()
            .one()
        )
        row.update(version_id=str(uuid4()), version_no=51, published_preflight_id=str(uuid4()))
        SqlRepository(conn).add("problem_versions", row)
    with pytest.raises(IntegrityError), engine.begin() as conn:
        cfg.attributes["connection"] = conn
        command.upgrade(cfg, "head")
    with engine.connect() as conn:
        assert conn.scalar(text("SELECT version_num FROM alembic_version")) == "b008"
        assert (
            str(
                conn.scalar(
                    text(
                        "SELECT published_preflight_id FROM problem_versions WHERE version_id=:id"
                    ),
                    {"id": row["version_id"]},
                )
            )
            == row["published_preflight_id"]
        )
