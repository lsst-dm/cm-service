from uuid import uuid1

import pytest
from httpx import AsyncClient

from lsst.cmservice.config import config


@pytest.mark.asyncio()
async def test_groups_api(client: AsyncClient) -> None:
    """Test `/groups` API endpoint."""
    # Create a fresh production
    pname = str(uuid1())
    response = await client.post(f"{config.prefix}/productions", json={"name": pname})
    assert response.status_code == 201
    pid = response.json()["id"]

    # Create a fresh campaign
    cname = str(uuid1())
    response = await client.post(f"{config.prefix}/campaigns", json={"production": pid, "name": cname})
    assert response.status_code == 201
    cid = response.json()["id"]

    # Create a couple fresh steps
    snames = []
    sids = []
    for n in range(2):
        snames.append(str(uuid1()))
        response = await client.post(f"{config.prefix}/steps", json={"campaign": cid, "name": snames[n]})
        assert response.status_code == 201
        sids.append(response.json()["id"])

    # Create a bunch of fresh groups; use same names in each of the above steps
    gnames = []
    gids = []
    for i in range(15):
        gnames.append(str(uuid1()))
        for j in range(len(sids)):
            response = await client.post(f"{config.prefix}/groups", json={"step": sids[j], "name": gnames[i]})
            assert response.status_code == 201
            data = response.json()
            assert data["step"] == sids[j]
            assert data["name"] == gnames[i]
            gids.append(data["id"])

    # Create an additional group and delete it to get a "dead" id
    gname_dead = str(uuid1())
    response = await client.post(f"{config.prefix}/groups", json={"step": sids[0], "name": gname_dead})
    gid_dead = int(response.json()["id"])
    gids_deleted = {gid_dead}
    response = await client.delete(f"{config.prefix}/groups/{gid_dead}")
    assert response.status_code == 204

    # Get list; verify first batch all there and dead one missing
    response = await client.get(f"{config.prefix}/groups")
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)
    gids_expected = set(gids)
    gids_retrieved = {group["id"] for group in data}
    assert gids_expected <= gids_retrieved
    assert gid_dead not in gids_retrieved

    # Verify list with step filter
    response = await client.get(f"{config.prefix}/groups?step={sids[1]}")
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)
    gnames_expected = set(gnames)
    gnames_retrieved = {group["name"] for group in data}
    assert gnames_expected == gnames_retrieved

    # Verify an individual get
    response = await client.get(f"{config.prefix}/groups/{gids[0]}")
    assert response.status_code == 200
    data = response.json()
    assert data["id"] == gids[0]
    assert data["step"] == sids[0]
    assert data["name"] == gnames[0]

    # Try to get one that shouldn't be there
    response = await client.get(f"{config.prefix}/groups/{gid_dead}")
    assert response.status_code == 404

    # Verify repeated delete
    response = await client.delete(f"{config.prefix}/groups/{gid_dead}")
    assert response.status_code == 204

    # Try update with mismatched IDs
    response = await client.put(
        f"{config.prefix}/groups/{gid_dead}",
        json={"id": gids[0], "step": sids[0], "name": gname_dead},
    )
    assert response.status_code == 400

    # Try update of something not there
    response = await client.put(
        f"{config.prefix}/groups/{gid_dead}",
        json={"id": gid_dead, "step": sids[0], "name": gname_dead},
    )
    assert response.status_code == 404

    # Try to create a name conflict
    response = await client.post(f"{config.prefix}/groups", json={"step": sids[0], "name": gnames[0]})
    assert response.status_code == 422

    # Try to update to a name conflict
    response = await client.put(
        f"{config.prefix}/groups/{gids[0]}",
        json={"id": gids[0], "step": sids[0], "name": gnames[1]},
    )
    assert response.status_code == 422

    # Try a valid update and verify results
    gname_updated = str(uuid1())
    response = await client.put(
        f"{config.prefix}/groups/{gids[0]}",
        json={"id": gids[0], "step": sids[0], "name": gname_updated},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["id"] == gids[0]
    assert data["step"] == sids[0]
    assert data["name"] == gname_updated

    # Also check update results via individual get
    response = await client.get(f"{config.prefix}/groups/{gids[0]}")
    data = response.json()
    assert data["id"] == gids[0]
    assert data["step"] == sids[0]
    assert data["name"] == gname_updated

    # Delete one of the steps; verify associated groups deleted
    response = await client.get(f"{config.prefix}/groups?step={sids[1]}")
    assert response.status_code == 200
    gids_to_delete = {group["id"] for group in response.json()}
    response = await client.delete(f"{config.prefix}/steps/{sids[1]}")
    assert response.status_code == 204
    response = await client.get(f"{config.prefix}/groups?step={sids[1]}")
    assert response.status_code == 200
    assert response.json() == []
    gids_deleted |= gids_to_delete
    gids_expected -= gids_to_delete

    # Pagination check: loop retrieving pages and checking as we go
    skip = 0
    stride = 6
    gids_retrieved = set()
    results = await client.get(f"{config.prefix}/groups?skip={skip}&limit={stride}")
    assert results.status_code == 200
    data = results.json()
    while len(data) != 0:
        gids_batch = {group["id"] for group in data}
        assert gids_batch.isdisjoint(gids_retrieved)
        gids_retrieved |= gids_batch
        skip += stride
        results = await client.get(f"{config.prefix}/groups?skip={skip}&limit={stride}")
        assert results.status_code == 200
        data = results.json()

    # Check we got everything expected, and none of the things we expected not
    # to get
    assert gids_expected <= gids_retrieved
    assert gids_retrieved.isdisjoint(gids_deleted)
