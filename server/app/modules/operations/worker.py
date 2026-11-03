"""Deliver transactional notifications every five seconds."""

import argparse
import signal
import threading

from app.shared.config import Settings
from app.shared.database import create_database_engine
from app.shared.repository import SqlRepository
from app.shared.uow import UnitOfWork

from .application import deliver


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--once", action="store_true")
    args = parser.parse_args()
    engine = create_database_engine(Settings.from_env().database_url)
    stop = threading.Event()
    signal.signal(signal.SIGTERM, lambda *unused: stop.set())
    signal.signal(signal.SIGINT, lambda *unused: stop.set())
    try:
        while not stop.is_set():
            try:
                with UnitOfWork(engine) as conn:
                    deliver(SqlRepository(conn))
            except Exception:
                print("NOTIFICATION_DELIVERY_RETRY_REQUIRED")
                if args.once:
                    return 2
            if args.once:
                return 0
            stop.wait(5)
        return 0
    finally:
        engine.dispose()


if __name__ == "__main__":
    raise SystemExit(main())
