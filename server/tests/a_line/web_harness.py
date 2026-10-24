# ruff: noqa: E402
"""Explicit browser-test harness. Never import from the production application."""

import atexit
import os
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path
from uuid import uuid4

SERVER = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(SERVER), str(SERVER / "a_line")]

import uvicorn
from alembic import command
from alembic.config import Config
from app.modules.assignments.application import Assignments
from app.modules.courses.application import Courses
from app.modules.identity.domain import utc
from app.modules.problems.application import Problems
from app.modules.problems.domain import content_digest, profile_digest
from astra_a.app import create_app
from astra_a.security import ArgonPasswords
from astra_a.storage import SqlRepository
from conftest import TestCoordination, TestEffects
from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.x509.oid import NameOID
from sqlalchemy import create_engine
from sqlalchemy.engine import make_url
from test_problems import SyntheticPreflight, profile


def main():
    url = os.environ["ASTRA_A_DATABASE_URL"]
    if not (make_url(url).database or "").endswith("_test"):
        raise RuntimeError("Browser harness requires a dedicated _test database.")
    cert_dir = SERVER.parent / ".local/a-browser-tls"
    cert_dir.mkdir(parents=True, exist_ok=True)
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    name = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "localhost")])
    now = datetime.now(UTC)
    cert = (
        x509.CertificateBuilder()
        .subject_name(name)
        .issuer_name(name)
        .public_key(key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(now - timedelta(minutes=5))
        .not_valid_after(now + timedelta(days=2))
        .add_extension(x509.SubjectAlternativeName([x509.DNSName("localhost")]), critical=False)
        .sign(key, hashes.SHA256())
    )
    (cert_dir / "key.pem").write_bytes(
        key.private_bytes(
            serialization.Encoding.PEM,
            serialization.PrivateFormat.PKCS8,
            serialization.NoEncryption(),
        )
    )
    (cert_dir / "cert.pem").write_bytes(cert.public_bytes(serialization.Encoding.PEM))
    schema = "a_browser_" + uuid4().hex
    root = create_engine(url)
    with root.begin() as connection:
        connection.exec_driver_sql(f"CREATE SCHEMA {schema}")
    engine = create_engine(url, connect_args={"options": f"-csearch_path={schema} -ctimezone=UTC"})

    def cleanup():
        engine.dispose()
        with root.begin() as connection:
            connection.exec_driver_sql(f"DROP SCHEMA IF EXISTS {schema} CASCADE")
        root.dispose()

    atexit.register(cleanup)
    config = Config(str(SERVER / "a_line/alembic.ini"))
    passwords = ArgonPasswords()
    with engine.begin() as connection:
        config.attributes["connection"] = connection
        command.upgrade(config, "head")
        connection.exec_driver_sql(
            "CREATE TABLE a_test_events (action text NOT NULL, object_id text NOT NULL)"
        )
        repo = SqlRepository(connection)
        for index, (login, role) in enumerate(
            [
                ("teacher_a", "TEACHER"),
                ("teacher_b", "TEACHER"),
                ("student_a", "STUDENT"),
                ("admin_a", "ADMIN"),
            ],
            1,
        ):
            repo.add(
                "users",
                dict(
                    user_id=f"10000000-0000-4000-8000-{index:012}",
                    login_name=login,
                    display_name=login,
                    role=role,
                    status="ACTIVE",
                    password_hash=passwords.hash("ExamplePassword123!"),
                    must_change_password=False,
                    revision=1,
                    created_at=repo.now(),
                    updated_at=repo.now(),
                ),
            )
        # Explicit synthetic teaching fixture for browser tests; no program is executed.
        effects = TestEffects()
        actor = repo.get("users", "10000000-0000-4000-8000-000000000001")
        courses = Courses(repo, effects)
        cid = courses.create(actor, {"title": "编辑器测试课程"})["course_id"]
        courses.member(
            actor,
            cid,
            "10000000-0000-4000-8000-000000000003",
            {"status": "ACTIVE", "expected_revision": 1},
        )
        service = Problems(repo, effects)
        pid = service.create(actor, {"course_id": cid})["problem_id"]
        content = {
            "problem_id": pid,
            "title": "两数之和",
            "statement": "输入两个整数，输出它们的和。",
            "samples": [{"input": "1 2", "output": "3"}],
            "tags": ["基础"],
            "profile": profile(),
            "source_ref": "浏览器测试合成题目",
        }
        vid = service.create_version(actor, content)["version_id"]
        service.put_case(
            actor, vid, 1, {"input_text": "3 4", "answer_text": "7", "expected_revision": 1}
        )
        for revision, lang in enumerate(["cpp17", "python3"], 2):
            service.put_reference(
                actor,
                vid,
                lang,
                {
                    "code": "synthetic test reference - never executed",
                    "expected_revision": revision,
                },
            )
        snapshot = service.snapshot(vid)
        evidence = {
            "preflight_id": str(uuid4()),
            "version_id": vid,
            "content_digest": content_digest(snapshot),
            "profile_hash": profile_digest(snapshot["profile"]),
            "state": "PASSED",
            "cases": [
                {
                    "language_key": lang,
                    "case_kind": kind,
                    "case_order": 1,
                    "state": "FINISHED",
                    "verdict": "AC",
                }
                for lang in ["cpp17", "python3"]
                for kind in ["SAMPLE", "HIDDEN"]
            ],
        }
        service.preflight = SyntheticPreflight(evidence)
        service.publish(
            actor,
            vid,
            {
                "expected_revision": 4,
                "preflight_id": evidence["preflight_id"],
                "reason": "浏览器合成测试证据，仅用于测试装配",
            },
        )
        assignments = Assignments(repo, effects, TestCoordination())
        aid = assignments.create(
            actor,
            {
                "course_id": cid,
                "title": "编辑器固定作业",
                "items": [{"problem_id": pid, "version_id": vid, "points": 100}],
                "open_at": utc(repo.now() - timedelta(hours=1)),
                "due_at": utc(repo.now() + timedelta(days=1)),
                "ai_policy": "DISABLED",
            },
        )["assignment_id"]
        assignments.publish(
            actor, aid, {"expected_revision": 1, "reason": "专供浏览器独立测试的固定教学作业"}
        )
        from app.modules.learning.application import seed_global_feedback

        seed_global_feedback(repo, "10000000-0000-4000-8000-000000000004")
    app = create_app(
        engine,
        TestEffects(),
        secret=os.urandom(32),
        origin="https://localhost:4175",
        profiles=[profile()],
        assignment_guard=TestCoordination(),
    )

    @app.get("/health")
    def health():
        return {"status": "test-ready"}

    uvicorn.run(app, host="127.0.0.1", port=8011, access_log=False, log_level="warning")


if __name__ == "__main__":
    main()
