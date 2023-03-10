from asyncio import AbstractEventLoop, get_event_loop_policy
from typing import AsyncIterator, Iterator

import pytest
import pytest_asyncio
import structlog
from asgi_lifespan import LifespanManager
from fastapi import FastAPI
from httpx import AsyncClient
from safir.database import create_database_engine, initialize_database
from sqlalchemy.ext.asyncio import AsyncEngine
from sqlalchemy.schema import CreateSchema

from lsst.cmservice import main
from lsst.cmservice.config import config
from lsst.cmservice.db import Base


@pytest.fixture(scope="session")
def event_loop() -> Iterator[AbstractEventLoop]:
    policy = get_event_loop_policy()
    loop = policy.new_event_loop()
    yield loop
    loop.close()


@pytest_asyncio.fixture(scope="session")
async def engine() -> AsyncIterator[AsyncEngine]:
    """Return a SQLAlchemy AsyncEngine configured to talk to the app db."""
    logger = structlog.get_logger(config.logger_name)
    engine = create_database_engine(config.database_url, config.database_password)
    # Remove this clause if Safir PR #140 is merged
    if Base.metadata.schema is not None:
        async with engine.begin() as conn:
            await conn.execute(CreateSchema(Base.metadata.schema, True))
    await initialize_database(engine, logger, schema=Base.metadata, reset=True)
    yield engine
    await engine.dispose()


@pytest_asyncio.fixture(scope="session")
async def app(engine: AsyncEngine) -> AsyncIterator[FastAPI]:
    """Return a configured test application.

    Wraps the application in a lifespan manager so that startup and shutdown
    events are sent during test execution.
    """
    async with LifespanManager(main.app):
        yield main.app


@pytest_asyncio.fixture(scope="session")
async def client(app: FastAPI) -> AsyncIterator[AsyncClient]:
    """Return an ``httpx.AsyncClient`` configured to talk to the test app."""
    async with AsyncClient(app=app, base_url="https://example.com/") as client:
        yield client
