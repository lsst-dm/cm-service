import os
import uuid

import pytest
from httpx import AsyncClient
from pydantic import parse_obj_as

from lsst.cmservice import models
from lsst.cmservice.common.enums import LevelEnum
from lsst.cmservice.config import config

from .util_functions import create_tree, delete_all_productions


@pytest.mark.asyncio()
@pytest.mark.filterwarnings("ignore::pytest.PytestUnraisableExceptionWarning")
async def test_productions_api(client: AsyncClient) -> None:
    """Test `/productions` API endpoint."""

    # generate a uuid to avoid collisions
    uuid_int = uuid.uuid1().int

    os.environ["CM_CONFIGS"] = "examples"

    # intialize a tree down to one level lower
    await create_tree(client, LevelEnum.campaign, uuid_int)

    # delete everything we just made in the session
    await delete_all_productions(client)

    # confirm cleanup
    result = await client.get(f"{config.prefix}/production/list")
    productions = parse_obj_as(
        list[models.Production],
        result.json(),
    )

    assert len(productions) == 0
