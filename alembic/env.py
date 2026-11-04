import os
from logging import getLogger
from logging.config import fileConfig

from alembic.runtime.environment import NameFilterParentNames, NameFilterType
from sqlalchemy import create_engine, make_url, pool, text

from alembic import context
from lsst.cmservice.models.db.base import BaseSQLModel

# this is the Alembic Config object, which provides
# access to the values within the .ini file in use.
config = context.config

# Interpret the config file for Python logging.
# This line sets up loggers basically.
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# add your model's MetaData object here
# for 'autogenerate' support
TARGET_METADATA = BaseSQLModel.metadata

# Build the migration in the schema given on the command line or default to
# the schema built into the metadata. This should be the app config value
# derived from env:CM_DATABASE_SCHEMA.
TARGET_SCHEMA: str = (
    context.get_x_argument(as_dictionary=True).get("schema") or TARGET_METADATA.schema or "public"
)

ALEMBIC_SCHEMA: str = context.get_x_argument(as_dictionary=True).get("alembic_schema") or TARGET_SCHEMA

# other values from the config, defined by the needs of env.py,
# can be acquired using `config.get_main_option("...")`

logger = getLogger("alembic")


def schema_name_filter(name: str | None, type_: NameFilterType, parent_names: NameFilterParentNames) -> bool:
    """Limit autogenerate reflection to the target schema."""
    if type_ == "schema":
        return name == TARGET_SCHEMA
    return True


def get_database_url(candidates: list[str | None]) -> str:
    """Returns the first database URL from the candidates, which must be a
    PostgreSQL database; no other database backend is supported.
    """
    url = next((u for u in candidates if u is not None), None)
    if url is None:
        msg = "No database URL: set DB__URL or pass `-x cm_database_url=...`"
        raise RuntimeError(msg)
    if (backend := make_url(url).get_backend_name()) != "postgresql":
        msg = f"Unsupported database backend {backend!r}; only PostgreSQL is supported"
        raise RuntimeError(msg)
    return url


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode.

    This configures the context with just a URL
    and not an Engine, though an Engine is acceptable
    here as well.  By skipping the Engine creation
    we don't even need a DBAPI to be available.

    Calls to context.execute() here emit the given string to the
    script output.

    """
    url = get_database_url(
        [
            os.getenv("DB__URL"),
            context.get_x_argument(as_dictionary=True).get("cm_database_url"),
            config.get_main_option("sqlalchemy.url", default=None),
        ]
    )
    context.configure(
        url=url,
        target_metadata=TARGET_METADATA,
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
    """
    url = get_database_url(
        [
            context.get_x_argument(as_dictionary=True).get("cm_database_url"),
            os.getenv("DB__URL"),
            config.get_main_option("sqlalchemy.url", default=None),
        ]
    )

    # Set PG* environment variables from DB__* environment variables to capture
    # any that are not part of the URL
    os.environ["PGPASSWORD"] = os.getenv("DB__PASSWORD", "")
    os.environ["PGPORT"] = os.getenv("DB__PORT", "5432")

    connectable = create_engine(url, poolclass=pool.NullPool)

    logger.info("Using schema %s for alembic revision table", ALEMBIC_SCHEMA)
    logger.info("Using schema %s for database revisions", TARGET_SCHEMA)

    with connectable.connect() as connection:
        # Explicit pre-migration schema creation, needed for the schema
        # in which the alembic version_table is being created, if different
        # the target schema.
        connection.execute(text(f"CREATE SCHEMA IF NOT EXISTS {ALEMBIC_SCHEMA}"))
        connection.execute(text(f"CREATE SCHEMA IF NOT EXISTS {TARGET_SCHEMA}"))
        connection.commit()
        # Operations are performed in the first schema on the search_path
        connection.execute(text(f"set search_path to {TARGET_SCHEMA}"))
        connection.commit()

        context.configure(
            connection=connection,
            target_metadata=TARGET_METADATA,
            version_table_schema=ALEMBIC_SCHEMA,
            include_schemas=True,
            include_name=schema_name_filter,
        )

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
