# CM-Service Database Migration

Database migrations and schema evolution are handled by `alembic`, a database tool
that is part of the `sqlalchemy` toolkit ecosystem.

Alembic is included in the project's dependency graph via the Safir package.

## Running Alembic

The `alembic` tool establishes an execution environment via the `env.py` file which
may use configuration elements from the `../alembic.ini` file. This execution
environment includes the creation of a SQLAlchemy connection engine which is subsequently
used by the migration scripts.

The default database connection URL used by Alembic to create a SQLAlchemy engine is
a `:memory:` instance of SQLite, which is effectively a no-op. In descending order
of preference, the database connection URL can be specified by:

- any `-x cm_database_url=...` argument passed to `alembic`.
- the `CM_DATABASE_URL` environment variable.
- the value of the `sqlalchemy.url` configuration value in `alembic.ini` (which should
  be a path to a sqlite database file).

With the project's virtual environment installed and activated (`source .venv/bin/activate`),
`alembic` is available to invoke at the command line.

## Migrating a Database

The command `alembic upgrade head` will migrate the database to the current "head" or
most recent migration, and `alembic downgrade base` will do the opposite, effectively
destroying all Alembic-managed database resources.

Alembic can also run in "offline" mode, which instead of using a connection engine to
affect change in a database generates SQL files that can be manually applied to a database.
In offline mode, the connection URL is used to flavor the dialect of the generated SQL
instead of creating a database connection.

To use offline mode, pass `--sql` as an argument to the `alembic` command; optionally
pipe the command's output to a file: `alembic upgrade head --sql > migration.sql`.

The database revisions are applied to a database schema identified by one of these
parameters:

- `-x schema=...` Alembic command parameter
- `CM_DATABASE_SCHEMA` environment variable (via app config object)
- `"public"`

The Alembic versions table is stored in the same schema as the database revisions
unless the `-x alembic_schema=...` command parameter is used.

### Incremental Migrations

In development or testing, it may be useful to "step" through the migrations one or more at
a time. This incremental migration approach is supported by Alembic through "relative
migration identifiers", which can be as simple as `alembic upgrade +1` and `alembic downgrade -1`
to apply/remove one migration at a time.

The degree to which incremental migrations are useful depends on the scope of the migration
work occuring in each revision.

## Capturing Initial State - Methodology

The initial state of the database is captured through the use of the application's
existing base model with the Alembic `--autogenerate` option against an empty PostgreSQL
database.

Before an autogenerated revision is attempted, an empty Alembic revision is created and applied
to the (empty) database. This initial empty base revision is then backfilled to contain
the definitions of any Enum column types detected by Alembic, since these cannot be created
automatically.

Finally, the instances of Enum columns in the auto-generated revision are modified to
include a `create_type=False` parameter.

## Creating Additional Revisions

A new revision is created when Alembic is invoked with the `revision` command. The
template file `script.py.mako` is used as a blueprint for the new revision's Python
script.

A new migration can be created one of two ways:

1. Make code changes to affect the SQLAlchemy `DeclarativeBase` and use `--autogenerate`
   with Alembic.
2. Write Alembic revision and then change code to match.

In the either case, a new Alembic revision will be most often created by calling

```
alembic revision -m MESSAGE [--autogenerate]
```

Where `MESSAGE` is a commit-style message describing the revision.
