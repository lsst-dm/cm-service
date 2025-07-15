import importlib
from collections.abc import AsyncIterator, Iterator
from typing import Any

import pytest
import pytest_asyncio
import structlog
from asgi_lifespan import LifespanManager
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from pytest import TempPathFactory
from safir.database import create_database_engine, initialize_database
from safir.testing.uvicorn import UvicornProcess, spawn_uvicorn
from sqlalchemy.ext.asyncio import AsyncEngine

from lsst.cmservice import db
from lsst.cmservice.common.enums import ScriptMethodEnum
from lsst.cmservice.config import config as config_


@pytest.fixture(autouse=True)
def set_app_config(monkeypatch: Any) -> None:
    """Set any required app configuration for testing."""
    config_.script_handler = ScriptMethodEnum.bash


# FIXME this fixture should be refactored not to use unnecessary safir helper
#       functions, as all this functionality already exists without it.
@pytest_asyncio.fixture(name="engine")
async def engine_fixture() -> AsyncIterator[AsyncEngine]:
    """Return a SQLAlchemy AsyncEngine configured to talk to the app db."""
    logger = structlog.get_logger(__name__)
    the_engine = create_database_engine(config_.db.url, config_.db.password)
    await initialize_database(the_engine, logger, schema=db.Base.metadata, reset=True)
    yield the_engine
    await the_engine.dispose()


@pytest_asyncio.fixture(name="app")
async def app_fixture() -> AsyncIterator[FastAPI]:
    """Return a configured test application.

    Wraps the application in a lifespan manager so that startup and shutdown
    events are sent during test execution.
    """
    main_ = importlib.import_module("lsst.cmservice.main")
    app: FastAPI = getattr(main_, "app")
    async with LifespanManager(app):
        yield app


@pytest_asyncio.fixture(name="client")
async def client_fixture(app: FastAPI) -> AsyncIterator[AsyncClient]:
    """Return an ``httpx.AsyncClient`` configured to talk to the test app."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="https:") as the_client:
        yield the_client


# FIXME this fixture should be replaced by patching the CLIRunner's httpx
#       client (see client_fixture)
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
