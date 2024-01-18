import pytest
from httpx import AsyncClient

from lsst.cmservice.config import config


@pytest.mark.asyncio()
async def test_groups_api(client: AsyncClient) -> None:
    """Test `/groups` API endpoint."""

    # Get list, it should be emtpy
    response = await client.get(f"{config.prefix}/group/list")
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)
    # gids_expected = set(gids)
    gids_retrieved = {group["id"] for group in data}
    assert not gids_retrieved

    # Verify an individual get
    # response = await client.get(f"{config.prefix}/group/get/{data[0]['id']}")
    # assert response.status_code == 200
    # data = response.json()
    # assert data["id"] == gids[0]
    # assert data["parent_id"] == 3
    # assert data["name"] == "group0"
