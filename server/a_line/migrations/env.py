import os
from alembic import context
from sqlalchemy import create_engine

config = context.config


def migrate(connection):
    context.configure(connection=connection, version_table="alembic_version_a")
    with context.begin_transaction():
        context.run_migrations()


if config.attributes.get("connection") is not None:
    migrate(config.attributes["connection"])
else:
    url = os.environ["ASTRA_A_DATABASE_URL"]
    engine = create_engine(url)
    with engine.connect() as connection:
        migrate(connection)
