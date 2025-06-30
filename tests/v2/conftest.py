"""Shared conftest module for v2 unit and functional tests."""

import importlib
import os
from collections.abc import AsyncGenerator, Generator
from typing import TYPE_CHECKING
from uuid import NAMESPACE_DNS, uuid4

import pytest
import pytest_asyncio
from fastapi.testclient import TestClient
from httpx import ASGITransport, AsyncClient
from sqlalchemy import insert
from sqlalchemy.pool import NullPool
from sqlalchemy.schema import CreateSchema, DropSchema
from testcontainers.postgres import PostgresContainer

from lsst.cmservice.common.types import AnyAsyncSession
from lsst.cmservice.config import config
from lsst.cmservice.db.campaigns_v2 import metadata
from lsst.cmservice.db.session import DatabaseSessionDependency, db_session_dependency

if TYPE_CHECKING:
    from fastapi import FastAPI

POSTGRES_CONTAINER_IMAGE = "postgres:16"


@pytest.fixture(scope="module")
def monkeypatch_module() -> Generator[pytest.MonkeyPatch]:
    with pytest.MonkeyPatch.context() as mp:
        yield mp


@pytest.fixture(scope="module", autouse=True)
def patched_config(monkeypatch_module: pytest.MonkeyPatch, tmp_path_factory: pytest.TempPathFactory) -> None:
    """Fixture which monkeypatches configuration settings"""
    monkeypatch_module.setattr(
        target=config.bps, name="artifact_path", value=tmp_path_factory.mktemp("output")
    )


@pytest_asyncio.fixture(scope="module", loop_scope="module")
async def rawdb(monkeypatch_module: pytest.MonkeyPatch) -> AsyncGenerator[DatabaseSessionDependency]:
    """Test fixture for a postgres container.

    A scoped ephemeral container will be created for the test if the env var
    `TEST__LOCAL_DB` is not set; otherwise the fixture will assume that the
    correct database is available to the test environment through ordinary
    configuration parameters.

    The tests are performed within a random temporary schema that is created
    and dropped along with the tables.
    """

    monkeypatch_module.setattr(target=config.asgi, name="enable_frontend", value=False)
    monkeypatch_module.setattr(target=config.db, name="table_schema", value=uuid4().hex[:8])

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
        await aconn.run_sync(metadata.drop_all)
        await aconn.execute(CreateSchema(config.db.table_schema, if_not_exists=True))
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
        await aconn.commit()
    yield rawdb
    async with rawdb.engine.begin() as aconn:
        await aconn.run_sync(metadata.drop_all)
        await aconn.execute(DropSchema(config.db.table_schema, if_exists=True))
        await aconn.commit()


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


@pytest_asyncio.fixture(scope="function", loop_scope="module")
async def test_campaign(aclient: AsyncClient) -> AsyncGenerator[str]:
    """Fixture managing a test campaign with two (additional) nodes."""
    campaign_name = uuid4().hex[-8:]
    node_ids = []

    x = await aclient.post(
        "/cm-service/v2/campaigns",
        json={
            "apiVersion": "io.lsst.cmservice/v1",
            "kind": "campaign",
            "metadata": {"name": campaign_name},
            "spec": {},
        },
    )
    campaign_edge_url = x.headers["Edges"]
    campaign = x.json()

    # create a trio of nodes for the campaign
    for _ in range(3):
        x = await aclient.post(
            "/cm-service/v2/nodes",
            json={
                "apiVersion": "io.lsst.cmservice/v1",
                "kind": "node",
                "metadata": {"name": uuid4().hex[-8:], "namespace": campaign["id"]},
                "spec": {},
            },
        )
        node = x.json()
        node_ids.append(node["name"])

    # Create edges between each campaign node with parallelization
    _ = await aclient.post(
        "/cm-service/v2/edges",
        json={
            "apiVersion": "io.lsst.cmservice/v1",
            "kind": "edge",
            "metadata": {"name": uuid4().hex[-8:], "namespace": campaign["id"]},
            "spec": {
                "source": "START",
                "target": node_ids[0],
            },
        },
    )
    _ = await aclient.post(
        "/cm-service/v2/edges",
        json={
            "apiVersion": "io.lsst.cmservice/v1",
            "kind": "edge",
            "metadata": {"name": uuid4().hex[-8:], "namespace": campaign["id"]},
            "spec": {
                "source": node_ids[0],
                "target": node_ids[1],
            },
        },
    )
    _ = await aclient.post(
        "/cm-service/v2/edges",
        json={
            "apiVersion": "io.lsst.cmservice/v1",
            "kind": "edge",
            "metadata": {"name": uuid4().hex[-8:], "namespace": campaign["id"]},
            "spec": {
                "source": node_ids[0],
                "target": node_ids[2],
            },
        },
    )
    _ = await aclient.post(
        "/cm-service/v2/edges",
        json={
            "apiVersion": "io.lsst.cmservice/v1",
            "kind": "edge",
            "metadata": {"name": uuid4().hex[-8:], "namespace": campaign["id"]},
            "spec": {
                "source": node_ids[1],
                "target": "END",
            },
        },
    )
    _ = await aclient.post(
        "/cm-service/v2/edges",
        json={
            "apiVersion": "io.lsst.cmservice/v1",
            "kind": "edge",
            "metadata": {"name": uuid4().hex[-8:], "namespace": campaign["id"]},
            "spec": {
                "source": node_ids[2],
                "target": "END",
            },
        },
    )
    yield campaign_edge_url
