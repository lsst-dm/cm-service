import os
import uuid

import pytest
from httpx import AsyncClient

from lsst.cmservice import models
from lsst.cmservice.common.enums import LevelEnum
from lsst.cmservice.config import config

from .util_functions import (
    check_and_parse_response,
    check_get_methods,
    check_scripts,
    check_update_methods,
    create_tree,
    delete_all_productions,
)


@pytest.mark.asyncio()
@pytest.mark.filterwarnings("ignore::pytest.PytestUnraisableExceptionWarning")
async def test_jobs_api(client: AsyncClient) -> None:
    """Test `/jobs` API endpoint."""

    # generate a uuid to avoid collisions
    uuid_int = uuid.uuid1().int

    os.environ["CM_CONFIGS"] = "examples"

    # intialize a tree down to one level lower
    await create_tree(client, LevelEnum.job, uuid_int)

    response = await client.get(f"{config.prefix}/job/list")
    jobs = check_and_parse_response(
        response,
        list[models.Job],
    )
    entry = jobs[0]

    # check get methods
    await check_get_methods(client, entry, "job", models.Job, models.Group)

    # check update methods
    await check_update_methods(client, entry, "job", models.Job)

    # check scripts
    await check_scripts(client, entry, "job")

    # delete everything we just made in the session
    await delete_all_productions(client)

    # confirm cleanup
    response = await client.get(f"{config.prefix}/production/list")
    productions = check_and_parse_response(
        response,
        list[models.Production],
    )

    assert len(productions) == 0
