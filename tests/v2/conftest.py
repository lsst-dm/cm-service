"""Shared conftest module for v2 unit and functional tests."""

import importlib
import os
from collections.abc import AsyncGenerator, Generator
from typing import TYPE_CHECKING

import pytest
import pytest_asyncio
from fastapi.testclient import TestClient
from httpx import ASGITransport, AsyncClient
from sqlalchemy.pool import NullPool
from sqlmodel import SQLModel
from testcontainers.postgres import PostgresContainer

from lsst.cmservice.common.types import AnyAsyncSession
from lsst.cmservice.config import config
from lsst.cmservice.db.session import DatabaseSessionDependency, db_session_dependency

if TYPE_CHECKING:
    from fastapi import FastAPI

POSTGRES_CONTAINER_IMAGE = "postgres:16"


@pytest.fixture(scope="module")
def monkeypatch_module() -> Generator[pytest.MonkeyPatch]:
    with pytest.MonkeyPatch.context() as mp:
        yield mp


@pytest_asyncio.fixture(scope="module", loop_scope="module")
async def rawdb(monkeypatch_module: pytest.MonkeyPatch) -> AsyncGenerator[DatabaseSessionDependency]:
    """Test fixture for a postgres container.

    A scoped ephemeral container will be created for the test if the env var
    `TEST__LOCAL_DB` is not set; otherwise the fixture will assume that the
    correct database is available to the test environment through ordinary
    configuration parameters.
    """

    monkeypatch_module.setattr(target=config.asgi, name="enable_frontend", value=False)

    if os.getenv("TEST__LOCAL_DB") is not None:
        db_session_dependency.pool_class = NullPool
        await db_session_dependency.initialize()
        assert db_session_dependency.engine is not None
        yield db_session_dependency
        await db_session_dependency.aclose()
    else:
        with PostgresContainer(
            image=POSTGRES_CONTAINER_IMAGE,
            username="cm-service",
            password="INSECURE-PASSWORD",
            dbname="cm-service",
            driver="asyncpg",
        ) as postgres:
            psql_url = postgres.get_connection_url()
            monkeypatch_module.setattr(target=config.db, name="url", value=psql_url)
            monkeypatch_module.setattr(target=config.db, name="password", value=postgres.password)
            monkeypatch_module.setattr(target=config.db, name="echo", value=True)
            db_session_dependency.pool_class = NullPool
            await db_session_dependency.initialize()
            assert db_session_dependency.engine is not None
            yield db_session_dependency
            await db_session_dependency.aclose()


@pytest_asyncio.fixture(scope="module", loop_scope="module")
async def testdb(rawdb: DatabaseSessionDependency) -> AsyncGenerator[DatabaseSessionDependency]:
    """Test fixture for a migrated postgres container.

    This fixture creates all the database objects defined for the ORM metadata
    and drops them at the end of the fixture scope.
    """
    # v1 objects are created from the legacy DeclarativeBase class and
    # v2 objects are created from the SQLModel metadata.
    assert rawdb.engine is not None
    async with rawdb.engine.begin() as aconn:
        await aconn.run_sync(SQLModel.metadata.drop_all)
        await aconn.run_sync(SQLModel.metadata.create_all)
    yield rawdb
    async with rawdb.engine.begin() as aconn:
        await aconn.run_sync(SQLModel.metadata.drop_all)


@pytest_asyncio.fixture(name="session", scope="module", loop_scope="module")
async def session_fixture(testdb: DatabaseSessionDependency) -> AsyncGenerator[AnyAsyncSession]:
    """Test fixture for an async database session"""
    assert testdb.engine is not None
    assert testdb.sessionmaker is not None
    async with testdb.sessionmaker() as session:
        try:
            yield session
        finally:
            await session.close()
    await testdb.engine.dispose()


def client_fixture(session: AnyAsyncSession) -> Generator[TestClient]:
    """Test fixture for a FastAPI test client with dependency injection
    overriden.
    """

    def get_session_override() -> AnyAsyncSession:
        return session

    main_ = importlib.import_module("lsst.cmservice.main")
    app: FastAPI = getattr(main_, "app")

    app.dependency_overrides[db_session_dependency] = get_session_override
    client = TestClient(app)
    yield client
    app.dependency_overrides.clear()


@pytest_asyncio.fixture(name="aclient", scope="module", loop_scope="module")
async def async_client_fixture(session: AnyAsyncSession) -> AsyncGenerator[AsyncClient]:
    """Test fixture for an HTTPX async test client with dependency injection
    overriden.
    """
    main_ = importlib.import_module("lsst.cmservice.main")
    app: FastAPI = getattr(main_, "app")

    def get_session_override() -> AnyAsyncSession:
        return session

    app.dependency_overrides[db_session_dependency] = get_session_override
    async with AsyncClient(
        follow_redirects=True, transport=ASGITransport(app), base_url="http://test"
    ) as aclient:
        yield aclient
    app.dependency_overrides.clear()
