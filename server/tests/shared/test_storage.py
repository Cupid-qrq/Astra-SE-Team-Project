from pathlib import Path
from uuid import uuid4

import pytest
from alembic import command
from alembic.config import Config
from alembic.script import ScriptDirectory
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError

from app.shared.effects import TransactionalEffects
from app.shared.repository import SqlRepository
from app.shared.uow import UnitOfWork


@pytest.fixture
def migrated(database):
    config = Config(str(Path(__file__).parents[2] / "alembic.ini"))
    with database.begin() as connection:
        config.attributes["connection"] = connection
        command.upgrade(config, "head")
    return database


def user(repo, name="teacher"):
    key = str(uuid4())
    repo.add(
        "users",
        dict(
            user_id=key,
            login_name=name,
            display_name=name,
            role="TEACHER",
            status="ACTIVE",
            password_hash="test-only",
            must_change_password=False,
            revision=1,
            created_at=repo.now(),
            updated_at=repo.now(),
        ),
    )
    return key


def test_single_head_upgrade_preserves_data(database):
    config = Config(str(Path(__file__).parents[2] / "alembic.ini"))
    assert ScriptDirectory.from_config(config).get_heads() == ["b006"]
    with database.begin() as conn:
        config.attributes["connection"] = conn
        command.upgrade(config, "b001")
        repo = SqlRepository(conn)
        key = user(repo)
        for revision in ["b002", "b003", "b004", "head", "head"]:
            command.upgrade(config, revision)
            assert repo.get("users", key)["display_name"] == "teacher"
        assert conn.scalar(text("SELECT version_num FROM alembic_version")) == "b006"
        assert conn.scalar(text("SELECT to_regclass('alembic_version_a')")) is None


def test_formal_chain_refuses_a_validation_schema(database):
    config = Config(str(Path(__file__).parents[2] / "alembic.ini"))
    with database.begin() as conn:
        conn.execute(text("CREATE TABLE alembic_version_a(version_num varchar(32))"))
    with pytest.raises(RuntimeError, match="validation"):
        with database.begin() as conn:
            config.attributes["connection"] = conn
            command.upgrade(config, "head")


def test_course_and_effects_commit_together(migrated):
    from app.modules.courses.application import Courses

    with UnitOfWork(migrated) as conn:
        repo = SqlRepository(conn)
        repo.guard()
        key = user(repo)
        service = Courses(repo, TransactionalEffects(repo, str(uuid4())))
        course = service.create({"user_id": key, "role": "TEACHER"}, {"title": "课程"})
    with migrated.connect() as conn:
        assert conn.scalar(text("SELECT count(*) FROM courses")) == 1
        assert conn.scalar(text("SELECT count(*) FROM audit_events")) == 1
        assert conn.scalar(text("SELECT count(*) FROM outbox_events")) == 1
        assert str(conn.scalar(text("SELECT object_id FROM audit_events"))) == course["course_id"]


def test_outbox_failure_rolls_back_audit_and_business(migrated):
    from app.modules.courses.application import Courses

    with migrated.begin() as conn:
        conn.execute(text("ALTER TABLE outbox_events ADD CONSTRAINT inject_failure CHECK (false)"))
    with pytest.raises(IntegrityError):
        with UnitOfWork(migrated) as conn:
            repo = SqlRepository(conn)
            key = user(repo)
            Courses(repo, TransactionalEffects(repo, str(uuid4()))).create(
                {"user_id": key, "role": "TEACHER"}, {"title": "回滚"}
            )
    with migrated.connect() as conn:
        for table in ["users", "courses", "audit_events", "outbox_events"]:
            assert conn.scalar(text(f"SELECT count(*) FROM {table}")) == 0


def test_audit_is_immutable_and_summary_contains_no_body(migrated):
    with UnitOfWork(migrated) as conn:
        repo = SqlRepository(conn)
        key = user(repo)
        TransactionalEffects(repo, str(uuid4())).record(
            repo, key, "USER_UPDATED", key, summary={"code": "sensitive sentinel"}
        )
    with migrated.connect() as conn:
        assert "sensitive sentinel" not in str(
            conn.execute(text("SELECT payload FROM outbox_events")).scalar()
        )
    for sql in ["UPDATE audit_events SET reason='changed'", "DELETE FROM audit_events"]:
        with pytest.raises(IntegrityError):
            with migrated.begin() as conn:
                conn.execute(text(sql))


