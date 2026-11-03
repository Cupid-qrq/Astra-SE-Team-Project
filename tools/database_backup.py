"""PostgreSQL backup/restore to a NEW database. Secrets stay in child environment."""

import argparse
import hashlib
import json
import os
import re
import shutil
import subprocess
from contextlib import contextmanager
from datetime import UTC, datetime
from pathlib import Path
from urllib.parse import unquote, urlsplit


def pg_environment(url, database=None):
    env = {
        key: os.environ[key]
        for key in ("PATH", "SystemRoot", "WINDIR", "TEMP", "TMP", "HOME", "LANG")
        if key in os.environ
    }
    env.update(
        PGHOST=url.hostname or "127.0.0.1",
        PGPORT=str(url.port or 5432),
        PGUSER=unquote(url.username or ""),
        PGPASSWORD=unquote(url.password or ""),
        PGDATABASE=database or url.path.lstrip("/"),
        PGCONNECT_TIMEOUT="10",
        PGOPTIONS="-c timezone=UTC",
    )
    return env


def run(command, env):
    completed = subprocess.run(command, env=env, capture_output=True, timeout=600)
    if completed.returncode:
        raise RuntimeError("POSTGRES_TOOL_FAILED_" + Path(command[0]).name)
    return completed.stdout.decode("utf-8")


@contextmanager
def exported_snapshot(url):
    holder = subprocess.Popen(
        ["psql", "-qAt", "-v", "ON_ERROR_STOP=1"],
        env=pg_environment(url),
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
        text=True,
        encoding="utf-8",
    )
    try:
        holder.stdin.write(
            "BEGIN ISOLATION LEVEL REPEATABLE READ READ ONLY;\nSELECT pg_export_snapshot();\n"
        )
        holder.stdin.flush()
        snapshot = holder.stdout.readline().strip()
        if re.fullmatch(r"[0-9A-Fa-f-]+", snapshot) is None:
            raise RuntimeError("Snapshot export failed")
        yield snapshot
    finally:
        if holder.poll() is None:
            holder.stdin.write("ROLLBACK;\n\\q\n")
            holder.stdin.flush()
            try:
                holder.wait(timeout=10)
            except subprocess.TimeoutExpired:
                holder.kill()
                holder.wait()


def evidence(url, database=None, snapshot=None):
    env = pg_environment(url, database)

    def query(sql):
        if snapshot:
            sql = (
                "BEGIN ISOLATION LEVEL REPEATABLE READ READ ONLY; SET TRANSACTION SNAPSHOT '"
                + snapshot
                + "'; "
                + sql
                + "; COMMIT;"
            )
        return run(["psql", "-qAt", "-v", "ON_ERROR_STOP=1", "-c", sql], env)

    tables = query(
        "SELECT tablename FROM pg_tables WHERE schemaname='public' ORDER BY tablename"
    ).splitlines()
    counts = {}
    checks = []
    for table in tables:
        quoted = '"' + table.replace('"', '""') + '"'
        counts[table] = int(query("SELECT count(*) FROM " + quoted).strip())
        rows = query(
            "SELECT row_to_json(t)::text FROM "
            + quoted
            + " t ORDER BY row_to_json(t)::text LIMIT 100"
        ).splitlines()
        checks.extend(hashlib.sha256((table + row).encode()).hexdigest() for row in rows)
    return dict(counts=counts, sample_hashes=checks[:100], checked_records=min(len(checks), 100))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=["backup", "restore", "inventory"])
    parser.add_argument("--file", type=Path, required=True)
    parser.add_argument("--target")
    args = parser.parse_args()
    url = urlsplit(os.environ["ASTRA_DATABASE_URL"])
    if url.scheme != "postgresql+psycopg":
        raise ValueError("PostgreSQL URL required")
    if args.action == "inventory":
        now = datetime.now(UTC).timestamp()
        print(
            json.dumps(
                {
                    "files": [
                        {
                            "name": p.name,
                            "older_than_30_days": now - p.stat().st_mtime > 30 * 86400,
                        }
                        for p in args.file.glob("*.dump")
                    ]
                }
            )
        )
        return 0
    if not shutil.which("pg_dump") or not shutil.which("pg_restore"):
        raise RuntimeError("PostgreSQL client tools are required on PATH")
    if args.action == "backup":
        if args.file.exists():
            raise ValueError("Backup destination already exists")
        args.file.parent.mkdir(parents=True, exist_ok=True)
        descriptor = os.open(args.file, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
        os.close(descriptor)
        with exported_snapshot(url) as snapshot:
            run(
                [
                    "pg_dump",
                    "--snapshot",
                    snapshot,
                    "--format=custom",
                    "--no-owner",
                    "--no-privileges",
                    "--file",
                    str(args.file),
                ],
                pg_environment(url),
            )
            manifest = dict(
                created_at=datetime.now(UTC).isoformat(),
                sha256=hashlib.sha256(args.file.read_bytes()).hexdigest(),
                evidence=evidence(url, snapshot=snapshot),
            )
        args.file.with_suffix(args.file.suffix + ".json").write_text(
            json.dumps(manifest, indent=2), encoding="utf-8"
        )
        print(
            json.dumps(
                {
                    "backup_created": True,
                    "checked_records": manifest["evidence"]["checked_records"],
                }
            )
        )
    else:
        if (
            not args.target
            or not re.fullmatch(r"[a-z][a-z0-9_]{0,45}_restore", args.target)
            or args.target == url.path.lstrip("/")
        ):
            raise ValueError("Restore target must be a NEW *_restore database")
        manifest = json.loads(
            args.file.with_suffix(args.file.suffix + ".json").read_text(encoding="utf-8")
        )
        if hashlib.sha256(args.file.read_bytes()).hexdigest() != manifest["sha256"]:
            raise ValueError("Backup digest mismatch")
        admin_env = pg_environment(url, "postgres")
        exists = run(
            [
                "psql",
                "-At",
                "-c",
                "SELECT count(*) FROM pg_database WHERE datname='" + args.target + "'",
            ],
            admin_env,
        ).strip()
        if exists != "0":
            raise ValueError("Restore target already exists")
        run(
            [
                "psql",
                "-v",
                "ON_ERROR_STOP=1",
                "-c",
                'CREATE DATABASE "' + args.target + '"',
            ],
            admin_env,
        )
        run(
            [
                "pg_restore",
                "--exit-on-error",
                "--no-owner",
                "--no-privileges",
                "--dbname",
                args.target,
                str(args.file),
            ],
            pg_environment(url, args.target),
        )
        restored = evidence(url, args.target)
        if restored != manifest["evidence"]:
            raise RuntimeError("Restore reconciliation failed")
        print(
            json.dumps(
                {
                    "restored": True,
                    "checked_records": restored["checked_records"],
                    "reconciled": True,
                }
            )
        )
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception:
        raise SystemExit("DATABASE_BACKUP_OPERATION_FAILED") from None
