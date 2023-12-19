import pytest
from httpx import AsyncClient

from lsst.cmservice.config import config


@pytest.mark.asyncio()
async def test_productions_api(client: AsyncClient) -> None:
    """Test `/productions` API endpoint."""

    # Get list; it should be empty
    response = await client.get(f"{config.prefix}/production/list")
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)
    # pids_expected = set(pids)
    pids_retrieved = {production["id"] for production in data}
    assert not pids_retrieved

    # Verify an individual get
    # response =
    #   await client.get(f"{config.prefix}/production/get/{data[0]['id']}")
    # assert response.status_code == 200
    # data = response.json()
    # assert data["id"] == pids[0]
    # assert data["name"] == 'p1'
