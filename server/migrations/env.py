import os

from alembic import context
from sqlalchemy import text

from app.shared.database import create_database_engine


def migrate(connection):
    if connection.scalar(text("SELECT to_regclass('alembic_version_a')")) is not None:
        raise RuntimeError("A validation schema cannot be migrated as a formal database.")
    context.configure(connection=connection, version_table="alembic_version")
    with context.begin_transaction():
        context.run_migrations()


connection = context.config.attributes.get("connection")
if connection is not None:
    migrate(connection)
else:
    engine = create_database_engine(os.environ["ASTRA_DATABASE_URL"])
    try:
        with engine.connect() as connection:
            # The legacy-chain probe starts a transaction; own its commit as well.
            with connection.begin():
                migrate(connection)
    finally:
        engine.dispose()
