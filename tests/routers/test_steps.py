import pytest
from httpx import AsyncClient

from lsst.cmservice.config import config


@pytest.mark.asyncio()
async def test_steps_api(client: AsyncClient) -> None:
    """Test `/steps` API endpoint."""

    sids = list(range(3, 6))

    # Get list; verify first batch all there and dead one missing
    response = await client.get(f"{config.prefix}/steps")
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)
    sids_expected = set(sids)
    sids_retrieved = {step["id"] for step in data}
    assert sids_expected <= sids_retrieved

    # Verify an individual get
    response = await client.get(f"{config.prefix}/steps/{sids[0]}")
    assert response.status_code == 200
    data = response.json()
    assert data["id"] == sids[0]
    assert data["parent_id"] == 13
    assert data["name"] == "isr"
