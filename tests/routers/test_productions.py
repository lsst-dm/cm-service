import os
import uuid

import pytest
from httpx import AsyncClient

from lsst.cmservice.common.enums import LevelEnum

from .util_functions import cleanup, create_tree


@pytest.mark.asyncio()
@pytest.mark.filterwarnings("ignore::pytest.PytestUnraisableExceptionWarning")
@pytest.mark.parametrize("api_version", ["v1"])
async def test_production_routes(client: AsyncClient, api_version: str) -> None:
    """Test `/production` API endpoint."""

    # generate a uuid to avoid collisions
    uuid_int = uuid.uuid1().int

    os.environ["CM_CONFIGS"] = "examples"

    # intialize a tree down to one level lower
    await create_tree(client, api_version, LevelEnum.campaign, uuid_int)

    # delete everything we just made in the session
    await cleanup(client, api_version, check_cascade=True)
