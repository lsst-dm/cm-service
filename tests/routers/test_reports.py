import os
import uuid

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
async def test_report_routes(client: AsyncClient) -> None:
    """Test `/job` API endpoint."""

    # generate a uuid to avoid collisions
    uuid_int = uuid.uuid1().int

    os.environ["CM_CONFIGS"] = "examples"

    # intialize a tree down to one level lower
    await create_tree(client, LevelEnum.job, uuid_int)

    response = await client.get(f"{config.prefix}/job/list")
    jobs = check_and_parse_response(response, list[models.Job])
    entry = jobs[0]

    manifest_report_query = models.LoadManifestReport(
        fullname=entry.fullname,
        yaml_file=os.path.abspath("examples/manifest_report_2.yaml"),
    )

    response = await client.post(
        f"{config.prefix}/load/manifest_report",
        content=manifest_report_query.model_dump_json(),
    )
    assert response.is_success
