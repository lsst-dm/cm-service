import pytest
from httpx import AsyncClient

from lsst.cmservice.config import config


@pytest.mark.asyncio()
@pytest.mark.filterwarnings("ignore::pytest.PytestUnraisableExceptionWarning")
async def test_steps_api(client: AsyncClient) -> None:
    """Test `/steps` API endpoint."""

    # Get list, it should be empty
    response = await client.get(f"{config.prefix}/step/list")
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)
    # sids_expected = set(sids)
    sids_retrieved = {step["id"] for step in data}
    assert not sids_retrieved

    # Verify an individual get
    # response = await client.get(f"{config.prefix}/step/get/{data[0]['id']}")
    # assert response.status_code == 200
    # data = response.json()
    # assert data["id"] == sids[0]
    # assert data["parent_id"] == 13
    # assert data["name"] == "isr"
