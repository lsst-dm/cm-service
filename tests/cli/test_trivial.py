import pytest
from click.testing import CliRunner
from safir.testing.uvicorn import UvicornProcess

from lsst.cmservice import models
from lsst.cmservice.cli.client import client_top
from lsst.cmservice.client.clientconfig import client_config
from lsst.cmservice.config import config

from .util_functions import (
    check_and_parse_result,
    cleanup,
)


@pytest.mark.asyncio()
async def test_cli_trivial_campaign(uvicorn: UvicornProcess) -> None:
    """Test fake end to end run using example/example_trivial.yaml"""

    client_config.service_url = f"{uvicorn.url}{config.prefix}"
    runner = CliRunner()

    yaml_file = "examples/example_trivial.yaml"

    # Just use table output, we don't need the return value
    result = runner.invoke(client_top, f"load specification --yaml_file {yaml_file}")
    assert result.exit_code == 0

    result = runner.invoke(client_top, f"load specification --yaml_file {yaml_file} --allow_update")
    assert result.exit_code == 0

    result = runner.invoke(
        client_top,
        f"load campaign --yaml_file {yaml_file} --name test --parent_name trivial "
        "--spec_block_name campaign --spec_name trivial_htcondor --data dummy:a "
        "--campaign_yaml examples/start_trivial.yaml --output yaml",
    )
    campaign = check_and_parse_result(result, models.Campaign)
    assert campaign.name == "test"

    # delete everything we just made in the session
    cleanup(runner, client_top)
