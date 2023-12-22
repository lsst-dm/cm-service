from click.testing import CliRunner
from safir.testing.uvicorn import UvicornProcess

from lsst.cmservice.cli.commands import client_top, server
from lsst.cmservice.config import config


def test_commands(uvicorn: UvicornProcess) -> None:
    env = {"CM_SERVICE": f"{uvicorn.url}{config.prefix}"}
    runner = CliRunner(env=env)

    result = runner.invoke(server, "--version")
    assert result.exit_code == 0
    assert "version" in result.output

    result = runner.invoke(server, "--help")
    assert result.exit_code == 0
    assert "Usage:" in result.output

    result = runner.invoke(server, "init")
    assert result.exit_code == 0

    result = runner.invoke(client_top, "get productions")
    assert result.exit_code == 0

    result = runner.invoke(client_top, "get productions -o yaml")
    assert result.exit_code == 0

    result = runner.invoke(client_top, "get productions -o json")
    assert result.exit_code == 0

    result = runner.invoke(client_top, "get campaigns")
    assert result.exit_code == 0

    result = runner.invoke(client_top, "get campaigns -o yaml")
    assert result.exit_code == 0

    # FIXME StatusEnum not JSON serializable
    # result = runner.invoke(client_top, "get campaigns -o json")
    # assert result.exit_code == 0
