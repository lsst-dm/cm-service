from uuid import uuid1

import pytest
from httpx import AsyncClient

from lsst.cmservice.config import config


@pytest.mark.asyncio()
async def test_steps_api(client: AsyncClient) -> None:
    """Test `/steps` API endpoint."""
    # Create a fresh production
    pname = str(uuid1())
    response = await client.post(f"{config.prefix}/productions", json={"name": pname})
    assert response.status_code == 201
    pid = response.json()["id"]

    # Create a couple fresh campaigns
    cnames = []
    cids = []
    for n in range(2):
        cnames.append(str(uuid1()))
        response = await client.post(
            f"{config.prefix}/campaigns",
            json={"production": pid, "name": cnames[n]},
        )
        assert response.status_code == 201
        cids.append(response.json()["id"])

    # Create a bunch of fresh steps; use same names in each of the above
    # campaigns
    snames = []
    sids = []
    for i in range(15):
        snames.append(str(uuid1()))
        for j in range(len(cids)):
            response = await client.post(
                f"{config.prefix}/steps",
                json={"campaign": cids[j], "name": snames[i]},
            )
            assert response.status_code == 201
            data = response.json()
            assert data["campaign"] == cids[j]
            assert data["name"] == snames[i]
            sids.append(data["id"])

    # Create an additional step and delete it to get a "dead" id
    sname_dead = str(uuid1())
    response = await client.post(f"{config.prefix}/steps", json={"campaign": cids[0], "name": sname_dead})
    sid_dead = int(response.json()["id"])
    sids_deleted = {sid_dead}
    response = await client.delete(f"{config.prefix}/steps/{sid_dead}")
    assert response.status_code == 204

    # Get list; verify first batch all there and dead one missing
    response = await client.get(f"{config.prefix}/steps")
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)
    sids_expected = set(sids)
    sids_retrieved = {step["id"] for step in data}
    assert sids_expected <= sids_retrieved
    assert sid_dead not in sids_retrieved

    # Verify list with campaign filter
    response = await client.get(f"{config.prefix}/steps?campaign={cids[1]}")
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)
    snames_expected = set(snames)
    snames_retrieved = {step["name"] for step in data}
    assert snames_expected == snames_retrieved

    # Verify an individual get
    response = await client.get(f"{config.prefix}/steps/{sids[0]}")
    assert response.status_code == 200
    data = response.json()
    assert data["id"] == sids[0]
    assert data["campaign"] == cids[0]
    assert data["name"] == snames[0]

    # Try to get one that shouldn't be there
    response = await client.get(f"{config.prefix}/steps/{sid_dead}")
    assert response.status_code == 404

    # Verify repeated delete
    response = await client.delete(f"{config.prefix}/steps/{sid_dead}")
    assert response.status_code == 204

    # Try update with mismatched IDs
    response = await client.put(
        f"{config.prefix}/steps/{sid_dead}",
        json={"id": sids[0], "campaign": cids[0], "name": sname_dead},
    )
    assert response.status_code == 400

    # Try update of something not there
    response = await client.put(
        f"{config.prefix}/steps/{sid_dead}",
        json={"id": sid_dead, "campaign": cids[0], "name": sname_dead},
    )
    assert response.status_code == 404

    # Try to create a name conflict
    response = await client.post(f"{config.prefix}/steps", json={"campaign": cids[0], "name": snames[0]})
    assert response.status_code == 422

    # Try to update to a name conflict
    response = await client.put(
        f"{config.prefix}/steps/{sids[0]}",
        json={"id": sids[0], "campaign": cids[0], "name": snames[1]},
    )
    assert response.status_code == 422

    # Try a valid update and verify results
    sname_updated = str(uuid1())
    response = await client.put(
        f"{config.prefix}/steps/{sids[0]}",
        json={"id": sids[0], "campaign": cids[0], "name": sname_updated},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["id"] == sids[0]
    assert data["campaign"] == cids[0]
    assert data["name"] == sname_updated

    # Also check update results via individual get
    response = await client.get(f"{config.prefix}/steps/{sids[0]}")
    data = response.json()
    assert data["id"] == sids[0]
    assert data["campaign"] == cids[0]
    assert data["name"] == sname_updated

    # Delete one of the campaigns; verify associated steps deleted
    response = await client.get(f"{config.prefix}/steps?campaign={cids[1]}")
    assert response.status_code == 200
    sids_to_delete = {step["id"] for step in response.json()}
    response = await client.delete(f"{config.prefix}/campaigns/{cids[1]}")
    assert response.status_code == 204
    response = await client.get(f"{config.prefix}/steps?campaign={cids[1]}")
    assert response.status_code == 200
    assert response.json() == []
    sids_deleted |= sids_to_delete
    sids_expected -= sids_to_delete

    # Pagination check: loop retrieving pages and checking as we go
    skip = 0
    stride = 6
    sids_retrieved = set()
    results = await client.get(f"{config.prefix}/steps?skip={skip}&limit={stride}")
    assert results.status_code == 200
    data = results.json()
    while len(data) != 0:
        sids_batch = {step["id"] for step in data}
        assert sids_batch.isdisjoint(sids_retrieved)
        sids_retrieved |= sids_batch
        skip += stride
        results = await client.get(f"{config.prefix}/steps?skip={skip}&limit={stride}")
        assert results.status_code == 200
        data = results.json()

    # Check we got everything expected, and none of the things we expected not
    # to get
    assert sids_expected <= sids_retrieved
    assert sids_retrieved.isdisjoint(sids_deleted)
