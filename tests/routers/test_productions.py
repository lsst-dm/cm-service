import pytest
from httpx import AsyncClient

from lsst.cmservice.config import config


@pytest.mark.asyncio()
async def test_productions_api(client: AsyncClient) -> None:
    """Test `/productions` API endpoint."""

    pids = [4]

    # Get list; verify first batch all there and dead one missing
    response = await client.get(f"{config.prefix}/productions/list")
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)
    pids_expected = set(pids)
    pids_retrieved = {production["id"] for production in data}
    assert pids_expected <= pids_retrieved

    # Verify an individual get
    response = await client.get(f"{config.prefix}/productions/{pids[0]}")
    assert response.status_code == 200
    data = response.json()
    assert data["id"] == pids[0]
