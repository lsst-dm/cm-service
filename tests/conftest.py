from collections.abc import AsyncIterator

import pytest_asyncio
import structlog
from asgi_lifespan import LifespanManager
from fastapi import FastAPI
from httpx import AsyncClient
from pytest import TempPathFactory
from safir.database import create_database_engine, initialize_database
from safir.testing.uvicorn import UvicornProcess, spawn_uvicorn
from sqlalchemy.ext.asyncio import AsyncEngine

from lsst.cmservice import db, main
from lsst.cmservice.config import config


@pytest_asyncio.fixture(name="engine")
async def engine_fixture() -> AsyncIterator[AsyncEngine]:
    """Return a SQLAlchemy AsyncEngine configured to talk to the app db."""
    logger = structlog.get_logger(config.logger_name)
    the_engine = create_database_engine(config.database_url, config.database_password)
    await initialize_database(the_engine, logger, schema=db.Base.metadata, reset=True)
    yield the_engine
    await the_engine.dispose()


@pytest_asyncio.fixture(name="app")
async def app_fixture() -> AsyncIterator[FastAPI]:
    """Return a configured test application.

    Wraps the application in a lifespan manager so that startup and shutdown
    events are sent during test execution.
    """
    async with LifespanManager(main.app):
        yield main.app


@pytest_asyncio.fixture(name="client")
async def client_fixture(app: FastAPI) -> AsyncIterator[AsyncClient]:
    """Return an ``httpx.AsyncClient`` configured to talk to the test app."""
    async with AsyncClient(app=app, base_url="https:") as the_client:
        yield the_client


@pytest_asyncio.fixture(name="uvicorn")
async def uvicorn_fixture(tmp_path_factory: TempPathFactory) -> AsyncIterator[UvicornProcess]:
    """Spawn and return a uvicorn process hosting the test app."""
    my_uvicorn = spawn_uvicorn(
        working_directory=tmp_path_factory.mktemp("uvicorn"),
        app="lsst.cmservice.main:app",
        timeout=10,
    )
    yield my_uvicorn
    my_uvicorn.process.terminate()
