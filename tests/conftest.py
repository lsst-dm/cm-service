"""Shared conftest module for all tests, providing database fixtures."""

from collections.abc import AsyncGenerator, Callable, Generator
from uuid import NAMESPACE_DNS, uuid4

import pytest
import pytest_asyncio
from pydantic import SecretStr
from sqlalchemy import insert
from sqlalchemy.ext.asyncio import async_sessionmaker
from sqlalchemy.pool import NullPool
from sqlalchemy.schema import CreateSchema, DropSchema
from sqlmodel.ext.asyncio.session import AsyncSession
from testcontainers.postgres import PostgresContainer

from lsst.cmservice.config import config
from lsst.cmservice.db.session import DatabaseManager, db_session_dependency
from lsst.cmservice.models.db import Base
from lsst.cmservice.models.types import AnyAsyncSession

POSTGRES_CONTAINER_IMAGE = "postgres:17"


@pytest.fixture(scope="session")
def postgres_container() -> Generator[PostgresContainer]:
    """Session-scoped ephemeral postgres container shared by all tests.

    Isolation between tests is achieved with a dedicated schema per test (see
    the `testdb` fixture) rather than a dedicated container.
    """
    with PostgresContainer(
        image=POSTGRES_CONTAINER_IMAGE,
        username="cm-service",
        password="INSECURE-PASSWORD",
        dbname="cm-service",
        driver="asyncpg",
    ) as postgres:
        yield postgres


@pytest_asyncio.fixture(scope="function", loop_scope="module")
async def testdb(
    postgres_container: PostgresContainer, monkeypatch: pytest.MonkeyPatch
) -> AsyncGenerator[DatabaseManager]:
    """Test fixture for a database manager bound to a fresh schema.

    A random schema is created for each test and all the database objects
    defined for the ORM metadata are created within it. Because the ORM
    metadata schema is fixed at import time, the engine is configured with a
    schema translation map that redirects the metadata schema to the test
    schema. The schema is dropped at the end of the test.
    """
    metadata = Base.metadata
    test_schema = f"test_{uuid4().hex[:8]}"

    monkeypatch.setattr(target=config.db, name="url", value=postgres_container.get_connection_url())
    monkeypatch.setattr(target=config.db, name="password", value=SecretStr(postgres_container.password))
    monkeypatch.setattr(target=config.db, name="table_schema", value=test_schema)

    db_session_dependency.pool_class = NullPool
    await db_session_dependency.initialize()
    assert db_session_dependency.engine is not None
    db_session_dependency.engine = db_session_dependency.engine.execution_options(
        schema_translate_map={metadata.schema: test_schema}
    )
    db_session_dependency.sessionmaker = async_sessionmaker(
        db_session_dependency.engine, class_=AsyncSession, expire_on_commit=False
    )

    async with db_session_dependency.engine.begin() as aconn:
        await aconn.execute(CreateSchema(test_schema))
        await aconn.run_sync(metadata.create_all)
        await aconn.execute(
            insert(metadata.tables[f"{metadata.schema}.campaigns_v2"]).values(
                id="dda54a0c-6878-5c95-ac4f-007f6808049e",
                namespace=str(NAMESPACE_DNS),
                name="DEFAULT",
                owner="root",
                status="accepted",
                metadata={},
                configuration={},
            )
        )
    yield db_session_dependency
    async with db_session_dependency.engine.begin() as aconn:
        await aconn.execute(DropSchema(test_schema, cascade=True))
    await db_session_dependency.aclose()


@pytest_asyncio.fixture(name="session_factory", scope="function", loop_scope="module")
async def session_factory_fixture(
    testdb: DatabaseManager,
) -> Callable[..., AsyncGenerator[AnyAsyncSession]]:
    """Test fixture for providing an AsyncSession Factory."""

    async def session_factory() -> AsyncGenerator[AnyAsyncSession]:
        assert testdb.engine is not None
        assert testdb.sessionmaker is not None
        async with testdb.sessionmaker() as session:
            try:
                yield session
            finally:
                await session.close()
        await testdb.engine.dispose()

    return session_factory


@pytest_asyncio.fixture(name="session", scope="function", loop_scope="module")
async def session_fixture(session_factory: Callable) -> AsyncGenerator[AnyAsyncSession]:
    """Test fixture for an async database session, useful for tests that need
    a database session directly.
    """
    async for session in session_factory():
        yield session
