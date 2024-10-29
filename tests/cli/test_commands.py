from click.testing import CliRunner
from safir.testing.uvicorn import UvicornProcess

from lsst.cmservice.cli.commands import client_top, server
from lsst.cmservice.client.clientconfig import client_config
from lsst.cmservice.config import config


def test_commands_cli(uvicorn: UvicornProcess) -> None:
    """Test miscellaneous CLI commands"""
    client_config.service_url = f"{uvicorn.url}{config.prefix}"
    runner = CliRunner()

    result = runner.invoke(server, "--version")
    assert result.exit_code == 0
    assert "version" in result.output

    result = runner.invoke(server, "--help")
    assert result.exit_code == 0
    assert "Usage:" in result.output

    result = runner.invoke(server, "init")
    assert result.exit_code == 0

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

    # FIXME StatusEnum not JSON serializable
    # result = runner.invoke(client_top, "campaign list -o json")
    # assert result.exit_code == 0
