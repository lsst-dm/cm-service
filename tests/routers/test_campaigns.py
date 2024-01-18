import pytest
from httpx import AsyncClient

from lsst.cmservice.config import config


@pytest.mark.asyncio()
async def test_campaigns_api(client: AsyncClient) -> None:
    """Test `/campaigns` API endpoint."""

    # Get list; verify first batch all there and dead one missing
    response = await client.get(f"{config.prefix}/campaign/list")
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)
    # cids_expected = set(cids)
    cids_retrieved = {campaign["id"] for campaign in data}
    assert cids_retrieved

    # Verify an individual get
    response = await client.get(f"{config.prefix}/campaign/get/{data[0]['id']}")
    assert response.status_code == 200
    data = response.json()
    assert data["id"]  # == cids[0]
    assert data["parent_id"]  # == pids[0]
