import uuid
from pathlib import Path

import pytest
from click.testing import CliRunner
from safir.testing.uvicorn import UvicornProcess

from lsst.cmservice import models
from lsst.cmservice.cli.client import client_top
from lsst.cmservice.client.clientconfig import client_config
from lsst.cmservice.common.enums import DEFAULT_NAMESPACE
from lsst.cmservice.config import config

from .util_functions import (
    check_and_parse_result,
    cleanup,
)


@pytest.mark.asyncio()
@pytest.mark.parametrize("api_version", ["v1"])
async def test_cli_trivial_campaign(uvicorn: UvicornProcess, api_version: str) -> None:
    """Test fake end to end run using example/example_trivial.yaml"""

    client_config.service_url = f"{uvicorn.url}{config.asgi.prefix}/{api_version}"
    runner = CliRunner()
    fixtures = Path(__file__).parent.parent / "fixtures" / "seeds"

    namespace = uuid.uuid5(DEFAULT_NAMESPACE, "trivial_campaign")
    yaml_file = f"{fixtures}/example_trivial.yaml"

    # Load the specification file without a namespace
    result = runner.invoke(client_top, f"load specification --yaml_file {yaml_file}")
    assert result.exit_code == 0

    # Load the specification file with a namespace
    result = runner.invoke(client_top, f"load specification --yaml_file {yaml_file} --namespace {namespace}")
    assert result.exit_code == 0

    result = runner.invoke(
        client_top,
        f"load campaign --yaml_file {yaml_file} --campaign_yaml {fixtures}/start_trivial.yaml --output yaml",
    )
    # "--spec_block_name campaign --spec_name trivial_htcondor --data dummy:a "
    campaign = check_and_parse_result(result, models.Campaign)
    assert campaign.name == "trivial_campaign"

    # delete everything we just made in the session
    cleanup(runner, client_top)
