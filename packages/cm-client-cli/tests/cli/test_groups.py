import os
import uuid

import pytest
from click.testing import CliRunner

from lsst.cmservice.client.cli.client import client_top
from lsst.cmservice.core import models
from lsst.cmservice.core.common.enums import DEFAULT_NAMESPACE, LevelEnum

from .util_functions import (
    check_and_parse_result,
    check_get_methods,
    check_scripts,
    check_update_methods,
    create_tree,
)


@pytest.mark.asyncio()
async def test_group_cli(runner: CliRunner) -> None:
    """Test `group` CLI command"""

    # generate a uuid to avoid collisions
    namespace = uuid.uuid5(DEFAULT_NAMESPACE, str(uuid.uuid1()))

    os.environ["CM_CONFIGS"] = "examples"

    result = runner.invoke(client_top, "group list --output yaml")
    groups = check_and_parse_result(result, list[models.Group])
    assert len(groups) == 0, "Group list not empty"

    # intialize a tree down to one level lower
    create_tree(runner, client_top, LevelEnum.job, namespace)

    result = runner.invoke(client_top, "group list --output yaml")
    groups = check_and_parse_result(result, list[models.Group])
    entry = groups[0]

    # check get methods
    check_get_methods(runner, client_top, entry, "group", models.Group)

    # check update methods
    check_update_methods(runner, client_top, entry, "group", models.Group)

    # check scripts
    check_scripts(runner, client_top, entry, "group")
