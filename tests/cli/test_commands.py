from click.testing import CliRunner
from safir.testing.uvicorn import UvicornProcess

from lsst.cmservice.cli.commands import main
from lsst.cmservice.config import config


def test_commands(uvicorn: UvicornProcess) -> None:
    env = {"CM_SERVICE": f"{uvicorn.url}{config.prefix}"}
    runner = CliRunner(env=env)

    result = runner.invoke(main, "--version")
    assert result.exit_code == 0
    assert "version" in result.output

    result = runner.invoke(main, "--help")
    assert result.exit_code == 0
    assert "Usage:" in result.output

    result = runner.invoke(main, "init")
    assert result.exit_code == 0

    result = runner.invoke(main, "get productions")
    assert result.exit_code == 0

    result = runner.invoke(main, "get productions -o yaml")
    assert result.exit_code == 0

    result = runner.invoke(main, "get productions -o json")
    assert result.exit_code == 0

    result = runner.invoke(main, "get campaigns")
    assert result.exit_code == 0

    result = runner.invoke(main, "get campaigns -o yaml")
    assert result.exit_code == 0

    # FIXME StatusEnum not JSON serializable
    # result = runner.invoke(main, "get campaigns -o json")
    # assert result.exit_code == 0
