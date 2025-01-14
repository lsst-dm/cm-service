import os
import uuid

import pytest
from click.testing import CliRunner
from safir.testing.uvicorn import UvicornProcess

from lsst.cmservice.cli.client import client_top
from lsst.cmservice.client.clientconfig import client_config
from lsst.cmservice.common.enums import LevelEnum
from lsst.cmservice.config import config

from .util_functions import cleanup, create_tree


@pytest.mark.parametrize("api_version", ["v1"])
async def test_production_cli(uvicorn: UvicornProcess, api_version: str) -> None:
    """Test `production` CLI command"""

    client_config.service_url = f"{uvicorn.url}{config.asgi.prefix}/{api_version}"
    runner = CliRunner()

    # generate a uuid to avoid collisions
    uuid_int = uuid.uuid1().int

    os.environ["CM_CONFIGS"] = "examples"

    # intialize a tree down to one level lower
    create_tree(runner, client_top, LevelEnum.campaign, uuid_int)

    # delete everything we just made in the session
    cleanup(runner, client_top, check_cascade=True)
