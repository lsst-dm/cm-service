from collections.abc import Generator

import pytest
from click.testing import CliRunner
from safir.testing.uvicorn import UvicornProcess

from lsst.cmservice.client.cli.client import client_top
from lsst.cmservice.client.client.clientconfig import client_config
from lsst.cmservice.core.config import config

from .util_functions import cleanup


@pytest.fixture(scope="function", params=["v1"])
def runner(uvicorn: UvicornProcess, request: pytest.FixtureRequest) -> Generator[CliRunner]:
    client_config.service_url = f"{uvicorn.url}{config.asgi.prefix}/{request.param}"
    runner = CliRunner()
    yield runner
    # delete everything we just made in the session
    cleanup(runner, client_top, check_cascade=True)
