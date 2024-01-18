import pytest
from httpx import AsyncClient

from lsst.cmservice.config import config


@pytest.mark.asyncio()
async def test_groups_api(client: AsyncClient) -> None:
    """Test `/groups` API endpoint."""

    gids = list(range(12, 18))

    # Get list; verify first batch all there and dead one missing
    response = await client.get(f"{config.prefix}/groups/list")
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)
    gids_expected = set(gids)
    gids_retrieved = {group["id"] for group in data}
    assert gids_expected <= gids_retrieved

    # Verify an individual get
    response = await client.get(f"{config.prefix}/groups/{gids[0]}")
    assert response.status_code == 200
    data = response.json()
    assert data["id"] == gids[0]
    assert data["parent_id"] == 3
    assert data["name"] == "group0"
