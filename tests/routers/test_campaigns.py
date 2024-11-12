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
    check_queue,
    check_scripts,
    check_update_methods,
    cleanup,
    create_tree,
)


@pytest.mark.asyncio()
async def test_campaign_routes(client: AsyncClient) -> None:
    """Test `/campaign` API endpoint."""

    # generate a uuid to avoid collisions
    uuid_int = uuid.uuid1().int

    os.environ["CM_CONFIGS"] = "examples"

    # intialize a tree down to one level lower
    await create_tree(client, LevelEnum.step, uuid_int)

    response = await client.get(f"{config.prefix}/campaign/list")
    campaigns = check_and_parse_response(response, list[models.Campaign])
    entry = campaigns[0]

    add_steps_query = models.AddSteps(
        fullname=entry.fullname,
        child_configs=[],
    )

    response = await client.post(
        f"{config.prefix}/load/steps",
        content=add_steps_query.model_dump_json(),
    )
    campaign_check = check_and_parse_response(response, models.Campaign)
    assert entry.id == campaign_check.id

    # check get methods
    await check_get_methods(client, entry, "campaign", models.Campaign, models.Production)

    # check update methods
    await check_update_methods(client, entry, "campaign", models.Campaign)

    # check scripts
    await check_scripts(client, entry, "campaign")

    # check queues
    await check_queue(client, entry)

    # delete everything we just made in the session
    await cleanup(client, check_cascade=True)
