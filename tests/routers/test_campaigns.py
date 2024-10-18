import os
import uuid

import pytest
from httpx import AsyncClient
from pydantic import parse_obj_as

from lsst.cmservice import models
from lsst.cmservice.common.enums import LevelEnum
from lsst.cmservice.config import config

from .util_functions import (
    check_get_methods,
    check_scripts,
    check_update_methods,
    create_tree,
    delete_all_productions,
)


@pytest.mark.asyncio()
async def test_campaigns_api(client: AsyncClient) -> None:
    """Test `/campaigns` API endpoint."""

    # generate a uuid to avoid collisions
    uuid_int = uuid.uuid1().int

    os.environ["CM_CONFIGS"] = "examples"

    # intialize a tree down to one level lower
    await create_tree(client, LevelEnum.step, uuid_int)

    result = await client.get(f"{config.prefix}/campaign/list")
    campaigns = parse_obj_as(
        list[models.Campaign],
        result.json(),
    )
    entry = campaigns[0]

    # check get methods
    await check_get_methods(client, entry, models.Campaign, models.Production)

    # check update methods
    await check_update_methods(client, entry, "campaign", models.Campaign)

    # check scripts
    await check_scripts(client, entry, "campaign")

    # delete everything we just made in the session
    await delete_all_productions(client)

    # confirm cleanup
    result = await client.get(f"{config.prefix}/production/list")
    productions = parse_obj_as(
        list[models.Production],
        result.json(),
    )

    assert len(productions) == 0
