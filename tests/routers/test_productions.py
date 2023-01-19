from uuid import uuid1

import pytest
from httpx import AsyncClient

from lsst.cmservice.config import config


@pytest.mark.asyncio
async def test_productions_api(client: AsyncClient) -> None:
    """Test `/productions` API endpoint"""

    # Create a bunch of fresh productions
    pnames = []
    pids = []
    for n in range(15):
        pnames.append(str(uuid1()))
        response = await client.post(f"{config.prefix}/productions", json={"name": pnames[n]})
        assert response.status_code == 201
        data = response.json()
        assert data["name"] == pnames[n]
        pids.append(data["id"])

    # Create an additional production and delete it to get a "dead" id
    pname_dead = str(uuid1())
    response = await client.post(f"{config.prefix}/productions", json={"name": pname_dead})
    pid_dead = int(response.json()["id"])
    response = await client.delete(f"{config.prefix}/productions/{pid_dead}")
    assert response.status_code == 204

    # Get list; verify first batch all there and dead one missing
    response = await client.get(f"{config.prefix}/productions")
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)
    pids_expected = set(pids)
    pids_retrieved = {production["id"] for production in data}
    assert pids_expected <= pids_retrieved
    assert pid_dead not in pids_retrieved

    # Verify an individual get
    response = await client.get(f"{config.prefix}/productions/{pids[0]}")
    assert response.status_code == 200
    data = response.json()
    assert data["id"] == pids[0]
    assert data["name"] == pnames[0]

    # Try to get one that shouldn't be there
    response = await client.get(f"{config.prefix}/productions/{pid_dead}")
    assert response.status_code == 404

    # Verify repeated delete
    response = await client.delete(f"{config.prefix}/productions/{pid_dead}")
    assert response.status_code == 204

    # Try update with mismatched IDs
    response = await client.put(
        f"{config.prefix}/productions/{pid_dead}", json={"id": pids[0], "name": pname_dead}
    )
    assert response.status_code == 400

    # Try update of something not there
    response = await client.put(
        f"{config.prefix}/productions/{pid_dead}", json={"id": pid_dead, "name": pname_dead}
    )
    assert response.status_code == 404

    # Try to create a name conflict
    response = await client.post(f"{config.prefix}/productions", json={"name": pnames[0]})
    assert response.status_code == 422

    # Try to update to a name conflict
    response = await client.put(
        f"{config.prefix}/productions/{pids[0]}", json={"id": pids[0], "name": pnames[1]}
    )
    assert response.status_code == 422

    # Try a valid update and verify results
    pname_updated = str(uuid1())
    response = await client.put(
        f"{config.prefix}/productions/{pids[0]}", json={"id": pids[0], "name": pname_updated}
    )
    assert response.status_code == 200
    data = response.json()
    assert data["id"] == pids[0]
    assert data["name"] == pname_updated

    # Also check update results via individual get
    response = await client.get(f"{config.prefix}/productions/{pids[0]}")
    data = response.json()
    assert data["id"] == pids[0]
    assert data["name"] == pname_updated

    # Pagination check: loop retrieving pages and checking as we go
    skip = 0
    stride = 6
    pids_retrieved = set()
    results = await client.get(f"{config.prefix}/productions?skip={skip}&limit={stride}")
    assert results.status_code == 200
    data = results.json()
    while len(data) != 0:
        pids_batch = {production["id"] for production in data}
        assert pids_batch.isdisjoint(pids_retrieved)
        pids_retrieved |= pids_batch
        skip += stride
        results = await client.get(f"{config.prefix}/productions?skip={skip}&limit={stride}")
        assert results.status_code == 200
        data = results.json()

    # Check we got everything expected, and none of the things we expected not
    # to get
    assert pids_expected <= pids_retrieved
    assert pid_dead not in pids_retrieved
