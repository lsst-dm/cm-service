import os
import uuid

import pytest
from click.testing import CliRunner

from lsst.cmservice import models
from lsst.cmservice.cli.client import client_top
from lsst.cmservice.common.enums import DEFAULT_NAMESPACE, LevelEnum

from .util_functions import (
    check_and_parse_result,
    check_get_methods,
    check_scripts,
    check_update_methods,
    create_tree,
)


@pytest.mark.asyncio()
async def test_step_cli(runner: CliRunner) -> None:
    """Test `step` CLI command"""

    # generate a uuid to avoid collisions
    namespace = uuid.uuid5(DEFAULT_NAMESPACE, str(uuid.uuid1()))

    os.environ["CM_CONFIGS"] = "examples"

    result = runner.invoke(client_top, "step list --output yaml")
    steps = check_and_parse_result(result, list[models.Step])
    assert len(steps) == 0, "Step list not empty"

    # intialize a tree down to one level lower
    create_tree(runner, client_top, LevelEnum.group, namespace=namespace)

    result = runner.invoke(client_top, "step list --output yaml")
    steps = check_and_parse_result(result, list[models.Step])
    entry = steps[0]

    # check get methods
    check_get_methods(runner, client_top, entry, "step", models.Step)

    # check update methods
    check_update_methods(runner, client_top, entry, "step", models.Step)

    # check scripts
    check_scripts(runner, client_top, entry, "step")
