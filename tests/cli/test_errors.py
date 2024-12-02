import pytest
from click.testing import CliRunner
from safir.testing.uvicorn import UvicornProcess

from lsst.cmservice import models
from lsst.cmservice.cli.client import client_top
from lsst.cmservice.client.clientconfig import client_config
from lsst.cmservice.config import config

from .util_functions import (
    check_and_parse_result,
    delete_all_rows,
)


@pytest.mark.asyncio()
async def test_error_create_cli(uvicorn: UvicornProcess) -> None:
    """Test error matching in pipetask_error_type.match.

    Correctly match a real error to the error_type database and fail to match a
    fake error which is not in the database.
    """

    client_config.service_url = f"{uvicorn.url}{config.prefix}"
    runner = CliRunner()

    result = runner.invoke(
        client_top,
        "pipetask_error_type create --error_source manifest --error_flavor configuration "
        "--error_action review --task_name skyObjectMean "
        '--diagnostic_message "The error message from a regular pipetask error" --output yaml',
    )

    e1 = check_and_parse_result(result, models.PipetaskErrorType)
    assert e1.task_name == "skyObjectMean"

    delete_all_rows(runner, client_top, "pipetask_error_type", models.PipetaskErrorType)


@pytest.mark.asyncio()
async def test_load_error_types_cli(uvicorn: UvicornProcess) -> None:
    """Test `error_type` db table."""

    client_config.service_url = f"{uvicorn.url}{config.prefix}"
    runner = CliRunner()

    result = runner.invoke(client_top, "load error-types --yaml_file examples/error_types.yaml")
    assert result.exit_code == 0

    result = runner.invoke(client_top, "load error-types --yaml_file examples/error_types.yaml")
    assert result.exit_code == 0

    result = runner.invoke(
        client_top, "load error-types --allow_update --yaml_file examples/error_types.yaml"
    )
    assert result.exit_code == 0

    result = runner.invoke(client_top, "action rematch --rematch")
    assert result.exit_code == 0

    delete_all_rows(runner, client_top, "pipetask_error_type", models.PipetaskErrorType)
