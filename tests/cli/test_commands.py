from click.testing import CliRunner

from lsst.cmservice.cli.commands import main


def test_commands() -> None:
    runner = CliRunner()

    result = runner.invoke(main, ["--version"])
    assert result.exit_code == 0
    assert "version" in result.output

    result = runner.invoke(main, ["--help"])
    assert result.exit_code == 0
    assert "Usage:" in result.output

    result = runner.invoke(main, ["help"])
    assert result.exit_code == 0
    assert "Usage:" in result.output

    result = runner.invoke(main, ["help", "init"])
    assert result.exit_code == 0
    assert "Usage:" in result.output

    result = runner.invoke(main, ["help", "bogus"])
    assert result.exit_code == 2
    assert "Usage:" in result.output
