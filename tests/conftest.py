from collections.abc import AsyncIterator, Generator, Iterator
from typing import Any

import pytest
import pytest_asyncio
import structlog
from asgi_lifespan import LifespanManager
from fastapi import FastAPI
from fastapi.testclient import TestClient
from httpx import ASGITransport, AsyncClient
from pytest import TempPathFactory
from safir.database import create_database_engine, initialize_database
from safir.testing.uvicorn import UvicornProcess, spawn_uvicorn
from sqlalchemy.ext.asyncio import AsyncEngine

from lsst.cmservice import db, main
from lsst.cmservice.client import CMClient
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
    async with AsyncClient(transport=ASGITransport(app=app), base_url="https:") as the_client:
        yield the_client


@pytest.fixture(name="pyclient")
def pyclient_fixture(app: FastAPI) -> Generator[CMClient, None, None]:
    """Return a ``client.CMClient`` configured to talk to the test app."""
    yield CMClient(TestClient(app=app, base_url=f"http://testserver{config.prefix}/"))  # [sic]


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


def pytest_addoption(parser: Any) -> None:
    parser.addoption(
        "--run-playwright",
        action="store_true",
        default=False,
        help="run playwright tests",
    )


def pytest_configure(config: Any) -> None:
    config.addinivalue_line("markers", "playwright: mark test as a playwright test")


def pytest_collection_modifyitems(config: Any, items: Iterator) -> None:
    if config.getoption("--run-playwright"):
        # --run-playwright given in cli: do not skip playwright
        return
    skip_playwright = pytest.mark.skip(reason="need --run-playwright option to run")
    for item in items:
        if "playwright" in item.keywords:
            item.add_marker(skip_playwright)
