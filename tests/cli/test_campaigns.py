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
    check_queue,
    check_scripts,
    check_update_methods,
    cleanup,
    create_tree,
)


async def test_campaign_cli(uvicorn: UvicornProcess) -> None:
    """Test `campaign` CLI command"""

    client_config.service_url = f"{uvicorn.url}{config.prefix}"
    runner = CliRunner()

    # generate a uuid to avoid collisions
    uuid_int = uuid.uuid1().int

    os.environ["CM_CONFIGS"] = "examples"

    result = runner.invoke(client_top, "campaign list --output yaml")
    campaigns = check_and_parse_result(result, list[models.Campaign])
    assert len(campaigns) == 0, "Campaign list not empty"

    # intialize a tree down to one level lower
    create_tree(runner, client_top, LevelEnum.step, uuid_int)

    result = runner.invoke(client_top, "campaign list --output yaml")
    campaigns = check_and_parse_result(result, list[models.Campaign])
    entry = campaigns[0]

    # check get methods
    check_get_methods(runner, client_top, entry, "campaign", models.Campaign, models.Production)

    # check update methods
    check_update_methods(runner, client_top, entry, "campaign", models.Campaign)

    # check scripts
    check_scripts(runner, client_top, entry, "campaign")

    # check queue
    check_queue(runner, client_top, entry)

    # delete everything we just made in the session
    cleanup(runner, client_top, check_cascade=True)
