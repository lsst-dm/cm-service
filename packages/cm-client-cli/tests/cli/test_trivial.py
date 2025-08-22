import uuid
from pathlib import Path
from typing import Any

import pytest
from click.testing import CliRunner
from safir.testing.uvicorn import UvicornProcess

from lsst.cmservice.client.cli.client import client_top
from lsst.cmservice.client.client.clientconfig import client_config
from lsst.cmservice.core import models
from lsst.cmservice.core.common.enums import DEFAULT_NAMESPACE
from lsst.cmservice.core.config import config

from .util_functions import (
    check_and_parse_result,
    cleanup,
)


@pytest.mark.asyncio()
@pytest.mark.parametrize("api_version", ["v1"])
async def test_cli_trivial_campaign(monkeypatch: Any, uvicorn: UvicornProcess, api_version: str) -> None:
    """Test fake end to end run using example_trivial.yaml seed"""
    client_config.service_url = f"{uvicorn.url}{config.asgi.prefix}/{api_version}"
    runner = CliRunner()
    fixtures = Path(__file__).parent.parent / "fixtures" / "seeds"
    monkeypatch.setenv("FIXTURES", str(fixtures))

    namespace = uuid.uuid5(DEFAULT_NAMESPACE, "trivial_campaign")
    yaml_file = f"{fixtures}/test_trivial.yaml"

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
    campaign = check_and_parse_result(result, models.Campaign)
    assert campaign.name == "trivial_campaign"

    # delete everything we just made in the session
    cleanup(runner, client_top)
