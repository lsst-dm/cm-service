from uuid import uuid1

import pytest
from httpx import AsyncClient

from lsst.cmservice.config import config


@pytest.mark.asyncio()
async def test_campaigns_api(client: AsyncClient) -> None:
    """Test `/campaigns` API endpoint."""
    # Create a couple fresh productions
    pnames = []
    pids = []
    for n in range(2):
        pnames.append(str(uuid1()))
        response = await client.post(f"{config.prefix}/productions", json={"name": pnames[n]})
        assert response.status_code == 201
        pids.append(response.json()["id"])

    # Create a bunch of fresh campaigns; use same names in each of the above
    # productions
    cnames = []
    cids = []
    for i in range(15):
        cnames.append(str(uuid1()))
        for j in range(len(pids)):
            response = await client.post(
                f"{config.prefix}/campaigns",
                json={"production": pids[j], "name": cnames[i]},
            )
            assert response.status_code == 201
            data = response.json()
            assert data["production"] == pids[j]
            assert data["name"] == cnames[i]
            cids.append(data["id"])

    # Create an additional campaign and delete it to get a "dead" id
    cname_dead = str(uuid1())
    response = await client.post(
        f"{config.prefix}/campaigns",
        json={"production": pids[0], "name": cname_dead},
    )
    cid_dead = int(response.json()["id"])
    cids_deleted = {cid_dead}
    response = await client.delete(f"{config.prefix}/campaigns/{cid_dead}")
    assert response.status_code == 204

    # Get list; verify first batch all there and dead one missing
    response = await client.get(f"{config.prefix}/campaigns")
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)
    cids_expected = set(cids)
    cids_retrieved = {campaign["id"] for campaign in data}
    assert cids_expected <= cids_retrieved
    assert cid_dead not in cids_retrieved

    # Verify list with production filter
    response = await client.get(f"{config.prefix}/campaigns?production={pids[1]}")
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)
    cnames_expected = set(cnames)
    cnames_retrieved = {campaign["name"] for campaign in data}
    assert cnames_expected == cnames_retrieved

    # Verify an individual get
    response = await client.get(f"{config.prefix}/campaigns/{cids[0]}")
    assert response.status_code == 200
    data = response.json()
    assert data["id"] == cids[0]
    assert data["production"] == pids[0]
    assert data["name"] == cnames[0]

    # Try to get one that shouldn't be there
    response = await client.get(f"{config.prefix}/campaigns/{cid_dead}")
    assert response.status_code == 404

    # Verify repeated delete
    response = await client.delete(f"{config.prefix}/campaigns/{cid_dead}")
    assert response.status_code == 204

    # Try update with mismatched IDs
    response = await client.put(
        f"{config.prefix}/campaigns/{cid_dead}",
        json={"id": cids[0], "production": pids[0], "name": cname_dead},
    )
    assert response.status_code == 400

    # Try update of something not there
    response = await client.put(
        f"{config.prefix}/campaigns/{cid_dead}",
        json={"id": cid_dead, "production": pids[0], "name": cname_dead},
    )
    assert response.status_code == 404

    # Try to create a name conflict
    response = await client.post(
        f"{config.prefix}/campaigns",
        json={"production": pids[0], "name": cnames[0]},
    )
    assert response.status_code == 422

    # Try to update to a name conflict
    response = await client.put(
        f"{config.prefix}/campaigns/{cids[0]}",
        json={"id": cids[0], "production": pids[0], "name": cnames[1]},
    )
    assert response.status_code == 422

    # Try a valid update and verify results
    cname_updated = str(uuid1())
    response = await client.put(
        f"{config.prefix}/campaigns/{cids[0]}",
        json={"id": cids[0], "production": pids[0], "name": cname_updated},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["id"] == cids[0]
    assert data["production"] == pids[0]
    assert data["name"] == cname_updated

    # Also check update results via individual get
    response = await client.get(f"{config.prefix}/campaigns/{cids[0]}")
    data = response.json()
    assert data["id"] == cids[0]
    assert data["production"] == pids[0]
    assert data["name"] == cname_updated

    # Delete one of the productions; verify associated campaigns deleted
    response = await client.get(f"{config.prefix}/campaigns?production={pids[1]}")
    assert response.status_code == 200
    cids_to_delete = {campaign["id"] for campaign in response.json()}
    response = await client.delete(f"{config.prefix}/productions/{pids[1]}")
    assert response.status_code == 204
    response = await client.get(f"{config.prefix}/campaigns?production={pids[1]}")
    assert response.status_code == 200
    assert response.json() == []
    cids_deleted |= cids_to_delete
    cids_expected -= cids_to_delete

    # Pagination check: loop retrieving pages and checking as we go
    skip = 0
    stride = 6
    cids_retrieved = set()
    results = await client.get(f"{config.prefix}/campaigns?skip={skip}&limit={stride}")
    assert results.status_code == 200
    data = results.json()
    while len(data) != 0:
        cids_batch = {campaign["id"] for campaign in data}
        assert cids_batch.isdisjoint(cids_retrieved)
        cids_retrieved |= cids_batch
        skip += stride
        results = await client.get(f"{config.prefix}/campaigns?skip={skip}&limit={stride}")
        assert results.status_code == 200
        data = results.json()

    # Check we got everything expected, and none of the things we expected not
    # to get
    assert cids_expected <= cids_retrieved
    assert cids_retrieved.isdisjoint(cids_deleted)
