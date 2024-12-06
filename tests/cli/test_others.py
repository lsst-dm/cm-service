from click.testing import CliRunner
from safir.testing.uvicorn import UvicornProcess

from lsst.cmservice import models
from lsst.cmservice.cli.client import client_top
from lsst.cmservice.client.clientconfig import client_config
from lsst.cmservice.config import config

from .util_functions import check_and_parse_result


async def test_others_cli(uvicorn: UvicornProcess) -> None:
    """Test `other` CLI command"""

    client_config.service_url = f"{uvicorn.url}{config.prefix}"
    runner = CliRunner()

    result = runner.invoke(client_top, "pipetask_error list --output yaml")
    check = check_and_parse_result(result, list[models.PipetaskError])
    assert len(check) == 0

    result = runner.invoke(client_top, "product_set list --output yaml")
    check = check_and_parse_result(result, list[models.ProductSet])  # type: ignore
    assert len(check) == 0

    result = runner.invoke(client_top, "script_dependency list --output yaml")
    check = check_and_parse_result(result, list[models.Dependency])  # type: ignore
    assert len(check) == 0

    result = runner.invoke(client_top, "script_error list --output yaml")
    check = check_and_parse_result(result, list[models.ScriptError])  # type: ignore
    assert len(check) == 0

    result = runner.invoke(client_top, "task_set list --output yaml")
    check = check_and_parse_result(result, list[models.TaskSet])  # type: ignore
    assert len(check) == 0

    result = runner.invoke(client_top, "wms_task_report list --output yaml")
    check = check_and_parse_result(result, list[models.WmsTaskReport])  # type: ignore
    assert len(check) == 0
