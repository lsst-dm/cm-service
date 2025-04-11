import pytest
from click.testing import CliRunner
from safir.testing.uvicorn import UvicornProcess

from lsst.cmservice import models
from lsst.cmservice.cli.client import client_top
from lsst.cmservice.client.clientconfig import client_config
from lsst.cmservice.config import config

from .util_functions import check_and_parse_result


@pytest.mark.parametrize("api_version", ["v1"])
async def test_others_cli(uvicorn: UvicornProcess, api_version: str) -> None:
    """Test `other` CLI command"""

    client_config.service_url = f"{uvicorn.url}{config.asgi.prefix}/{api_version}"
    runner = CliRunner()

    result = runner.invoke(client_top, "pipetask_error list --output yaml")
    check = check_and_parse_result(result, list[models.PipetaskError])
    assert len(check) == 0

    result = runner.invoke(client_top, "product_set list --output yaml")
    products = check_and_parse_result(result, list[models.ProductSet])
    assert len(products) == 0

    result = runner.invoke(client_top, "script_dependency list --output yaml")
    dependencies = check_and_parse_result(result, list[models.Dependency])
    assert len(dependencies) == 0

    result = runner.invoke(client_top, "script_error list --output yaml")
    scripts = check_and_parse_result(result, list[models.ScriptError])
    assert len(scripts) == 0

    result = runner.invoke(client_top, "task_set list --output yaml")
    tasks = check_and_parse_result(result, list[models.TaskSet])
    assert len(tasks) == 0

    result = runner.invoke(client_top, "wms_task_report list --output yaml")
    reports = check_and_parse_result(result, list[models.WmsTaskReport])
    assert len(reports) == 0
