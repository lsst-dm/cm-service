import os
from logging import getLogger
from logging.config import fileConfig

from sqlalchemy import create_engine, pool, text

import lsst.cmservice.core.db
from alembic import context

# this is the Alembic Config object, which provides
# access to the values within the .ini file in use.
config = context.config

# Interpret the config file for Python logging.
# This line sets up loggers basically.
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# add your model's MetaData object here
# for 'autogenerate' support
target_metadata = lsst.cmservice.core.db.Base.metadata

# other values from the config, defined by the needs of env.py,
# can be acquired using `config.get_main_option("...")`

logger = getLogger("alembic")


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode.

    This configures the context with just a URL
    and not an Engine, though an Engine is acceptable
    here as well.  By skipping the Engine creation
    we don't even need a DBAPI to be available.

    Calls to context.execute() here emit the given string to the
    script output.

    """
    url = next(
        (
            u
            for u in [
                os.getenv("DB__URL"),
                context.get_x_argument(as_dictionary=True).get("cm_database_url"),
                config.get_main_option("sqlalchemy.url", default=None),
                "sqlite://",
            ]
            if u is not None
        ),
    )
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Run migrations in 'online' mode.

    In this scenario we need to create an Engine
    and associate a connection with the context.

    The database engine URI is consumed in descending order from:
    - An `-x cm_database_url=...` CLI argument
    - A `DB__URL` environment variable
    - The value of `sqlalchemy.url` specified in the alembic.ini
    - A sqlite :memory: database
    """
    url = next(
        (
            u
            for u in [
                context.get_x_argument(as_dictionary=True).get("cm_database_url"),
                os.getenv("DB__URL"),
                config.get_main_option("sqlalchemy.url", default=None),
                "sqlite://",
            ]
            if u is not None
        ),
    )

    # Set PG* environment variables from DB__* environment variables to capture
    # any that are not part of the URL
    os.environ["PGPASSWORD"] = os.getenv("DB__PASSWORD", "")
    os.environ["PGPORT"] = os.getenv("DB__PORT", "5432")

    connectable = create_engine(url, poolclass=pool.NullPool)

    # Build the migration in the schema given on the command line or default to
    # the schema built into the metadata. This should be the app config value
    # derived from env:CM_DATABASE_SCHEMA.
    target_schema = (
        context.get_x_argument(as_dictionary=True).get("schema") or target_metadata.schema or "public"
    )
    alembic_schema = context.get_x_argument(as_dictionary=True).get("alembic_schema") or target_schema

    logger.info(f"Using schema {alembic_schema} for alembic revision table")
    logger.info(f"Using schema {target_schema} for database revisions")

    with connectable.connect() as connection:
        if connection.dialect.name == "postgresql":
            # Explicit pre-migration schema creation, needed for the schema
            # in which the alembic version_table is being created, if different
            # the target schema.
            connection.execute(text(f"CREATE SCHEMA IF NOT EXISTS {alembic_schema}"))
            connection.execute(text(f"CREATE SCHEMA IF NOT EXISTS {target_schema}"))
            connection.commit()
            # Operations are performed in the first schema on the search_path
            connection.execute(text(f"set search_path to {target_schema}"))
            connection.commit()

        elif connection.dialect.name == "sqlite":
            # SQLite does not care about schema
            alembic_schema = None
            target_schema = None

        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            version_table_schema=alembic_schema,
            include_schemas=False,
        )

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
