# ruff: noqa: E402
"""Explicit formal-app browser harness; never imported by production."""

import json
import os
import re
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path

SERVER = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(SERVER), str(SERVER / "tests/shared")]

import uvicorn
from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.x509.oid import NameOID
from http_fixtures import profile
from sqlalchemy import create_engine
from sqlalchemy.engine import make_url
from teaching_fixtures import seed

from app.main import create_app
from app.modules.learning.application import seed_global_feedback
from app.shared.config import Settings
from app.shared.passwords import ArgonPasswords
from app.shared.repository import SqlRepository
from app.shared.uow import UnitOfWork


def scope():
    run = os.environ.get("ASTRA_BROWSER_RUN", "")
    if re.fullmatch("[0-9a-f]{32}", run) is None:
        raise RuntimeError("Formal browser run identifier is required.")
    url = make_url(os.environ["ASTRA_TEST_DATABASE_URL"])
    if url.drivername != "postgresql+psycopg" or not (url.database or "").endswith("_test"):
        raise RuntimeError("Formal browser harness requires a dedicated PostgreSQL _test database.")
    schema = "b_browser_" + run
    marker = SERVER.parent / ".local" / ("b-browser-" + run + ".json")
    return url, schema, marker


def cleanup():
    url, schema, marker = scope()
    try:
        data = json.loads(marker.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return
    if data != {"schema": schema, "database": url.database}:
        raise RuntimeError("Browser schema marker does not match this run.")
    root = create_engine(url, hide_parameters=True)
    try:
        with root.begin() as conn:
            conn.exec_driver_sql("SET LOCAL lock_timeout = '3000ms'")
            conn.exec_driver_sql(f'DROP SCHEMA IF EXISTS "{schema}" CASCADE')
        marker.unlink(missing_ok=True)
    finally:
        root.dispose()


def tls():
    target = SERVER.parent / ".local/b-browser-tls"
    target.mkdir(parents=True, exist_ok=True)
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
    (target / "key.pem").write_bytes(
        key.private_bytes(
            serialization.Encoding.PEM,
            serialization.PrivateFormat.PKCS8,
            serialization.NoEncryption(),
        )
    )
    (target / "cert.pem").write_bytes(cert.public_bytes(serialization.Encoding.PEM))


def main():
    url, schema, marker = scope()
    marker.parent.mkdir(parents=True, exist_ok=True)
    with marker.open("x", encoding="utf-8") as handle:
        json.dump({"schema": schema, "database": url.database}, handle)
    root = create_engine(url, hide_parameters=True)
    engine = None
    try:
        with root.begin() as conn:
            conn.exec_driver_sql(f'CREATE SCHEMA "{schema}"')
        engine = create_engine(
            url,
            hide_parameters=True,
            connect_args={"options": f"-csearch_path={schema} -ctimezone=UTC"},
        )
        public_profile = profile()
        ids = seed(engine, SERVER / "alembic.ini", profile=public_profile, browser=True)
        passwords = ArgonPasswords()
        with UnitOfWork(engine) as conn:
            repo = SqlRepository(conn)
            for key in ("teacher", "student", "admin"):
                repo.change("users", ids[key], password_hash=passwords.hash("ExamplePassword123!"))
            teacher = repo.get("users", ids["teacher"])
            assert teacher is not None
            repo.add(
                "users",
                {
                    **teacher,
                    "user_id": "10000000-0000-4000-8000-000000000002",
                    "login_name": "teacher_b",
                    "display_name": "teacher_b",
                },
            )
            seed_global_feedback(repo, ids["admin"])
        tls()
        app = create_app(
            Settings(
                str(url.render_as_string(hide_password=False)),
                os.urandom(32),
                "https://localhost:4175",
                os.urandom(32).hex(),
                profiles=(public_profile,),
            ),
            engine=engine,
        )
        uvicorn.run(app, host="127.0.0.1", port=8012, access_log=False, log_level="warning")
    finally:
        if engine is not None:
            engine.dispose()
        root.dispose()
        # Graceful exits clean here; Playwright global teardown also cleans after a forced stop.
        cleanup()


if __name__ == "__main__":
    if sys.argv[1:] == ["--cleanup"]:
        cleanup()
    elif sys.argv[1:]:
        raise SystemExit("Unknown harness argument")
    else:
        main()
