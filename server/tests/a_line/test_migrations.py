import os
from pathlib import Path
from uuid import uuid4

import pytest
from alembic import command
from alembic.config import Config
from astra_a.storage import SqlRepository
from sqlalchemy import create_engine, text
from sqlalchemy.exc import IntegrityError
from test_assignments import make_assignment, publish
from test_problems import attach_evidence, make_version


def test_previous_revision_upgrade_preserves_identity_rows(env):
    # env first validates the configured URL and dedicated _test database suffix.
    engine = create_engine(os.environ["ASTRA_A_DATABASE_URL"])
    schema = "a_upgrade_" + uuid4().hex
    try:
        with engine.begin() as conn:
            conn.exec_driver_sql(f"CREATE SCHEMA {schema}")
            conn.exec_driver_sql(f"SET LOCAL search_path TO {schema}")
            config = Config(str(Path(__file__).parents[2] / "a_line/alembic.ini"))
            config.attributes["connection"] = conn
            command.upgrade(config, "a001")
            uid = str(uuid4())
            conn.execute(
                text(
                    "INSERT INTO users VALUES (:uid, 'old_user', '历史账号', 'STUDENT', 'ACTIVE', 'archived-test-hash', true, 7, now(), now())"
                ),
                {"uid": uid},
            )
            command.upgrade(config, "head")
            command.upgrade(config, "head")
            assert conn.execute(
                text("SELECT display_name, revision FROM users WHERE user_id=:uid"), {"uid": uid}
            ).one() == ("历史账号", 7)
            assert (
                conn.scalar(
                    text(
                        "SELECT count(*) FROM information_schema.tables WHERE table_schema=:schema AND table_name='problem_versions'"
                    ),
                    {"schema": schema},
                )
                == 1
            )
    finally:
        with engine.begin() as conn:
            conn.exec_driver_sql(f"DROP SCHEMA IF EXISTS {schema} CASCADE")
        engine.dispose()


def test_database_rejects_published_content_and_hidden_material_edits(env):
    _, _, _, vid, revision, _ = make_version(env)
    evidence = attach_evidence(env, vid)
    teacher = env.login("teacher_a")
    assert (
        teacher.post(
            f"/api/v1/problem-versions/{vid}/publish",
            json={
                "expected_revision": revision,
                "preflight_id": evidence["preflight_id"],
                "reason": "验证数据库也拒绝改写已经发布的内容",
            },
        ).status_code
        == 200
    )
    for statement in [
        "UPDATE problem_versions SET title='改写' WHERE version_id=:vid",
        "DELETE FROM testcases WHERE version_id=:vid",
        "UPDATE reference_programs SET code='changed'::bytea WHERE version_id=:vid",
    ]:
        with pytest.raises(IntegrityError):
            with env.engine.begin() as conn:
                conn.execute(text(statement), {"vid": vid})


def test_publication_audit_failure_rolls_back_revision_and_checksum(env):
    _, _, _, vid, revision, _ = make_version(env)
    evidence = attach_evidence(env, vid)
    teacher = env.login("teacher_a")
    env.effects.fail = True
    assert (
        teacher.post(
            f"/api/v1/problem-versions/{vid}/publish",
            json={
                "expected_revision": revision,
                "preflight_id": evidence["preflight_id"],
                "reason": "验证审计记录失败时不得发布题目版本",
            },
        ).status_code
        == 503
    )
    env.effects.fail = False
    value = teacher.get(f"/api/v1/problem-versions/{vid}").json()
    assert (
        value["revision"] == revision
        and value["published_at"] is None
        and value["checksum"] is None
    )


def test_each_previous_revision_upgrade_preserves_teaching_data(env):
    teacher, _, _, vid, aid, _ = make_assignment(env)
    publish(teacher, aid)
    groups = [
        ("a001", ["users", "courses", "course_members"]),
        (
            "a002",
            ["problem_families", "problems", "problem_versions", "testcases", "reference_programs"],
        ),
        ("a003", ["assignments", "assignment_items"]),
    ]
    with env.engine.begin() as conn:
        repo = SqlRepository(conn)
        saved = {t: repo.rows(t) for _, tables in groups for t in tables}
    engine = create_engine(os.environ["ASTRA_A_DATABASE_URL"])
    schema = "a_upgrade_" + uuid4().hex
    try:
        with engine.begin() as conn:
            conn.exec_driver_sql(f"CREATE SCHEMA {schema}")
            conn.exec_driver_sql(f"SET LOCAL search_path TO {schema}")
            config = Config(str(Path(__file__).parents[2] / "a_line/alembic.ini"))
            config.attributes["connection"] = conn
            repo = SqlRepository(conn)
            for revision, tables in groups:
                command.upgrade(config, revision)
                for table in tables:
                    for record in saved[table]:
                        # Load published materials before enabling publication, as in the application.
                        if table == "problem_versions":
                            record = dict(
                                record,
                                published_at=None,
                                checksum=None,
                                published_preflight_id=None,
                            )
                        if table == "assignments":
                            record = dict(record, published_at=None)
                        repo.add(table, record)
                if revision == "a002":
                    original = next(v for v in saved["problem_versions"] if v["version_id"] == vid)
                    repo.change(
                        "problem_versions",
                        vid,
                        published_at=original["published_at"],
                        checksum=original["checksum"],
                        published_preflight_id=original["published_preflight_id"],
                    )
                if revision == "a003":
                    repo.change(
                        "assignments", aid, published_at=saved["assignments"][0]["published_at"]
                    )
            command.upgrade(config, "head")
            command.upgrade(config, "head")
            assert repo.get("assignments", aid) == saved["assignments"][0]
            assert repo.get("problem_versions", vid) == saved["problem_versions"][0]
            assert repo.rows("testcases") == saved["testcases"]
    finally:
        with engine.begin() as conn:
            conn.exec_driver_sql(f"DROP SCHEMA IF EXISTS {schema} CASCADE")
        engine.dispose()