def test_page_is_stable_and_bounded(migrated):
    with UnitOfWork(migrated) as conn:
        repo = SqlRepository(conn)
        for i in range(5):
            user(repo, f"user{i}")
        first = repo.page("users", limit=2)
        second = repo.page("users", limit=2, after=first[-1]["user_id"])
        assert len(first) == len(second) == 2
        assert {x["user_id"] for x in first}.isdisjoint(x["user_id"] for x in second)
        assert repo.rows("users", user_id=[]) == []
        with pytest.raises(ValueError):
            repo.page("users", limit=1000)
        with pytest.raises(ValueError):
            repo.get("course_members", str(uuid4()))


@pytest.mark.parametrize("table", ["audit_events", "outbox_events"])
def test_effect_write_failure_rolls_back_member_epoch(migrated, table):
    from datetime import timedelta

    with UnitOfWork(migrated) as conn:
        repo = SqlRepository(conn)
        key = user(repo)
        now = repo.now()
        cid, aid = str(uuid4()), str(uuid4())
        repo.add(
            "courses",
            dict(
                course_id=cid,
                teacher_id=key,
                title="course",
                status="ACTIVE",
                revision=1,
                archived_at=None,
                created_at=now,
                updated_at=now,
            ),
        )
        repo.add(
            "assignments",
            dict(
                assignment_id=aid,
                course_id=cid,
                title="assignment",
                open_at=now,
                due_at=now + timedelta(hours=1),
                ai_policy="DISABLED",
                published_at=now,
                revision=1,
                grade_epoch=1,
                fairness_review="NONE",
                active_grade_version=None,
                active_rejudge_batch_id=None,
                created_at=now,
                updated_at=now,
            ),
        )
        conn.exec_driver_sql(f"ALTER TABLE {table} ADD CONSTRAINT inject_failure CHECK (false)")
    with pytest.raises(IntegrityError):
        with UnitOfWork(migrated) as conn:
            repo = SqlRepository(conn)
            repo.guard()
            effects = TransactionalEffects(repo, str(uuid4()))
            effects.membership_changed(repo, cid)
            effects.record(repo, key, "MEMBER_UPDATED", cid)
    with migrated.connect() as conn:
        assert conn.execute(text("SELECT revision,grade_epoch FROM assignments")).one() == (1, 1)
        assert conn.scalar(text("SELECT count(*) FROM audit_events")) == 0


def test_guard_serializes_connections(migrated):
    from sqlalchemy.exc import OperationalError

    with UnitOfWork(migrated) as first:
        SqlRepository(first).guard()
        with pytest.raises(OperationalError):
            with UnitOfWork(migrated) as second:
                second.execute(text("SET LOCAL lock_timeout='100ms'"))
                SqlRepository(second).guard()
    with UnitOfWork(migrated) as second:
        SqlRepository(second).guard()


def test_migration_snapshots_match_a_history():
    base = Path(__file__).parents[2]
    for source in (base / "a_line/migrations/sql").glob("*.sql"):
        assert source.read_bytes() == (base / "migrations/sql" / source.name).read_bytes()


def test_effects_refuse_another_transaction(migrated):
    with UnitOfWork(migrated) as first, UnitOfWork(migrated) as second:
        repo = SqlRepository(first)
        with pytest.raises(RuntimeError, match="same repository"):
            TransactionalEffects(repo, str(uuid4())).record(
                SqlRepository(second), None, "TEST_EVENT", str(uuid4())
            )


def test_formal_metadata_has_no_schema_drift(migrated):
    from alembic.autogenerate import compare_metadata
    from alembic.migration import MigrationContext

    from app.shared.metadata import metadata

    with migrated.connect() as conn:
        context = MigrationContext.configure(
            conn, opts={"include_object": lambda obj, name, *args: name != "entries"}
        )
        assert compare_metadata(context, metadata) == []


@pytest.mark.parametrize(
    "action,expected",
    [
        ("MEMBER_UPDATED", "course"),
        ("PASSWORD_RESET", "user"),
        ("VERSION_UPDATED", "problem_version"),
        ("DEADLINE_EXTENDED", "assignment"),
    ],
)
def test_audit_tracks_aggregate_not_action_prefix(migrated, action, expected):
    with UnitOfWork(migrated) as conn:
        repo = SqlRepository(conn)
        key = user(repo)
        TransactionalEffects(repo, str(uuid4())).record(repo, key, action, key)
    with migrated.connect() as conn:
        assert conn.scalar(text("SELECT object_type FROM audit_events")) == expected
