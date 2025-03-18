import pytest
from click.testing import CliRunner
from safir.testing.uvicorn import UvicornProcess

from lsst.cmservice.cli.client import client_top
from lsst.cmservice.client.clientconfig import client_config
from lsst.cmservice.config import config


@pytest.mark.parametrize("api_version", ["v1"])
def test_commands_cli(uvicorn: UvicornProcess, api_version: str) -> None:
    """Test miscellaneous CLI commands"""
    client_config.service_url = f"{uvicorn.url}{config.asgi.prefix}/{api_version}"
    runner = CliRunner()

    result = runner.invoke(client_top, "campaign list")
    assert result.exit_code == 0

    result = runner.invoke(client_top, "campaign list -o yaml")
    assert result.exit_code == 0

    result = runner.invoke(client_top, "campaign list -o json")
    assert result.exit_code == 0
