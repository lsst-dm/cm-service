import os
import uuid

from click.testing import CliRunner
from safir.testing.uvicorn import UvicornProcess

from lsst.cmservice import models
from lsst.cmservice.cli.commands import client_top
from lsst.cmservice.client.clientconfig import client_config
from lsst.cmservice.common.enums import LevelEnum
from lsst.cmservice.config import config

from .util_functions import (
    check_and_parse_result,
    check_get_methods,
    check_scripts,
    check_update_methods,
    create_tree,
    delete_all_productions,
)


async def test_groups_api(uvicorn: UvicornProcess) -> None:
    """Test `/groups` API endpoint."""

    client_config.service_url = f"{uvicorn.url}{config.prefix}"
    runner = CliRunner()

    # generate a uuid to avoid collisions
    uuid_int = uuid.uuid1().int

    os.environ["CM_CONFIGS"] = "examples"

    result = runner.invoke(client_top, "group list " "--output yaml ")
    groups = check_and_parse_result(
        result,
        list[models.Group],
    )
    assert len(groups) == 0, "Group list not empty"

    # intialize a tree down to one level lower
    create_tree(runner, client_top, LevelEnum.job, uuid_int)

    result = runner.invoke(client_top, "group list " "--output yaml ")
    groups = check_and_parse_result(
        result,
        list[models.Group],
    )
    entry = groups[0]

    # check get methods
    check_get_methods(runner, client_top, entry, "group", models.Group, models.Step)

    # check update methods
    check_update_methods(runner, client_top, entry, "group", models.Group)

    # check scripts
    check_scripts(runner, client_top, entry, "group")

    # delete everything we just made in the session
    delete_all_productions(runner, client_top)

    # confirm cleanup
    result = runner.invoke(client_top, "production list " "--output yaml ")
    productions = check_and_parse_result(
        result,
        list[models.Production],
    )

    assert len(productions) == 0
