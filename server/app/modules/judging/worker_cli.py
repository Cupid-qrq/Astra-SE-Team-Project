"""Explicit standalone preflight Worker. Application startup never starts it."""

import argparse
import hashlib
import json
import signal
import threading

from app.adapters.course_executor import CourseExecutor
from app.adapters.judge_profiles import SnapshotCatalog
from app.modules.judging.worker import PreflightWorker
from app.modules.judging.worker_store import WorkerStore
from app.modules.submissions.worker import SubmissionWorker
from app.modules.submissions.worker_store import SubmissionStore
from app.shared.config import Settings
from app.shared.database import create_database_engine


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--executor-host", required=True)
    parser.add_argument("--image", required=True)
    parser.add_argument("--executor-script", default="/opt/astra-course-test/course_executor.py")
    parser.add_argument("--executor-state-dir", default="/var/lib/astra-course-executor")
    parser.add_argument("--enable-execution", action="store_true", required=True)
    parser.add_argument("--once", action="store_true")
    args = parser.parse_args()
    engine = None
    try:
        settings = Settings.from_env()
        catalog = SnapshotCatalog(settings.profiles)
        executor = CourseExecutor(
            args.executor_host,
            args.image,
            script=args.executor_script,
            state_dir=args.executor_state_dir,
        )
        languages = {
            row["language_key"] for profile in settings.profiles for row in profile["languages"]
        }
        if any(
            row["image_digest"] != args.image
            for profile in settings.profiles
            for row in profile["languages"]
        ):
            raise ValueError("Profile image mismatch")
        engine = create_database_engine(settings.database_url)
        store = WorkerStore(engine)
        store.bind_executor(
            hashlib.sha256(json.dumps(executor.command, separators=(",", ":")).encode()).hexdigest()
        )
        worker = PreflightWorker(store, catalog, {language: executor for language in languages})
        student_worker = SubmissionWorker(
            SubmissionStore(engine), catalog, {language: executor for language in languages}
        )
        stop = threading.Event()
        signal.signal(signal.SIGTERM, lambda *unused: stop.set())
        signal.signal(signal.SIGINT, lambda *unused: stop.set())
        while not stop.is_set():
            recovered = student_worker.recover_once() or worker.recover_once()
            worked = False if recovered else (student_worker.run_once() or worker.run_once())
            if args.once:
                return 0
            stop.wait(1 if worked or recovered else 2)
        return 0
    except Exception:
        print("PREFLIGHT_WORKER_UNAVAILABLE")
        return 2
    finally:
        if engine is not None:
            engine.dispose()


if __name__ == "__main__":
    raise SystemExit(main())
