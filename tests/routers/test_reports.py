import os

import pytest
from httpx import AsyncClient

from lsst.cmservice import models
from lsst.cmservice.common.enums import LevelEnum
from lsst.cmservice.config import config

from .util_functions import (
    check_and_parse_response,
    create_tree,
)


@pytest.mark.asyncio()
@pytest.mark.filterwarnings("ignore::pytest.PytestUnraisableExceptionWarning")
@pytest.mark.parametrize("api_version", ["v1"])
async def test_report_routes(client: AsyncClient, api_version: str) -> None:
    """Test `/job` API endpoint."""

    uuid_int = 467858

    os.environ["CM_CONFIGS"] = "examples"

    # intialize a tree down to one level lower
    await create_tree(client, api_version, LevelEnum.job, uuid_int)

    response = await client.get(f"{config.asgi.prefix}/{api_version}/job/list")
    jobs = check_and_parse_response(response, list[models.Job])
    entry = [job for job in jobs if str(uuid_int) in job.name][0]

    manifest_report_query = models.LoadManifestReport(
        fullname=entry.fullname,
        yaml_file="examples/manifest_report_2.yaml",
    )

    response = await client.post(
        f"{config.asgi.prefix}/{api_version}/load/manifest_report",
        content=manifest_report_query.model_dump_json(),
    )
    assert response.is_success
