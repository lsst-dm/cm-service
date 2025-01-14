from click.testing import CliRunner
from safir.testing.uvicorn import UvicornProcess

from lsst.cmservice.cli.client import client_top
from lsst.cmservice.client.clientconfig import client_config
from lsst.cmservice.config import config


def test_commands_cli(uvicorn: UvicornProcess) -> None:
    """Test miscellaneous CLI commands"""
    client_config.service_url = f"{uvicorn.url}{config.asgi.prefix}"
    runner = CliRunner()

    result = runner.invoke(client_top, "production list")
    assert result.exit_code == 0

    result = runner.invoke(client_top, "production list -o yaml")
    assert result.exit_code == 0

    result = runner.invoke(client_top, "production list -o json")
    assert result.exit_code == 0

    result = runner.invoke(client_top, "campaign list")
    assert result.exit_code == 0

    result = runner.invoke(client_top, "campaign list -o yaml")
    assert result.exit_code == 0

    result = runner.invoke(client_top, "campaign list -o json")
    assert result.exit_code == 0
