import os
from asyncio import AbstractEventLoop, get_event_loop_policy
from collections.abc import AsyncGenerator, AsyncIterator, Iterator
from pathlib import Path

import pytest
import pytest_asyncio
import structlog
from asgi_lifespan import LifespanManager
from fastapi import FastAPI
from httpx import AsyncClient
from safir.database import create_async_session, create_database_engine, initialize_database
from safir.testing.uvicorn import UvicornProcess, spawn_uvicorn
from sqlalchemy.ext.asyncio import AsyncEngine

from lsst.cmservice import db, main
from lsst.cmservice.config import config
from lsst.cmservice.handlers import interface


@pytest.fixture(scope="session", name="event_loop")
def event_loop_fixture() -> Iterator[AbstractEventLoop]:
    """Return a AbstractEventLoop that does some abstract stuff"""
    policy = get_event_loop_policy()
    loop = policy.new_event_loop()
    yield loop
    loop.close()


@pytest_asyncio.fixture(scope="session", name="engine")
async def engine_fixture() -> AsyncIterator[AsyncEngine]:
    """Return a SQLAlchemy AsyncEngine configured to talk to the app db."""
    os.environ["CM_CONFIGS"] = "examples"
    logger = structlog.get_logger(config.logger_name)
    the_engine = create_database_engine(config.database_url, config.database_password)
    await initialize_database(the_engine, logger, schema=db.Base.metadata, reset=True)
    yield the_engine
    await the_engine.dispose()


@pytest_asyncio.fixture(scope="session", name="session")
async def session_fixture(engine: AsyncEngine) -> AsyncGenerator:
    """Return a SQLAlchemy AsyncEngine configured to talk to the app db."""
    logger = structlog.get_logger(config.logger_name)
    async with engine.begin():
        the_session = await create_async_session(engine, logger)
        specification = await interface.load_specification(the_session, "examples/empty_config.yaml")
        check = await db.SpecBlockAssociation.get_row_by_fullname(the_session, "base#campaign")
        check2 = await specification.get_block(the_session, "campaign")
        assert check.fullname == "base#campaign"
        assert check2.name == "campaign"
        yield the_session
        await the_session.close()


@pytest_asyncio.fixture(scope="session", name="app")
async def app_fixture() -> AsyncIterator[FastAPI]:
    """Return a configured test application.

    Wraps the application in a lifespan manager so that startup and shutdown
    events are sent during test execution.
    """
    async with LifespanManager(main.app):
        yield main.app


@pytest_asyncio.fixture(scope="session", name="client")
async def client_fixture(app: FastAPI) -> AsyncIterator[AsyncClient]:
    """Return an ``httpx.AsyncClient`` configured to talk to the test app."""
    async with AsyncClient(app=app, base_url="https:") as the_client:
        yield the_client


@pytest_asyncio.fixture
async def uvicorn(tmp_path: Path) -> AsyncIterator[UvicornProcess]:
    """Spawn and return a uvicorn process configured to talk to test app."""
    my_uvicorn = spawn_uvicorn(working_directory=tmp_path, app="lsst.cmservice.main:app")
    yield my_uvicorn
    my_uvicorn.process.terminate()
