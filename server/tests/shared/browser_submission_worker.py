# ruff: noqa: E402
"""Explicit browser-only executor double. Never imported by production."""

import json
import sys
from pathlib import Path

SERVER = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(SERVER), str(SERVER / "tests/shared")]
from sqlalchemy import create_engine, select
from web_harness import scope

from app.adapters.course_executor import ExecutionResult
from app.adapters.judge_profiles import SnapshotCatalog
from app.modules.submissions.worker import SubmissionWorker
from app.modules.submissions.worker_store import SubmissionStore
from app.shared.metadata import metadata


def main():
    url, schema, marker = scope()
    if json.loads(marker.read_text(encoding="utf-8")) != {
        "schema": schema,
        "database": url.database,
    }:
        raise RuntimeError("Browser fixture scope mismatch")
    engine = create_engine(
        url, hide_parameters=True, connect_args={"options": "-csearch_path=" + schema}
    )
    try:
        with engine.connect() as conn:
            profiles = (
                conn.execute(select(metadata.tables["problem_versions"].c.profile)).scalars().all()
            )

        class Executor:
            def __init__(self, image):
                self.image = image

            def execute(self, identity, language, code, stdin, timeout=40):
                if code not in (b"# public browser worker fixture\nprint(1)", b"print(123)"):
                    raise RuntimeError("Unexpected browser fixture code")
                return ExecutionResult(
                    "RUN", None, 0, b"123" if code == b"print(123)" else b"1", 1, None
                )

            def cancel(self, identity):
                return True

        profile = profiles[0]
        worker = SubmissionWorker(
            SubmissionStore(engine),
            SnapshotCatalog((profile,)),
            {row["language_key"]: Executor(row["image_digest"]) for row in profile["languages"]},
        )
        for _ in range(10):
            if not worker.run_once():
                break
        print("BROWSER_EXECUTOR_DOUBLE_COMPLETED")
    finally:
        engine.dispose()


if __name__ == "__main__":
    main()
