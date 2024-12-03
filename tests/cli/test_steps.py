import os
import uuid

from click.testing import CliRunner
from safir.testing.uvicorn import UvicornProcess

from lsst.cmservice import models
from lsst.cmservice.cli.client import client_top
from lsst.cmservice.client.clientconfig import client_config
from lsst.cmservice.common.enums import LevelEnum
from lsst.cmservice.config import config

from .util_functions import (
    check_and_parse_result,
    check_get_methods,
    check_scripts,
    check_update_methods,
    cleanup,
    create_tree,
)


async def test_step_cli(uvicorn: UvicornProcess) -> None:
    """Test `step` CLI command"""

    client_config.service_url = f"{uvicorn.url}{config.prefix}"
    runner = CliRunner()

    # generate a uuid to avoid collisions
    uuid_int = uuid.uuid1().int

    os.environ["CM_CONFIGS"] = "examples"

    result = runner.invoke(client_top, "step list --output yaml")
    steps = check_and_parse_result(result, list[models.Step])
    assert len(steps) == 0, "Step list not empty"

    # intialize a tree down to one level lower
    create_tree(runner, client_top, LevelEnum.group, uuid_int)

    result = runner.invoke(client_top, "step list --output yaml")
    steps = check_and_parse_result(result, list[models.Step])
    entry = steps[0]

    # check get methods
    check_get_methods(runner, client_top, entry, "step", models.Step)

    # check update methods
    check_update_methods(runner, client_top, entry, "step", models.Step)

    # check scripts
    check_scripts(runner, client_top, entry, "step")

    # delete everything we just made in the session
    cleanup(runner, client_top, check_cascade=True)
