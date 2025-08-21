import importlib
from collections.abc import AsyncIterator

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

from lsst.cmservice.core import db
from lsst.cmservice.core.common.enums import ScriptMethodEnum
from lsst.cmservice.core.common.flags import Features
from lsst.cmservice.core.config import config as config_


@pytest.fixture(autouse=True)
def set_app_config() -> None:
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
async def app_fixture(monkeypatch: pytest.MonkeyPatch) -> AsyncIterator[FastAPI]:
    """Return a configured test application.

    Wraps the application in a lifespan manager so that startup and shutdown
    events are sent during test execution.
    """
    config = importlib.import_module("lsst.cmservice.core.config")
    monkeypatch.setattr(
        target=config.config.features,
        name="enabled",
        value=Features.API_V1 | Features.API_V2 | Features.WEBAPP_V1,
    )
    main_ = importlib.import_module("lsst.cmservice.api.main")
    app: FastAPI = getattr(main_, "app")
    async with LifespanManager(app):
        yield app


@pytest_asyncio.fixture(name="client")
async def client_fixture(app: FastAPI) -> AsyncIterator[AsyncClient]:
    """Return an ``httpx.AsyncClient`` configured to talk to the test app."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="https:") as the_client:
        yield the_client


@pytest_asyncio.fixture(name="uvicorn")
async def uvicorn_fixture(tmp_path_factory: TempPathFactory) -> AsyncIterator[UvicornProcess]:
    """Spawn and return a uvicorn process hosting the test app."""
    my_uvicorn = spawn_uvicorn(
        working_directory=tmp_path_factory.mktemp("uvicorn"),
        app="lsst.cmservice.api.main:app",
        timeout=10,
        env={
            "FEATURE_API_V1": "1",
        },
    )
    yield my_uvicorn
    my_uvicorn.process.terminate()
