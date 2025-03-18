import os

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
)


@pytest.mark.asyncio()
@pytest.mark.filterwarnings("ignore::pytest.PytestUnraisableExceptionWarning")
@pytest.mark.parametrize("api_version", ["v1"])
async def test_group_routes(client: AsyncClient, api_version: str) -> None:
    """Test `/group` API endpoint."""

    uuid_int = 209451

    os.environ["CM_CONFIGS"] = "examples"

    # intialize a tree down to one level lower
    await create_tree(client, api_version, LevelEnum.job, uuid_int)

    response = await client.get(f"{config.asgi.prefix}/{api_version}/group/list")
    groups = check_and_parse_response(response, list[models.Group])
    entry = [group for group in groups if str(uuid_int) in group.name][0]

    # check get methods
    await check_get_methods(client, api_version, entry, "group", models.Group)

    # check update methods
    await check_update_methods(client, api_version, entry, "group", models.Group)

    # check scripts
    await check_scripts(client, api_version, entry, "group")
