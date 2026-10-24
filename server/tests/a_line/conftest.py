import os
from datetime import UTC, datetime, timedelta
from pathlib import Path
from uuid import uuid4

import pytest
from alembic import command
from alembic.config import Config
from app.modules.identity.domain import Fault
from app.modules.identity.models import metadata
from astra_a.app import create_app
from astra_a.security import ArgonPasswords
from astra_a.storage import SqlRepository
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url

BASE = Path(__file__).resolve().parents[2] / "a_line"


class Clock:
    def __init__(self):
        self.value = datetime(2026, 10, 25, 8, tzinfo=UTC)

    def __call__(self):
        return self.value

    def advance(self, delta: timedelta):
        self.value += delta


class TestEffects:
    """Transactional recorder. No production audit/outbox tables are simulated."""

    fail = False

    def record(self, repo, actor, action, object_id, reason="", summary=None):
        if self.fail:
            raise Fault(503, "AUDIT_UNAVAILABLE", "审计暂不可用。", retry=2)
        repo.connection.execute(
            text("INSERT INTO a_test_events (action, object_id) VALUES (:action,:object_id)"),
            {"action": action, "object_id": object_id},
        )

    def membership_changed(self, repo, course_id):
        from app.modules.assignments.application import membership_changed

        membership_changed(repo, course_id)

    def account_disabled(self, repo, user_id):
        for member in repo.rows("course_members", user_id=user_id, status="ACTIVE"):
            repo.get("courses", member["course_id"], lock=True)
            self.membership_changed(repo, member["course_id"])


class TestCoordination:
    def before_change(self, repo, assignment, action):
        return None

    def status(self, repo, assignment):
        return {
            "grade_state": "REJUDGING" if assignment["active_rejudge_batch_id"] else "PROVISIONAL",
            "fairness_notice": None,
        }


@pytest.fixture
def env():
    url = os.environ.get("ASTRA_A_DATABASE_URL")
    if not url:
        pytest.fail("ASTRA_A_DATABASE_URL is required; real PostgreSQL tests never skip.")
    parsed = make_url(url)
    if parsed.get_backend_name() != "postgresql" or not (parsed.database or "").endswith("_test"):
        pytest.fail("Use a dedicated PostgreSQL database with suffix _test.")
    schema = "a_test_" + uuid4().hex
    root = create_engine(url)
    with root.begin() as connection:
        connection.exec_driver_sql(f"CREATE SCHEMA {schema}")
    engine = create_engine(url, connect_args={"options": f"-csearch_path={schema} -ctimezone=UTC"})
    config = Config(str(BASE / "alembic.ini"))
    try:
        with engine.begin() as connection:
            config.attributes["connection"] = connection
            command.upgrade(config, "head")
            connection.exec_driver_sql(
                "CREATE TABLE a_test_events (action text NOT NULL, object_id text NOT NULL)"
            )
        instance = Environment(engine)
        yield instance
    finally:
        engine.dispose()
        with root.begin() as connection:
            connection.exec_driver_sql(f"DROP SCHEMA {schema} CASCADE")
        root.dispose()


class Environment:
    password = "ExamplePassword123!"

    def __init__(self, engine):
        self.engine, self.clock, self.effects = engine, Clock(), TestEffects()
        self.tables, self.users = metadata.tables, {}
        self.coordination = TestCoordination()
        passwords = ArgonPasswords()
        with engine.begin() as connection:
            repo = SqlRepository(connection, self.clock)
            for name, role in [
                ("teacher_a", "TEACHER"),
                ("teacher_b", "TEACHER"),
                ("student_a", "STUDENT"),
                ("student_b", "STUDENT"),
                ("admin_a", "ADMIN"),
            ]:
                uid = str(uuid4())
                self.users[name] = uid
                repo.add(
                    "users",
                    dict(
                        user_id=uid,
                        login_name=name,
                        display_name=name,
                        role=role,
                        status="ACTIVE",
                        password_hash=passwords.hash(self.password),
                        must_change_password=False,
                        revision=1,
                        created_at=self.clock(),
                        updated_at=self.clock(),
                    ),
                )
        self.app = create_app(
            engine,
            self.effects,
            secret=b"test-only-session-key-32-bytes-long",
            origin="https://testserver",
            clock=self.clock,
            assignment_guard=self.coordination,
        )

    def client(self):
        return TestClient(self.app, base_url="https://testserver")

    def login(self, name, password=None):
        client = self.client()
        csrf = client.get("/api/v1/auth/session").json()["csrf_token"]
        client.headers.update({"Origin": "https://testserver", "X-CSRF-Token": csrf})
        response = client.post(
            "/api/v1/auth/login", json={"login_name": name, "password": password or self.password}
        )
        assert response.status_code == 200, response.text
        client.headers["X-CSRF-Token"] = client.get("/api/v1/auth/session").json()["csrf_token"]
        return client
