import os

import pytest
from httpx import AsyncClient

from lsst.cmservice import models
from lsst.cmservice.config import config

from .util_functions import (
    check_and_parse_response,
    cleanup,
)


@pytest.mark.asyncio()
async def test_routers_trivial_campaign(
    client: AsyncClient,
) -> None:
    """Test fake end to end run using example/example_trivial.yaml"""

    os.environ["CM_CONFIGS"] = "examples"

    spec_load_model = models.YamlFileQuery(
        yaml_file="examples/example_trivial.yaml",
    )

    response = await client.post(
        f"{config.asgi.prefix}/load/specification",
        content=spec_load_model.model_dump_json(),
    )
    specification = check_and_parse_response(response, models.Specification)
    assert specification

    campaign_load_model = models.LoadAndCreateCampaign(
        yaml_file="examples/example_trivial.yaml",
        name="test",
        parent_name="trivial_htcondor",
        spec_block_assoc_name="trivial_htcondor#campaign",
    )

    response = await client.post(
        f"{config.asgi.prefix}/load/campaign",
        content=campaign_load_model.model_dump_json(),
    )
    campaign = check_and_parse_response(response, models.Campaign)
    assert campaign.name == "test"

    # delete everything we just made in the session
    await cleanup(client)
