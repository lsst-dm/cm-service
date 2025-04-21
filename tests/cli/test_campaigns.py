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
    check_queue,
    check_scripts,
    check_update_methods,
    create_tree,
)


@pytest.mark.asyncio()
async def test_campaign_cli(runner: CliRunner) -> None:
    """Test `campaign` CLI command"""

    namespace = uuid.uuid5(DEFAULT_NAMESPACE, str(uuid.uuid1()))

    os.environ["CM_CONFIGS"] = "examples"

    result = runner.invoke(client_top, "campaign list --output yaml")
    campaigns = check_and_parse_result(result, list[models.Campaign])
    assert len(campaigns) == 0, "Campaign list not empty"

    # intialize a tree down to one level lower
    create_tree(runner, client_top, LevelEnum.step, namespace)

    result = runner.invoke(client_top, "campaign list --output yaml")
    campaigns = check_and_parse_result(result, list[models.Campaign])
    entry = campaigns[0]

    # test other output cases
    result = runner.invoke(client_top, "campaign list --output json")
    assert result.exit_code == 0

    result = runner.invoke(client_top, "campaign list")
    assert result.exit_code == 0

    result = runner.invoke(client_top, f"campaign get all --row_id {entry.id} --output json")
    assert result.exit_code == 0

    result = runner.invoke(client_top, f"campaign get all --row_id {entry.id}")
    assert result.exit_code == 0

    result = runner.invoke(client_top, f"campaign get data_dict --row_id {entry.id} --output json")
    assert result.exit_code == 0

    result = runner.invoke(client_top, f"campaign get data_dict --row_id {entry.id}")
    assert result.exit_code == 0

    # badly formated update dict
    result = runner.invoke(
        client_top, f"campaign update data_dict --update_dict aa --row_id {entry.id} --output json"
    )
    assert result.exit_code == 2

    # check get methods
    check_get_methods(runner, client_top, entry, "campaign", models.Campaign)

    # check update methods
    check_update_methods(runner, client_top, entry, "campaign", models.Campaign)

    # check scripts
    check_scripts(runner, client_top, entry, "campaign")

    # check queue
    result = runner.invoke(client_top, f"campaign update status --status accepted --row_id {entry.id}")
    assert result.exit_code == 0
    check_queue(runner, client_top, entry, run_daemon=True)
